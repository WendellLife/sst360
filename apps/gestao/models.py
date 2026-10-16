"""Gestao de SST de uma empresa cliente.

Uma Gestao e o contrato de acompanhamento: etapa do metodo, documentos tecnicos
com validade, treinamentos, plano de acao, prazos e a linha do tempo do que foi
feito. O portal do cliente le daqui.
"""
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel


# --------------------------------------------------------------------- gestao


class EtapaMetodo(models.TextChoices):
    """As 12 etapas do metodo de implantacao."""

    DIAGNOSTICO = "01", "Diagnóstico técnico inicial"
    RISCOS = "02", "Mapeamento de riscos"
    DOCUMENTAL = "03", "Ajuste documental"
    PLANO = "04", "Plano de ação"
    GESTAO_ATIVA = "05", "Gestão ativa"
    TREINAMENTOS = "06", "Treinamentos"
    SAUDE = "07", "Gestão de exames e saúde"
    ESOCIAL = "08", "eSocial integrado"
    INDICADORES = "09", "Indicadores e relatórios"
    JURIDICO = "10", "Suporte jurídico e pericial"
    AUDITORIAS = "11", "Auditorias internas"
    CULTURA = "12", "Cultura de segurança implementada"

    @classmethod
    def numero(cls, valor: str) -> int:
        try:
            return int(valor)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def cor(cls, valor: str) -> str:
        numero = cls.numero(valor)
        if numero <= 4:
            return "amarelo"
        if numero <= 11:
            return "azul"
        return "verde"


class ModeloAcompanhamento(models.TextChoices):
    SEMANAL = "SEM", "Semanal"
    QUINZENAL = "QUI", "Quinzenal"
    MENSAL = "MEN", "Mensal"


class Servico(models.TextChoices):
    """Linhas de servico do portfolio."""

    DOCUMENTOS = "DOC", "Documentos e programas"
    GESTAO_ATIVA = "GES", "Gestão ativa personalizada"
    TREINAMENTOS = "TRE", "Treinamentos"
    SAUDE = "SAU", "Saúde ocupacional integrada"
    ESOCIAL = "ESO", "Gestão do eSocial"
    FAP = "FAP", "Redução do FAP"
    PERICIAL = "PER", "Assistência jurídica e pericial"
    PSICOSSOCIAL = "PSI", "Riscos psicossociais (NR-01)"


