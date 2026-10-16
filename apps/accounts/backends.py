from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsuarioOuEmailBackend(ModelBackend):
    """Entra com o nome de usuário ou com o e-mail (sem diferenciar maiúsculas)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and "@" in username:
            User = get_user_model()
            achado = User._default_manager.filter(email__iexact=username.strip()).order_by("id").first()
            if achado is None:
                User().set_password(password)  # mesmo tempo de resposta de um usuário existente
                return None
            username = achado.get_username()
        return super().authenticate(request, username=username, password=password, **kwargs)
