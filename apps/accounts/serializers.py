from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers


class CurrentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "username", "email", "first_name", "last_name")
        read_only_fields = fields


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = get_user_model()
        fields = ("id", "username", "email", "first_name", "last_name", "password")
        read_only_fields = ("id",)
        extra_kwargs = {
            "email": {"required": True, "allow_blank": False},
            "first_name": {"required": True, "allow_blank": False},
            "last_name": {"required": True, "allow_blank": False},
        }

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs["password"].strip():
            raise serializers.ValidationError(
                {"password": ["Password cannot consist only of whitespace."]}
            )
        candidate = self.Meta.model(
            username=attrs["username"],
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs

    def create(self, validated_data: dict[str, Any]) -> User:
        try:
            with transaction.atomic():
                return self.Meta.model.objects.create_user(**validated_data)
        except IntegrityError as error:
            username = self.Meta.model.normalize_username(validated_data["username"])
            if self.Meta.model.objects.filter(username=username).exists():
                raise serializers.ValidationError(
                    {"username": ["This username is already in use."]}
                ) from error
            raise