class Gestao(TimeStampedModel):
    """Contrato de gestao de SST de uma empresa."""

    empresa = models.ForeignKey(
        "empresas.Empresa", verbose_name="empresa", related_name="gestoes", on_delete=models.CASCADE
    )
    codigo = models.CharField("código", max_length=20, unique=True, blank=True)
    etapa = models.CharField(
        "etapa do método", max_length=2, choices=EtapaMetodo.choices, default=EtapaMetodo.DIAGNOSTICO
    )
    modelo = models.CharField(
        "modelo de acompanhamento", max_length=3, choices=ModeloAcompanhamento.choices,
        default=ModeloAcompanhamento.MENSAL,
    )
    servicos = models.JSONField("serviços contratados", default=list, blank=True)
    inicio = models.DateField("início do contrato", default=timezone.localdate)
    encerrado_em = models.DateField("encerrado em", null=True, blank=True)

    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="responsável interno",
        related_name="gestoes", on_delete=models.SET_NULL, null=True, blank=True,
    )
    responsavel_tecnico = models.CharField(
        "responsável técnico", max_length=150, blank=True,
        help_text="Engenheiro ou técnico de segurança que assina os documentos.",
    )
    medico_coordenador = models.CharField("médico coordenador do PCMSO", max_length=150, blank=True)

    certificacao_sgsst = models.BooleanField(
        "certificação em sistema de gestão de SST", default=False,
        help_text="NR-01, item 1.5.4.4.6.1: com certificação, a revisão do PGR passa de 2 para 3 anos.",
    )
    fap_atual = models.DecimalField(
        "FAP vigente", max_digits=5, decimal_places=4, null=True, blank=True,
        help_text="Fator Acidentário de Prevenção, de 0,5000 a 2,0000.",
    )
    fap_meta = models.DecimalField("FAP meta", max_digits=5, decimal_places=4, null=True, blank=True)
    valor_mensal = models.DecimalField(
        "valor mensal do contrato", max_digits=12, decimal_places=2, null=True, blank=True
    )
    observacoes = models.TextField("observações", blank=True)

    class Meta:
        verbose_name = "gestão de SST"
        verbose_name_plural = "gestões de SST"
        ordering = ["encerrado_em", "-inicio", "-id"]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.empresa}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            ano = (self.inicio or timezone.localdate()).year
            prefixo = f"SST-{ano}-"
            ultimos = (
                Gestao.objects.filter(codigo__startswith=prefixo)
                .values_list("codigo", flat=True)
            )
            maior = max((int(c.rsplit("-", 1)[-1]) for c in ultimos if c.rsplit("-", 1)[-1].isdigit()), default=0)
            self.codigo = f"{prefixo}{maior + 1:03d}"
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("gestao:detalhe", args=[self.pk])

    @property
    def ativa(self) -> bool:
        return self.encerrado_em is None

    @property
    def etapa_numero(self) -> int:
        return EtapaMetodo.numero(self.etapa)

    @property
    def cor_etapa(self) -> str:
        return EtapaMetodo.cor(self.etapa)

    @property
    def servicos_rotulos(self) -> list[str]:
        nomes = dict(Servico.choices)
        return [nomes[s] for s in self.servicos or [] if s in nomes]

    @property
    def meses_revisao_pgr(self) -> int:
        return 36 if self.certificacao_sgsst else 24

    @property
    def prazos_abertos(self):
        return self.prazos.filter(status=StatusPrazo.PENDENTE).order_by("data_fim")


# ------------------------------------------------------------------ registros


class TipoRegistro(models.TextChoices):
    VISITA = "VIS", "Visita técnica"
    INSPECAO = "INSP", "Inspeção / checklist"
    AUDITORIA = "AUD", "Auditoria interna"
    REUNIAO = "REU", "Reunião de segurança"
    DOCUMENTO = "DOC", "Entrega de documento"
    TREINAMENTO = "TRE", "Treinamento"
    OCORRENCIA = "OCO", "Acidente / incidente"
    ESOCIAL = "ESO", "Envio ao eSocial"
    PERICIA = "PER", "Perícia / assistência técnica"
    OUTRO = "OUT", "Outro"


class Registro(TimeStampedModel):
    """O que foi feito na gestao, em ordem cronologica."""

    gestao = models.ForeignKey(
        Gestao, verbose_name="gestão", related_name="registros", on_delete=models.CASCADE
    )
    data = models.DateField("data", default=timezone.localdate)
    tipo = models.CharField("tipo", max_length=4, choices=TipoRegistro.choices, default=TipoRegistro.VISITA)
    titulo = models.CharField("título", max_length=200)
    descricao = models.TextField("descrição", blank=True)
    visivel_cliente = models.BooleanField(
        "visível no portal do cliente", default=True,
        help_text="Desmarque para manter o registro restrito à equipe interna.",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="registrado por",
        related_name="registros", on_delete=models.SET_NULL, null=True, blank=True,
    )

    class Meta:
        verbose_name = "registro"
        verbose_name_plural = "registros"
        ordering = ["-data", "-id"]

    def __str__(self) -> str:
        return f"{self.data:%d/%m/%Y} - {self.titulo}"


# --------------------------------------------------------------------- prazos


class StatusPrazo(models.TextChoices):
    PENDENTE = "PEND", "Pendente"
    CUMPRIDO = "CUMP", "Cumprido"
    PRORROGADO = "PROR", "Prorrogado"
    PERDIDO = "PERD", "Perdido"


class TipoPrazo(models.TextChoices):
    NORMATIVO = "NORMA", "Exigência normativa"
    ESOCIAL = "ESOC", "Prazo do eSocial"
    CONTRATUAL = "CONTR", "Compromisso do contrato"
    INTERNO = "INT", "Controle interno"


