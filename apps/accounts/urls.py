from django.urls import path

from apps.accounts.views import (
    CurrentUserView,
    LogoutView,
    RegisterView,
    TokenLoginView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", TokenLoginView.as_view(), name="token-login"),
    path("me/", CurrentUserView.as_view(), name="me"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
