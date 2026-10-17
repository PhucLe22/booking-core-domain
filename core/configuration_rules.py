"""
Rules for the custom fields of a resource type (ResourceType.configuration["fields"]).

A field is defined with a type and optional rules, eg:

    "capacity": {"type": "integer", "required": true, "min": 1, "max": 200, "default": 4}
    "floor":    {"type": "string", "max_length": 10, "pattern": "^[0-9]+F$"}
    "payment":  {"type": "string", "enum_type": "PAYMENT_METHOD"}
    "languages": {"type": "array", "item_type": "string", "choices": ["vi", "en"], "unique": true}

- check_field_definition() checks a definition when a resource type is saved
- check_configuration() checks a resource's values against every definition

To support a new rule, add one entry to RULES.
"""

import copy
import re
from datetime import date, datetime, time
from typing import Any, Callable, NamedTuple

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator, URLValidator


# =========================================================
# FIELD TYPES
# =========================================================


def _is_int(value):
    # bool is a subclass of int, so it must not pass as integer/number
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _iso(parser):
    def check(value):
        if not isinstance(value, str):
            return False
        try:
            parser(value)
        except ValueError:
            return False
        return True

    return check


def _django_validator(validator_class):
    def check(value):
        if not isinstance(value, str):
            return False
        try:
            validator_class()(value)
        except DjangoValidationError:
            return False
        return True

    return check


FIELD_TYPES = {
    "string": lambda value: isinstance(value, str),
    "integer": _is_int,
    "number": _is_number,
    "boolean": lambda value: isinstance(value, bool),
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "date": _iso(date.fromisoformat),
    "time": _iso(time.fromisoformat),
    "datetime": _iso(datetime.fromisoformat),
    "email": _django_validator(EmailValidator),
    "url": _django_validator(URLValidator),
}

# how a wrong value is described, eg "'opens_at' must be a time like 09:30!"
TYPE_MESSAGES = {
    "date": "a date like 2026-10-15",
    "time": "a time like 09:30",
    "datetime": "a date and time like 2026-10-15T09:30",
    "email": "a valid email address",
    "url": "a valid URL",
}

TEXT_TYPES = ("string", "email", "url")
NUMBER_TYPES = ("integer", "number")
TIME_TYPES = ("date", "time", "datetime")
ITEM_TYPES = tuple(t for t in FIELD_TYPES if t not in ("object", "array"))

# keys of a definition that are not rules
BASE_KEYS = {"type", "required", "default", "label", "help", "item_type"}


def type_error(name, field_type):
    if field_type in TYPE_MESSAGES:
        return f"'{name}' must be {TYPE_MESSAGES[field_type]}!"
    return f"'{name}' must be of type {field_type}!"


def _comparable(value, field_type):
    """A value that can be compared with < and >, eg "09:30" -> time(9, 30)."""
    if field_type == "date":
        return date.fromisoformat(value)
    if field_type == "time":
        return time.fromisoformat(value)
    if field_type == "datetime":
        # compare without the zone so naive and aware values never clash
        return datetime.fromisoformat(value).replace(tzinfo=None)
    return value


# =========================================================
# RULES
# =========================================================


class Rule(NamedTuple):
    # field types the rule can be used on
    types: tuple
    # (rule_value, field, name) -> error message or None, when a resource type is saved
    check_definition: Callable[[Any, dict, str], Any]
    # (value, rule_value, field, name) -> error message or None, when a resource is saved
    check_value: Callable[[Any, Any, dict, str], Any]


def _whole_number(key):
    def check(rule_value, field, name):
        if not _is_int(rule_value) or rule_value < 0:
            return f"'{name}.{key}' must be a whole number of 0 or more!"
        return None

    return check


def _same_type_as_field(key):
    def check(rule_value, field, name):
        if not FIELD_TYPES[field["type"]](rule_value):
            return f"'{name}.{key}' must be {TYPE_MESSAGES.get(field['type'], 'of type ' + field['type'])}!"
        return None

    return check


