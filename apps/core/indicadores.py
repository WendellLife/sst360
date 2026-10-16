"""Indicadores do painel interno.

Uma única função monta todos os números; a tela de indicadores e a apresentação
(.pptx) leem o mesmo dicionário, então o que se vê na tela é o que vai para o slide.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.crm.models import Estagio, Lead
from apps.empresas.models import Empresa, SituacaoEmpresa
from apps.gestao.fap import NIVEIS
from apps.gestao.models import (
    AcaoPlano,
    Documento,
    EtapaMetodo,
    Gestao,
    Prazo,
    StatusDocumento,
    StatusPrazo,
    StatusTreinamento,
    Treinamento,
)
from apps.gestao.services import indicadores_gestao
from apps.gestao.views import panorama_carteira
from apps.publico.models import Diagnostico, Urgencia
from apps.relacionamento.models import Reuniao, StatusReuniao
from apps.vendas.models import SERVICOS_VENDA, Cobranca, StatusVenda, Venda

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
ZERO = Decimal("0")


@dataclass
class Periodo:
    de: date
    ate: date

    @property
    def rotulo(self) -> str:
        return f"{self.de:%d/%m/%Y} a {self.ate:%d/%m/%Y}"

    @property
    def dias(self) -> int:
        return (self.ate - self.de).days + 1


def periodo_padrao(hoje=None) -> Periodo:
    """Do primeiro dia do mês, cinco meses atrás, até hoje (seis meses de leitura)."""
    hoje = hoje or timezone.localdate()
    mes, ano = hoje.month - 5, hoje.year
    while mes < 1:
        mes += 12
        ano -= 1
    return Periodo(date(ano, mes, 1), hoje)


def ler_periodo(dados) -> Periodo:
    padrao = periodo_padrao()

    def ler(nome, valor):
        try:
            return date.fromisoformat(dados.get(nome, ""))
        except ValueError:
            return valor

    de, ate = ler("de", padrao.de), ler("ate", padrao.ate)
    if de > ate:
        de, ate = ate, de
    return Periodo(de, ate)


def meses_do_periodo(periodo: Periodo) -> list[tuple[int, int]]:
    meses, ano, mes = [], periodo.de.year, periodo.de.month
    while (ano, mes) <= (periodo.ate.year, periodo.ate.month):
        meses.append((ano, mes))
        mes += 1
        if mes > 12:
            mes, ano = 1, ano + 1
    return meses[-12:]


def pct(parte, todo) -> int:
    return round(parte / todo * 100) if todo else 0


def calcular(periodo: Periodo | None = None) -> dict:
    periodo = periodo or periodo_padrao()
    hoje = timezone.localdate()
    gestoes = list(
        Gestao.objects.filter(encerrado_em__isnull=True)
        .select_related("empresa")
        .prefetch_related("documentos", "treinamentos", "acoes", "fichas_fap")
    )
    ids = [g.pk for g in gestoes]

    # ------------------------------------------------------------ carteira
    empresas = {g.empresa_id: g.empresa for g in gestoes}
    carteira = {
        "clientes": Empresa.objects.filter(situacao=SituacaoEmpresa.CLIENTE).count(),
        "gestoes": len(gestoes),
        "trabalhadores": sum(e.num_trabalhadores or 0 for e in empresas.values()),
        "receita_mensal": sum((g.valor_mensal or ZERO for g in gestoes), ZERO),
        "por_etapa": [
            {"rotulo": f"{valor} · {rotulo}", "curto": valor, "nome": rotulo,
             "total": sum(1 for g in gestoes if g.etapa == valor)}
            for valor, rotulo in EtapaMetodo.choices
        ],
    }

    # ------------------------------------------------------------ conformidade
    docs = [d for g in gestoes for d in g.documentos.all() if d.status != StatusDocumento.SUBSTITUIDO]
    situacoes_doc = {s: sum(1 for d in docs if d.situacao == s) for s in ("vigente", "a_vencer", "vencido", "elaboracao")}
    treinos = [t for g in gestoes for t in g.treinamentos.all()]
    realizados_periodo = [t for t in treinos if t.status == StatusTreinamento.REALIZADO and t.realizado_em
                          and periodo.de <= t.realizado_em <= periodo.ate]
    reciclagens = [t for t in treinos if t.status == StatusTreinamento.REALIZADO]
    prazos_periodo = list(Prazo.objects.filter(gestao_id__in=ids, data_fim__gte=periodo.de, data_fim__lte=periodo.ate))
    cumpridos = [p for p in prazos_periodo if p.status == StatusPrazo.CUMPRIDO]
    no_prazo = [p for p in cumpridos if p.concluido_em and p.concluido_em <= p.data_fim]
    pendentes_atrasados = Prazo.objects.filter(gestao_id__in=ids, status=StatusPrazo.PENDENTE, data_fim__lt=hoje).count()
    proximos_30 = Prazo.objects.filter(gestao_id__in=ids, status=StatusPrazo.PENDENTE,
                                       data_fim__gte=hoje, data_fim__lte=hoje + timedelta(days=30)).count()
    acoes = [a for g in gestoes for a in g.acoes.all()]
    encerradas = sum(1 for a in acoes if a.encerrada)
    conformidade = {
        "documentos": {**situacoes_doc, "total": len(docs), "pct_vigentes": pct(situacoes_doc["vigente"] + situacoes_doc["a_vencer"], len(docs))},
        "treinamentos": {
            "turmas_periodo": len(realizados_periodo),
            "pessoas_periodo": sum(t.participantes for t in realizados_periodo),
            "horas_periodo": sum((t.carga_horaria or 0) * t.participantes for t in realizados_periodo),
            "em_dia": sum(1 for t in reciclagens if t.situacao == "em_dia"),
            "a_vencer": sum(1 for t in reciclagens if t.situacao == "a_vencer"),
            "vencidas": sum(1 for t in reciclagens if t.situacao == "vencido"),
        },
        "prazos": {
            "no_periodo": len(prazos_periodo), "cumpridos": len(cumpridos), "no_prazo": len(no_prazo),
            "pct_no_prazo": pct(len(no_prazo), len(cumpridos)), "atrasados": pendentes_atrasados, "proximos_30": proximos_30,
        },
        "acoes": {
            "total": len(acoes), "encerradas": encerradas, "pct": pct(encerradas, len(acoes)),
            "atrasadas": sum(1 for a in acoes if a.atrasada),
            "abertas": len(acoes) - encerradas,
            "custo_aberto": sum((a.custo_estimado or ZERO for a in acoes if not a.encerrada), ZERO),
        },
    }

    # ------------------------------------------------------------ por cliente
    fap = {x["gestao"].pk: x for x in panorama_carteira(Gestao.objects.filter(pk__in=ids))}
    clientes = []
    for g in gestoes:
        ind = indicadores_gestao(g)
        x = fap.get(g.pk)
        atrasados_g = Prazo.objects.filter(gestao=g, status=StatusPrazo.PENDENTE, data_fim__lt=hoje).count()
        clientes.append({
            "gestao": g, "empresa": g.empresa, "nome": str(g.empresa), "etapa": g.etapa,
            "etapa_rotulo": g.get_etapa_display(), "ind": ind,
            "pct_docs": pct(ind["documentos_vigentes"] + ind["documentos_a_vencer"], ind["documentos_total"]),
            "prazos_atrasados": atrasados_g, "fap": x,
            "alerta": ind["documentos_vencidos"] + ind["acoes_atrasadas"] + atrasados_g + ind["treinamentos_vencidos"],
        })
    clientes.sort(key=lambda c: (-c["alerta"], c["nome"]))

    # ------------------------------------------------------------ FAP
    linhas_fap = list(fap.values())
    com_fap = [x for x in linhas_fap if x["c"]]
    fap_dados = {
        "linhas": sorted(com_fap, key=lambda x: -(x["c"].fap or 0)),
        "com_fap": len(com_fap), "sem_fap": len(linhas_fap) - len(com_fap),
        "potencial": sum((x["potencial"] for x in linhas_fap), ZERO),
        "acrescimo": sum((x["acrescimo"] for x in linhas_fap), ZERO),
        "custo_rat": sum((x["c"].custo_anual or ZERO for x in com_fap), ZERO),
        "bloqueados": sum(1 for x in com_fap if x["vigente"].bloqueio),
        "nao_contratado": sum(1 for x in linhas_fap if not x["contratado"]),
        "por_nivel": [{"codigo": c, "rotulo": r, "cor": cor,
                       "total": sum(1 for x in com_fap if x["c"].nivel and x["c"].nivel["codigo"] == c)}
                      for _, c, r, cor in NIVEIS],
        "oportunidades": [x for x in sorted(linhas_fap, key=lambda x: -x["prioridade"]) if x["potencial"]][:5],
    }

    # ------------------------------------------------------------ comercial
    vendas = list(Venda.objects.select_related("empresa").filter(data__gte=periodo.de, data__lte=periodo.ate))
    ativas = [v for v in vendas if v.status != StatusVenda.CANCELADA]
    def soma(lista):
        return sum((v.total for v in lista), ZERO)
    por_mes = []
    for ano, mes in meses_do_periodo(periodo):
        do_mes = [v for v in ativas if v.data.year == ano and v.data.month == mes]
        por_mes.append({"rotulo": f"{MESES[mes - 1]}/{str(ano)[2:]}", "total": soma(do_mes),
                        "recebido": soma([v for v in do_mes if v.status == StatusVenda.RECEBIDA]), "qtd": len(do_mes)})
    por_servico = sorted(
        [{"rotulo": r, "total": soma([v for v in ativas if v.servico == c]), "qtd": sum(1 for v in ativas if v.servico == c)}
         for c, r in SERVICOS_VENDA], key=lambda x: -x["total"])
    por_servico = [x for x in por_servico if x["qtd"]]
    por_cliente = {}
    for v in ativas:
        por_cliente.setdefault(v.empresa_id, {"rotulo": str(v.empresa), "total": ZERO, "qtd": 0})
        por_cliente[v.empresa_id]["total"] += v.total
        por_cliente[v.empresa_id]["qtd"] += 1
    leads = list(Lead.objects.all())
    abertos = [l for l in leads if l.estagio not in (Estagio.GANHO, Estagio.PERDIDO)]
    fechados_periodo = [l for l in leads if l.estagio in (Estagio.GANHO, Estagio.PERDIDO)
                        and periodo.de <= timezone.localtime(l.atualizado_em).date() <= periodo.ate]
    ganhos = sum(1 for l in fechados_periodo if l.estagio == Estagio.GANHO)
    diags = list(Diagnostico.objects.filter(criado_em__date__gte=periodo.de, criado_em__date__lte=periodo.ate))
    comercial = {
        "vendas": {
            "total": soma(ativas), "quantidade": len(ativas), "canceladas": len(vendas) - len(ativas),
            "recebido": soma([v for v in ativas if v.status == StatusVenda.RECEBIDA]),
            "a_receber": soma([v for v in ativas if v.status in (StatusVenda.FECHADA, StatusVenda.FATURADA)]),
            "recorrente": soma([v for v in ativas if v.cobranca == Cobranca.MENSAL]),
            "ticket_medio": (soma(ativas) / len(ativas)).quantize(Decimal("0.01")) if ativas else ZERO,
            "por_mes": por_mes, "por_servico": por_servico,
            "por_cliente": sorted(por_cliente.values(), key=lambda x: -x["total"])[:6],
        },
        "funil": {
            "abertos": len(abertos),
            "pipeline": sum((l.valor_estimado or ZERO for l in abertos), ZERO),
            "por_estagio": [{"rotulo": r, "total": sum(1 for l in abertos if l.estagio == c),
                             "valor": sum((l.valor_estimado or ZERO for l in abertos if l.estagio == c), ZERO)}
                            for c, r in Estagio.funil()],
            "ganhos": ganhos, "perdidos": len(fechados_periodo) - ganhos,
            "conversao": pct(ganhos, len(fechados_periodo)),
        },
        "diagnosticos": {
            "total": len(diags),
            "por_urgencia": [{"codigo": c, "rotulo": r, "total": sum(1 for d in diags if d.urgencia == c)} for c, r in Urgencia.choices],
            "viraram_lead": sum(1 for d in diags if d.lead_id),
            "whatsapp": sum(1 for d in diags if d.whatsapp_em),
            "pct_lead": pct(sum(1 for d in diags if d.lead_id), len(diags)),
            "exposicao_media": (sum((Decimal(str(d.exposicao["maximo"] or 0)) for d in diags), ZERO) / len(diags)).quantize(Decimal("0.01")) if diags else ZERO,
        },
        "visitas": Reuniao.objects.filter(gestao_id__in=ids, status=StatusReuniao.REALIZADA,
                                          quando__date__gte=periodo.de, quando__date__lte=periodo.ate).count(),
    }

    # ------------------------------------------------------------ destaques (frases para o resumo)
    destaques = []
    if conformidade["prazos"]["atrasados"]:
        destaques.append(("alerta", f"{conformidade['prazos']['atrasados']} prazo(s) normativo(s) atrasado(s) na carteira."))
    if situacoes_doc["vencido"]:
        destaques.append(("alerta", f"{situacoes_doc['vencido']} documento(s) técnico(s) vencido(s)."))
    if conformidade["acoes"]["atrasadas"]:
        destaques.append(("alerta", f"{conformidade['acoes']['atrasadas']} ação(ões) do plano com prazo vencido."))
    if fap_dados["potencial"]:
        destaques.append(("oportunidade", f"Economia possível de {moeda(fap_dados['potencial'])}/ano no FAP dos clientes."))
    if fap_dados["nao_contratado"]:
        destaques.append(("oportunidade", f"{fap_dados['nao_contratado']} cliente(s) sem o serviço de redução do FAP."))
    if comercial["vendas"]["total"]:
        destaques.append(("resultado", f"{moeda(comercial['vendas']['total'])} vendidos no período, {moeda(comercial['vendas']['recebido'])} já recebidos."))
    if conformidade["treinamentos"]["pessoas_periodo"]:
        destaques.append(("resultado", f"{conformidade['treinamentos']['pessoas_periodo']} pessoa(s) treinada(s) no período."))

    return {
        "periodo": periodo, "gerado_em": timezone.localtime(), "carteira": carteira, "conformidade": conformidade,
        "clientes": clientes, "fap": fap_dados, "comercial": comercial, "destaques": destaques,
    }


def moeda(valor) -> str:
    texto = f"{float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def moeda_curta(valor) -> str:
    v = float(valor or 0)
    if abs(v) >= 1_000_000:
        return "R$ " + f"{v / 1_000_000:.1f}".replace(".", ",") + " mi"
    if abs(v) >= 1_000:
        return "R$ " + f"{v / 1_000:.0f}" + " mil"
    return moeda(v)
