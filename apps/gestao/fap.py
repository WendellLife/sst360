"""Cálculo do FAP (Fator Acidentário de Prevenção).

Metodologia aprovada pelo CNPS (Res. 1.308/2009 e alterações, em especial a Res. 1.316/2010
e a Res. 1.329/2017):

    IC = (0,50 × percentil de gravidade + 0,35 × percentil de frequência + 0,15 × percentil de custo) × 0,02

O FAP é o próprio IC, limitado ao intervalo de 0,5000 a 2,0000. A interpolação da faixa de
bonificação deixou de ser aplicada na vigência 2011, e a redução de 25% da faixa de malus foi
extinta a partir da vigência 2019. Morte, invalidez permanente ou rotatividade média acima de
75% bloqueiam a bonificação (FAP = 1,0000).

RAT ajustado = alíquota do RAT (1%, 2% ou 3%) × FAP. A contribuição incide sobre a folha,
13º salário incluído.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

PESOS = (("gravidade", Decimal("0.50")), ("frequencia", Decimal("0.35")), ("custo", Decimal("0.15")))
MINIMO, MAXIMO, NEUTRO = Decimal("0.5"), Decimal("2.0"), Decimal("1")
QUATRO = Decimal("0.0001")
FOLHAS_POR_ANO = 13  # 12 meses + 13º salário

# (limite superior inclusivo, código, rótulo, cor)
NIVEIS = [
    (Decimal("0.7500"), "BMAX", "Bônus alto", "verde"),
    (Decimal("0.9999"), "BON", "Bônus", "verde"),
    (Decimal("1.0000"), "NEU", "Neutro", "cinza"),
    (Decimal("1.5000"), "MAL", "Malus", "amarelo"),
    (Decimal("2.0000"), "MMAX", "Malus alto", "vermelho"),
]
EXPLICACAO_NIVEL = {
    "BMAX": "Desconto de 25% a 50% no RAT. Manter é o objetivo: um único afastamento grave pode tirar a empresa desta faixa.",
    "BON": "Desconto no RAT, mas há espaço para chegar perto de 0,5000 reduzindo afastamentos e o tempo de benefício.",
    "NEU": "Sem desconto nem acréscimo. Pode ser efeito de bloqueio (morte, invalidez ou rotatividade).",
    "MAL": "Acréscimo de até 50% no RAT. A empresa paga mais que a média do CNAE por acidentes e afastamentos.",
    "MMAX": "Acréscimo de 50% a 100% no RAT. Prioridade máxima: gestão de afastamentos, nexo (NTEP) e contestação.",
}


def _dec(valor):
    return None if valor is None or valor == "" else Decimal(str(valor))


def nivel_do_fap(fap):
    if fap is None:
        return None
    for limite, codigo, rotulo, cor in NIVEIS:
        if fap <= limite:
            return {"codigo": codigo, "rotulo": rotulo, "cor": cor, "explicacao": EXPLICACAO_NIVEL[codigo]}
    return {"codigo": "MMAX", "rotulo": "Malus alto", "cor": "vermelho", "explicacao": EXPLICACAO_NIVEL["MMAX"]}


def indice_composto(gravidade, frequencia, custo):
    """Pontuação do FAP. Devolve None se faltar algum percentil."""
    valores = [_dec(gravidade), _dec(frequencia), _dec(custo)]
    if any(v is None for v in valores):
        return None
    soma = sum(v * peso for v, (_, peso) in zip(valores, PESOS))
    return (soma * Decimal("0.02")).quantize(QUATRO, ROUND_HALF_UP)


def fap_do_indice(ic, bloqueio=""):
    if ic is None:
        return None
    fap = min(max(ic, MINIMO), MAXIMO)
    if bloqueio and fap < NEUTRO:
        fap = NEUTRO
    return fap.quantize(QUATRO)


@dataclass
class CalculoFap:
    grau: int
    ic: Decimal | None
    fap_calculado: Decimal | None
    fap: Decimal | None
    origem: str
    nivel: dict | None
    rat_ajustado: Decimal | None  # em %
    custo_mensal: Decimal | None
    custo_anual: Decimal | None
    diferenca_neutro_anual: Decimal | None  # >0 economia frente ao FAP 1,0; <0 acréscimo
    contribuicoes: list = field(default_factory=list)  # pontos de cada percentil na pontuação
    pontos: Decimal | None = None  # pontuação de 0 a 100 (IC / 0,02)
    perda_bloqueio_anual: Decimal | None = None  # bônus que o bloqueio tirou da empresa
    fap_sem_bloqueio: Decimal | None = None  # FAP que a pontuação daria sem o bloqueio

    @property
    def desconto_percentual(self):
        if self.fap is None:
            return None
        return ((NEUTRO - self.fap) * 100).quantize(Decimal("0.1"))


def calcular(ficha=None, *, grau=None, gravidade=None, frequencia=None, custo=None, bloqueio="",
             fap_oficial=None, folha_mensal=None) -> CalculoFap:
    if ficha is not None:
        grau, gravidade, frequencia, custo = ficha.grau_rat, ficha.percentil_gravidade, ficha.percentil_frequencia, ficha.percentil_custo
        bloqueio, fap_oficial, folha_mensal = ficha.bloqueio, ficha.fap_oficial, ficha.folha_mensal
    ic = indice_composto(gravidade, frequencia, custo)
    fap_calc = fap_do_indice(ic, bloqueio)
    fap_oficial = _dec(fap_oficial)
    fap = fap_oficial if fap_oficial is not None else fap_calc
    origem = "oficial" if fap_oficial is not None else ("calculado" if fap_calc is not None else "")
    grau = int(grau or 0)
    rat = (Decimal(grau) * fap).quantize(QUATRO) if fap is not None and grau else None
    folha = _dec(folha_mensal)
    custo_mes = (folha * rat / 100).quantize(Decimal("0.01")) if folha and rat is not None else None
    custo_ano = custo_mes * FOLHAS_POR_ANO if custo_mes is not None else None
    dif = (folha * Decimal(grau) * (NEUTRO - fap) / 100 * FOLHAS_POR_ANO).quantize(Decimal("0.01")) if folha and fap is not None and grau else None
    contribs = []
    if ic is not None:
        for (nome, peso), valor in zip(PESOS, (gravidade, frequencia, custo)):
            contribs.append({"nome": nome, "peso": int(peso * 100), "percentil": _dec(valor),
                             "pontos": (_dec(valor) * peso).quantize(Decimal("0.01"))})
    perda = None
    if bloqueio and ic is not None and fap_oficial is None and folha and grau:
        sem_bloqueio = fap_do_indice(ic)
        if sem_bloqueio < NEUTRO:
            perda = (folha * Decimal(grau) * (NEUTRO - sem_bloqueio) / 100 * FOLHAS_POR_ANO).quantize(Decimal("0.01"))
    return CalculoFap(
        grau=grau, ic=ic, fap_calculado=fap_calc, fap=fap, origem=origem, nivel=nivel_do_fap(fap),
        rat_ajustado=rat, custo_mensal=custo_mes, custo_anual=custo_ano, diferenca_neutro_anual=dif,
        contribuicoes=contribs, perda_bloqueio_anual=perda, fap_sem_bloqueio=fap_do_indice(ic) if bloqueio else None, pontos=(ic / Decimal("0.02")).quantize(Decimal("0.01")) if ic is not None else None,
    )


def economia_meta(calculo: CalculoFap, meta, folha_mensal):
    """Economia anual ao levar o FAP atual até a meta."""
    meta, folha = _dec(meta), _dec(folha_mensal)
    if calculo.fap is None or meta is None or not folha or not calculo.grau or meta >= calculo.fap:
        return None
    return (folha * Decimal(calculo.grau) * (calculo.fap - meta) / 100 * FOLHAS_POR_ANO).quantize(Decimal("0.01"))


# ---------------------------------------------------------------- panorama para venda
SERVICO_FAP = "FAP"  # Servico.FAP, sem importar models aqui


def panorama(gestao, ano=None, fichas=None) -> dict:
    """FAP de uma gestão lido como argumento comercial.

    Devolve a ficha vigente com o cálculo, a tendência (próxima vigência ou anterior),
    o potencial de economia por ano e o argumento de venda em uma frase.
    """
    from django.utils import timezone

    ano = ano or timezone.localdate().year
    fichas = list(fichas if fichas is not None else gestao.fichas_fap.all())
    fichas.sort(key=lambda f: -f.vigencia)
    vigente = next((f for f in fichas if f.vigencia <= ano), None)
    futuras = [f for f in fichas if f.vigencia > ano]
    proxima = min(futuras, key=lambda f: f.vigencia) if futuras else None
    anterior = next((f for f in fichas if vigente and f.vigencia < vigente.vigencia), None)
    contratado = SERVICO_FAP in (gestao.servicos or [])
    base = {"gestao": gestao, "empresa": gestao.empresa, "vigente": vigente, "proxima": proxima,
            "contratado": contratado, "c": None, "potencial": Decimal("0"), "acrescimo": Decimal("0"),
            "economia_meta": None, "tendencia": None, "argumento": "", "prioridade": 0}
    if vigente is None:
        base["argumento"] = (
            "Sem FAP registrado. Pedir o extrato do FAPWeb: é a porta de entrada do serviço de redução do FAP."
            if not contratado else "Serviço contratado, mas o FAP ainda não foi lançado. Registrar o extrato do FAPWeb."
        )
        return base

    c = vigente.calculo
    eco_meta = economia_meta(c, gestao.fap_meta, vigente.folha_mensal)
    acrescimo = -c.diferenca_neutro_anual if c.diferenca_neutro_anual is not None and c.diferenca_neutro_anual < 0 else Decimal("0")
    potencial = max([v for v in (eco_meta, acrescimo, c.perda_bloqueio_anual) if v is not None] or [Decimal("0")])

    tendencia = None
    comparar = proxima or anterior
    if comparar is not None and comparar.calculo.fap is not None and c.fap is not None:
        novo, velho = (comparar.calculo.fap, c.fap) if proxima else (c.fap, comparar.calculo.fap)
        delta = (novo - velho).quantize(QUATRO)
        tendencia = {
            "de": comparar.vigencia if not proxima else vigente.vigencia,
            "para": comparar.vigencia if proxima else vigente.vigencia,
            "delta": delta, "sentido": "sobe" if delta > 0 else "cai" if delta < 0 else "estável",
            "cor": "vermelho" if delta > 0 else "verde" if delta < 0 else "cinza",
        }

    nivel = c.nivel["codigo"] if c.nivel else ""
    if vigente.bloqueio and c.perda_bloqueio_anual:
        arg = f"Bonificação bloqueada: contestar no FAPWeb pode devolver até {_moeda(c.perda_bloqueio_anual)}/ano."
    elif nivel in ("MAL", "MMAX"):
        arg = (f"Paga {_moeda(acrescimo)}/ano acima do FAP neutro. Gestão de afastamentos e revisão do nexo (NTEP) "
               f"atacam a gravidade, que pesa 50% da pontuação.") if acrescimo else \
              "FAP acima de 1: a empresa paga mais RAT que a média do CNAE. Informe a folha para quantificar."
    elif tendencia and tendencia["sentido"] == "sobe" and proxima:
        arg = f"O FAP {proxima.vigencia} sobe {_num(tendencia['delta'])}: agir agora evita o aumento do RAT."
    elif nivel in ("BON", "BMAX"):
        arg = "Em bônus: o trabalho é manter. Um afastamento grave tira a empresa da faixa."
        if eco_meta:
            arg += f" Até a meta ainda há {_moeda(eco_meta)}/ano."
    else:
        arg = f"FAP neutro. Até a meta: {_moeda(eco_meta)}/ano." if eco_meta else "FAP neutro: há espaço para bonificação reduzindo afastamentos."
    if not contratado and potencial:
        arg += " Redução do FAP não contratada."

    prioridade = potencial + (Decimal("1") if not contratado else Decimal("0"))
    base.update(c=c, potencial=potencial, acrescimo=acrescimo, economia_meta=eco_meta, tendencia=tendencia,
                argumento=arg, prioridade=prioridade)
    return base


def _moeda(v):
    texto = f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _num(v):
    sinal = "+" if v > 0 else ""
    return sinal + f"{float(v):.4f}".replace(".", ",")