class Prazo(TimeStampedModel):
    gestao = models.ForeignKey(
        Gestao, verbose_name="gestão", related_name="prazos", on_delete=models.CASCADE
    )
    titulo = models.CharField("título", max_length=200)
    base_legal = models.CharField(
        "base normativa", max_length=120, blank=True, help_text="Ex.: NR-01, item 1.5.4.4.6."
    )
    tipo = models.CharField("tipo", max_length=5, choices=TipoPrazo.choices, default=TipoPrazo.NORMATIVO)
    data_inicio = models.DateField("início", null=True, blank=True)
    data_fim = models.DateField("vencimento")
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="responsável",
        related_name="prazos", on_delete=models.SET_NULL, null=True, blank=True,
    )
    status = models.CharField("status", max_length=4, choices=StatusPrazo.choices, default=StatusPrazo.PENDENTE)
    concluido_em = models.DateField("concluído em", null=True, blank=True)
    origem = models.CharField(
        "origem automática", max_length=40, blank=True, editable=False,
        help_text="Preenchido quando o prazo nasce de um documento ou treinamento.",
    )
    observacoes = models.TextField("observações", blank=True)

    class Meta:
        verbose_name = "prazo"
        verbose_name_plural = "prazos"
        ordering = ["data_fim"]

    def __str__(self) -> str:
        return f"{self.titulo} ({self.data_fim:%d/%m/%Y})"

    @property
    def dias_restantes(self) -> int:
        return (self.data_fim - timezone.localdate()).days

    @property
    def dias_atraso(self) -> int:
        return max(0, -self.dias_restantes)

    @property
    def atrasado(self) -> bool:
        return self.status == StatusPrazo.PENDENTE and self.dias_restantes < 0

    @property
    def cor(self) -> str:
        if self.status == StatusPrazo.CUMPRIDO:
            return "verde"
        if self.status == StatusPrazo.PERDIDO or self.atrasado:
            return "vermelho"
        if self.dias_restantes <= settings.PRAZO_ALERTA_DIAS:
            return "amarelo"
        return "azul"


# ---------------------------------------------------- documentos tecnicos


class TipoDocumento(models.TextChoices):
    PGR = "PGR", "PGR — Programa de Gerenciamento de Riscos"
    PCMSO = "PCMSO", "PCMSO — Programa de Controle Médico de Saúde Ocupacional"
    RELATORIO_PCMSO = "RAPCM", "Relatório analítico do PCMSO"
    LTCAT = "LTCAT", "LTCAT — Laudo Técnico das Condições Ambientais do Trabalho"
    AEP = "AEP", "AEP — Análise Ergonômica Preliminar"
    AET = "AET", "AET — Análise Ergonômica do Trabalho"
    PSICOSSOCIAL = "PSI", "Avaliação de riscos psicossociais (NR-01)"
    LI = "LI", "LI — Laudo de Insalubridade"
    LP = "LP", "LP — Laudo de Periculosidade"
    PCA = "PCA", "PCA — Programa de Conservação Auditiva"
    PPR = "PPR", "PPR — Programa de Proteção Respiratória"
    POP = "POP", "POP / procedimento operacional"
    INSPECAO = "INSP", "Relatório de inspeção"
    PARECER = "PAR", "Parecer técnico"
    OUTRO = "OUT", "Outro"

    @classmethod
    def sigla(cls, valor: str) -> str:
        rotulo = dict(cls.choices).get(valor, valor)
        return rotulo.split(" — ")[0]


class StatusDocumento(models.TextChoices):
    ELABORACAO = "ELAB", "Em elaboração"
    VIGENTE = "VIG", "Emitido"
    SUBSTITUIDO = "SUBS", "Substituído"


def caminho_documento(instance, filename: str) -> str:
    return f"gestoes/{instance.gestao_id}/documentos/{filename}"


