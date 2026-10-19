"""Download autenticado dos arquivos enviados (documentos técnicos, pedidos do portal, planilhas)."""
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from apps.gestao.models import Documento, ImportacaoPlano
from apps.relacionamento.models import DocumentoSolicitado

from .arquivos import resposta_download


def _equipe_tecnica(user) -> bool:
    return user.is_interno and user.tem_modulo("tecnico")


def _cliente_da_gestao(user, gestao) -> bool:
    return bool(user.is_cliente and user.empresa_id and gestao.empresa_id == user.empresa_id)


@login_required
@require_GET
def documento(request, pk):
    obj = get_object_or_404(Documento.objects.select_related("gestao"), pk=pk)
    if not (_equipe_tecnica(request.user) or (_cliente_da_gestao(request.user, obj.gestao) and obj.visivel_cliente)):
        raise Http404("Arquivo não encontrado.")
    return resposta_download(obj.arquivo, obj.nome)


@login_required
@require_GET
def documento_solicitado(request, pk):
    obj = get_object_or_404(DocumentoSolicitado.objects.select_related("gestao"), pk=pk)
    if not (_equipe_tecnica(request.user) or _cliente_da_gestao(request.user, obj.gestao)):
        raise Http404("Arquivo não encontrado.")
    return resposta_download(obj.arquivo, obj.titulo)


@login_required
@require_GET
def importacao_plano(request, pk):
    obj = get_object_or_404(ImportacaoPlano, pk=pk)
    if not _equipe_tecnica(request.user):
        raise Http404("Arquivo não encontrado.")
    return resposta_download(obj.arquivo)
