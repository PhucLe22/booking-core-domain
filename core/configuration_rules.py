"""
Rules for the custom fields of a resource type (ResourceType.configuration["fields"]).

A field is defined with a type and optional rules, eg:

    "capacity": {"type": "integer", "required": true, "min": 1, "max": 200, "default": 4}
    "floor":    {"type": "string", "max_length": 10, "pattern": "^[0-9]+F$"}
    "payment":  {"type": "string", "enum_type": "PAYMENT_METHOD"}
    "languages": {"type": "array", "item_type": "string", "choices": ["vi", "en"], "unique": true}

The format of docs/web_api_spec.md (FieldDefinition, snake_case) works too: the rules can
be grouped in "validation", select fields list their "options", and "scope" tells whether
the value belongs to the resource (default) or to a booking, eg:

    "room_size": {"type": "select", "options": [{"value": "S", "label": "Small"}]}
    "photo":     {"type": "file", "validation": {"max_size_bytes": 2000000,
                                                 "allowed_mime_types": ["image/*"]}}
    "parent":    {"type": "reference",
                  "validation": {"target_resource_type_id": "<uuid>"}}
    "note":      {"type": "long_text", "scope": "booking",
                  "validation": {"max_length": 500}}

- check_field_definition() checks a definition when a resource type is saved
- check_configuration() checks a resource's values against every definition

To support a new rule, add one entry to RULES.
"""

import copy
import re
import uuid
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
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


def _is_text(value):
    return isinstance(value, str)


def _is_uuid(value):
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _is_text_list(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_uuid_list(value):
    return isinstance(value, list) and all(_is_uuid(item) for item in value)


# digits, spaces and + ( ) - . ; 6 to 20 characters, eg +84 912 345 678
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9 ().-]{5,19}$")


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
    # types of docs/web_api_spec.md
    "text": _is_text,
    "long_text": _is_text,
    "phone": lambda value: isinstance(value, str) and bool(PHONE_PATTERN.match(value)),
    "select": _is_text,  # one value of "options"
    "multi_select": _is_text_list,  # values of "options"
    "reference": _is_uuid,  # id of a resource of validation.target_resource_type_id
    "file": _is_uuid,  # id of an uploaded file (storage service)
    "multi_file": _is_uuid_list,
}

# how a wrong value is described, eg "'opens_at' must be a time like 09:30!"
TYPE_MESSAGES = {
    "date": "a date like 2026-10-15",
    "time": "a time like 09:30",
    "datetime": "a date and time like 2026-10-15T09:30",
    "email": "a valid email address",
    "url": "a valid URL",
    "phone": "a phone number like +84 912 345 678",
    "select": "one of the options",
    "multi_select": "a list of options",
    "reference": "the id of a resource",
    "file": "the id of an uploaded file",
    "multi_file": "a list of uploaded file ids",
}

TEXT_TYPES = ("string", "email", "url", "text", "long_text", "phone")
FREE_TEXT_TYPES = ("string", "text", "long_text")
NUMBER_TYPES = ("integer", "number")
TIME_TYPES = ("date", "time", "datetime")
SELECT_TYPES = ("select", "multi_select")
FILE_TYPES = ("file", "multi_file")
# types whose value is a list
LIST_TYPES = ("array", "multi_select", "multi_file")
# item types of an "array" field (the spec list types have fixed items)
ITEM_TYPES = (
    "string", "integer", "number", "boolean", "date", "time", "datetime", "email", "url",
)

# keys of a definition that are not rules
BASE_KEYS = {
    "type", "required", "default", "label", "help", "item_type", "scope", "validation",
}
# where the value of a field is kept (docs/web_api_spec.md FieldDefinition.scope)
SCOPES = ("resource", "booking")


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
    return value if field["type"] in LIST_TYPES else [value]


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


def _check_multiple_of_definition(rule_value, field, name):
    if not _is_number(rule_value) or rule_value <= 0:
        return f"'{name}.multiple_of' must be a number greater than 0!"
    return None


