"""Login por codigo de uso unico para o cliente.

O codigo nunca e guardado em claro: fica o hash, como uma senha. O envio passa
por um canal configuravel — hoje e-mail, amanha WhatsApp — sem mudar o fluxo.
"""
from __future__ import annotations

import logging
import secrets
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import models, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger(__name__)

TAMANHO = 6
VALIDADE_MINUTOS = 10
MAX_TENTATIVAS = 5
MAX_PEDIDOS_POR_JANELA = 3
JANELA_PEDIDOS_MINUTOS = 15


def gerar_codigo() -> str:
    """Seis digitos sorteados de forma criptografica."""
    return f"{secrets.randbelow(10 ** TAMANHO):0{TAMANHO}d}"


class CodigoAcesso(TimeStampedModel):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="usuario",
        related_name="codigos_acesso", on_delete=models.CASCADE,
    )
    codigo_hash = models.CharField("codigo (hash)", max_length=128)
    expira_em = models.DateTimeField("expira em")
    tentativas = models.PositiveSmallIntegerField("tentativas", default=0)
    usado_em = models.DateTimeField("usado em", null=True, blank=True)
    canal = models.CharField("canal de envio", max_length=20, default="email")

    class Meta:
        verbose_name = "codigo de acesso"
        verbose_name_plural = "codigos de acesso"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.usuario} ({self.criado_em:%d/%m %H:%M})"

    @property
    def expirado(self) -> bool:
        return timezone.now() > self.expira_em

    @property
    def valido(self) -> bool:
        return not self.usado_em and not self.expirado and self.tentativas < MAX_TENTATIVAS

    def confere(self, digitado: str) -> bool:
        """Compara o codigo digitado e consome uma tentativa.

        Atômico: a linha fica travada durante a conferência, então dois pedidos simultâneos com o
        código certo não entram os dois (uso único) e as tentativas não se perdem na soma.
        """
        with transaction.atomic():
            atual = CodigoAcesso.objects.select_for_update().get(pk=self.pk)
            if not atual.valido:
                self.tentativas, self.usado_em = atual.tentativas, atual.usado_em
                return False
            atual.tentativas += 1
            acertou = check_password(digitado.strip(), atual.codigo_hash)
            if acertou:
                atual.usado_em = timezone.now()
            atual.save(update_fields=["tentativas", "usado_em", "atualizado_em"])
        self.tentativas, self.usado_em = atual.tentativas, atual.usado_em
        return acertou


class EnvioCodigoFalhou(Exception):
    """O canal (SMTP) não entregou o código; o registro criado foi descartado."""


def pode_pedir(usuario) -> bool:
    """Evita que alguem peça codigo em serie para um mesmo usuario."""
    desde = timezone.now() - timezone.timedelta(minutes=JANELA_PEDIDOS_MINUTOS)
    recentes = CodigoAcesso.objects.filter(usuario=usuario, criado_em__gte=desde).count()
    return recentes < MAX_PEDIDOS_POR_JANELA


def criar_e_enviar(usuario) -> CodigoAcesso | None:
    """Gera o codigo, guarda o hash e manda pelo canal configurado."""
    if not pode_pedir(usuario):
        logger.warning("Pedidos de codigo em excesso para o usuario %s", usuario.pk)
        return None

    codigo = gerar_codigo()
    registro = CodigoAcesso.objects.create(
        usuario=usuario,
        codigo_hash=make_password(codigo),
        expira_em=timezone.now() + timezone.timedelta(minutes=VALIDADE_MINUTOS),
        canal=settings.CANAL_CODIGO_ACESSO,
    )
    try:
        _enviar(usuario, codigo)
    except (SMTPException, OSError) as erro:
        # sem entrega, o código não serve para nada e não deve gastar o limite de pedidos do usuário
        logger.error("Falha ao enviar o codigo de acesso ao usuario %s: %s", usuario.pk, erro)
        registro.delete()
        raise EnvioCodigoFalhou from erro
    # um codigo novo (entregue) invalida os anteriores
    CodigoAcesso.objects.filter(usuario=usuario, usado_em__isnull=True).exclude(pk=registro.pk).update(
        expira_em=timezone.now()
    )
    return registro


def _enviar(usuario, codigo: str) -> None:
    canal = settings.CANAL_CODIGO_ACESSO
    if canal == "email" and usuario.email:
        contexto = {"codigo": codigo, "minutos": VALIDADE_MINUTOS, "usuario": usuario}
        send_mail(
            subject=f"Código de acesso ao portal: {codigo}",
            message=render_to_string("accounts/email_codigo.txt", contexto),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[usuario.email],
            fail_silently=False,
        )
        return
    # Nenhum canal configurado: registra para o time conseguir ajudar o cliente.
    logger.info("Codigo de acesso gerado para %s (canal %s indisponivel)", usuario.pk, canal)
