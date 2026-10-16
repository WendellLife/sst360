from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import TemplateView, View

from apps.accounts.mixins import EquipeInternaMixin
from apps.crm.models import Estagio, Lead
from apps.empresas.models import Empresa, SituacaoEmpresa
from apps.gestao.models import (
    Documento,
    EtapaMetodo,
    Gestao,
    Prazo,
    StatusDocumento,
    StatusPrazo,
    StatusTreinamento,
    Treinamento,
)
from apps.gestao.services import acoes_atrasadas
from apps.gestao.views import panorama_carteira
from apps.publico.models import Diagnostico
from apps.relacionamento.models import Reuniao, StatusReuniao
from apps.vendas.models import Venda
from apps.vendas.services import totais as totais_vendas


class HomeView(View):
    """A raiz do site: visitante ve a pagina publica, quem entrou vai ao seu espaco."""

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from apps.publico.conteudo import COMO_FUNCIONA, DIFERENCIAIS, DORES, ETAPAS_METODO, SERVICOS

            return render(
                request,
                "publico/home.html",
                {
                    "como_funciona": COMO_FUNCIONA,
                    "servicos": SERVICOS,
                    "diferenciais": DIFERENCIAIS,
                    "dores": DORES,
                    "etapas": ETAPAS_METODO,
                },
            )
        if request.user.is_cliente:
            return redirect("portal:home")
        return redirect("core:dashboard")


class DashboardView(EquipeInternaMixin, TemplateView):
    template_name = "core/dashboard.html"
    extra_context = {"secao": "painel"}

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        limite = hoje + timedelta(days=settings.PRAZO_ALERTA_DIAS)
        limite_venc = hoje + timedelta(days=settings.VENCIMENTO_ALERTA_DIAS)

        gestoes = Gestao.objects.filter(encerrado_em__isnull=True)

        carteira_fap = panorama_carteira()
        contexto["fap_oportunidades"] = [x for x in carteira_fap if x["potencial"]][:5]
        contexto["fap_potencial_total"] = sum((x["potencial"] for x in carteira_fap), 0)
        contexto["fap_malus"] = sum(1 for x in carteira_fap if x["c"] and x["c"].nivel and x["c"].nivel["codigo"] in ("MAL", "MMAX"))
        vendas_mes = list(Venda.objects.select_related("empresa").filter(data__gte=hoje.replace(day=1), data__lte=hoje))
        contexto["vendas_mes"] = totais_vendas(vendas_mes)
        contexto["ultimas_vendas"] = Venda.objects.select_related("empresa").exclude(status="CANC")[:5]
        contexto["total_clientes"] = Empresa.objects.filter(situacao=SituacaoEmpresa.CLIENTE).count()
        contexto["total_gestoes"] = gestoes.count()
        contexto["receita_mensal"] = gestoes.aggregate(t=Sum("valor_mensal"))["t"] or 0
        contexto["trabalhadores"] = (
            Empresa.objects.filter(gestoes__in=gestoes).distinct().aggregate(t=Sum("num_trabalhadores"))["t"] or 0
        )

        contexto["prazos_criticos"] = (
            Prazo.objects.filter(status=StatusPrazo.PENDENTE, data_fim__lte=limite)
            .select_related("gestao", "gestao__empresa", "responsavel")
            .order_by("data_fim")[:10]
        )
        contexto["total_prazos_atrasados"] = Prazo.objects.filter(
            status=StatusPrazo.PENDENTE, data_fim__lt=hoje
        ).count()

        documentos_alerta = Documento.objects.filter(
            status=StatusDocumento.VIGENTE, valido_ate__lte=limite_venc, gestao__in=gestoes
        ).select_related("gestao", "gestao__empresa").order_by("valido_ate")
        contexto["documentos_alerta"] = documentos_alerta[:6]
        contexto["total_documentos_vencidos"] = documentos_alerta.filter(valido_ate__lt=hoje).count()
        contexto["total_documentos_alerta"] = documentos_alerta.count()

        contexto["treinamentos_alerta"] = (
            Treinamento.objects.filter(
                status=StatusTreinamento.REALIZADO, valido_ate__lte=limite_venc, gestao__in=gestoes
            )
            .select_related("gestao", "gestao__empresa")
            .order_by("valido_ate")[:6]
        )

        atrasadas = acoes_atrasadas()
        contexto["total_acoes_atrasadas"] = atrasadas.count()

        etapas = {linha["etapa"]: linha["total"] for linha in gestoes.values("etapa").annotate(total=Count("id"))}
        contexto["por_etapa"] = [
            {"valor": valor, "rotulo": rotulo, "total": etapas.get(valor, 0), "cor": EtapaMetodo.cor(valor)}
            for valor, rotulo in EtapaMetodo.choices
            if etapas.get(valor, 0)
        ]

        contexto["proximas_visitas"] = (
            Reuniao.objects.filter(
                status=StatusReuniao.AGENDADA, quando__gte=timezone.now(), gestao__in=gestoes
            )
            .select_related("gestao", "gestao__empresa")
            .order_by("quando")[:5]
        )

        leads_abertos = Lead.objects.exclude(estagio__in=[Estagio.GANHO, Estagio.PERDIDO])
        contexto["total_leads"] = leads_abertos.count()
        contexto["pipeline_valor"] = leads_abertos.aggregate(t=Sum("valor_estimado"))["t"] or 0
        contexto["leads_atrasados"] = (
            leads_abertos.filter(proximo_contato__lt=hoje).select_related("responsavel").order_by("proximo_contato")[:5]
        )
        contexto["leads_por_estagio"] = [
            {"rotulo": rotulo, "total": leads_abertos.filter(estagio=valor).count()}
            for valor, rotulo in Estagio.funil()
        ]
        contexto["diagnosticos_novos"] = Diagnostico.objects.filter(
            lead__isnull=True, atendido_em__isnull=True
        ).count()

        contexto["empresas_sem_gestao"] = (
            Empresa.objects.filter(situacao=SituacaoEmpresa.CLIENTE)
            .annotate(qtd=Count("gestoes", filter=Q(gestoes__encerrado_em__isnull=True)))
            .filter(qtd=0)[:5]
        )
        return contexto


