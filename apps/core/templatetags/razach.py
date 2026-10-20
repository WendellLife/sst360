"""Tags do design system Razach, carregadas como builtins (sem {% load %}).

{% icone "circle-check" 16 %}: ícone Lucide local (static/razach/icons/), inline, herda currentColor.
"""

import re

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.core import icones

register = template.Library()


@register.simple_tag
def icone(nome, tamanho=16, classe="", estilo=""):
    return icones.svg(nome, tamanho, classe, estilo)


_ATRIBUTO = re.compile(r"""([a-zA-Z_][\w:.-]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?""")
_NOME_ATRIBUTO = re.compile(r"^[a-zA-Z_][\w:.-]*$")
_MANIPULADOR = re.compile(r"^on[a-z]+$", re.IGNORECASE)
_ATRIBUTOS_DE_URL = {"href", "xlink:href", "src", "srcdoc", "action", "formaction", "poster", "ping", "background"}
_ESQUEMA_PERIGOSO = re.compile(r"^(?:javascript|data|vbscript):", re.IGNORECASE)
_SEM_BRANCOS = re.compile(r"[\x00-\x20]+")


def _pares(attrs):
    if isinstance(attrs, dict):
        yield from attrs.items()
        return
    for m in _ATRIBUTO.finditer(str(attrs)):
        valor = next((g for g in m.group(2, 3, 4) if g is not None), True)
        yield m.group(1), valor


@register.filter
def atributos(attrs):
    """Monta atributos HTML escapados a partir de um dict ou de um texto `nome="valor" outro`.

    Nomes inválidos, manipuladores `on<evento>` e URLs `javascript:`/`data:`/`vbscript:` em atributos de URL (o navegador ignora brancos dentro do esquema) são descartados; valores sempre escapados. Valor True
    (ou texto sem `=`) vira atributo booleano; False/None omite o atributo.
    """
    if not attrs:
        return ""
    partes = []
    for nome, valor in _pares(attrs):
        nome = str(nome)
        if not _NOME_ATRIBUTO.match(nome) or _MANIPULADOR.match(nome) or valor is False or valor is None:
            continue
        if nome.lower() in _ATRIBUTOS_DE_URL and _ESQUEMA_PERIGOSO.match(_SEM_BRANCOS.sub("", str(valor))):
            continue
        if valor is True:
            partes.append(format_html("{}", nome))
        else:
            partes.append(format_html('{}="{}"', nome, valor))
    return mark_safe(" ".join(partes))
