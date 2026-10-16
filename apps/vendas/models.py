"""Vendas de serviços lançadas à mão pela equipe, por empresa atendida."""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.gestao.models import Servico

SERVICOS_VENDA = [*Servico.choices, ("OUT", "Outro serviço")]


class Cobranca(models.TextChoices):
    UNICA = "UNI", "Pagamento único"
    MENSAL = "MEN", "Mensal (recorrente)"


class StatusVenda(models.TextChoices):
    FECHADA = "FECH", "Fechada"
    FATURADA = "FAT", "Faturada"
    RECEBIDA = "REC", "Recebida"
    CANCELADA = "CANC", "Cancelada"

    @classmethod
    def cor(cls, valor: str) -> str:
        return {cls.FECHADA: "azul", cls.FATURADA: "amarelo", cls.RECEBIDA: "verde", cls.CANCELADA: "cinza"}.get(valor, "cinza")


class Venda(TimeStampedModel):
    empresa = models.ForeignKey(
        "empresas.Empresa", verbose_name="empresa", related_name="vendas", on_delete=models.CASCADE
    )
    gestao = models.ForeignKey(
        "gestao.Gestao", verbose_name="gestão de SST", related_name="vendas",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    data = models.DateField("data da venda", default=timezone.localdate)
    servico = models.CharField("serviço", max_length=3, choices=SERVICOS_VENDA)
    descricao = models.CharField(
        "descrição", max_length=200,
        help_text="O que foi vendido. Ex.: Treinamento NR-35 para 14 pessoas.",
    )
    quantidade = models.PositiveIntegerField("quantidade", default=1)
    valor_unitario = models.DecimalField("valor unitário", max_digits=12, decimal_places=2)
    cobranca = models.CharField("cobrança", max_length=3, choices=Cobranca.choices, default=Cobranca.UNICA)
    status = models.CharField("status", max_length=4, choices=StatusVenda.choices, default=StatusVenda.FECHADA)
    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="vendido por", related_name="vendas",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    observacoes = models.TextField("observações", blank=True)

    class Meta:
        verbose_name = "venda"
        verbose_name_plural = "vendas"
        ordering = ["-data", "-id"]

    def __str__(self) -> str:
        return f"{self.descricao} · {self.empresa}"

    def get_absolute_url(self) -> str:
        return reverse("vendas:editar", args=[self.pk])

    @property
    def total(self) -> Decimal:
        return (self.valor_unitario or Decimal("0")) * (self.quantidade or 0)

    @property
    def cor(self) -> str:
        return StatusVenda.cor(self.status)

    @property
    def ativa(self) -> bool:
        return self.status != StatusVenda.CANCELADA
