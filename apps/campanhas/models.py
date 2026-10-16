"""Régua de relacionamento: campanha mensal por e-mail e WhatsApp para leads que ainda não são clientes."""
import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel

MESES_NOMES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
               "setembro", "outubro", "novembro", "dezembro"]


class Etapa(models.TextChoices):
    """Etapa da régua no mês, pela distância até a renovação do contrato do lead."""

    MENSAL = "MEN", "Conteúdo do mês"
    R90 = "R90", "Renovação em 3 meses"
    R60 = "R60", "Renovação em 2 meses"
    R30 = "R30", "Renovação no próximo mês"
    R0 = "R0", "Mês da renovação"

    @classmethod
    def cor(cls, valor):
        return {cls.MENSAL: "cinza", cls.R90: "azul", cls.R60: "amarelo", cls.R30: "vermelho", cls.R0: "vermelho"}.get(valor, "cinza")


class Canal(models.TextChoices):
    EMAIL = "EML", "E-mail"
    WHATSAPP = "WPP", "WhatsApp"


class StatusEnvio(models.TextChoices):
    PENDENTE = "PEND", "Pendente"
    ENVIADO = "ENV", "Enviado"
    FALHOU = "FALHA", "Falhou"
    PULADO = "PUL", "Pulado"

    @classmethod
    def cor(cls, valor):
        return {cls.PENDENTE: "amarelo", cls.ENVIADO: "verde", cls.FALHOU: "vermelho", cls.PULADO: "cinza"}.get(valor, "cinza")


class Modelo(TimeStampedModel):
    """Texto de cada etapa da régua. Aceita campos como {contato}, {empresa} e {link_proposta}."""

    etapa = models.CharField("etapa", max_length=3, choices=Etapa.choices, unique=True)
    assunto = models.CharField("assunto do e-mail", max_length=200)
    email = models.TextField("texto do e-mail")
    whatsapp = models.TextField("mensagem do WhatsApp")

    class Meta:
        verbose_name = "modelo de mensagem"
        verbose_name_plural = "modelos de mensagem"
        ordering = ["etapa"]

    def __str__(self) -> str:
        return self.get_etapa_display()


class Campanha(TimeStampedModel):
    """A campanha de um mês: tema e conteúdo útil que vão em todas as mensagens."""

    ano = models.PositiveSmallIntegerField("ano")
    mes = models.PositiveSmallIntegerField("mês")
    tema = models.CharField("tema do mês", max_length=150)
    conteudo = models.TextField(
        "conteúdo do mês",
        help_text="Um parágrafo útil para o leitor (norma, prazo, multa, dica). Entra no lugar de {conteudo}.",
    )
    envios_gerados_em = models.DateTimeField("envios gerados em", null=True, blank=True)
    emails_enviados_em = models.DateTimeField("e-mails enviados em", null=True, blank=True)

    class Meta:
        verbose_name = "campanha"
        verbose_name_plural = "campanhas"
        ordering = ["-ano", "-mes"]
        constraints = [models.UniqueConstraint(fields=["ano", "mes"], name="campanha_unica_por_mes")]

    def __str__(self) -> str:
        return self.rotulo

    @property
    def rotulo(self) -> str:
        return f"{MESES_NOMES[self.mes - 1]}/{self.ano}"

    @property
    def chave(self) -> str:
        return f"{self.ano}-{self.mes:02d}"


class Envio(TimeStampedModel):
    """Uma mensagem para um lead num canal, dentro da campanha do mês."""

    campanha = models.ForeignKey(Campanha, verbose_name="campanha", related_name="envios", on_delete=models.CASCADE)
    lead = models.ForeignKey("crm.Lead", verbose_name="lead", related_name="envios", on_delete=models.CASCADE)
    canal = models.CharField("canal", max_length=3, choices=Canal.choices)
    etapa = models.CharField("etapa", max_length=3, choices=Etapa.choices)
    status = models.CharField("status", max_length=5, choices=StatusEnvio.choices, default=StatusEnvio.PENDENTE)
    token = models.UUIDField("token", default=uuid.uuid4, unique=True, editable=False)
    enviado_em = models.DateTimeField("enviado em", null=True, blank=True)
    aberto_em = models.DateTimeField("aberto em", null=True, blank=True)
    clicado_em = models.DateTimeField("clicou em", null=True, blank=True)
    erro = models.CharField("erro", max_length=300, blank=True)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="enviado por", related_name="envios_campanha",
        on_delete=models.SET_NULL, null=True, blank=True,
    )

    class Meta:
        verbose_name = "envio"
        verbose_name_plural = "envios"
        ordering = ["-campanha__ano", "-campanha__mes", "lead__razao_social"]
        constraints = [models.UniqueConstraint(fields=["campanha", "lead", "canal"], name="envio_unico_por_canal")]

    def __str__(self) -> str:
        return f"{self.get_canal_display()} · {self.lead} · {self.campanha}"

    @property
    def cor_etapa(self):
        return Etapa.cor(self.etapa)

    @property
    def cor_status(self):
        return StatusEnvio.cor(self.status)
