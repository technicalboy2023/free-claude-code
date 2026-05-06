"""Tests for core.anthropic.conversion._sanitize_json_schema."""

import pytest

from core.anthropic.conversion import _sanitize_json_schema


class TestBooleanSchemaStripping:
    """Boolean sub-schemas (True/False used *as* a schema) must be removed."""

    def test_top_level_boolean_false_is_stripped(self):
        keep, _ = _sanitize_json_schema(False)
        assert keep is False

    def test_top_level_boolean_true_is_stripped(self):
        keep, _ = _sanitize_json_schema(True)
        assert keep is False

    def test_boolean_in_properties_map_is_stripped(self):
        schema = {
            "type": "object",
            "properties": {
                "ok": {"type": "string"},
                "blocked": False,
            },
        }
        keep, sanitized = _sanitize_json_schema(schema)
        assert keep is True
        assert "blocked" not in sanitized["properties"]
        assert "ok" in sanitized["properties"]

    def test_boolean_in_additionalProperties_is_stripped(self):
        schema = {"type": "object", "additionalProperties": False}
        keep, sanitized = _sanitize_json_schema(schema)
        assert keep is True
        assert "additionalProperties" not in sanitized

    def test_boolean_in_anyOf_list_is_stripped(self):
        schema = {"anyOf": [False, {"type": "string"}]}
        keep, sanitized = _sanitize_json_schema(schema)
        assert keep is True
        assert sanitized["anyOf"] == [{"type": "string"}]

    def test_boolean_in_allOf_list_is_stripped(self):
        schema = {"allOf": [True, {"type": "number"}]}
        keep, sanitized = _sanitize_json_schema(schema)
        assert keep is True
        assert sanitized["allOf"] == [{"type": "number"}]


class TestMetadataKeyStripping:
    """Informational-only metadata keys are stripped; functional keys are preserved."""

    @pytest.mark.parametrize("key", ["$schema", "title", "$id", "$comment", "examples"])
    def test_metadata_keys_are_stripped(self, key):
        schema = {"type": "string", key: "some_value"}
        keep, sanitized = _sanitize_json_schema(schema)
        assert keep is True
        assert key not in sanitized
        assert sanitized["type"] == "string"

    def test_default_key_is_preserved(self):
        """The ``default`` keyword carries functional value and must not be stripped."""
        schema = {"type": "string", "default": False}
        keep, sanitized = _sanitize_json_schema(schema)
        assert keep is True
        assert sanitized["default"] is False

    def test_default_key_preserved_with_string_value(self):
        schema = {"type": "string", "default": "hello"}
        keep, sanitized = _sanitize_json_schema(schema)
        assert keep is True
        assert sanitized["default"] == "hello"

    def test_default_key_preserved_with_none_value(self):
        schema = {"type": "string", "default": None}
        keep, sanitized = _sanitize_json_schema(schema)
        assert keep is True
        assert sanitized["default"] is None


class TestFunctionalKeysPreserved:
    """Core JSON Schema keywords must survive sanitization."""

    def test_type_and_required_preserved(self):
        schema = {
            "type": "object",
            "required": ["a"],
            "properties": {"a": {"type": "string"}},
        }
        _, sanitized = _sanitize_json_schema(schema)
        assert sanitized["type"] == "object"
        assert sanitized["required"] == ["a"]

    def test_enum_preserved(self):
        schema = {"type": "string", "enum": ["a", "b"]}
        _, sanitized = _sanitize_json_schema(schema)
        assert sanitized["enum"] == ["a", "b"]

    def test_description_preserved(self):
        schema = {"type": "string", "description": "A field"}
        _, sanitized = _sanitize_json_schema(schema)
        assert sanitized["description"] == "A field"

    def test_items_with_valid_schema_preserved(self):
        schema = {"type": "array", "items": {"type": "string"}}
        _, sanitized = _sanitize_json_schema(schema)
        assert sanitized["items"] == {"type": "string"}

    def test_items_with_boolean_schema_stripped(self):
        schema = {"type": "array", "items": True}
        _, sanitized = _sanitize_json_schema(schema)
        assert "items" not in sanitized


class TestNestedRecursion:
    """Sanitization must recurse into nested schema structures."""

    def test_deeply_nested_boolean_stripped(self):
        schema = {
            "type": "object",
            "properties": {
                "outer": {
                    "type": "object",
                    "properties": {
                        "inner": {
                            "type": "object",
                            "additionalProperties": False,
                        }
                    },
                }
            },
        }
        _, sanitized = _sanitize_json_schema(schema)
        inner = sanitized["properties"]["outer"]["properties"]["inner"]
        assert "additionalProperties" not in inner

    def test_non_schema_passthrough(self):
        """Scalar and string values are passed through unchanged."""
        keep, val = _sanitize_json_schema("hello")
        assert keep is True
        assert val == "hello"

        keep, val = _sanitize_json_schema(42)
        assert keep is True
        assert val == 42

    def test_list_of_schemas(self):
        _, sanitized = _sanitize_json_schema(
            [{"type": "string"}, False, {"type": "number"}]
        )
        assert sanitized == [{"type": "string"}, {"type": "number"}]
