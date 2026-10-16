from django.contrib import messages
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.mixins import EquipeInternaMixin

from apps.gestao.models import Gestao
from apps.gestao.views import panorama_carteira
from apps.vendas.forms import VendaForm
from apps.vendas.models import StatusVenda
from apps.vendas.services import totais

from .forms import ContatoForm, EmpresaForm
from .models import Empresa


class EmpresaListView(EquipeInternaMixin, ListView):
    model = Empresa
    template_name = "empresas/lista.html"
    extra_context = {"secao": "empresas"}
    context_object_name = "empresas"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Empresa.objects.select_related("responsavel")
            .annotate(gestoes_ativas=Count("gestoes", filter=Q(gestoes__encerrado_em__isnull=True)))
            .order_by("razao_social")
        )
        busca = self.request.GET.get("q", "").strip()
        situacao = self.request.GET.get("situacao", "").strip()
        if busca:
            qs = qs.filter(
                Q(razao_social__icontains=busca)
                | Q(nome_fantasia__icontains=busca)
                | Q(cnpj__icontains=busca)
            )
        if situacao:
            qs = qs.filter(situacao=situacao)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "")
        contexto["situacao"] = self.request.GET.get("situacao", "")
        ids = [e.pk for e in contexto["empresas"]]
        por_empresa = {}
        for linha in panorama_carteira(Gestao.objects.filter(encerrado_em__isnull=True, empresa_id__in=ids)):
            por_empresa.setdefault(linha["empresa"].pk, linha)
        for empresa in contexto["empresas"]:
            empresa.fap = por_empresa.get(empresa.pk)
        return contexto


class EmpresaDetailView(EquipeInternaMixin, DetailView):
    model = Empresa
    template_name = "empresas/detalhe.html"
    extra_context = {"secao": "empresas"}
    context_object_name = "empresa"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["gestoes"] = self.object.gestoes.order_by("encerrado_em", "-inicio")
        contexto["contatos"] = self.object.contatos.all()
        contexto["form_contato"] = ContatoForm()
        vendas = list(self.object.vendas.select_related("vendedor", "gestao"))
        contexto["vendas"] = vendas
        contexto["totais_vendas"] = totais(vendas)
        contexto["form_venda"] = VendaForm(empresa=self.object, initial={
            "vendedor": self.request.user.pk,
            "gestao": getattr(self.object.gestoes.filter(encerrado_em__isnull=True).first(), "pk", None),
        })
        contexto["status_venda"] = StatusVenda.choices
        contexto["faps"] = panorama_carteira(self.object.gestoes.filter(encerrado_em__isnull=True))
        return contexto

    def post(self, request, *args, **kwargs):
        """Cadastro rapido de contato pela propria pagina da empresa."""
        self.object = self.get_object()
        form = ContatoForm(request.POST)
        if form.is_valid():
            contato = form.save(commit=False)
            contato.empresa = self.object
            contato.save()
            messages.success(request, "Contato adicionado.")
        else:
            messages.error(request, "Verifique os dados do contato.")
        contexto = self.get_context_data(object=self.object)
        contexto["form_contato"] = form
        return self.render_to_response(contexto)


class EmpresaCreateView(EquipeInternaMixin, CreateView):
    model = Empresa
    form_class = EmpresaForm
    template_name = "empresas/form.html"
    extra_context = {"secao": "empresas"}

    def form_valid(self, form):
        messages.success(self.request, "Empresa cadastrada.")
        return super().form_valid(form)


class EmpresaUpdateView(EquipeInternaMixin, UpdateView):
    model = Empresa
    form_class = EmpresaForm
    template_name = "empresas/form.html"
    extra_context = {"secao": "empresas"}

    def form_valid(self, form):
        messages.success(self.request, "Empresa atualizada.")
        return super().form_valid(form)
