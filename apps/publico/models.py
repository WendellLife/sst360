import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Urgencia(models.TextChoices):
    ALTA = "ALTA", "Exposição alta"
    MEDIA = "MEDIA", "Exposição moderada"
    BAIXA = "BAIXA", "Exposição baixa"

    @classmethod
    def da_pontuacao(cls, pontos: int) -> str:
        """Alta a partir de 50% da pontuacao maxima; moderada a partir de 25%."""
        from .conteudo import PONTUACAO_MAXIMA

        if pontos >= PONTUACAO_MAXIMA * 0.50:
            return cls.ALTA
        if pontos >= PONTUACAO_MAXIMA * 0.25:
            return cls.MEDIA
        return cls.BAIXA

    @classmethod
    def cor(cls, valor: str) -> str:
        return {cls.ALTA: "vermelho", cls.MEDIA: "amarelo", cls.BAIXA: "verde"}.get(valor, "cinza")

    @classmethod
    def minutos_sla(cls, valor: str) -> int | None:
        """Tempo prometido para o primeiro contato humano."""
        return {cls.ALTA: 30, cls.MEDIA: 240, cls.BAIXA: 1440}.get(valor)

    @classmethod
    def prazo_legivel(cls, valor: str) -> str:
        return {cls.ALTA: "30 minutos", cls.MEDIA: "4 horas", cls.BAIXA: "1 dia útil"}.get(valor, "")


RESULTADOS = {
    Urgencia.ALTA: {
        "titulo": "Exposição alta: risco de autuação e de passivo trabalhista.",
        "mensagem": "As respostas indicam lacunas em itens exigidos pelas NRs e pelo eSocial. "
                    "Caso prioritário: retorno da equipe técnica em até 30 minutos, no horário comercial.",
    },
    Urgencia.MEDIA: {
        "titulo": "Exposição moderada: base existente, com pontos a corrigir.",
        "mensagem": "Há estrutura, mas com documentos, exames ou treinamentos fora do prazo. "
                    "Corrigir agora custa menos do que responder a uma fiscalização.",
    },
    Urgencia.BAIXA: {
        "titulo": "Exposição baixa: gestão em dia, com espaço para otimizar.",
        "mensagem": "O próximo ganho costuma estar em indicadores, redução do FAP e prevenção "
                    "de afastamentos.",
    },
}


