"""
Unit tests for core/configuration_rules.py (no database needed).

Run: python -m unittest core.tests.test_configuration_rules
"""

import unittest
from unittest import mock

from core import configuration_rules as rules
from core.configuration_rules import check_configuration, check_field_definition


def schema(**fields):
    return {"fields": fields}


class FieldDefinitionTests(unittest.TestCase):
    def test_valid_definitions(self):
        valid = {
            "capacity": {"type": "integer", "required": True, "min": 1, "max": 200, "default": 4},
            "floor": {"type": "string", "max_length": 10, "pattern": "^[0-9]+F$"},
            "size": {"type": "string", "choices": ["S", "M", "L"]},
            "price": {"type": "number", "min": 0},
            "opens_at": {"type": "time", "min": "06:00", "max": "22:00"},
            "valid_until": {"type": "date", "min": "2026-01-01"},
            "contact": {"type": "email", "label": "Contact email"},
            "website": {"type": "url"},
            "languages": {"type": "array", "item_type": "string", "choices": ["vi", "en"], "min_items": 1, "unique": True},
            "extra": {"type": "object"},
        }
        for name, field in valid.items():
            with self.subTest(name):
                self.assertEqual(check_field_definition(name, field), [])

    def test_invalid_definitions(self):
        cases = [
            ({"type": "integer", "unknown": 1}, "'unknown' is not a valid rule"),
            ({"type": "string", "min": 1}, "'min' cannot be used on a string field"),
            ({"type": "integer", "min": "1"}, "'capacity.min' must be of type integer"),
            ({"type": "integer", "min": 10, "max": 5}, "cannot be greater than"),
            ({"type": "string", "max_length": -1}, "must be a whole number of 0 or more"),
            ({"type": "string", "pattern": "("}, "is not a valid regular expression"),
            ({"type": "string", "choices": []}, "must be a non-empty list"),
            ({"type": "string", "choices": ["A", "A"]}, "has duplicate values"),
            ({"type": "integer", "choices": [1, "2"]}, "Every choice of 'capacity' must be of type integer"),
            ({"type": "string", "item_type": "string"}, "can only be used on an array field"),
            ({"type": "array", "item_type": "object"}, "'capacity.item_type' must be one of"),
            ({"type": "integer", "min": 1, "default": 0}, "Default of 'capacity' is not valid"),
            ({"type": "integer", "required": "yes"}, "must be true or false"),
            ({"type": "money"}, "has invalid type 'money'"),
            ({"type": "time", "min": "25:00"}, "must be a time like 09:30"),
        ]
        for field, expected in cases:
            with self.subTest(field=field):
                errors = check_field_definition("capacity", field)
                self.assertTrue(any(expected in e for e in errors), errors)

    def test_choices_and_enum_type_together(self):
        with mock.patch.dict(rules.RULES, {"enum_type": rules.RULES["enum_type"]._replace(check_definition=lambda *a: None)}):
            errors = check_field_definition("payment", {"type": "string", "choices": ["CASH"], "enum_type": "PAYMENT_METHOD"})
        self.assertIn("'payment' can use choices or enum_type, not both!", errors)


class ConfigurationTests(unittest.TestCase):
    def check(self, configuration, **fields):
        return check_configuration(configuration, schema(**fields))

    def test_types_and_required(self):
        _, errors = self.check({"capacity": "8"}, capacity={"type": "integer", "required": True}, floor={"type": "string", "required": True})
        self.assertEqual(errors["capacity"], ["'capacity' must be of type integer!"])
        self.assertEqual(errors["floor"], ["'floor' is required!"])

    def test_bool_is_not_a_number(self):
        _, errors = self.check({"capacity": True}, capacity={"type": "integer"})
        self.assertEqual(errors["capacity"], ["'capacity' must be of type integer!"])

    def test_unknown_field(self):
        _, errors = self.check({"color": "red"}, capacity={"type": "integer"})
        self.assertEqual(errors["color"], ["'color' is not a valid field for this resource type!"])

    def test_default_is_filled_in(self):
        result, errors = self.check({}, capacity={"type": "integer", "required": True, "default": 4})
        self.assertEqual(errors, {})
        self.assertEqual(result, {"capacity": 4})

    def test_rules(self):
        cases = [
            ({"type": "integer", "min": 1}, -5, "'f' must be at least 1!"),
            ({"type": "number", "max": 100}, 100.5, "'f' must be at most 100!"),
            ({"type": "string", "min_length": 3}, "ab", "'f' must have at least 3 characters!"),
            ({"type": "string", "max_length": 2}, "abc", "'f' cannot exceed 2 characters!"),
            ({"type": "string", "pattern": "^[0-9]+F$"}, "third", "'f' has an invalid format!"),
            ({"type": "string", "choices": ["S", "M"]}, "XL", "'f' must be one of: S, M!"),
            ({"type": "array", "min_items": 1}, [], "'f' needs at least 1 items!"),
            ({"type": "array", "max_items": 1}, [1, 2], "'f' can have at most 1 items!"),
            ({"type": "array", "unique": True}, ["vi", "vi"], "'f' has duplicate items!"),
            ({"type": "array", "item_type": "integer"}, [1, "2"], "Every item of 'f' must be of type integer!"),
            ({"type": "array", "choices": ["vi", "en"]}, ["vi", "fr"], "'f' must be one of: vi, en!"),
            ({"type": "date", "min": "2026-01-01"}, "2025-12-31", "'f' must be on or after 2026-01-01!"),
            ({"type": "time", "max": "22:00"}, "23:00", "'f' must be on or before 22:00!"),
            ({"type": "date"}, "15/10/2026", "'f' must be a date like 2026-10-15!"),
            ({"type": "email"}, "not-an-email", "'f' must be a valid email address!"),
            ({"type": "url"}, "example", "'f' must be a valid URL!"),
        ]
        for field, value, expected in cases:
            with self.subTest(field=field, value=value):
                _, errors = self.check({"f": value}, f=field)
                self.assertEqual(errors.get("f"), [expected])

    def test_valid_values_pass(self):
        result, errors = self.check(
            {"capacity": 8, "floor": "3F", "languages": ["vi", "en"], "opens_at": "08:30", "contact": "a@b.com", "website": "https://x.vn"},
            capacity={"type": "integer", "min": 1, "max": 20},
            floor={"type": "string", "pattern": "^[0-9]+F$"},
            languages={"type": "array", "item_type": "string", "choices": ["vi", "en"], "unique": True},
            opens_at={"type": "time", "min": "06:00"},
            contact={"type": "email"},
            website={"type": "url"},
        )
        self.assertEqual(errors, {})
        self.assertEqual(result["capacity"], 8)

    def test_enum_type_uses_active_master_data(self):
        with mock.patch.object(rules, "_enum_codes", return_value={"CASH", "CARD"}):
            _, ok = self.check({"payment": "CASH"}, payment={"type": "string", "enum_type": "PAYMENT_METHOD"})
            _, bad = self.check({"payment": "BITCOIN"}, payment={"type": "string", "enum_type": "PAYMENT_METHOD"})
        self.assertEqual(ok, {})
        self.assertEqual(bad["payment"], ["'payment' must be an active value of PAYMENT_METHOD!"])


if __name__ == "__main__":
    unittest.main()
