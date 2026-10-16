"""Ícones Lucide locais (lucide-static 0.469.0), injetados inline para herdar currentColor.

Nome sem SVG em static/razach/icons/ (ou fora do padrão "letras-e-digitos") não derruba a página:
cai no ícone "info" e registra um aviso no log, uma vez por nome. O teste de
apps/core/tests_interface.py confere que todo ícone literal dos templates tem arquivo.
"""

import logging
import re
from functools import lru_cache

from django.contrib.staticfiles import finders
from django.utils.html import format_html
from django.utils.safestring import mark_safe

logger = logging.getLogger(__name__)

RESERVA = "info"
NOME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_ABRE = re.compile(r"<svg[^>]*>", re.S)
_FECHA = re.compile(r"</svg>\s*$", re.S)
_COMENTARIO = re.compile(r"<!--.*?-->", re.S)


def caminho(nome):
    """Arquivo do ícone, ou None quando o nome é inválido ou não há SVG local."""
    nome = str(nome or "")
    if not NOME.match(nome):
        return None
    return finders.find(f"razach/icons/{nome}.svg")


def existe(nome):
    return caminho(nome) is not None


def _ler(arquivo):
    with open(arquivo, encoding="utf-8") as f:
        texto = _COMENTARIO.sub("", f.read()).strip()
    texto = _FECHA.sub("", _ABRE.sub("", texto, count=1)).strip()
    return " ".join(linha.strip() for linha in texto.splitlines() if linha.strip())


@lru_cache(maxsize=None)
def corpo(nome):
    """Conteúdo interno do <svg> (paths), sem o comentário de licença."""
    arquivo = caminho(nome)
    if arquivo:
        return _ler(arquivo)
    if nome == RESERVA:
        logger.error("Ícone de reserva %r sem arquivo local.", RESERVA)
        return ""
    logger.warning("Ícone Lucide sem arquivo local: %r. No lugar, vai %r.", nome, RESERVA)
    return corpo(RESERVA)


def svg(nome, tamanho=16, classe="", estilo=""):
    classes = "ic" + (f" {classe}" if classe else "")
    atributos = format_html(
        'class="{}" width="{}" height="{}" viewBox="0 0 24 24" aria-hidden="true" focusable="false"',
        classes,
        tamanho,
        tamanho,
    )
    if estilo:
        atributos = format_html('{} style="{}"', atributos, estilo)
    return mark_safe(f"<svg {atributos}>{corpo(str(nome or ''))}</svg>")
