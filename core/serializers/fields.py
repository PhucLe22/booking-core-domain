from rest_framework import serializers


class CodeRelatedField(serializers.SlugRelatedField):
    """
    Relates to a model by its code, case-insensitive on input,
    eg: "active" -> EnumDefinition with code "ACTIVE".
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("slug_field", "code")
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if isinstance(data, str):
            data = data.strip().upper()
        return super().to_internal_value(data)


def enum_values(enum_type_code):
    """Active values of an enum type, eg: enum_values("RESOURCE_STATUS")."""
    from core.models import EnumDefinition

    return EnumDefinition.objects.filter(
        enum_type__code=enum_type_code, is_active=True
    )
