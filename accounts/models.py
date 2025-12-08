from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid


class User(AbstractUser):
    """
    Usuário base. Pode adicionar campos extras depois, se quiser.
    """
    pass


class Robinho(models.Model):
    """
    Token de acesso pago ao bolão.
    """
    codigo = models.CharField(max_length=32, unique=True, db_index=True)
    email = models.EmailField(blank=True, null=True)
    pago = models.BooleanField(default=False)
    pago_em = models.DateTimeField(blank=True, null=True)

    usado = models.BooleanField(default=False)
    usado_em = models.DateTimeField(blank=True, null=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.codigo} (pago={self.pago}, usado={self.usado})"

    @staticmethod
    def gerar_codigo():
        return uuid.uuid4().hex[:10].upper()
