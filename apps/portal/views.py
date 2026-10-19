"""Portal do cliente: a empresa acompanha a propria gestao de SST."""
from datetime import timedelta

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone

from apps.gestao.views import contexto_fap
from django.views.generic import DetailView, TemplateView, View

from apps.accounts.mixins import ClienteMixin
from apps.gestao.models import (
    EtapaMetodo,
    Gestao,
    StatusAcao,
    StatusDocumento,
    StatusPrazo,
    StatusTreinamento,
    TipoRisco,
)
from apps.gestao.services import indicadores_gestao, resumo_plano
from apps.publico.conteudo import ETAPAS_METODO
from apps.relacionamento.forms import EnvioDocumentoForm, MensagemForm
from apps.relacionamento.models import DocumentoSolicitado, StatusDocumento as StatusPedido


def montar_trilha(gestao) -> list[dict]:
    """As 12 etapas do metodo como o cliente as acompanha."""
    atual = gestao.etapa_numero
    return [
        {
            "numero": EtapaMetodo.numero(valor),
            "nome": rotulo,
            "concluida": EtapaMetodo.numero(valor) < atual,
            "atual": EtapaMetodo.numero(valor) == atual,
        }
        for valor, rotulo in EtapaMetodo.choices
    ]


class BasePortalView(ClienteMixin, TemplateView):
    """Base das telas do portal: sempre a gestao da propria empresa."""

    secao = ""

    @property
    def gestao(self):
        if not hasattr(self, "_gestao"):
            self._gestao = (
                Gestao.objects.filter(empresa=self.request.user.empresa)
                .order_by("encerrado_em", "-inicio")
                .first()
            )
        return self._gestao

    def notificacoes(self) -> list[dict]:
        """O que merece a atencao do cliente agora, em ordem de urgencia."""
        gestao = self.gestao
        if not gestao:
            return []

        hoje = timezone.localdate()
        avisos = []
        for pedido in gestao.solicitacoes.filter(
            status__in=[StatusPedido.SOLICITADO, StatusPedido.RECUSADO]
        ).order_by("prazo"):
            quando = "sem prazo definido"
            if pedido.prazo:
                quando = (
                    f"venceu em {pedido.prazo:%d/%m}" if pedido.atrasado
                    else f"até {pedido.prazo:%d/%m}"
                )
            avisos.append({
                "texto": f"Documento pendente: {pedido.titulo}",
                "quando": quando,
                "url": "portal:documentos",
                "alerta": pedido.atrasado,
            })

        atrasadas = [a for a in gestao.acoes.filter(visivel_cliente=True) if a.atrasada]
        if atrasadas:
            avisos.append({
                "texto": f"{len(atrasadas)} ação(ões) do plano com prazo vencido",
                "quando": "no plano de ação",
                "url": "portal:plano",
                "alerta": True,
            })

        nao_lidas = gestao.mensagens.filter(lida_em__isnull=True, autor__tipo="INTERNO").count()
        if nao_lidas:
            avisos.append({
                "texto": f"{nao_lidas} mensagem(ns) nova(s) da equipe",
                "quando": "na conversa",
                "url": "portal:conversa",
                "alerta": False,
            })

        proxima = (
            gestao.reunioes.filter(visivel_cliente=True, quando__gte=timezone.now())
            .order_by("quando").first()
        )
        if proxima and proxima.quando.date() <= hoje + timedelta(days=7):
            avisos.append({
                "texto": f"{proxima.get_tipo_display()}: {proxima.titulo}",
                "quando": f"{timezone.localtime(proxima.quando):%d/%m às %H:%M}",
                "url": "portal:reunioes",
                "alerta": False,
            })

        for prazo in gestao.prazos.filter(
            status=StatusPrazo.PENDENTE, data_fim__lte=hoje + timedelta(days=30)
        ).order_by("data_fim")[:3]:
            avisos.append({
                "texto": prazo.titulo,
                "quando": f"{prazo.data_fim:%d/%m/%Y}",
                "url": "portal:home",
                "alerta": prazo.atrasado,
            })
        return avisos

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["empresa"] = self.request.user.empresa
        contexto["gestao"] = self.gestao
        contexto["secao"] = self.secao
        if self.gestao:
            contexto["documentos_pendentes"] = self.gestao.solicitacoes.filter(
                status__in=[StatusPedido.SOLICITADO, StatusPedido.RECUSADO]
            ).count()
            contexto["notificacoes"] = self.notificacoes()
        return contexto


class PortalHomeView(BasePortalView):
    template_name = "portal/home.html"
    secao = "inicio"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        gestao = self.gestao
        if not gestao:
            return contexto
        prazos = list(gestao.prazos.filter(status=StatusPrazo.PENDENTE).order_by("data_fim")[:8])
        contexto["registros"] = gestao.registros.filter(visivel_cliente=True)[:12]
        contexto["prazos"] = prazos
        contexto["ind"] = indicadores_gestao(gestao)
        contexto["trilha"] = montar_trilha(gestao)
        contexto["etapa_info"] = next(
            (e for e in ETAPAS_METODO if e["numero"] == gestao.etapa_numero), None
        )
        contexto["proxima_etapa"] = next(
            (e for e in ETAPAS_METODO if e["numero"] == gestao.etapa_numero + 1), None
        )
        pendente = gestao.solicitacoes.filter(
            status__in=[StatusPedido.SOLICITADO, StatusPedido.RECUSADO]
        ).order_by("prazo").first()
        contexto["documento_pendente"] = pendente
        contexto["proximo_prazo"] = prazos[0] if prazos else None
        contexto["proxima_reuniao"] = (
            gestao.reunioes.filter(visivel_cliente=True, quando__gte=timezone.now())
            .order_by("quando").first()
        )
        contexto.update(contexto_fap(gestao))
        contexto["alertas_documentos"] = [
            d for d in gestao.documentos.filter(visivel_cliente=True)
            if d.situacao in ("vencido", "a_vencer")
        ]
        return contexto