class Documento(TimeStampedModel):
    """Programa, laudo ou relatorio tecnico entregue ao cliente."""

    gestao = models.ForeignKey(
        Gestao, verbose_name="gestão", related_name="documentos", on_delete=models.CASCADE
    )
    tipo = models.CharField("tipo", max_length=5, choices=TipoDocumento.choices, default=TipoDocumento.PGR)
    titulo = models.CharField("título", max_length=200, blank=True)
    status = models.CharField(
        "status", max_length=4, choices=StatusDocumento.choices, default=StatusDocumento.VIGENTE
    )
    emitido_em = models.DateField("emitido em", null=True, blank=True)
    valido_ate = models.DateField(
        "revisar até", null=True, blank=True,
        help_text="Em branco, é calculado pela periodicidade do tipo de documento.",
    )
    responsavel_tecnico = models.CharField("responsável técnico", max_length=150, blank=True)
    arquivo = models.FileField("arquivo", upload_to=caminho_documento, blank=True)
    visivel_cliente = models.BooleanField("visível no portal do cliente", default=True)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="enviado por",
        related_name="documentos", on_delete=models.SET_NULL, null=True, blank=True,
    )

    class Meta:
        verbose_name = "documento técnico"
        verbose_name_plural = "documentos técnicos"
        ordering = ["tipo", "-emitido_em"]

    def __str__(self) -> str:
        return self.nome

    @property
    def nome(self) -> str:
        return self.titulo or self.get_tipo_display()

    @property
    def sigla(self) -> str:
        return TipoDocumento.sigla(self.tipo)

    @property
    def dias_para_vencer(self) -> int | None:
        if not self.valido_ate:
            return None
        return (self.valido_ate - timezone.localdate()).days

    @property
    def situacao(self) -> str:
        """Leitura do documento hoje: em elaboracao, vigente, a vencer ou vencido."""
        if self.status == StatusDocumento.ELABORACAO:
            return "elaboracao"
        if self.status == StatusDocumento.SUBSTITUIDO:
            return "substituido"
        dias = self.dias_para_vencer
        if dias is None:
            return "vigente"
        if dias < 0:
            return "vencido"
        if dias <= settings.VENCIMENTO_ALERTA_DIAS:
            return "a_vencer"
        return "vigente"

    @property
    def situacao_rotulo(self) -> str:
        dias = self.dias_para_vencer
        return {
            "elaboracao": "Em elaboração",
            "substituido": "Substituído",
            "vigente": "Vigente",
            "a_vencer": f"Revisar em {dias} dias" if dias is not None else "A vencer",
            "vencido": f"Vencido há {abs(dias)} dias" if dias is not None else "Vencido",
        }[self.situacao]

    @property
    def cor(self) -> str:
        return {
            "elaboracao": "azul",
            "substituido": "cinza",
            "vigente": "verde",
            "a_vencer": "amarelo",
            "vencido": "vermelho",
        }[self.situacao]


# ------------------------------------------------------------- treinamentos


class TipoTreinamento(models.TextChoices):
    CIPA = "CIPA", "CIPA (NR-05)"
    BRIGADA = "BRIG", "Brigada de incêndio"
    ABANDONO = "ABAN", "Plano de abandono / simulado"
    PRIMEIROS_SOCORROS = "PSOC", "Primeiros socorros"
    GHS = "GHS", "Identificação e rotulagem — GHS"
    INTEGRACAO = "INTG", "Integração de segurança"
    NR06 = "NR06", "NR-06 — Uso de EPI"
    NR10 = "NR10", "NR-10 — Segurança em eletricidade"
    NR11 = "NR11", "NR-11 — Operação de empilhadeira"
    NR12 = "NR12", "NR-12 — Máquinas e equipamentos"
    NR18 = "NR18", "NR-18 — Construção civil"
    NR33 = "NR33", "NR-33 — Espaço confinado"
    NR35 = "NR35", "NR-35 — Trabalho em altura"
    COMPORTAMENTAL = "COMP", "Comportamental e percepção de risco"
    OUTRO = "OUT", "Outro"


class Modalidade(models.TextChoices):
    PRESENCIAL = "PRES", "Presencial"
    ONLINE = "ONL", "On-line"
    IN_COMPANY = "INC", "In company"


