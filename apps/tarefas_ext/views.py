from django.contrib import messages
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.mixins import ComercialMixin

from . import servicos


class PainelTarefasView(ComercialMixin, TemplateView):
    """Área comercial: o que o sistema Tarefas sabe dos clientes (somente leitura)."""

    template_name = "tarefas_ext/painel.html"
    extra_context = {"secao": "tarefas"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        st = servicos.status()
        ctx["status"] = st
        ctx["url_tarefas"] = servicos.url_tarefas()
        if st["ok"]:
            dados = servicos.painel()
            filtro = self.request.GET.get("vinculo", "")
            linhas = dados["linhas"]
            if filtro in ("cliente", "lead", "sem_cadastro"):
                linhas = [l for l in linhas if l["vinculo"] == filtro]
            ctx.update(dados, linhas=linhas, vinculo=filtro)
        return ctx


class CriarLeadView(ComercialMixin, View):
    def post(self, request, pk):
        if not servicos.status()["ok"]:
            messages.error(request, "O sistema Tarefas não está ligado.")
            return redirect("tarefas_ext:painel")
        lead, criado = servicos.criar_lead(pk, request.user)
        if criado:
            messages.success(request, f"Lead {lead} criado no funil a partir do sistema Tarefas.")
            return redirect(lead.get_absolute_url())
        if lead:
            messages.info(request, f"{lead} já está no funil.")
            return redirect(lead.get_absolute_url())
        messages.info(request, "Essa empresa já é cliente no SST360.")
        return redirect("tarefas_ext:painel")


class ImportarTodosView(ComercialMixin, View):
    """Traz para o funil, de uma vez, todos os clientes ativos do Tarefas que ainda não estão no SST360."""

    def post(self, request):
        if not servicos.status()["ok"]:
            messages.error(request, "O sistema Tarefas não está ligado.")
            return redirect("tarefas_ext:painel")
        r = servicos.importar_clientes(request.user)
        if r["criados"]:
            messages.success(request, f"{len(r['criados'])} lead(s) criado(s) a partir do sistema Tarefas, com você como responsável.")
        else:
            messages.info(request, "Todos os clientes ativos do Tarefas já estão no SST360.")
        return redirect("tarefas_ext:painel")
