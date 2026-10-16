from datetime import date

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, ListView, UpdateView, View

from apps.accounts.mixins import ComercialMixin
from apps.empresas.models import Empresa

from .forms import VendaForm
from .models import SERVICOS_VENDA, StatusVenda, Venda
from .services import totais


def destino_seguro(request, padrao):
    proximo = request.POST.get("next") or request.GET.get("next")
    if proximo and url_has_allowed_host_and_scheme(proximo, allowed_hosts={request.get_host()}):
        return proximo
    return padrao


class VendaListView(ComercialMixin, ListView):
    template_name = "vendas/lista.html"
    context_object_name = "vendas"
    extra_context = {"secao": "vendas"}
    paginate_by = 50

    def periodo(self):
        hoje = timezone.localdate()
        def ler(nome, padrao):
            try:
                return date.fromisoformat(self.request.GET.get(nome, ""))
            except ValueError:
                return padrao
        return ler("de", hoje.replace(day=1)), ler("ate", hoje)

    def get_queryset(self):
        de, ate = self.periodo()
        qs = Venda.objects.select_related("empresa", "vendedor").filter(data__gte=de, data__lte=ate)
        g = self.request.GET
        if g.get("q", "").strip():
            busca = g["q"].strip()
            qs = qs.filter(Q(descricao__icontains=busca) | Q(empresa__razao_social__icontains=busca) | Q(empresa__nome_fantasia__icontains=busca))
        if g.get("servico"):
            qs = qs.filter(servico=g["servico"])
        if g.get("status"):
            qs = qs.filter(status=g["status"])
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        de, ate = self.periodo()
        lista = list(self.get_queryset())
        contexto.update(
            de=de, ate=ate, q=self.request.GET.get("q", ""), servico_atual=self.request.GET.get("servico", ""),
            status_atual=self.request.GET.get("status", ""), servicos=SERVICOS_VENDA, status_opcoes=StatusVenda.choices,
            tot=totais(lista),
            por_servico=sorted(
                [
                    {"rotulo": rotulo, "total": sum((v.total for v in lista if v.servico == valor and v.ativa), 0),
                     "qtd": sum(1 for v in lista if v.servico == valor and v.ativa)}
                    for valor, rotulo in SERVICOS_VENDA
                ],
                key=lambda x: -x["total"],
            ),
        )
        contexto["por_servico"] = [x for x in contexto["por_servico"] if x["qtd"]]
        maior = max((x["total"] for x in contexto["por_servico"]), default=0)
        for x in contexto["por_servico"]:
            x["percentual"] = round(x["total"] / maior * 100) if maior else 0
        return contexto


class VendaCreateView(ComercialMixin, CreateView):
    model = Venda
    form_class = VendaForm
    template_name = "vendas/form.html"
    extra_context = {"secao": "vendas"}

    def empresa(self):
        pk = self.request.GET.get("empresa") or self.request.POST.get("empresa")
        return Empresa.objects.filter(pk=pk).first() if pk else None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["empresa"] = self.empresa()
        return kwargs

    def get_initial(self):
        inicial = super().get_initial()
        inicial["vendedor"] = self.request.user.pk
        if self.request.GET.get("servico"):
            inicial["servico"] = self.request.GET["servico"]
        empresa = self.empresa()
        if empresa:
            gestao = empresa.gestoes.filter(encerrado_em__isnull=True).first()
            if gestao:
                inicial["gestao"] = gestao.pk
        return inicial

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["empresa"] = self.empresa()
        return contexto

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f"Venda registrada: {self.object.descricao}.")
        return redirect(destino_seguro(self.request, self.object.empresa.get_absolute_url()))

    def form_invalid(self, form):
        if self.request.POST.get("origem") == "empresa":
            erros = "; ".join(f"{form.fields[c].label if c in form.fields else c}: {' '.join(l)}" for c, l in form.errors.items())
            messages.error(self.request, f"Venda não registrada. {erros}")
            return redirect(destino_seguro(self.request, reverse("vendas:lista")))
        return super().form_invalid(form)


class VendaUpdateView(ComercialMixin, UpdateView):
    model = Venda
    form_class = VendaForm
    template_name = "vendas/form.html"
    extra_context = {"secao": "vendas"}

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["empresa"] = self.object.empresa
        return contexto

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, "Venda atualizada.")
        return redirect(destino_seguro(self.request, self.object.empresa.get_absolute_url()))


class VendaStatusView(ComercialMixin, View):
    def post(self, request, pk):
        venda = get_object_or_404(Venda, pk=pk)
        status = request.POST.get("status")
        if status in dict(StatusVenda.choices):
            venda.status = status
            venda.save(update_fields=["status", "atualizado_em"])
            messages.success(request, f"Venda marcada como {venda.get_status_display().lower()}.")
        return redirect(destino_seguro(request, venda.empresa.get_absolute_url()))
