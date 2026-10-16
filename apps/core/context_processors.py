from django.conf import settings
from django.utils import timezone


def branding(request):
    """Nome do sistema e contadores que a barra lateral mostra."""
    contexto = {
        "APP_NOME": settings.SISTEMA_NOME,
        "APP_DESCRICAO": "Gestão de saúde e segurança do trabalho",
        "CONSULTORIA_NOME": settings.CONSULTORIA_NOME,
        "CONSULTORIA_SITE": settings.CONSULTORIA_SITE,
        "DEBUG": settings.DEBUG,
    }
    usuario = getattr(request, "user", None)
    if usuario is not None and usuario.is_authenticated and getattr(usuario, "is_interno", False):
        from datetime import timedelta

        from apps.crm.models import Estagio, Lead
        from apps.gestao.models import Documento, Prazo, StatusDocumento, StatusPrazo
        from apps.publico.models import Diagnostico

        hoje = timezone.localdate()
        contexto["prazos_atrasados"] = Prazo.objects.filter(
            status=StatusPrazo.PENDENTE, data_fim__lt=hoje
        ).count()
        contexto["vencimentos_total"] = Documento.objects.filter(
            status=StatusDocumento.VIGENTE,
            valido_ate__lte=hoje + timedelta(days=settings.VENCIMENTO_ALERTA_DIAS),
            gestao__encerrado_em__isnull=True,
        ).count()
        contexto["leads_atrasados_total"] = (
            Lead.objects.exclude(estagio__in=[Estagio.GANHO, Estagio.PERDIDO])
            .filter(proximo_contato__lt=hoje)
            .count()
        )
        contexto["diagnosticos_abertos"] = Diagnostico.objects.filter(
            lead__isnull=True, atendido_em__isnull=True
        ).count()
    return contexto