class IndicadoresView(EquipeInternaMixin, TemplateView):
    """Dashboards da carteira: conformidade, plano de ação, FAP e comercial."""

    template_name = "core/indicadores.html"
    extra_context = {"secao": "indicadores"}

    def get_context_data(self, **kwargs):
        from . import graficos
        from .indicadores import calcular, ler_periodo, moeda, moeda_curta

        contexto = super().get_context_data(**kwargs)
        periodo = ler_periodo(self.request.GET)
        d = calcular(periodo)
        cf, cm = d["conformidade"], d["comercial"]
        docs = cf["documentos"]
        tre = cf["treinamentos"]
        contexto.update(d)
        contexto["graficos"] = {
            "vendas_mes": graficos.colunas(cm["vendas"]["por_mes"], formato=moeda, formato_eixo=moeda_curta, titulo="Vendas por mês", largura=600),
            "vendas_servico": graficos.barras(cm["vendas"]["por_servico"], formato=moeda, extra=lambda i: f"· {i['qtd']}", titulo="Vendas por serviço", largura=460, largura_rotulo=170, valor_w=130),
            "vendas_cliente": graficos.barras(cm["vendas"]["por_cliente"], formato=moeda, titulo="Vendas por cliente", largura=300, largura_rotulo=120, valor_w=95),
            "etapas": graficos.colunas(d["carteira"]["por_etapa"], rotulo="curto", titulo="Gestões por etapa do método", altura=170, destaque_ultimo=False, largura=900),
            "documentos": graficos.empilhada([
                {"rotulo": "Vigentes", "total": docs["vigente"], "classe": "g-ok"},
                {"rotulo": "A revisar em 60 dias", "total": docs["a_vencer"], "classe": "g-atencao"},
                {"rotulo": "Vencidos", "total": docs["vencido"], "classe": "g-critico"},
                {"rotulo": "Em elaboração", "total": docs["elaboracao"], "classe": "g-neutra"},
            ], titulo="Situação dos documentos"),
            "reciclagens": graficos.empilhada([
                {"rotulo": "Em dia", "total": tre["em_dia"], "classe": "g-ok"},
                {"rotulo": "A reciclar em 60 dias", "total": tre["a_vencer"], "classe": "g-atencao"},
                {"rotulo": "Vencidas", "total": tre["vencidas"], "classe": "g-critico"},
            ], titulo="Situação das reciclagens"),
            "fap": graficos.pontos_fap(d["fap"]["linhas"], titulo="FAP de cada cliente", largura=600),
            "funil": graficos.barras(cm["funil"]["por_estagio"], extra=lambda i: f"· {moeda(i['valor'])}/mês", titulo="Leads por estágio", largura=460, largura_rotulo=140, valor_w=150),
            "diagnosticos": graficos.barras(cm["diagnosticos"]["por_urgencia"], titulo="Diagnósticos por exposição", largura=560, largura_rotulo=150,
                                           classe=lambda i: {"ALTA": "g-critico", "MEDIA": "g-atencao", "BAIXA": "g-ok"}[i["codigo"]]),
        }
        contexto["filtro"] = {"de": periodo.de.isoformat(), "ate": periodo.ate.isoformat()}
        contexto["query"] = self.request.GET.urlencode()
        return contexto


class ApresentacaoIndicadoresView(EquipeInternaMixin, View):
    """Baixa os indicadores do período como apresentação PowerPoint (.pptx)."""

    def get(self, request):
        from django.http import HttpResponse

        from .apresentacao import gerar_apresentacao
        from .indicadores import calcular, ler_periodo

        periodo = ler_periodo(request.GET)
        arquivo = gerar_apresentacao(calcular(periodo), autor=request.user.get_full_name() or request.user.username)
        nome = f"indicadores-sst360-{periodo.de:%Y%m%d}-{periodo.ate:%Y%m%d}.pptx"
        resposta = HttpResponse(
            arquivo.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
        return resposta
