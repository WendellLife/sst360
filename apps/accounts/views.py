"""Entrada do portal por codigo de uso unico."""
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect, render
from django.views.generic import View

from .codigos import MAX_TENTATIVAS, VALIDADE_MINUTOS, CodigoAcesso, criar_e_enviar
from .models import TipoUsuario

User = get_user_model()

SESSAO_USUARIO = "codigo_usuario_id"

# Mensagem unica: nao dizemos se o contato existe ou nao.
AVISO_ENVIO = (
    "Se esse contato estiver cadastrado, o codigo chega em instantes. "
    f"Ele vale por {VALIDADE_MINUTOS} minutos."
)


def _somente_digitos(valor: str) -> str:
    return "".join(c for c in valor if c.isdigit())


class PedirCodigoView(View):
    """Passo 1: o cliente informa o contato cadastrado."""

    template_name = "accounts/codigo_pedir.html"

    def get(self, request):
        return render(request, self.template_name, {})

    def post(self, request):
        contato = (request.POST.get("contato") or "").strip()
        if not contato:
            return render(request, self.template_name, {"erro": "Informe seu e-mail ou celular."})

        usuario = self._encontrar(contato)
        if usuario:
            registro = criar_e_enviar(usuario)
            if registro is None:
                return render(request, self.template_name, {
                    "erro": "Muitos pedidos seguidos. Aguarde alguns minutos e tente de novo.",
                })
            request.session[SESSAO_USUARIO] = usuario.pk

        messages.info(request, AVISO_ENVIO)
        return redirect("accounts:codigo_confirmar")

    def _encontrar(self, contato):
        """Procura o cliente pelo e-mail ou pelo telefone, sem revelar o resultado."""
        base = User.objects.filter(tipo=TipoUsuario.CLIENTE, is_active=True)
        if "@" in contato:
            return base.filter(email__iexact=contato).first()
        digitos = _somente_digitos(contato)
        if len(digitos) < 10:
            return None
        for usuario in base.exclude(telefone=""):
            if _somente_digitos(usuario.telefone).endswith(digitos[-10:]):
                return usuario
        return None


class ConfirmarCodigoView(View):
    """Passo 2: o cliente digita o codigo recebido."""

    template_name = "accounts/codigo_confirmar.html"

    def get(self, request):
        if not request.session.get(SESSAO_USUARIO):
            return render(request, self.template_name, {"sem_pedido": True})
        return render(request, self.template_name, {})

    def post(self, request):
        digitado = _somente_digitos(request.POST.get("codigo") or "")
        usuario_id = request.session.get(SESSAO_USUARIO)

        if len(digitado) != 6:
            return render(request, self.template_name, {"erro": "Digite os 6 digitos do codigo."})
        if not usuario_id:
            return render(request, self.template_name, {"sem_pedido": True})

        registro = (
            CodigoAcesso.objects.filter(usuario_id=usuario_id, usado_em__isnull=True)
            .order_by("-criado_em").first()
        )
        if registro is None or registro.expirado:
            return render(request, self.template_name, {
                "erro": "Esse codigo expirou. Peca um novo.", "expirado": True,
            })
        if registro.tentativas >= MAX_TENTATIVAS:
            return render(request, self.template_name, {
                "erro": "Tentativas demais para esse codigo. Peca um novo.", "expirado": True,
            })

        if not registro.confere(digitado):
            restantes = max(0, MAX_TENTATIVAS - registro.tentativas)
            return render(request, self.template_name, {
                "erro": f"Codigo invalido. Voce ainda tem {restantes} tentativa(s).",
                "expirado": restantes == 0,
            })

        request.session.pop(SESSAO_USUARIO, None)
        login(request, registro.usuario, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("portal:home")


# --------------------------------------------------------------------- gestão de usuários
from django.db.models import Q  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.views.generic import CreateView, ListView, TemplateView, UpdateView  # noqa: E402

from .forms import UsuarioForm  # noqa: E402
from .mixins import AdminMixin  # noqa: E402

MODULOS = [
    ("comercial", "Comercial", "Painel, indicadores, funil, leads, diagnósticos, vendas, campanhas, FAP e dados do Tarefas."),
    ("tecnico", "Técnico", "Gestões de SST, prazos, vencimentos, documentos, treinamentos e relacionamento."),
    ("admin", "Administração", "Cadastra pessoas e define o acesso de cada uma."),
]


class UsuariosView(AdminMixin, ListView):
    template_name = "accounts/usuarios.html"
    context_object_name = "usuarios"
    extra_context = {"secao": "usuarios", "modulos": MODULOS}

    def get_queryset(self):
        qs = User.objects.select_related("empresa").order_by("-is_active", "tipo", "first_name", "username")
        filtro = self.request.GET.get("tipo", "")
        if filtro in (TipoUsuario.INTERNO, TipoUsuario.CLIENTE):
            qs = qs.filter(tipo=filtro)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q) | Q(username__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        todos = User.objects.all()
        ctx.update(
            q=self.request.GET.get("q", ""), tipo=self.request.GET.get("tipo", ""),
            total_internos=todos.filter(tipo=TipoUsuario.INTERNO, is_active=True).count(),
            total_comercial=todos.filter(tipo=TipoUsuario.INTERNO, is_active=True).filter(Q(acesso_comercial=True) | Q(is_superuser=True)).count(),
            total_tecnico=todos.filter(tipo=TipoUsuario.INTERNO, is_active=True).filter(Q(acesso_tecnico=True) | Q(is_superuser=True)).count(),
            total_clientes=todos.filter(tipo=TipoUsuario.CLIENTE, is_active=True).count(),
        )
        return ctx


class _UsuarioFormMixin(AdminMixin):
    model = User
    form_class = UsuarioForm
    template_name = "accounts/usuario_form.html"
    extra_context = {"secao": "usuarios", "modulos": MODULOS}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["editor"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("accounts:usuarios")


class UsuarioNovoView(_UsuarioFormMixin, CreateView):
    def form_valid(self, form):
        resposta = super().form_valid(form)
        messages.success(self.request, f"Usuário {self.object} cadastrado.")
        return resposta


class UsuarioEditarView(_UsuarioFormMixin, UpdateView):
    context_object_name = "usuario"

    def form_valid(self, form):
        resposta = super().form_valid(form)
        messages.success(self.request, f"Acesso de {self.object} atualizado.")
        return resposta


class SemAcessoView(TemplateView):
    template_name = "accounts/sem_acesso.html"
