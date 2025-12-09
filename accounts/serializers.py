from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import Robinho

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email"]


class ActivateWithRobinhoSerializer(serializers.Serializer):
    codigo = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        codigo = attrs.get("codigo")
        try:
            robinho = Robinho.objects.get(codigo=codigo, ativo=True)
        except Robinho.DoesNotExist:
            raise serializers.ValidationError({"codigo": "Robinho inválido."})

        if not robinho.pago:
            raise serializers.ValidationError({"codigo": "Robinho ainda não pago."})
        if robinho.usado:
            raise serializers.ValidationError({"codigo": "Robinho já utilizado."})

        attrs["robinho"] = robinho
        return attrs

    def create(self, validated_data):
        robinho = validated_data["robinho"]
        username = validated_data["username"]
        email = validated_data["email"]
        password = validated_data["password"]

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )
        robinho.user = user
        robinho.usado = True
        robinho.usado_em = timezone.now()
        if not robinho.email:
            robinho.email = email
        robinho.save(update_fields=["user", "usado", "usado_em", "email"])
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")
        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Usuário ou senha inválidos.")
        if not user.is_active:
            raise serializers.ValidationError("Usuário inativo.")
        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if user is None or not user.is_authenticated:
            raise serializers.ValidationError("Usuário não autenticado.")

        old_password = attrs.get("old_password")
        new_password = attrs.get("new_password")
        new_password_confirm = attrs.get("new_password_confirm")

        if not user.check_password(old_password):
            raise serializers.ValidationError({"old_password": "Senha atual incorreta."})

        if new_password != new_password_confirm:
            raise serializers.ValidationError(
                {"new_password_confirm": "Confirmação diferente da nova senha."}
            )

        if len(new_password) < 8:
            raise serializers.ValidationError(
                {"new_password": "A nova senha deve ter pelo menos 8 caracteres."}
            )

        return attrs

    def save(self, **kwargs):
        request = self.context.get("request")
        user = request.user
        new_password = self.validated_data["new_password"]
        user.set_password(new_password)
        user.save()
        return user
