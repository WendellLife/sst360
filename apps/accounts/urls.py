from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path(
        "entrar/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("codigo/", views.PedirCodigoView.as_view(), name="codigo_pedir"),
    path("usuarios/", views.UsuariosView.as_view(), name="usuarios"),
    path("usuarios/novo/", views.UsuarioNovoView.as_view(), name="usuario_novo"),
    path("usuarios/<int:pk>/", views.UsuarioEditarView.as_view(), name="usuario_editar"),
    path("sem-acesso/", views.SemAcessoView.as_view(), name="sem_acesso"),
    path("codigo/confirmar/", views.ConfirmarCodigoView.as_view(), name="codigo_confirmar"),
    path(
        "senha/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change.html",
            success_url="/conta/senha/ok/",
        ),
        name="password_change",
    ),
    path(
        "senha/ok/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html"
        ),
        name="password_change_done",
    ),
]
