from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect


class EquipeInternaMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restringe a view à equipe interna e, quando `modulo` é dado, a quem tem esse módulo.

    modulo: "comercial", "tecnico", "admin", uma tupla deles (basta um) ou None (qualquer módulo).
    """

    modulo = None

    def test_func(self) -> bool:
        user = self.request.user
        if not (user.is_authenticated and user.is_interno):
            return False
        mods = self.modulo if isinstance(self.modulo, (tuple, list)) else (self.modulo,)
        return any(user.tem_modulo(m) for m in mods)

    def handle_no_permission(self):
        user = self.request.user
        if user.is_authenticated and user.is_interno:
            messages.warning(self.request, "Seu usuário não tem acesso a essa área. Fale com a administração do sistema.")
            destino = user.pagina_inicial()
            if self.request.resolver_match and self.request.resolver_match.view_name == destino:
                destino = "accounts:sem_acesso"
            return redirect(destino)
        return super().handle_no_permission()


class ComercialMixin(EquipeInternaMixin):
    modulo = "comercial"


class TecnicoMixin(EquipeInternaMixin):
    modulo = "tecnico"


class AdminMixin(EquipeInternaMixin):
    modulo = "admin"


class ClienteMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restringe a view a usuarios do portal do cliente."""

    def test_func(self) -> bool:
        user = self.request.user
        return bool(user.is_authenticated and user.is_cliente and user.empresa_id)