class StatusTreinamento(models.TextChoices):
    PLANEJADO = "PLAN", "Planejado"
    REALIZADO = "REAL", "Realizado"
    CANCELADO = "CANC", "Cancelado"


class Treinamento(TimeStampedModel):
    gestao = models.ForeignKey(
        Gestao, verbose_name="gestão", related_name="treinamentos", on_delete=models.CASCADE
    )
    tipo = models.CharField("treinamento", max_length=4, choices=TipoTreinamento.choices)
    titulo = models.CharField("título complementar", max_length=200, blank=True)
    modalidade = models.CharField(
        "modalidade", max_length=4, choices=Modalidade.choices, default=Modalidade.IN_COMPANY
    )
    status = models.CharField(
        "status", max_length=4, choices=StatusTreinamento.choices, default=StatusTreinamento.REALIZADO
    )
    previsto_para = models.DateField("previsto para", null=True, blank=True)
    realizado_em = models.DateField("realizado em", null=True, blank=True)
    carga_horaria = models.PositiveSmallIntegerField("carga horária (h)", null=True, blank=True)
    participantes = models.PositiveIntegerField("participantes", default=0)
    valido_ate = models.DateField(
        "reciclagem até", null=True, blank=True,
        help_text="Em branco, é calculado pela periodicidade do treinamento.",
    )
    visivel_cliente = models.BooleanField("visível no portal do cliente", default=True)

    class Meta:
        verbose_name = "treinamento"
        verbose_name_plural = "treinamentos"
        ordering = ["-realizado_em", "previsto_para"]

    def __str__(self) -> str:
        return self.nome

    @property
    def nome(self) -> str:
        base = self.get_tipo_display()
        return f"{base} · {self.titulo}" if self.titulo else base

    @property
    def dias_para_vencer(self) -> int | None:
        if not self.valido_ate or self.status != StatusTreinamento.REALIZADO:
            return None
        return (self.valido_ate - timezone.localdate()).days

    @property
    def situacao(self) -> str:
        if self.status == StatusTreinamento.CANCELADO:
            return "cancelado"
        if self.status == StatusTreinamento.PLANEJADO:
            return "planejado"
        dias = self.dias_para_vencer
        if dias is None:
            return "em_dia"
        if dias < 0:
            return "vencido"
        if dias <= settings.VENCIMENTO_ALERTA_DIAS:
            return "a_vencer"
        return "em_dia"

    @property
    def situacao_rotulo(self) -> str:
        dias = self.dias_para_vencer
        return {
            "cancelado": "Cancelado",
            "planejado": "Planejado",
            "em_dia": "Em dia",
            "a_vencer": f"Reciclar em {dias} dias" if dias is not None else "A vencer",
            "vencido": f"Reciclagem vencida há {abs(dias)} dias" if dias is not None else "Vencido",
        }[self.situacao]

    @property
    def cor(self) -> str:
        return {
            "cancelado": "cinza",
            "planejado": "azul",
            "em_dia": "verde",
            "a_vencer": "amarelo",
            "vencido": "vermelho",
        }[self.situacao]


# -------------------------------------------------------------- plano de acao


class TipoRisco(models.TextChoices):
    FISICO = "FIS", "Físico"
    QUIMICO = "QUI", "Químico"
    BIOLOGICO = "BIO", "Biológico"
    ERGONOMICO = "ERG", "Ergonômico"
    ACIDENTE = "ACI", "Acidente / mecânico"
    PSICOSSOCIAL = "PSI", "Psicossocial"
    GESTAO = "GES", "Gestão / documental"


class Prioridade(models.TextChoices):
    ALTA = "ALTA", "Alta"
    MEDIA = "MEDIA", "Média"
    BAIXA = "BAIXA", "Baixa"

    @classmethod
    def cor(cls, valor: str) -> str:
        return {cls.ALTA: "vermelho", cls.MEDIA: "amarelo", cls.BAIXA: "cinza"}.get(valor, "cinza")


