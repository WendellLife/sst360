"""Lado interno do relacionamento: pedir documento, marcar visita, responder."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import View

from apps.accounts.mixins import EquipeInternaMixin
from apps.gestao.models import Gestao, StatusAcao

from .forms import (
    ConferenciaDocumentoForm,
    MensagemForm,
    ReuniaoForm,
    SolicitacaoDocumentoForm,
)
from .models import DocumentoSolicitado, StatusDocumento


class RelacionamentoView(EquipeInternaMixin, View):
    """Tudo que a equipe troca com a empresa, num lugar so."""

    template_name = "gestao/relacionamento.html"

    def get(self, request, pk, **extra):
        gestao = get_object_or_404(
            Gestao.objects.select_related("empresa"), pk=pk
        )
        contexto = {
            "gestao": gestao,
            "secao": "gestao",
            "solicitacoes": gestao.solicitacoes.all(),
            "reunioes": gestao.reunioes.all(),
            "mensagens": gestao.mensagens.select_related("autor"),
            "acoes": gestao.acoes.exclude(status__in=StatusAcao.encerrados()).prefetch_related("eventos"),
            "status_acao": StatusAcao.choices,
            "form_solicitacao": extra.get("form_solicitacao") or SolicitacaoDocumentoForm(),
            "form_reuniao": extra.get("form_reuniao") or ReuniaoForm(),
            "form_mensagem": extra.get("form_mensagem") or MensagemForm(),
            "nao_lidas": gestao.mensagens.filter(lida_em__isnull=True).exclude(
                autor__tipo="INTERNO"
            ).count(),
        }
        gestao.mensagens.filter(lida_em__isnull=True).exclude(autor__tipo="INTERNO").update(
            lida_em=timezone.now()
        )
        return render(request, self.template_name, contexto)


class SolicitarDocumentoView(EquipeInternaMixin, View):
    def post(self, request, pk):
        gestao = get_object_or_404(Gestao, pk=pk)
        form = SolicitacaoDocumentoForm(request.POST)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.gestao = gestao
            solicitacao.solicitado_por = request.user
            solicitacao.save()
            messages.success(request, "Documento solicitado. Ele aparece no portal do cliente.")
        else:
            messages.error(request, "Confira os campos da solicitacao.")
        return redirect("relacionamento:painel", pk=gestao.pk)


class ConferirDocumentoView(EquipeInternaMixin, View):
    """Marca o documento recebido como validado ou pede reenvio."""

    def post(self, request, pk):
        solicitacao = get_object_or_404(DocumentoSolicitado, pk=pk)
        form = ConferenciaDocumentoForm(request.POST, instance=solicitacao)
        if form.is_valid():
            form.save()
            messages.success(request, "Conferencia registrada.")
        else:
            messages.error(request, "Nao foi possivel registrar a conferencia.")
        return redirect("relacionamento:painel", pk=solicitacao.gestao_id)


class ReuniaoCreateView(EquipeInternaMixin, View):
    def post(self, request, pk):
        gestao = get_object_or_404(Gestao, pk=pk)
        form = ReuniaoForm(request.POST)
        if form.is_valid():
            reuniao = form.save(commit=False)
            reuniao.gestao = gestao
            reuniao.save()
            messages.success(request, "Visita registrada.")
        else:
            messages.error(request, "Confira os dados da reuniao.")
        return redirect("relacionamento:painel", pk=gestao.pk)


class ResponderView(EquipeInternaMixin, View):
    def post(self, request, pk):
        gestao = get_object_or_404(Gestao, pk=pk)
        form = MensagemForm(request.POST)
        if form.is_valid():
            mensagem = form.save(commit=False)
            mensagem.gestao = gestao
            mensagem.autor = request.user
            mensagem.save()
        else:
            messages.error(request, "Escreva a mensagem antes de enviar.")
        return redirect("relacionamento:painel", pk=gestao.pk)