def _check_multiple_of(value, rule_value, field, name):
    try:
        remainder = Decimal(str(value)) % Decimal(str(rule_value))
    except InvalidOperation:
        return f"'{name}' must be a multiple of {rule_value}!"
    return None if remainder == 0 else f"'{name}' must be a multiple of {rule_value}!"


def _check_options_definition(rule_value, field, name):
    if not isinstance(rule_value, list) or not rule_value:
        return f"'{name}.options' must be a non-empty list!"
    values = []
    for option in rule_value:
        if (
            not isinstance(option, dict)
            or not isinstance(option.get("value"), str)
            or not option["value"]
            or not isinstance(option.get("label", ""), str)
        ):
            return (
                f"Every option of '{name}' must be like "
                '{"value": "S", "label": "Small"}!'
            )
        values.append(option["value"])
    if len(set(values)) != len(values):
        return f"'{name}.options' has duplicate values!"
    return None


def _check_options(value, rule_value, field, name):
    values = [option["value"] for option in rule_value]
    for item in _items(value, field):
        if item not in values:
            return f"'{name}' must be one of: {', '.join(values)}!"
    return None


def _check_target_resource_type_definition(rule_value, field, name):
    from core.models import ResourceType

    if not _is_uuid(rule_value):
        return f"'{name}.target_resource_type_id' must be the id of a resource type!"
    if not ResourceType.objects.filter(pk=rule_value).exists():
        return f"Resource type '{rule_value}' does not exist!"
    return None


def _check_target_resource_type(value, rule_value, field, name):
    from core.models import Resource

    if not Resource.objects.filter(pk=value, resource_type_id=rule_value).exists():
        return f"'{name}' must be a resource of the selected resource type!"
    return None


def _stored_files(ids):
    from core.models import StoredFile

    return list(StoredFile.objects.filter(pk__in=ids))


def _check_files_exist(value, field, name):
    ids = {str(item) for item in _items(value, field)}
    found = {str(stored.pk) for stored in _stored_files(ids)}
    if ids - found:
        return f"'{name}' must be the id of an uploaded file!"
    return None


def _check_max_size(value, rule_value, field, name):
    for stored in _stored_files(_items(value, field)):
        if stored.size_bytes > rule_value:
            return f"'{name}' cannot be larger than {rule_value} bytes!"
    return None


def _check_mime_types_definition(rule_value, field, name):
    if (
        not isinstance(rule_value, list)
        or not rule_value
        or not all(isinstance(item, str) and "/" in item for item in rule_value)
    ):
        return (
            f"'{name}.allowed_mime_types' must be a list like "
            '["image/png", "image/*"]!'
        )
    return None


def _mime_allowed(mime_type, allowed):
    mime_type = (mime_type or "").lower()
    for pattern in allowed:
        pattern = pattern.lower()
        if pattern.endswith("/*") and mime_type.startswith(pattern[:-1]):
            return True
        if mime_type == pattern:
            return True
    return False


def _check_mime_types(value, rule_value, field, name):
    for stored in _stored_files(_items(value, field)):
        if not _mime_allowed(stored.mime_type, rule_value):
            return f"'{name}' must be a file of type: {', '.join(rule_value)}!"
    return None


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
        FREE_TEXT_TYPES,
        _check_pattern_definition,
        lambda value, rule_value, field, name: (
            None if re.fullmatch(rule_value, value) else f"'{name}' has an invalid format!"
        ),
    ),
    "choices": Rule(
        ("string", "text", "integer", "number", "array"),
        _check_choices_definition,
        _check_choices,
    ),
    "enum_type": Rule(
        ("string", "text", "array") + SELECT_TYPES,
        _check_enum_type_definition,
        _check_enum_type,
    ),
    "min_items": Rule(
        LIST_TYPES,
        _whole_number("min_items"),
        _length(lambda n, r: n < r, lambda name, r: f"'{name}' needs at least {r} items!"),
    ),
    "max_items": Rule(
        LIST_TYPES,
        _whole_number("max_items"),
        _length(lambda n, r: n > r, lambda name, r: f"'{name}' can have at most {r} items!"),
    ),
    "unique": Rule(LIST_TYPES, _check_unique_definition, _check_unique),
    # rules of docs/web_api_spec.md
    "multiple_of": Rule(NUMBER_TYPES, _check_multiple_of_definition, _check_multiple_of),
    "options": Rule(SELECT_TYPES, _check_options_definition, _check_options),
    "target_resource_type_id": Rule(
        ("reference",),
        _check_target_resource_type_definition,
        _check_target_resource_type,
    ),
    "max_size_bytes": Rule(FILE_TYPES, _whole_number("max_size_bytes"), _check_max_size),
    "allowed_mime_types": Rule(
        FILE_TYPES, _check_mime_types_definition, _check_mime_types
    ),
}