class StatusAcao(models.TextChoices):
    NAO_INICIADA = "NAO", "Não iniciada"
    EM_ANDAMENTO = "AND", "Em andamento"
    AGUARDANDO = "AGU", "Aguardando a empresa"
    CONCLUIDA = "CONC", "Concluída"
    VERIFICADA = "VER", "Eficácia verificada"

    @classmethod
    def cor(cls, valor: str) -> str:
        return {
            cls.NAO_INICIADA: "cinza",
            cls.EM_ANDAMENTO: "azul",
            cls.AGUARDANDO: "amarelo",
            cls.CONCLUIDA: "verde",
            cls.VERIFICADA: "verde",
        }.get(valor, "cinza")

    @classmethod
    def progresso(cls, valor: str) -> int:
        return {
            cls.NAO_INICIADA: 0, cls.EM_ANDAMENTO: 40, cls.AGUARDANDO: 60,
            cls.CONCLUIDA: 90, cls.VERIFICADA: 100,
        }.get(valor, 0)

    @classmethod
    def encerrados(cls) -> list[str]:
        return [cls.CONCLUIDA, cls.VERIFICADA]


class AcaoPlano(TimeStampedModel):
    """Item do plano de acao do PGR."""

    gestao = models.ForeignKey(
        Gestao, verbose_name="gestão", related_name="acoes", on_delete=models.CASCADE
    )
    descricao = models.CharField("ação", max_length=250)
    risco = models.CharField("tipo de risco", max_length=3, choices=TipoRisco.choices, default=TipoRisco.ACIDENTE)
    setor = models.CharField("setor / GHE", max_length=120, blank=True)
    prioridade = models.CharField("prioridade", max_length=5, choices=Prioridade.choices, default=Prioridade.MEDIA)
    responsavel_empresa = models.CharField(
        "responsável na empresa", max_length=150, blank=True,
        help_text="Quem executa do lado do cliente.",
    )
    prazo = models.DateField("prazo", null=True, blank=True)
    status = models.CharField("status", max_length=4, choices=StatusAcao.choices, default=StatusAcao.NAO_INICIADA)
    concluida_em = models.DateField("concluída em", null=True, blank=True)
    custo_estimado = models.DecimalField("custo estimado", max_digits=12, decimal_places=2, null=True, blank=True)
    visivel_cliente = models.BooleanField("visível no portal", default=True)
    observacoes = models.TextField("observações", blank=True)

    class Meta:
        verbose_name = "ação do plano"
        verbose_name_plural = "plano de ação"
        ordering = ["status", "prazo", "-prioridade", "id"]

    def __str__(self) -> str:
        return self.descricao

    @property
    def encerrada(self) -> bool:
        return self.status in StatusAcao.encerrados()

    @property
    def atrasada(self) -> bool:
        return bool(not self.encerrada and self.prazo and self.prazo < timezone.localdate())

    @property
    def cor_status(self) -> str:
        if self.atrasada:
            return "vermelho"
        return StatusAcao.cor(self.status)

    @property
    def cor_prioridade(self) -> str:
        return Prioridade.cor(self.prioridade)

    @property
    def progresso(self) -> int:
        return StatusAcao.progresso(self.status)


class EventoAcao(TimeStampedModel):
    """Cada passo de uma acao do plano — o que o cliente acompanha."""

    acao = models.ForeignKey(
        AcaoPlano, verbose_name="ação", related_name="eventos", on_delete=models.CASCADE
    )
    data = models.DateField("data", default=timezone.localdate)
    descricao = models.CharField("o que aconteceu", max_length=250)
    visivel_cliente = models.BooleanField("visível no portal", default=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="registrado por",
        related_name="eventos_acao", on_delete=models.SET_NULL, null=True, blank=True,
    )

    class Meta:
        verbose_name = "andamento da ação"
        verbose_name_plural = "andamentos das ações"
        ordering = ["-data", "-id"]

    def __str__(self) -> str:
        return f"{self.data:%d/%m/%Y} - {self.descricao}"


class StatusImportacao(models.TextChoices):
    PENDENTE = "PEND", "Aguardando conferência"
    CONCLUIDA = "CONC", "Concluída"
    CANCELADA = "CANC", "Cancelada"


