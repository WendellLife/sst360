from django import template

from apps.core.validators import formatar_cnpj

register = template.Library()


@register.filter(name="cnpj")
def cnpj(valor):
    return formatar_cnpj(valor)


@register.filter(name="moeda")
def moeda(valor):
    if valor in (None, ""):
        return "-"
    texto = f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


@register.filter(name="badge_cor")
def badge_cor(chave):
    """Classe da etiqueta a partir da familia de cor (verde, amarelo...)."""
    familias = {"verde", "amarelo", "vermelho", "azul", "cinza"}
    return f"etiqueta--{chave}" if chave in familias else "etiqueta--cinza"


@register.filter(name="fap")
def fap(valor):
    """0.8732 -> 0,8732"""
    if valor in (None, ""):
        return "-"
    return f"{float(valor):.4f}".replace(".", ",")


@register.filter(name="sigla_doc")
def sigla_doc(valor):
    from apps.gestao.models import TipoDocumento

    return TipoDocumento.sigla(valor)


@register.filter(name="num_br")
def num_br(valor, casas=2):
    """1234.5 -> 1.234,50"""
    if valor in (None, ""):
        return "-"
    texto = f"{float(valor):,.{int(casas)}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter(name="absoluto")
def absoluto(valor):
    return abs(valor) if valor not in (None, "") else valor


@register.filter(name="posicao_fap")
def posicao_fap(valor):
    """Posição de 0 a 100 do FAP na régua de 0,5000 a 2,0000 (número com ponto, para CSS)."""
    if valor in (None, ""):
        return 0
    return round(max(0.0, min(100.0, (float(valor) - 0.5) / 1.5 * 100)), 1)


@register.filter(name="fap_sinal")
def fap_sinal(valor):
    """0.124 -> +0,1240"""
    if valor in (None, ""):
        return "-"
    sinal = "+" if valor > 0 else ""
    return sinal + f"{float(valor):.4f}".replace(".", ",")


@register.filter(name="moeda_curta")
def moeda_curta(valor):
    """24540 -> R$ 24,5 mil; 1250000 -> R$ 1,25 mi"""
    if valor in (None, ""):
        return "-"
    v = float(valor)
    if abs(v) >= 1_000_000:
        return "R$ " + f"{v / 1_000_000:.2f}".replace(".", ",") + " mi"
    if abs(v) >= 1_000:
        return "R$ " + f"{v / 1_000:.1f}".replace(".", ",") + " mil"
    return "R$ " + f"{v:.0f}"


ROTULOS_SECAO = {
    "painel": "Painel", "indicadores": "Indicadores", "gestao": "Gestões de SST", "prazos": "Prazos",
    "vencimentos": "Vencimentos", "empresas": "Empresas", "funil": "Funil comercial", "diagnosticos": "Diagnósticos",
    "leads": "Leads", "vendas": "Vendas", "campanhas": "Campanhas", "fap": "FAP dos clientes", "busca": "Busca",
    "inicio": "Início", "plano": "Plano de ação", "documentos": "Documentos", "treinamentos": "Treinamentos",
    "reunioes": "Visitas", "conversa": "Conversa", "usuarios": "Usuários e acessos", "tarefas": "Sistema Tarefas",
}


@register.filter(name="rotulo_secao")
def rotulo_secao(secao):
    """Nome do módulo para a trilha do cabeçalho."""
    return ROTULOS_SECAO.get(secao or "", "SST360")


@register.filter(name="iniciais")
def iniciais(nome):
    partes = [p for p in str(nome or "").split() if p]
    if not partes:
        return "?"
    return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()


@register.filter(name="grupo_secao")
def grupo_secao(secao):
    """Grupo da barra lateral para a trilha do cabeçalho (01 · Gestão, 02 · Captação)."""
    from apps.core.context_processors import SECAO_GRUPO

    return SECAO_GRUPO.get(secao or "", "")


@register.filter(name="resto_pct")
def resto_pct(pct):
    """100 - pct, limitado a 0..100 (recorte do medidor)."""
    try:
        return max(0, min(100, 100 - int(pct)))
    except (TypeError, ValueError):
        return 100


@register.simple_tag(takes_context=True)
def link_gestao(context, gestao, ancora=""):
    """Endereço de uma gestão para quem tem o módulo técnico; para os demais, a página da empresa."""
    pode = context.get("pode") or {}
    if pode.get("tecnico"):
        return gestao.get_absolute_url() + ancora
    return gestao.empresa.get_absolute_url()


def _id_ajuda(campo):
    return f"{campo.auto_id}_helptext" if campo.auto_id else ""


def _id_erro(campo):
    return f"{campo.auto_id}_error" if campo.auto_id else ""


@register.filter(name="id_ajuda")
def id_ajuda(campo):
    """Id do texto de ajuda do campo (o mesmo que o Django usa em aria-describedby)."""
    return _id_ajuda(campo)


@register.filter(name="id_erro")
def id_erro(campo):
    return _id_erro(campo)


@register.filter(name="campo_aria")
def campo_aria(campo):
    """Renderiza o campo ligando ajuda e erros por aria-describedby, com aria-required.

    O Django já marca required e aria-invalid; aqui entram o id do bloco de erros (sempre) e a
    ajuda em campos de fieldset (RadioSelect, grupos de checkbox), que ele deixa sem descrição.
    """
    ids = []
    if campo.help_text and _id_ajuda(campo):
        ids.append(_id_ajuda(campo))
    if campo.errors and _id_erro(campo):
        ids.append(_id_erro(campo))
    attrs = {}
    if ids:
        attrs["aria-describedby"] = " ".join(ids)
    if campo.field.required and not campo.field.widget.is_hidden and getattr(campo.field.widget, "input_type", "") != "checkbox":
        attrs["aria-required"] = "true"
    return campo.as_widget(attrs=attrs)
