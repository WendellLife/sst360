"""Regras de negocio da gestao de SST.

Periodicidades de revisao e reciclagem, prazos gerados a partir delas e os
prazos do eSocial que nascem de um registro. Os prazos gerados nunca
sobrescrevem um prazo editado a mao: o controle manual sempre prevalece.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Count, Q

from .models import (
    AcaoPlano,
    Documento,
    Gestao,
    Prazo,
    Servico,
    StatusAcao,
    StatusDocumento,
    StatusPrazo,
    StatusTreinamento,
    TipoDocumento,
    TipoPrazo,
    TipoRisco,
    TipoTreinamento,
    Treinamento,
)


def somar_meses(inicio: date, meses: int) -> date:
    """Mesma data N meses depois; no fim de mes, cai no ultimo dia valido."""
    mes = inicio.month - 1 + meses
    ano = inicio.year + mes // 12
    mes = mes % 12 + 1
    dia = min(inicio.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def proximo_dia_util(dia: date) -> date:
    """Dia util seguinte, sem considerar feriados (conferir o calendario local)."""
    seguinte = dia + timedelta(days=1)
    while seguinte.weekday() >= 5:
        seguinte += timedelta(days=1)
    return seguinte


@dataclass(frozen=True)
class Periodicidade:
    meses: int
    base: str
    nota: str
    tipo_prazo: str = TipoPrazo.NORMATIVO


# Revisao de documentos tecnicos. Onde a norma nao fixa prazo, a periodicidade
# e de controle interno e esta marcada assim.
PERIODICIDADE_DOCUMENTO: dict[str, Periodicidade] = {
    TipoDocumento.PGR: Periodicidade(
        24, "NR-01, item 1.5.4.4.6",
        "Revisão da avaliação de riscos a cada 2 anos, ou 3 anos com certificação em SGSST, "
        "e sempre que houver mudança de processo, acidente ou resultado de monitoramento.",
    ),
    TipoDocumento.PSICOSSOCIAL: Periodicidade(
        24, "NR-01, GRO",
        "Faz parte do inventário de riscos do PGR e acompanha a revisão dele.",
    ),
    TipoDocumento.PCMSO: Periodicidade(
        12, "NR-07",
        "Relatório analítico anual do PCMSO e atualização do programa.",
    ),
    TipoDocumento.RELATORIO_PCMSO: Periodicidade(
        12, "NR-07", "Relatório analítico anual do PCMSO.",
    ),
    TipoDocumento.AEP: Periodicidade(
        24, "NR-17", "Acompanha a revisão do PGR.",
    ),
    TipoDocumento.AET: Periodicidade(
        24, "", "Controle interno: revisar com o PGR ou quando mudar o posto de trabalho.",
        TipoPrazo.INTERNO,
    ),
    TipoDocumento.LTCAT: Periodicidade(
        12, "", "Controle interno: revisão anual e sempre que mudar o ambiente de trabalho.",
        TipoPrazo.INTERNO,
    ),
    TipoDocumento.LI: Periodicidade(
        12, "", "Controle interno: revisar quando mudar processo, agente ou função.",
        TipoPrazo.INTERNO,
    ),
    TipoDocumento.LP: Periodicidade(
        12, "", "Controle interno: revisar quando mudar processo, agente ou função.",
        TipoPrazo.INTERNO,
    ),
    TipoDocumento.PCA: Periodicidade(
        12, "", "Controle interno: revisão anual com os resultados das audiometrias.",
        TipoPrazo.INTERNO,
    ),
    TipoDocumento.PPR: Periodicidade(
        12, "", "Controle interno: revisão anual do programa.",
        TipoPrazo.INTERNO,
    ),
}

# Reciclagem de treinamentos. Estaduais (brigada) dependem da instrucao tecnica
# do Corpo de Bombeiros do estado: conferir.
PERIODICIDADE_TREINAMENTO: dict[str, Periodicidade] = {
    TipoTreinamento.NR35: Periodicidade(24, "NR-35", "Treinamento periódico bienal."),
    TipoTreinamento.NR10: Periodicidade(24, "NR-10", "Reciclagem bienal."),
    TipoTreinamento.NR33: Periodicidade(12, "NR-33", "Capacitação periódica anual."),
    TipoTreinamento.CIPA: Periodicidade(
        12, "NR-05", "Mandato de 1 ano: novo treinamento a cada gestão da CIPA.",
    ),
    TipoTreinamento.BRIGADA: Periodicidade(
        12, "Instrução técnica do CB estadual",
        "Reciclagem anual na maioria dos estados. Conferir a instrução técnica local.",
    ),
    TipoTreinamento.ABANDONO: Periodicidade(
        12, "", "Controle interno: simulado anual.", TipoPrazo.INTERNO,
    ),
    TipoTreinamento.PRIMEIROS_SOCORROS: Periodicidade(
        12, "", "Controle interno: reciclagem anual.", TipoPrazo.INTERNO,
    ),
    TipoTreinamento.NR11: Periodicidade(
        12, "", "Controle interno: reciclagem anual dos operadores.", TipoPrazo.INTERNO,
    ),
    TipoTreinamento.NR12: Periodicidade(
        24, "", "Controle interno: reciclar também quando mudar máquina ou método.", TipoPrazo.INTERNO,
    ),
}


def calcular_validade_documento(documento: Documento, gestao: Gestao | None = None) -> date | None:
    regra = PERIODICIDADE_DOCUMENTO.get(documento.tipo)
    if not regra or not documento.emitido_em:
        return None
    meses = regra.meses
    gestao = gestao or documento.gestao
    if documento.tipo in (TipoDocumento.PGR, TipoDocumento.PSICOSSOCIAL) and gestao.certificacao_sgsst:
        meses = 36
    return somar_meses(documento.emitido_em, meses)


def calcular_validade_treinamento(treinamento: Treinamento) -> date | None:
    regra = PERIODICIDADE_TREINAMENTO.get(treinamento.tipo)
    if not regra or not treinamento.realizado_em:
        return None
    return somar_meses(treinamento.realizado_em, regra.meses)


def _prazo_de_origem(gestao: Gestao, origem: str, defaults: dict) -> tuple[Prazo, bool]:
    """Um prazo por origem. Atualiza so enquanto ninguem mexeu nele."""
    prazo = gestao.prazos.filter(origem=origem).first()
    if prazo is None:
        return Prazo.objects.create(gestao=gestao, origem=origem, **defaults), True
    if prazo.status == StatusPrazo.PENDENTE and prazo.data_fim != defaults["data_fim"]:
        prazo.data_fim = defaults["data_fim"]
        prazo.data_inicio = defaults.get("data_inicio")
        prazo.save(update_fields=["data_fim", "data_inicio", "atualizado_em"])
    return prazo, False


def sincronizar_documento(documento: Documento, responsavel=None) -> Prazo | None:
    """Preenche a validade e mantem o prazo de revisao do documento."""
    if not documento.valido_ate:
        validade = calcular_validade_documento(documento)
        if validade:
            documento.valido_ate = validade
            documento.save(update_fields=["valido_ate", "atualizado_em"])
    origem = f"doc:{documento.pk}"
    if documento.status != StatusDocumento.VIGENTE or not documento.valido_ate:
        documento.gestao.prazos.filter(origem=origem, status=StatusPrazo.PENDENTE).delete()
        return None
    regra = PERIODICIDADE_DOCUMENTO.get(documento.tipo)
    prazo, _ = _prazo_de_origem(
        documento.gestao,
        origem,
        {
            "titulo": f"Revisar {documento.sigla}",
            "base_legal": regra.base if regra else "",
            "tipo": regra.tipo_prazo if regra else TipoPrazo.INTERNO,
            "data_inicio": documento.emitido_em,
            "data_fim": documento.valido_ate,
            "responsavel": responsavel or documento.gestao.responsavel,
            "observacoes": regra.nota if regra else "",
        },
    )
    return prazo


def sincronizar_treinamento(treinamento: Treinamento, responsavel=None) -> Prazo | None:
    """Preenche a validade e mantem o prazo de reciclagem do treinamento."""
    if not treinamento.valido_ate:
        validade = calcular_validade_treinamento(treinamento)
        if validade:
            treinamento.valido_ate = validade
            treinamento.save(update_fields=["valido_ate", "atualizado_em"])
    gestao = treinamento.gestao
    origem = f"trein:{treinamento.pk}"

    if treinamento.status == StatusTreinamento.PLANEJADO and treinamento.previsto_para:
        prazo, _ = _prazo_de_origem(
            gestao, origem,
            {
                "titulo": f"Realizar treinamento: {treinamento.get_tipo_display()}",
                "base_legal": "",
                "tipo": TipoPrazo.CONTRATUAL,
                "data_inicio": None,
                "data_fim": treinamento.previsto_para,
                "responsavel": responsavel or gestao.responsavel,
                "observacoes": "Turma planejada no cronograma de treinamentos.",
            },
        )
        return prazo

    if treinamento.status != StatusTreinamento.REALIZADO or not treinamento.valido_ate:
        gestao.prazos.filter(origem=origem, status=StatusPrazo.PENDENTE).delete()
        return None

    regra = PERIODICIDADE_TREINAMENTO.get(treinamento.tipo)
    # o prazo de "realizar" vira o de "reciclar": o anterior foi cumprido
    anterior = gestao.prazos.filter(origem=origem, status=StatusPrazo.PENDENTE).first()
    if anterior and anterior.titulo.startswith("Realizar"):
        anterior.status = StatusPrazo.CUMPRIDO
        anterior.concluido_em = treinamento.realizado_em
        anterior.origem = f"{origem}:feito"
        anterior.save(update_fields=["status", "concluido_em", "origem", "atualizado_em"])
    prazo, _ = _prazo_de_origem(
        gestao, origem,
        {
            "titulo": f"Reciclar {treinamento.get_tipo_display()}",
            "base_legal": regra.base if regra else "",
            "tipo": regra.tipo_prazo if regra else TipoPrazo.INTERNO,
            "data_inicio": treinamento.realizado_em,
            "data_fim": treinamento.valido_ate,
            "responsavel": responsavel or gestao.responsavel,
            "observacoes": regra.nota if regra else "",
        },
    )
    return prazo


@dataclass(frozen=True)
class MarcoContrato:
    chave: str
    titulo: str
    dias: int
    servico: str | None = None


# Compromissos que nascem com o contrato, contados do inicio.
MARCOS_CONTRATO: list[MarcoContrato] = [
    MarcoContrato("diagnostico", "Concluir o diagnóstico técnico inicial", 30),
    MarcoContrato("inventario", "Entregar inventário de riscos e plano de ação (PGR)", 60, Servico.DOCUMENTOS),
    MarcoContrato("psicossocial", "Entregar avaliação de riscos psicossociais (NR-01)", 90, Servico.PSICOSSOCIAL),
    MarcoContrato("esocial", "Conferir eventos S-2220 e S-2240 enviados ao eSocial", 45, Servico.ESOCIAL),
    MarcoContrato("fap", "Apresentar análise do FAP e do NTEP", 90, Servico.FAP),
]


def gerar_prazos_contrato(gestao: Gestao, responsavel=None) -> list[Prazo]:
    """Cria os compromissos do contrato que ainda nao existem."""
    criados = []
    servicos = set(gestao.servicos or [])
    for marco in MARCOS_CONTRATO:
        if marco.servico and marco.servico not in servicos:
            continue
        origem = f"contrato:{marco.chave}"
        if gestao.prazos.filter(origem__startswith=origem).exists():
            continue
        criados.append(
            Prazo.objects.create(
                gestao=gestao,
                origem=origem,
                titulo=marco.titulo,
                tipo=TipoPrazo.CONTRATUAL,
                data_inicio=gestao.inicio,
                data_fim=gestao.inicio + timedelta(days=marco.dias),
                responsavel=responsavel or gestao.responsavel,
                observacoes=f"{marco.dias} dias do início do contrato.",
            )
        )
    return criados


def gerar_prazo_cat(gestao: Gestao, data_ocorrencia: date, registro_id: int, responsavel=None) -> Prazo:
    """Acidente registrado: a CAT (S-2210) vai ao eSocial ate o 1o dia util seguinte."""
    prazo, _ = _prazo_de_origem(
        gestao,
        f"cat:{registro_id}",
        {
            "titulo": "Enviar CAT ao eSocial (S-2210)",
            "base_legal": "Lei 8.213/1991, art. 22 · eSocial S-2210",
            "tipo": TipoPrazo.ESOCIAL,
            "data_inicio": data_ocorrencia,
            "data_fim": proximo_dia_util(data_ocorrencia),
            "responsavel": responsavel or gestao.responsavel,
            "observacoes": "Até o primeiro dia útil seguinte ao acidente; em caso de óbito, "
                           "imediatamente. Feriados não entram no cálculo: conferir.",
        },
    )
    return prazo


def resumo_plano(gestao: Gestao) -> list[dict]:
    """Acoes do plano por tipo de risco: total, encerradas e atrasadas."""
    from django.utils import timezone

    hoje = timezone.localdate()
    encerrados = StatusAcao.encerrados()
    agregado = {
        linha["risco"]: linha
        for linha in gestao.acoes.values("risco").annotate(
            total=Count("id"),
            encerradas=Count("id", filter=Q(status__in=encerrados)),
            atrasadas=Count("id", filter=Q(prazo__lt=hoje) & ~Q(status__in=encerrados)),
        )
    }
    resultado = []
    for valor, rotulo in TipoRisco.choices:
        linha = agregado.get(valor)
        if not linha:
            continue
        total = linha["total"]
        resultado.append(
            {
                "risco": valor,
                "rotulo": rotulo,
                "total": total,
                "encerradas": linha["encerradas"],
                "atrasadas": linha["atrasadas"],
                "percentual": round(linha["encerradas"] / total * 100) if total else 0,
            }
        )
    return resultado


def indicadores_gestao(gestao: Gestao) -> dict:
    """Numeros de topo da gestao, usados no painel e no portal."""
    documentos = [d for d in gestao.documentos.all() if d.status != StatusDocumento.SUBSTITUIDO]
    treinamentos = [t for t in gestao.treinamentos.all() if t.status == StatusTreinamento.REALIZADO]
    acoes = list(gestao.acoes.all())
    encerradas = sum(1 for a in acoes if a.encerrada)
    return {
        "documentos_total": len(documentos),
        "documentos_vigentes": sum(1 for d in documentos if d.situacao == "vigente"),
        "documentos_a_vencer": sum(1 for d in documentos if d.situacao == "a_vencer"),
        "documentos_vencidos": sum(1 for d in documentos if d.situacao == "vencido"),
        "treinamentos_total": len(treinamentos),
        "treinamentos_em_dia": sum(1 for t in treinamentos if t.situacao == "em_dia"),
        "treinamentos_vencidos": sum(1 for t in treinamentos if t.situacao == "vencido"),
        "pessoas_treinadas": sum(t.participantes for t in treinamentos),
        "acoes_total": len(acoes),
        "acoes_encerradas": encerradas,
        "acoes_atrasadas": sum(1 for a in acoes if a.atrasada),
        "acoes_percentual": round(encerradas / len(acoes) * 100) if acoes else 0,
    }


def acoes_atrasadas():
    from django.utils import timezone

    return AcaoPlano.objects.filter(
        prazo__lt=timezone.localdate(), gestao__encerrado_em__isnull=True
    ).exclude(status__in=StatusAcao.encerrados())
