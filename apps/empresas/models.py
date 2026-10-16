from django.db import models
from django.urls import reverse

from apps.core.models import TimeStampedModel
from apps.core.validators import formatar_cnpj, validar_cnpj

UFS = [
    ("AC", "AC"), ("AL", "AL"), ("AP", "AP"), ("AM", "AM"), ("BA", "BA"),
    ("CE", "CE"), ("DF", "DF"), ("ES", "ES"), ("GO", "GO"), ("MA", "MA"),
    ("MT", "MT"), ("MS", "MS"), ("MG", "MG"), ("PA", "PA"), ("PB", "PB"),
    ("PR", "PR"), ("PE", "PE"), ("PI", "PI"), ("RJ", "RJ"), ("RN", "RN"),
    ("RS", "RS"), ("RO", "RO"), ("RR", "RR"), ("SC", "SC"), ("SP", "SP"),
    ("SE", "SE"), ("TO", "TO"),
]


class Porte(models.TextChoices):
    MEI = "MEI", "MEI"
    ME = "ME", "Microempresa"
    EPP = "EPP", "Empresa de pequeno porte"
    MEDIA = "MEDIA", "Media empresa"
    GRANDE = "GRANDE", "Grande empresa"


class GrauRisco(models.IntegerChoices):
    """Grau de risco da atividade principal (NR-04, Anexo I)."""

    G1 = 1, "Grau 1"
    G2 = 2, "Grau 2"
    G3 = 3, "Grau 3"
    G4 = 4, "Grau 4"


class SituacaoEmpresa(models.TextChoices):
    PROSPECT = "PROSPECT", "Prospect"
    CLIENTE = "CLIENTE", "Cliente ativo"
    SUSPENSO = "SUSPENSO", "Contrato suspenso"
    ENCERRADO = "ENCERRADO", "Contrato encerrado"


class Empresa(TimeStampedModel):
    razao_social = models.CharField("razao social", max_length=200)
    nome_fantasia = models.CharField("nome fantasia", max_length=200, blank=True)
    cnpj = models.CharField("CNPJ", max_length=18, unique=True, validators=[validar_cnpj])
    porte = models.CharField("porte", max_length=10, choices=Porte.choices, default=Porte.EPP)
    atividade = models.CharField("atividade principal", max_length=200, blank=True)
    cnae = models.CharField("CNAE principal", max_length=10, blank=True)
    grau_risco = models.PositiveSmallIntegerField(
        "grau de risco (NR-04)", choices=GrauRisco.choices, null=True, blank=True
    )
    num_trabalhadores = models.PositiveIntegerField("trabalhadores", null=True, blank=True)
    situacao = models.CharField(
        "situacao", max_length=10, choices=SituacaoEmpresa.choices, default=SituacaoEmpresa.CLIENTE
    )

    cep = models.CharField("CEP", max_length=9, blank=True)
    logradouro = models.CharField("logradouro", max_length=200, blank=True)
    numero = models.CharField("numero", max_length=20, blank=True)
    complemento = models.CharField("complemento", max_length=100, blank=True)
    bairro = models.CharField("bairro", max_length=100, blank=True)
    cidade = models.CharField("cidade", max_length=100, blank=True)
    uf = models.CharField("UF", max_length=2, choices=UFS, blank=True)

    telefone = models.CharField("telefone", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    site = models.URLField("site", blank=True)

    responsavel = models.ForeignKey(
        "accounts.User",
        verbose_name="responsavel interno",
        related_name="empresas_responsavel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    inicio_contrato = models.DateField("inicio do contrato", null=True, blank=True)
    observacoes = models.TextField("observacoes", blank=True)

    class Meta:
        verbose_name = "empresa"
        verbose_name_plural = "empresas"
        ordering = ["razao_social"]

    def __str__(self) -> str:
        return self.nome_fantasia or self.razao_social

    def get_absolute_url(self) -> str:
        return reverse("empresas:detalhe", args=[self.pk])

    @property
    def cnpj_formatado(self) -> str:
        return formatar_cnpj(self.cnpj)

    @property
    def gestao_ativa(self):
        return self.gestoes.filter(encerrado_em__isnull=True).first()


class Contato(TimeStampedModel):
    empresa = models.ForeignKey(
        Empresa, verbose_name="empresa", related_name="contatos", on_delete=models.CASCADE
    )
    nome = models.CharField("nome", max_length=150)
    cargo = models.CharField("cargo", max_length=120, blank=True)
    email = models.EmailField("e-mail", blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    principal = models.BooleanField("contato principal", default=False)

    class Meta:
        verbose_name = "contato"
        verbose_name_plural = "contatos"
        ordering = ["-principal", "nome"]

    def __str__(self) -> str:
        return f"{self.nome} ({self.empresa})"