# rules a type cannot do without: type -> (rules, one of them is needed)
REQUIRED_RULES = {
    "select": ("options", "enum_type"),
    "multi_select": ("options", "enum_type"),
    "reference": ("target_resource_type_id",),
}

# rules that must not cross: (low, high)
RULE_PAIRS = [("min", "max"), ("min_length", "max_length"), ("min_items", "max_items")]


# =========================================================
# CHECKS
# =========================================================


def flat_definition(field):
    """
    The definition with the rules of "validation" moved to the top level, eg
    {"type": "text", "validation": {"max_length": 5}}
    -> {"type": "text", "max_length": 5}.
    """
    validation = field.get("validation")
    if not isinstance(validation, dict):
        return field
    flat = {key: value for key, value in field.items() if key != "validation"}
    flat.update(validation)
    return flat


def check_value(name, value, field):
    """Return the first error of one value against its field definition, or None."""
    field = flat_definition(field)
    field_type = field.get("type")
    if field_type not in FIELD_TYPES:
        return None
    if not FIELD_TYPES[field_type](value):
        return type_error(name, field_type)

    item_type = field.get("item_type")
    if field_type == "array" and item_type in FIELD_TYPES:
        if not all(FIELD_TYPES[item_type](item) for item in value):
            return f"Every item of '{name}' must be {TYPE_MESSAGES.get(item_type, 'of type ' + item_type)}!"

    if field_type in FILE_TYPES:
        message = _check_files_exist(value, field, name)
        if message:
            return message

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

    validation = field.get("validation", {})
    if not isinstance(validation, dict):
        return [f"'{name}.validation' must be an object!"]
    twice = sorted(set(validation) & (set(field) - {"validation"}))
    if twice:
        return [
            f"'{name}' sets {', '.join(twice)} twice (in the field and in validation)!"
        ]
    for key in validation:
        if key in BASE_KEYS:
            return [f"'{name}.validation' cannot hold '{key}'!"]
    field = flat_definition(field)

    errors = []
    if field.get("scope", "resource") not in SCOPES:
        errors.append(f"'{name}.scope' must be one of: {', '.join(SCOPES)}!")
    needed = REQUIRED_RULES.get(field_type)
    if needed and not any(key in field for key in needed):
        errors.append(f"'{name}' needs {' or '.join(needed)}!")
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
    if "options" in field and "enum_type" in field:
        errors.append(f"'{name}' can use options or enum_type, not both!")

    if not errors and "default" in field:
        message = check_value(name, field["default"], field)
        if message:
            errors.append(f"Default of '{name}' is not valid: {message}")
    return errors


def check_configuration(configuration, schema, scope="resource"):
    """
    Check a resource configuration against the "fields" of its resource type.
    Only the fields of `scope` are used: "resource" (default) for a resource,
    "booking" for the values of a booking.
    Missing fields with a default get that default.
    Return (configuration with defaults, {field: [message]} errors).
    """
    all_fields = (schema or {}).get("fields") or {}
    fields = {
        name: field
        for name, field in all_fields.items()
        if (field or {}).get("scope", "resource") == scope
    }
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
        if name in fields:
            continue
        if name in all_fields:
            other = (all_fields[name] or {}).get("scope", "resource")
            errors[name] = [f"'{name}' is filled in on the {other}, not here!"]
        else:
            errors[name] = [f"'{name}' is not a valid field for this resource type!"]

    return result, errors