class Diagnostico(TimeStampedModel):
    """Respostas do diagnostico de SST feito no site, com a exposicao calculada."""

    token = models.UUIDField("identificador publico", default=uuid.uuid4, unique=True, editable=False)
    nome = models.CharField("nome", max_length=150, blank=True)
    empresa = models.CharField("empresa", max_length=200, blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)

    contato_em = models.DateTimeField("contato informado em", null=True, blank=True)
    whatsapp_em = models.DateTimeField(
        "chamou no WhatsApp em", null=True, blank=True,
        help_text="Quando a pessoa clicou para falar com o comercial pelo WhatsApp.",
    )

    respostas = models.JSONField("respostas", default=list)
    pontuacao = models.PositiveIntegerField("pontuacao", default=0)
    urgencia = models.CharField("exposição", max_length=5, choices=Urgencia.choices)

    atendido_em = models.DateTimeField("primeiro contato em", null=True, blank=True)
    atendido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="atendido por",
        related_name="diagnosticos",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    lead = models.OneToOneField(
        "crm.Lead",
        verbose_name="lead gerado",
        related_name="diagnostico",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    observacoes = models.TextField("observacoes", blank=True)

    class Meta:
        verbose_name = "diagnostico"
        verbose_name_plural = "diagnosticos"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.empresa or self.nome or 'Diagnostico'} ({self.get_urgencia_display()})"

    def get_absolute_url(self) -> str:
        return reverse("crm:diagnosticos")

    @property
    def tem_contato(self) -> bool:
        return self.contato_em is not None

    @property
    def cor(self) -> str:
        return Urgencia.cor(self.urgencia)

    @property
    def prazo_contato(self):
        """Ate quando o primeiro contato humano deveria acontecer."""
        minutos = Urgencia.minutos_sla(self.urgencia)
        if minutos is None:
            return None
        return self.criado_em + timedelta(minutes=minutos)

    @property
    def minutos_sem_contato(self) -> int:
        fim = self.atendido_em or timezone.now()
        return max(0, int((fim - self.criado_em).total_seconds() // 60))

    @property
    def sla_estourado(self) -> bool:
        minutos = Urgencia.minutos_sla(self.urgencia)
        if minutos is None or self.atendido_em:
            return False
        return self.minutos_sem_contato > minutos

    @property
    def resumo_sla(self) -> str:
        if self.lead_id or self.atendido_em:
            return "contato humano feito"
        if self.sla_estourado:
            return f"prazo estourado — {self.minutos_sem_contato} min sem contato humano"
        return f"{Urgencia.prazo_legivel(self.urgencia)} para o 1º contato · aguardando"

    @property
    def pontuacao_maxima(self) -> int:
        from .conteudo import PONTUACAO_MAXIMA

        return PONTUACAO_MAXIMA

    @property
    def servicos_indicados(self) -> list[dict]:
        """Servicos que as respostas apontam, do mais citado ao menos citado.

        O servico da resposta sobre prioridade vem primeiro: e o que o cliente quer resolver ja.
        """
        from apps.gestao.models import Servico

        from .conteudo import MOTIVO_SERVICO

        contagem: dict[str, int] = {}
        for item in self.respostas or []:
            peso = 100 if item.get("chave") == "prioridade" else 1
            for codigo in item.get("servicos") or []:
                contagem[codigo] = contagem.get(codigo, 0) + peso
        nomes = dict(Servico.choices)
        ordem = sorted(contagem.items(), key=lambda par: -par[1])
        return [
            {"codigo": codigo, "titulo": nomes.get(codigo, codigo), "motivo": MOTIVO_SERVICO.get(codigo, ""),
             "peso": peso}
            for codigo, peso in ordem if codigo in nomes
        ]

    @property
    def riscos_identificados(self) -> list[dict]:
        """Riscos que as respostas apontam, os de gravidade alta primeiro, sem repetir."""
        from .conteudo import PERGUNTAS_QUIZ, RISCOS, riscos_da_resposta

        rotulos = {p["chave"]: [o[0] for o in p["opcoes"]] for p in PERGUNTAS_QUIZ}
        codigos: list[str] = []
        for item in self.respostas or []:
            lista = item.get("riscos")
            if lista is None:  # diagnostico antigo: deduz pela resposta
                opcoes = rotulos.get(item.get("chave"), [])
                indice = opcoes.index(item.get("resposta")) if item.get("resposta") in opcoes else -1
                lista = riscos_da_resposta(item.get("chave"), indice)
            for codigo in lista:
                if codigo in RISCOS and codigo not in codigos:
                    codigos.append(codigo)
        ordem = {"alta": 0, "media": 1}
        codigos.sort(key=lambda c: ordem.get(RISCOS[c]["gravidade"], 2))
        from apps.gestao.models import Servico

        nomes = dict(Servico.choices)
        return [{"codigo": c, "servico_titulo": nomes.get(RISCOS[c]["servico"], ""), **RISCOS[c]} for c in codigos]

    @property
    def exposicao(self) -> dict:
        """Soma das multas de referência dos riscos identificados (cada risco uma vez)."""
        riscos = [r for r in self.riscos_identificados if r["minimo"] is not None]
        return {
            "minimo": sum(r["minimo"] for r in riscos),
            "maximo": sum(r["maximo"] for r in riscos),
            "itens": len(riscos),
            "riscos": len(self.riscos_identificados),
            "altos": sum(1 for r in self.riscos_identificados if r["gravidade"] == "alta"),
        }

    @property
    def referencia(self) -> str:
        return f"D-{self.pk:04d}" if self.pk else "D-novo"

    def resumo_texto(self) -> str:
        """Resumo do diagnóstico para o comercial: perfil, o que está inadequado e o que corrigir."""
        from apps.core.templatetags.sst_extras import moeda

        r = {item.get("chave"): item.get("resposta") for item in self.respostas or []}
        riscos = self.riscos_identificados
        exp = self.exposicao
        linhas = ["*Diagnóstico de SST · SST360*", f"Referência: {self.referencia}"]
        if self.empresa or self.nome:
            linhas.append("Empresa: " + " · ".join(x for x in [self.empresa, self.nome] if x))
        perfil = [
            f"{r['trabalhadores']} trabalhadores" if r.get("trabalhadores") else None,
            r.get("operacao"),
            f"unidades: {r['unidades'].lower()}" if r.get("unidades") else None,
        ]
        linhas.append("Perfil: " + " · ".join(x for x in perfil if x))
        if r.get("gestao_atual"):
            linhas.append("SST hoje: " + r["gestao_atual"])
        linhas.append(f"Resultado: {self.get_urgencia_display()} ({self.pontuacao} de {self.pontuacao_maxima} pontos)")
        if exp["itens"]:
            linhas.append(f"Exposição estimada em multas: {moeda(exp['minimo'])} a {moeda(exp['maximo'])}")
        if riscos:
            linhas += ["", f"*O que está inadequado ({len(riscos)}):*"]
            for n, risco in enumerate(riscos, start=1):
                multa = ""
                if risco["minimo"] is not None:
                    multa = (f" · multa {moeda(risco['minimo'])}" if risco["minimo"] == risco["maximo"]
                             else f" · multa {moeda(risco['minimo'])} a {moeda(risco['maximo'])}")
                gravidade = "alta" if risco["gravidade"] == "alta" else "média"
                linhas.append(f"{n}. {risco['titulo']} ({risco['norma']}) · gravidade {gravidade}{multa}")
                linhas.append(f"   Corrigir: {risco['correcao']}")
        servicos = self.servicos_indicados
        if servicos:
            linhas += ["", "*Serviços indicados:* " + ", ".join(s["titulo"] for s in servicos[:5])]
        if r.get("prioridade"):
            linhas.append("*Prioridade da empresa:* " + r["prioridade"])
        linhas += ["", "Quero eliminar esses riscos. Podem me passar o plano de regularização?"]
        return "\n".join(linhas)

    @property
    def perfil(self) -> str:
        """Resumo curto das respostas, para a lista do painel."""
        por_chave = {item.get("chave"): item.get("resposta") for item in self.respostas or []}
        partes = [
            f"{por_chave['trabalhadores']} trabalhadores" if por_chave.get("trabalhadores") else None,
            por_chave.get("operacao"),
            por_chave.get("ocorrencias"),
        ]
        return " · ".join(parte for parte in partes if parte)
