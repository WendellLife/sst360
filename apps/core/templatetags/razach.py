"""Tags do design system Razach, carregadas como builtins (sem {% load %}).

{% icone "circle-check" 16 %}: ícone Lucide local (static/razach/icons/), inline, herda currentColor.
"""

from django import template

from apps.core import icones

register = template.Library()


@register.simple_tag
def icone(nome, tamanho=16, classe="", estilo=""):
    return icones.svg(nome, tamanho, classe, estilo)