class PortalPlanoView(BasePortalView):
    template_name = "portal/plano.html"
    secao = "plano"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        if self.gestao:
            filtro = self.request.GET.get("risco", "")
            acoes = self.gestao.acoes.filter(visivel_cliente=True).prefetch_related("eventos")
            if filtro:
                acoes = acoes.filter(risco=filtro)
            acoes = list(acoes)
            contexto["acoes_abertas"] = [a for a in acoes if not a.encerrada]
            contexto["acoes_encerradas"] = [a for a in acoes if a.encerrada]
            contexto["resumo"] = resumo_plano(self.gestao)
            contexto["ind"] = indicadores_gestao(self.gestao)
            contexto["riscos"] = TipoRisco.choices
            contexto["risco_atual"] = filtro
        return contexto


class PortalDocumentosView(BasePortalView):
    template_name = "portal/documentos.html"
    secao = "documentos"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        if self.gestao:
            solicitacoes = list(self.gestao.solicitacoes.all())
            contexto["pendentes"] = [s for s in solicitacoes if s.pendente]
            contexto["entregues"] = [s for s in solicitacoes if not s.pendente]
            contexto["tecnicos"] = self.gestao.documentos.filter(visivel_cliente=True).exclude(
                status=StatusDocumento.SUBSTITUIDO
            )
            contexto["form"] = kwargs.get("form") or EnvioDocumentoForm()
        return contexto


class PortalTreinamentosView(BasePortalView):
    template_name = "portal/treinamentos.html"
    secao = "treinamentos"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        if self.gestao:
            treinamentos = list(
                self.gestao.treinamentos.filter(visivel_cliente=True).exclude(
                    status=StatusTreinamento.CANCELADO
                )
            )
            contexto["planejados"] = sorted(
                [t for t in treinamentos if t.status == StatusTreinamento.PLANEJADO],
                key=lambda t: t.previsto_para or timezone.localdate(),
            )
            contexto["realizados"] = [t for t in treinamentos if t.status == StatusTreinamento.REALIZADO]
            contexto["ind"] = indicadores_gestao(self.gestao)
        return contexto


class EnviarDocumentoView(ClienteMixin, View):
    """O cliente anexa o arquivo pedido pela equipe."""

    def post(self, request, pk):
        solicitacao = get_object_or_404(DocumentoSolicitado, pk=pk)
        if solicitacao.gestao.empresa_id != request.user.empresa_id:
            raise Http404("Documento não encontrado.")
        if solicitacao.status == StatusPedido.VALIDADO:
            messages.error(request, "Esse documento já foi validado pela equipe e não aceita novo envio.")
            return redirect("portal:documentos")

        form = EnvioDocumentoForm(request.POST, request.FILES, instance=solicitacao)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.status = StatusPedido.RECEBIDO
            solicitacao.enviado_em = timezone.now()
            solicitacao.save()
            messages.success(request, f"“{solicitacao.titulo}” enviado. A equipe confere e retorna.")
        else:
            messages.error(request, "Não foi possível enviar o arquivo. Tente novamente.")
        return redirect("portal:documentos")


class PortalReunioesView(BasePortalView):
    template_name = "portal/reunioes.html"
    secao = "reunioes"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        if self.gestao:
            reunioes = list(self.gestao.reunioes.filter(visivel_cliente=True))
            contexto["proximas"] = sorted([r for r in reunioes if r.futura], key=lambda r: r.quando)
            contexto["anteriores"] = [r for r in reunioes if not r.futura]
        return contexto


class PortalConversaView(BasePortalView):
    template_name = "portal/conversa.html"
    secao = "conversa"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        if self.gestao:
            contexto["mensagens"] = self.gestao.mensagens.select_related("autor")
            contexto["form"] = kwargs.get("form") or MensagemForm()
            self.gestao.mensagens.filter(
                lida_em__isnull=True, autor__tipo="INTERNO"
            ).update(lida_em=timezone.now())
        return contexto

    def post(self, request, *args, **kwargs):
        if not self.gestao:
            return redirect("portal:conversa")
        form = MensagemForm(request.POST)
        if form.is_valid():
            mensagem = form.save(commit=False)
            mensagem.gestao = self.gestao
            mensagem.autor = request.user
            mensagem.save()
            return redirect("portal:conversa")
        return self.render_to_response(self.get_context_data(form=form))


class PortalGestaoView(ClienteMixin, DetailView):
    """Linha do tempo completa da gestao."""

    model = Gestao
    template_name = "portal/gestao.html"
    context_object_name = "gestao"
    extra_context = {"secao": "inicio"}

    def get_object(self, queryset=None):
        gestao = super().get_object(queryset)
        if gestao.empresa_id != self.request.user.empresa_id:
            raise Http404("Gestão não encontrada.")
        return gestao

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["registros"] = self.object.registros.filter(visivel_cliente=True)
        contexto["documentos_pendentes"] = self.object.solicitacoes.filter(
            status__in=[StatusPedido.SOLICITADO, StatusPedido.RECUSADO]
        ).count()
        return contexto
