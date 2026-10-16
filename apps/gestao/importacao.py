"""Leitura de planilhas com o plano de acao do PGR.

Aceita .xlsx e .csv, com cabecalhos em portugues (com ou sem acento) e datas
no formato brasileiro. Nada e gravado aqui: o resultado e conferido na tela
antes de virar registro.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .models import Prioridade, StatusAcao, TipoRisco

# Nome do campo no sistema -> apelidos aceitos no cabecalho da planilha
COLUNAS = {
    "descricao": ["acao", "acoes", "medida", "medida de controle", "o que", "descricao", "acao corretiva"],
    "risco": ["risco", "tipo de risco", "agente", "categoria", "grupo de risco"],
    "setor": ["setor", "ghe", "setor ghe", "setor / ghe", "local", "area", "funcao"],
    "prioridade": ["prioridade", "nivel", "nivel de risco", "classificacao"],
    "prazo": ["prazo", "quando", "data limite", "data", "vencimento"],
    "responsavel_empresa": ["responsavel", "quem", "responsavel na empresa", "executor"],
    "status": ["status", "situacao", "andamento"],
    "custo_estimado": ["custo", "custo estimado", "investimento", "valor"],
    "observacoes": ["observacoes", "obs", "observacao", "notas", "como"],
}

RISCOS = {
    "fisico": TipoRisco.FISICO, "ruido": TipoRisco.FISICO, "calor": TipoRisco.FISICO,
    "vibracao": TipoRisco.FISICO, "radiacao": TipoRisco.FISICO,
    "quimico": TipoRisco.QUIMICO, "poeira": TipoRisco.QUIMICO, "fumos": TipoRisco.QUIMICO,
    "biologico": TipoRisco.BIOLOGICO,
    "ergonomico": TipoRisco.ERGONOMICO, "ergonomia": TipoRisco.ERGONOMICO,
    "acidente": TipoRisco.ACIDENTE, "mecanico": TipoRisco.ACIDENTE, "acidentes": TipoRisco.ACIDENTE,
    "psicossocial": TipoRisco.PSICOSSOCIAL, "psicossociais": TipoRisco.PSICOSSOCIAL,
    "gestao": TipoRisco.GESTAO, "documental": TipoRisco.GESTAO, "administrativo": TipoRisco.GESTAO,
}

PRIORIDADES = {
    "alta": Prioridade.ALTA, "alto": Prioridade.ALTA, "critica": Prioridade.ALTA,
    "critico": Prioridade.ALTA, "1": Prioridade.ALTA, "intoleravel": Prioridade.ALTA,
    "media": Prioridade.MEDIA, "medio": Prioridade.MEDIA, "moderado": Prioridade.MEDIA,
    "moderada": Prioridade.MEDIA, "2": Prioridade.MEDIA,
    "baixa": Prioridade.BAIXA, "baixo": Prioridade.BAIXA, "trivial": Prioridade.BAIXA,
    "toleravel": Prioridade.BAIXA, "3": Prioridade.BAIXA,
}

STATUS = {
    "nao iniciada": StatusAcao.NAO_INICIADA, "nao iniciado": StatusAcao.NAO_INICIADA,
    "pendente": StatusAcao.NAO_INICIADA, "aberta": StatusAcao.NAO_INICIADA, "aberto": StatusAcao.NAO_INICIADA,
    "em andamento": StatusAcao.EM_ANDAMENTO, "andamento": StatusAcao.EM_ANDAMENTO,
    "iniciada": StatusAcao.EM_ANDAMENTO,
    "aguardando": StatusAcao.AGUARDANDO,
    "concluida": StatusAcao.CONCLUIDA, "concluido": StatusAcao.CONCLUIDA, "feito": StatusAcao.CONCLUIDA,
    "finalizada": StatusAcao.CONCLUIDA,
    "verificada": StatusAcao.VERIFICADA, "eficacia verificada": StatusAcao.VERIFICADA,
}


def normalizar(texto) -> str:
    """'Setor / GHE ' -> 'setor ghe'."""
    if texto is None:
        return ""
    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return texto.strip()


# Apelidos tambem normalizados, para "setor / ghe" casar com "setor ghe".
COLUNAS = {campo: [normalizar(a) for a in apelidos] for campo, apelidos in COLUNAS.items()}


def converter_valor(bruto) -> Decimal | None:
    """Aceita 1234.56, '1.234,56', 'R$ 1.234,56', '1234,56' e '1,234.56'."""
    if bruto is None or str(bruto).strip() == "":
        return None
    if isinstance(bruto, (int, float, Decimal)):
        return Decimal(str(bruto)).quantize(Decimal("0.01"))
    texto = re.sub(r"[^\d,.\-]", "", str(bruto).strip())
    if not re.search(r"\d", texto):
        raise ValueError(f"valor invalido: {bruto!r}")
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return Decimal(texto).quantize(Decimal("0.01"))
    except InvalidOperation as erro:
        raise ValueError(f"valor invalido: {bruto!r}") from erro


def converter_data(bruto) -> date | None:
    """Aceita data do Excel, '31/12/2026', '31/12/26' e '2026-12-31'."""
    if bruto is None or str(bruto).strip() == "":
        return None
    if isinstance(bruto, datetime):
        return bruto.date()
    if isinstance(bruto, date):
        return bruto
    texto = str(bruto).strip()
    for formato in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise ValueError(f"data invalida: {bruto!r} (use dd/mm/aaaa)")


def _buscar(mapa: dict, bruto, padrao, nome: str):
    chave = normalizar(bruto)
    if not chave:
        return padrao
    if chave in mapa:
        return mapa[chave]
    for apelido, valor in mapa.items():
        if chave.startswith(apelido):
            return valor
    raise ValueError(f"{nome} nao reconhecido(a): {bruto!r}")


def converter_risco(bruto) -> str:
    return _buscar(RISCOS, bruto, TipoRisco.ACIDENTE, "risco")


def converter_prioridade(bruto) -> str:
    return _buscar(PRIORIDADES, bruto, Prioridade.MEDIA, "prioridade")


def converter_status(bruto) -> str:
    return _buscar(STATUS, bruto, StatusAcao.NAO_INICIADA, "status")


@dataclass
class LinhaAcao:
    linha: int
    descricao: str = ""
    risco: str = TipoRisco.ACIDENTE
    setor: str = ""
    prioridade: str = Prioridade.MEDIA
    prazo: date | None = None
    responsavel_empresa: str = ""
    status: str = StatusAcao.NAO_INICIADA
    custo_estimado: Decimal | None = None
    observacoes: str = ""
    erros: list[str] = field(default_factory=list)

    @property
    def valida(self) -> bool:
        return not self.erros

    @property
    def risco_rotulo(self) -> str:
        return dict(TipoRisco.choices).get(self.risco, self.risco)

    @property
    def prioridade_rotulo(self) -> str:
        return dict(Prioridade.choices).get(self.prioridade, self.prioridade)

    @property
    def status_rotulo(self) -> str:
        return dict(StatusAcao.choices).get(self.status, self.status)


@dataclass
class ResultadoLeitura:
    linhas: list[LinhaAcao] = field(default_factory=list)
    colunas_encontradas: dict[str, int] = field(default_factory=dict)
    colunas_ignoradas: list[str] = field(default_factory=list)

    @property
    def validas(self) -> list[LinhaAcao]:
        return [linha for linha in self.linhas if linha.valida]

    @property
    def invalidas(self) -> list[LinhaAcao]:
        return [linha for linha in self.linhas if not linha.valida]

    @property
    def alta_prioridade(self) -> int:
        return sum(1 for linha in self.validas if linha.prioridade == Prioridade.ALTA)


class PlanilhaInvalida(Exception):
    """A planilha nao pode ser lida (formato ou cabecalho)."""


def _linhas_do_arquivo(arquivo, nome_arquivo: str) -> list[list]:
    nome = (nome_arquivo or "").lower()
    conteudo = arquivo.read()
    if isinstance(conteudo, str):
        conteudo = conteudo.encode("utf-8")

    if nome.endswith(".csv") or nome.endswith(".txt"):
        for codificacao in ("utf-8-sig", "latin-1"):
            try:
                texto = conteudo.decode(codificacao)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise PlanilhaInvalida("Nao foi possivel ler o arquivo de texto.")
        amostra = texto[:2048]
        try:
            dialeto = csv.Sniffer().sniff(amostra, delimiters=";,\t")
        except csv.Error:
            dialeto = csv.excel
            dialeto.delimiter = ";" if amostra.count(";") > amostra.count(",") else ","
        return [linha for linha in csv.reader(io.StringIO(texto), dialeto)]

    if nome.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        try:
            planilha = load_workbook(io.BytesIO(conteudo), data_only=True, read_only=True)
        except Exception as erro:
            raise PlanilhaInvalida(f"Nao foi possivel abrir a planilha: {erro}") from erro
        aba = planilha[planilha.sheetnames[0]]
        return [list(linha) for linha in aba.iter_rows(values_only=True)]

    raise PlanilhaInvalida("Formato nao suportado. Envie um arquivo .xlsx ou .csv.")


def _mapear_cabecalho(cabecalho: list) -> tuple[dict[str, int], list[str]]:
    encontradas: dict[str, int] = {}
    ignoradas: list[str] = []
    for indice, celula in enumerate(cabecalho):
        chave = normalizar(celula)
        if not chave:
            continue
        for campo, apelidos in COLUNAS.items():
            if chave in apelidos and campo not in encontradas:
                encontradas[campo] = indice
                break
        else:
            ignoradas.append(str(celula).strip())
    return encontradas, ignoradas


def ler_planilha(arquivo, nome_arquivo: str = "") -> ResultadoLeitura:
    """Le o arquivo e devolve as linhas ja validadas, sem gravar nada."""
    linhas_brutas = _linhas_do_arquivo(arquivo, nome_arquivo or getattr(arquivo, "name", ""))
    linhas_brutas = [linha for linha in linhas_brutas if any(
        celula is not None and str(celula).strip() != "" for celula in linha
    )]
    if not linhas_brutas:
        raise PlanilhaInvalida("A planilha esta vazia.")

    colunas, ignoradas = _mapear_cabecalho(linhas_brutas[0])
    if "descricao" not in colunas:
        raise PlanilhaInvalida(
            "A primeira linha deve ser o cabecalho, com pelo menos a coluna Ação. "
            "Baixe a planilha modelo para conferir o formato."
        )

    resultado = ResultadoLeitura(colunas_encontradas=colunas, colunas_ignoradas=ignoradas)

    def celula(linha, campo):
        indice = colunas.get(campo)
        if indice is None or indice >= len(linha):
            return None
        return linha[indice]

    for numero, bruta in enumerate(linhas_brutas[1:], start=2):
        item = LinhaAcao(linha=numero)
        item.descricao = str(celula(bruta, "descricao") or "").strip()[:250]
        if not item.descricao:
            item.erros.append("linha sem ação")
        item.setor = str(celula(bruta, "setor") or "").strip()[:120]
        item.responsavel_empresa = str(celula(bruta, "responsavel_empresa") or "").strip()[:150]
        item.observacoes = str(celula(bruta, "observacoes") or "").strip()

        for campo, conversor in (
            ("risco", converter_risco),
            ("prioridade", converter_prioridade),
            ("status", converter_status),
            ("prazo", converter_data),
            ("custo_estimado", converter_valor),
        ):
            try:
                valor = conversor(celula(bruta, campo))
                if valor is not None:
                    setattr(item, campo, valor)
            except ValueError as erro:
                item.erros.append(str(erro))
        resultado.linhas.append(item)

    if not resultado.linhas:
        raise PlanilhaInvalida("A planilha tem cabecalho, mas nenhuma linha de ação.")
    return resultado


# ---------------------------------------------------------------------------
# Gravacao


def _chave_duplicidade(descricao: str, setor: str) -> str:
    return f"{normalizar(descricao)}|{normalizar(setor)}"


def aplicar_importacao(importacao, resultado: ResultadoLeitura, politica: str = "atualizar") -> dict:
    """Grava as linhas validas no plano de acao da gestao.

    politica define o que fazer com acao ja cadastrada (mesma descricao no
    mesmo setor): 'atualizar', 'ignorar' ou 'duplicar'.
    """
    from django.db import transaction

    from .models import AcaoPlano, StatusImportacao

    gestao = importacao.gestao
    existentes = {}
    for acao in gestao.acoes.all():
        existentes.setdefault(_chave_duplicidade(acao.descricao, acao.setor), acao)

    criar: list = []
    atualizar: list = []
    ignorados = 0
    campos = ["risco", "prioridade", "prazo", "responsavel_empresa", "status", "custo_estimado", "observacoes"]

    for linha in resultado.validas:
        chave = _chave_duplicidade(linha.descricao, linha.setor)
        atual = existentes.get(chave)
        if atual and politica == "ignorar":
            ignorados += 1
            continue
        if atual and politica == "atualizar":
            for campo in campos:
                valor = getattr(linha, campo)
                if valor not in (None, ""):
                    setattr(atual, campo, valor)
            atualizar.append(atual)
            continue
        nova = AcaoPlano(
            gestao=gestao,
            descricao=linha.descricao,
            setor=linha.setor,
            **{campo: getattr(linha, campo) for campo in campos},
        )
        criar.append(nova)
        existentes.setdefault(chave, nova)

    with transaction.atomic():
        if criar:
            AcaoPlano.objects.bulk_create(criar)
        if atualizar:
            AcaoPlano.objects.bulk_update(atualizar, [*campos, "atualizado_em"])
        importacao.status = StatusImportacao.CONCLUIDA
        importacao.linhas_lidas = len(resultado.linhas)
        importacao.linhas_validas = len(resultado.validas)
        importacao.criados = len(criar)
        importacao.atualizados = len(atualizar)
        importacao.ignorados = ignorados + len(resultado.invalidas)
        importacao.mensagem = (
            f"{len(criar)} ação(ões) criada(s), {len(atualizar)} atualizada(s), "
            f"{ignorados} já cadastrada(s) ignorada(s), "
            f"{len(resultado.invalidas)} linha(s) com erro descartada(s)."
        )
        importacao.save()

    return {
        "criados": len(criar),
        "atualizados": len(atualizar),
        "ignorados": ignorados,
        "com_erro": len(resultado.invalidas),
    }


def planilha_modelo() -> bytes:
    """Gera o XLSX modelo do plano de acao, com exemplos por tipo de risco."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    cabecalho = [
        "Ação", "Risco", "Setor / GHE", "Prioridade", "Prazo",
        "Responsável", "Status", "Custo estimado", "Observações",
    ]
    exemplos = [
        ["Enclausurar compressor da linha 2", "Físico", "Produção", "Alta", "30/11/2026",
         "Manutenção", "Em andamento", "18.500,00", "Ruído acima do nível de ação"],
        ["Instalar exaustão localizada na solda", "Químico", "Solda", "Alta", "15/12/2026",
         "Engenharia", "Não iniciada", "42.000,00", "Fumos metálicos"],
        ["Ajustar altura das bancadas de montagem", "Ergonômico", "Montagem", "Média", "31/01/2027",
         "Facilities", "Não iniciada", "", "Conforme AEP"],
        ["Aplicar pesquisa de fatores psicossociais", "Psicossocial", "Todos", "Média", "28/02/2027",
         "RH", "Não iniciada", "", "Integra o inventário de riscos (NR-01)"],
        ["Atualizar procedimento de bloqueio e etiquetagem", "Acidente", "Manutenção", "Alta", "20/11/2026",
         "Manutenção", "Concluída", "", ""],
    ]

    livro = Workbook()
    aba = livro.active
    aba.title = "Plano de ação"
    aba.append(cabecalho)
    for linha in exemplos:
        aba.append(linha)

    fundo = PatternFill("solid", fgColor="0C1719")
    for indice, _ in enumerate(cabecalho, start=1):
        celula = aba.cell(row=1, column=indice)
        celula.font = Font(bold=True, color="F4F7F7")
        celula.fill = fundo
        celula.alignment = Alignment(vertical="center")
        aba.column_dimensions[get_column_letter(indice)].width = 24
    aba.column_dimensions["A"].width = 46
    aba.freeze_panes = "A2"

    ajuda = livro.create_sheet("Instrucoes")
    for linha in [
        ["Como preencher"],
        [""],
        ["Ação", "obrigatório - a medida de controle"],
        ["Risco", "opcional - físico, químico, biológico, ergonômico, acidente, psicossocial ou gestão. Vazio = acidente"],
        ["Setor / GHE", "opcional - usado com a ação para identificar item já cadastrado"],
        ["Prioridade", "opcional - alta, média ou baixa. Vazio = média"],
        ["Prazo", "opcional - dd/mm/aaaa"],
        ["Responsável", "opcional - quem executa na empresa"],
        ["Status", "opcional - não iniciada, em andamento, aguardando, concluída, verificada"],
        ["Custo estimado", "opcional - aceita 1.234,56 ou 1234.56"],
        ["Observações", "opcional - texto livre"],
        [""],
        ["A ordem das colunas não importa; o sistema lê pelo cabeçalho."],
        ["Colunas a mais são ignoradas."],
    ]:
        ajuda.append(linha)
    ajuda.column_dimensions["A"].width = 20
    ajuda.column_dimensions["B"].width = 100
    ajuda["A1"].font = Font(bold=True, size=13)

    fluxo = io.BytesIO()
    livro.save(fluxo)
    return fluxo.getvalue()
