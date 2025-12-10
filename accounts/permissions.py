from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsSuperUserOrReadOnly(BasePermission):
    """
    - Métodos seguros (GET, HEAD, OPTIONS): qualquer usuário autenticado.
    - Métodos de escrita (PATCH, PUT, POST, DELETE): apenas superusuário.
    """

    def has_permission(self, request, view):
        user = request.user
        if request.method in SAFE_METHODS:
            return bool(user and user.is_authenticated)
        return bool(user and user.is_authenticated and user.is_superuser)