def _check_min(value, rule_value, field, name):
    if _comparable(value, field["type"]) < _comparable(rule_value, field["type"]):
        word = "on or after" if field["type"] in TIME_TYPES else "at least"
        return f"'{name}' must be {word} {rule_value}!"
    return None


def _check_max(value, rule_value, field, name):
    if _comparable(value, field["type"]) > _comparable(rule_value, field["type"]):
        word = "on or before" if field["type"] in TIME_TYPES else "at most"
        return f"'{name}' must be {word} {rule_value}!"
    return None


def _check_pattern_definition(rule_value, field, name):
    if not isinstance(rule_value, str) or not rule_value:
        return f"'{name}.pattern' must be a regular expression!"
    try:
        re.compile(rule_value)
    except re.error as exc:
        return f"'{name}.pattern' is not a valid regular expression ({exc})!"
    return None


def _items(value, field):
    """Values the item rules apply to: the items of an array, or the value itself."""
    return value if field["type"] == "array" else [value]


def _check_choices_definition(rule_value, field, name):
    if not isinstance(rule_value, list) or not rule_value:
        return f"'{name}.choices' must be a non-empty list!"
    item_type = field.get("item_type") if field["type"] == "array" else field["type"]
    if item_type and item_type in FIELD_TYPES:
        if not all(FIELD_TYPES[item_type](choice) for choice in rule_value):
            return f"Every choice of '{name}' must be of type {item_type}!"
    if len({str(choice) for choice in rule_value}) != len(rule_value):
        return f"'{name}.choices' has duplicate values!"
    return None


def _check_choices(value, rule_value, field, name):
    for item in _items(value, field):
        if item not in rule_value:
            return f"'{name}' must be one of: {', '.join(map(str, rule_value))}!"
    return None


def _enum_codes(enum_type_code):
    # imported here so the module also loads without the Django app registry (unit tests)
    from core.models import EnumDefinition

    return set(
        EnumDefinition.objects.filter(
            enum_type__code=enum_type_code, is_active=True
        ).values_list("code", flat=True)
    )


def _check_enum_type_definition(rule_value, field, name):
    from core.models import EnumType

    if not isinstance(rule_value, str) or not rule_value:
        return f"'{name}.enum_type' must be the code of a master data list!"
    if not EnumType.objects.filter(code=rule_value).exists():
        return f"Master data list '{rule_value}' does not exist!"
    return None


def _check_enum_type(value, rule_value, field, name):
    codes = _enum_codes(rule_value)
    for item in _items(value, field):
        if item not in codes:
            return f"'{name}' must be an active value of {rule_value}!"
    return None


def _check_unique_definition(rule_value, field, name):
    if not isinstance(rule_value, bool):
        return f"'{name}.unique' must be true or false!"
    return None


def _check_unique(value, rule_value, field, name):
    if rule_value and len({str(item) for item in value}) != len(value):
        return f"'{name}' has duplicate items!"
    return None


def _length(check, message):
    def run(value, rule_value, field, name):
        return message(name, rule_value) if check(len(value), rule_value) else None

    return run


RULES = {
    "min": Rule(NUMBER_TYPES + TIME_TYPES, _same_type_as_field("min"), _check_min),
    "max": Rule(NUMBER_TYPES + TIME_TYPES, _same_type_as_field("max"), _check_max),
    "min_length": Rule(
        TEXT_TYPES,
        _whole_number("min_length"),
        _length(lambda n, r: n < r, lambda name, r: f"'{name}' must have at least {r} characters!"),
    ),
    "max_length": Rule(
        TEXT_TYPES,
        _whole_number("max_length"),
        _length(lambda n, r: n > r, lambda name, r: f"'{name}' cannot exceed {r} characters!"),
    ),
    "pattern": Rule(
        ("string",),
        _check_pattern_definition,
        lambda value, rule_value, field, name: (
            None if re.fullmatch(rule_value, value) else f"'{name}' has an invalid format!"
        ),
    ),
    "choices": Rule(("string", "integer", "number", "array"), _check_choices_definition, _check_choices),
    "enum_type": Rule(("string", "array"), _check_enum_type_definition, _check_enum_type),
    "min_items": Rule(
        ("array",),
        _whole_number("min_items"),
        _length(lambda n, r: n < r, lambda name, r: f"'{name}' needs at least {r} items!"),
    ),
    "max_items": Rule(
        ("array",),
        _whole_number("max_items"),
        _length(lambda n, r: n > r, lambda name, r: f"'{name}' can have at most {r} items!"),
    ),
    "unique": Rule(("array",), _check_unique_definition, _check_unique),
}

