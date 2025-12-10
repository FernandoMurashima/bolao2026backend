from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ActivateWithRobinhoView,
    LoginView,
    MeView,
    ChangePasswordView,
    UserViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("ativar-robinho/", ActivateWithRobinhoView.as_view(), name="ativar-robinho"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
]

urlpatterns += router.urls