def caminho_importacao(instance, filename: str) -> str:
    return f"importacoes/{instance.gestao_id}/{filename}"


class ImportacaoPlano(TimeStampedModel):
    """Planilha do plano de acao enviada para a gestao."""

    gestao = models.ForeignKey(
        Gestao, verbose_name="gestão", related_name="importacoes", on_delete=models.CASCADE
    )
    arquivo = models.FileField("arquivo", upload_to=caminho_importacao)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="enviado por",
        related_name="importacoes", on_delete=models.SET_NULL, null=True, blank=True,
    )
    status = models.CharField(
        "status", max_length=4, choices=StatusImportacao.choices, default=StatusImportacao.PENDENTE
    )
    linhas_lidas = models.PositiveIntegerField("linhas lidas", default=0)
    linhas_validas = models.PositiveIntegerField("linhas válidas", default=0)
    criados = models.PositiveIntegerField("ações criadas", default=0)
    atualizados = models.PositiveIntegerField("ações atualizadas", default=0)
    ignorados = models.PositiveIntegerField("linhas ignoradas", default=0)
    mensagem = models.TextField("mensagem", blank=True)

    class Meta:
        verbose_name = "importação do plano de ação"
        verbose_name_plural = "importações do plano de ação"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.arquivo.name} ({self.get_status_display()})"


class GrauRat(models.IntegerChoices):
    """Alíquota básica do RAT (Lei 8.212/91, art. 22, II), pelo CNAE preponderante."""

    LEVE = 1, "1% · risco leve"
    MEDIO = 2, "2% · risco médio"
    GRAVE = 3, "3% · risco grave"


class BloqueioFap(models.TextChoices):
    NENHUM = "", "Sem bloqueio"
    MORTE_INVALIDEZ = "MORT", "Morte ou invalidez permanente no período-base"
    ROTATIVIDADE = "ROT", "Rotatividade média acima de 75%"


class FichaFap(TimeStampedModel):
    """FAP de uma vigência: grau do RAT, percentis, pontuação (IC), FAP e impacto na folha."""

    gestao = models.ForeignKey(Gestao, verbose_name="gestão", related_name="fichas_fap", on_delete=models.CASCADE)
    vigencia = models.PositiveSmallIntegerField(
        "vigência", help_text="Ano em que o FAP é aplicado. O período-base são os dois anos anteriores ao cálculo."
    )
    grau_rat = models.PositiveSmallIntegerField("grau do RAT", choices=GrauRat.choices, default=GrauRat.MEDIO)
    percentil_gravidade = models.DecimalField(
        "percentil de gravidade", max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="0 a 100, no extrato do FAPWeb. Peso 50% na pontuação.",
    )
    percentil_frequencia = models.DecimalField(
        "percentil de frequência", max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="0 a 100. Peso 35%.",
    )
    percentil_custo = models.DecimalField(
        "percentil de custo", max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="0 a 100. Peso 15%.",
    )
    bloqueio = models.CharField(
        "bloqueio da bonificação", max_length=4, choices=BloqueioFap.choices, blank=True, default="",
        help_text="Com bloqueio, um FAP abaixo de 1 passa a 1,0000.",
    )
    fap_oficial = models.DecimalField(
        "FAP oficial (FAPWeb)", max_digits=5, decimal_places=4, null=True, blank=True,
        help_text="Se preenchido, prevalece sobre o cálculo pelos percentis.",
    )
    folha_mensal = models.DecimalField(
        "folha de salários mensal", max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Remuneração total do estabelecimento, base do RAT.",
    )
    observacoes = models.TextField("observações", blank=True)

    class Meta:
        verbose_name = "ficha do FAP"
        verbose_name_plural = "fichas do FAP"
        ordering = ["-vigencia"]
        constraints = [models.UniqueConstraint(fields=["gestao", "vigencia"], name="fap_unico_por_vigencia")]

    def __str__(self) -> str:
        return f"FAP {self.vigencia} · {self.gestao}"

    @property
    def calculo(self):
        from .fap import calcular

        return calcular(self)
