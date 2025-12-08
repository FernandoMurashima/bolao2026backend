from django.urls import path
from .views import ActivateWithRobinhoView, LoginView, MeView

urlpatterns = [
    path("ativar-robinho/", ActivateWithRobinhoView.as_view(), name="ativar-robinho"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
]
