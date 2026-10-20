"""Entrada do portal por codigo de uso unico."""
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect, render
from django.views.generic import View

import threading

from django import db
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.views import LoginView

from . import limites
from .codigos import MAX_TENTATIVAS, VALIDADE_MINUTOS, CodigoAcesso, EnvioCodigoFalhou, criar_e_enviar
from .models import TipoUsuario

User = get_user_model()

SESSAO_USUARIO = "codigo_usuario_id"
SESSAO_FALSAS = "codigo_tentativas_falsas"

# Mensagem unica: nao dizemos se o contato existe ou nao.
AVISO_ENVIO = (
    "Se esse contato estiver cadastrado, o código chega em instantes. "
    f"Ele vale por {VALIDADE_MINUTOS} minutos."
)


def _somente_digitos(valor: str) -> str:
    return "".join(c for c in valor if c.isdigit())


_HASH_FALSO = make_password("000000")


def _enviar_codigo(usuario):
    def executar():
        try:
            criar_e_enviar(usuario)  # None: limite por usuário; o aviso ao cliente é o mesmo
        except EnvioCodigoFalhou:
            pass  # já registrado em log por criar_e_enviar
        finally:
            if settings.CODIGO_ENVIO_EM_THREAD:
                db.connection.close()

    if settings.CODIGO_ENVIO_EM_THREAD:
        threading.Thread(target=executar, daemon=True).start()
    else:
        executar()


MSG_BLOQUEIO = "Muitas tentativas. Aguarde alguns minutos e tente de novo."


class EntrarView(LoginView):
    """Login por senha da equipe, com limite de tentativas por IP e por usuário."""

    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        ip = limites.ip_do_pedido(request)
        nome = (request.POST.get("username") or "").strip()
        if limites.bloqueado("login-ip", ip, limites.LOGIN_POR_IP) or (
            nome and limites.bloqueado("login-ip-usuario", f"{ip}|{nome}", limites.LOGIN_POR_USUARIO)
        ):
            form = self.get_form()
            form.add_error(None, MSG_BLOQUEIO)
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        ip = limites.ip_do_pedido(self.request)
        limites.zerar("login-ip-usuario", f"{ip}|{(self.request.POST.get('username') or '').strip()}")
        return super().form_valid(form)

    def form_invalid(self, form):
        ip = limites.ip_do_pedido(self.request)
        limites.registrar("login-ip", ip)
        nome = (self.request.POST.get("username") or "").strip()
        if nome:
            # chave ip+usuário: quem erra a senha de alguém não consegue trancar o login dessa pessoa para todos
            limites.registrar("login-ip-usuario", f"{ip}|{nome}")
        return super().form_invalid(form)


class PedirCodigoView(View):
    """Passo 1: o cliente informa o contato cadastrado."""

    template_name = "accounts/codigo_pedir.html"

    def get(self, request):
        return render(request, self.template_name, {})

    def post(self, request):
        contato = (request.POST.get("contato") or "").strip()
        if not contato:
            return render(request, self.template_name, {"erro": "Informe seu e-mail ou celular."})

        ip = limites.ip_do_pedido(request)
        chave_contato = _somente_digitos(contato) if "@" not in contato else contato
        if limites.bloqueado("codigo-ip", ip, limites.CODIGO_POR_IP) or limites.bloqueado(
            "codigo-ip-contato", f"{ip}|{chave_contato}", limites.CODIGO_POR_CONTATO
        ):
            return render(request, self.template_name, {"erro": MSG_BLOQUEIO}, status=429)
        limites.registrar("codigo-ip", ip)
        limites.registrar("codigo-ip-contato", f"{ip}|{chave_contato}")

        # A resposta e a sessão são as mesmas exista o contato ou não (0 = pedido sem usuário).
        usuario = self._encontrar(contato)
        request.session[SESSAO_USUARIO] = usuario.pk if usuario else 0
        request.session.pop(SESSAO_FALSAS, None)
        if usuario:
            # O envio (SMTP) roda fora do pedido: o tempo de resposta não revela se o contato existe,
            # nem uma falha de envio vira diferença visível (ela fica no log).
            _enviar_codigo(usuario)

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
        if request.session.get(SESSAO_USUARIO) is None:
            return render(request, self.template_name, {"sem_pedido": True})
        return render(request, self.template_name, {})

    def post(self, request):
        digitado = _somente_digitos(request.POST.get("codigo") or "")
        usuario_id = request.session.get(SESSAO_USUARIO)

        ip = limites.ip_do_pedido(request)
        if limites.bloqueado("codigo-confirmar", ip, limites.CONFIRMAR_POR_IP):
            return render(request, self.template_name, {"erro": MSG_BLOQUEIO}, status=429)
        if len(digitado) != 6:
            return render(request, self.template_name, {"erro": "Digite os 6 dígitos do código."})
        if usuario_id is None:
            return render(request, self.template_name, {"sem_pedido": True})
        limites.registrar("codigo-confirmar", ip)
        if usuario_id == 0:
            return self._falso(request)

        registro = (
            CodigoAcesso.objects.filter(usuario_id=usuario_id, usado_em__isnull=True)
            .order_by("-criado_em").first()
        )
        if registro is None or registro.expirado:
            # mesma resposta de um pedido sem usuário: não revela se o contato existe
            return self._falso(request)
        if registro.tentativas >= MAX_TENTATIVAS:
            return render(request, self.template_name, {
                "erro": "Tentativas demais para esse código. Peça um novo.", "expirado": True,
            })

        if not registro.confere(digitado):
            restantes = max(0, MAX_TENTATIVAS - registro.tentativas)
            return render(request, self.template_name, {
                "erro": f"Código inválido. Restam {restantes} tentativa(s).",
                "expirado": restantes == 0,
            })

        request.session.pop(SESSAO_USUARIO, None)
        login(request, registro.usuario, backend="apps.accounts.backends.UsuarioOuEmailBackend")
        return redirect("portal:home")


    def _falso(self, request):
        """Pedido sem usuário (ou sem código vigente): devolve as mesmas respostas de um código real errado."""
        check_password("000000", _HASH_FALSO)  # custo parecido com o da conferência real
        feitas = request.session.get(SESSAO_FALSAS, 0)
        if feitas >= MAX_TENTATIVAS:
            return render(request, self.template_name, {
                "erro": "Tentativas demais para esse código. Peça um novo.", "expirado": True,
            })
        request.session[SESSAO_FALSAS] = feitas + 1
        restantes = max(0, MAX_TENTATIVAS - feitas - 1)
        return render(request, self.template_name, {
            "erro": f"Código inválido. Restam {restantes} tentativa(s).", "expirado": restantes == 0,
        })


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
