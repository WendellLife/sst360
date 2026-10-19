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
        # O que o usuário pode abrir: os templates escondem links e botões das áreas sem acesso.
        contexto["pode"] = {m: usuario.tem_modulo(m) for m in ("comercial", "tecnico", "admin")}
        contexto["inicio_url"] = _url_inicio(usuario)
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
        contexto["menu"] = montar_menu(request, usuario, contexto)
        contexto["barra"] = semana_de_prazos(hoje)
    return contexto


def _url_inicio(usuario):
    from django.urls import reverse

    return reverse(usuario.pagina_inicial())


# Barra lateral no padrão Razach Tarefas Internas: grupos numerados, ícone Lucide, contagem à direita.
# Cada item diz o módulo que libera o acesso (comercial, tecnico, admin; None = qualquer módulo).
GRUPOS = [
    ("01 · Comercial", [
        ("painel", "Painel", "core:dashboard", "layout-dashboard", None, "comercial"),
        ("indicadores", "Indicadores", "core:indicadores", "chart-column", None, "comercial"),
        ("funil", "Funil", "crm:funil", "filter", None, "comercial"),
        ("diagnosticos", "Diagnósticos", "crm:diagnosticos", "list-checks", "diagnosticos_abertos", "comercial"),
        ("leads", "Leads", "crm:lista", "user-plus", "leads_atrasados_total", "comercial"),
        ("vendas", "Vendas", "vendas:lista", "handshake", None, "comercial"),
        ("campanhas", "Campanhas", "campanhas:painel", "send", None, "comercial"),
        ("fap", "FAP dos clientes", "gestao:fap_carteira", "gauge", None, "comercial"),
        ("tarefas", "Sistema Tarefas", "tarefas_ext:painel", "square-kanban", None, "comercial"),
    ]),
    ("02 · Gestão de SST", [
        ("gestao", "Gestões de SST", "gestao:lista", "shield-check", None, "tecnico"),
        ("prazos", "Prazos", "gestao:agenda", "timer", "prazos_atrasados", "tecnico"),
        ("vencimentos", "Vencimentos", "gestao:vencimentos", "calendar-x", "vencimentos_total", "tecnico"),
        ("empresas", "Empresas", "empresas:lista", "building-2", None, None),
    ]),
    ("03 · Administração", [
        ("usuarios", "Usuários e acessos", "accounts:usuarios", "user-cog", None, "admin"),
    ]),
]
SECAO_GRUPO = {chave: rotulo for rotulo, itens in GRUPOS for chave, *_ in itens}
SECAO_GRUPO.update({"busca": "02 · Gestão de SST"})


def montar_menu(request, usuario, contexto):
    from django.urls import reverse

    menu = []
    for rotulo, itens in GRUPOS:
        visiveis = [
            {"chave": chave, "rotulo": nome, "url": reverse(rota), "icone": ic,
             "contagem": contexto.get(cont) if cont else None}
            for chave, nome, rota, ic, cont, modulo in itens
            if usuario.tem_modulo(modulo)
        ]
        if visiveis:
            menu.append({"rotulo": rotulo, "itens": visiveis})
    return menu


def semana_de_prazos(hoje):
    """Rodapé da barra lateral: prazos da semana corrente cumpridos até hoje."""
    from datetime import timedelta

    from apps.gestao.models import Prazo, StatusPrazo

    inicio = hoje - timedelta(days=hoje.weekday())
    fim = inicio + timedelta(days=6)
    qs = Prazo.objects.filter(data_fim__range=(inicio, fim), gestao__encerrado_em__isnull=True)
    total = qs.count()
    feitos = qs.filter(status=StatusPrazo.CUMPRIDO).count()
    pct = round(feitos * 100 / total) if total else 0
    return {"semana": hoje.isocalendar()[1], "feitos": feitos, "total": total, "pct": pct}