# rules that must not cross: (low, high)
RULE_PAIRS = [("min", "max"), ("min_length", "max_length"), ("min_items", "max_items")]


# =========================================================
# CHECKS
# =========================================================


def check_value(name, value, field):
    """Return the first error of one value against its field definition, or None."""
    field_type = field.get("type")
    if field_type not in FIELD_TYPES:
        return None
    if not FIELD_TYPES[field_type](value):
        return type_error(name, field_type)

    item_type = field.get("item_type")
    if field_type == "array" and item_type in FIELD_TYPES:
        if not all(FIELD_TYPES[item_type](item) for item in value):
            return f"Every item of '{name}' must be {TYPE_MESSAGES.get(item_type, 'of type ' + item_type)}!"

    for key, rule_value in field.items():
        rule = RULES.get(key)
        if rule is not None and field_type in rule.types:
            message = rule.check_value(value, rule_value, field, name)
            if message:
                return message
    return None


def check_field_definition(name, field):
    """Return the list of errors of one field definition (empty when it is valid)."""
    if not isinstance(field, dict):
        return [f"'{name}' must be an object!"]

    field_type = field.get("type")
    if field_type not in FIELD_TYPES:
        return [
            f"'{name}' has invalid type '{field_type}'! "
            f"Allowed types: {', '.join(FIELD_TYPES)}."
        ]

    errors = []
    if not isinstance(field.get("required", False), bool):
        errors.append(f"'{name}.required' must be true or false!")
    for key in ("label", "help"):
        if key in field and not isinstance(field[key], str):
            errors.append(f"'{name}.{key}' must be text!")
    if "item_type" in field:
        if field_type != "array":
            errors.append(f"'{name}.item_type' can only be used on an array field!")
        elif field["item_type"] not in ITEM_TYPES:
            errors.append(f"'{name}.item_type' must be one of: {', '.join(ITEM_TYPES)}!")

    for key, rule_value in field.items():
        if key in BASE_KEYS:
            continue
        rule = RULES.get(key)
        if rule is None:
            errors.append(f"'{key}' is not a valid rule (field '{name}')!")
        elif field_type not in rule.types:
            article = "an" if field_type[0] in "aeiou" else "a"
            errors.append(f"'{key}' cannot be used on {article} {field_type} field ('{name}')!")
        else:
            message = rule.check_definition(rule_value, field, name)
            if message:
                errors.append(message)
    if errors:
        return errors

    for low, high in RULE_PAIRS:
        if low in field and high in field:
            if _comparable(field[low], field_type) > _comparable(field[high], field_type):
                errors.append(f"'{name}.{low}' cannot be greater than '{name}.{high}'!")
    if "choices" in field and "enum_type" in field:
        errors.append(f"'{name}' can use choices or enum_type, not both!")

    if not errors and "default" in field:
        message = check_value(name, field["default"], field)
        if message:
            errors.append(f"Default of '{name}' is not valid: {message}")
    return errors


def check_configuration(configuration, schema):
    """
    Check a resource configuration against the "fields" of its resource type.
    Missing fields with a default get that default.
    Return (configuration with defaults, {field: [message]} errors).
    """
    fields = (schema or {}).get("fields") or {}
    result = dict(configuration or {})
    errors = {}

    for name, field in fields.items():
        field = field or {}
        if name not in result:
            if "default" in field:
                result[name] = copy.deepcopy(field["default"])
            elif field.get("required"):
                errors[name] = [f"'{name}' is required!"]
                continue
            else:
                continue
        message = check_value(name, result[name], field)
        if message:
            errors[name] = [message]

    for name in result:
        if name not in fields:
            errors[name] = [f"'{name}' is not a valid field for this resource type!"]

    return result, errors
