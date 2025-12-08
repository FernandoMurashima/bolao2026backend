from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User, Robinho


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    pass


@admin.register(Robinho)
class RobinhoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "email", "pago", "usado", "ativo", "criado_em")
    list_filter = ("pago", "usado", "ativo")
    search_fields = ("codigo", "email")
