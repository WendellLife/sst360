"""Gráficos em SVG desenhados no servidor.

Cores vêm de variáveis CSS (classes .g-*), então o gráfico acompanha o tema claro e
escuro sem JavaScript. Cada marca tem <title> (dica ao passar o mouse) e o gráfico
tem uma tabela equivalente na página para leitores de tela.
Especificação: barras de até 24px, ponta arredondada de 4px e base reta, grade de 1px.
"""
from html import escape

from django.utils.safestring import mark_safe


def _n(v) -> float:
    return float(v or 0)


def _fmt(v, formato):
    return formato(v) if formato else f"{_n(v):,.0f}".replace(",", ".")


def _barra_vertical(x, y_base, largura, altura, raio=4):
    """Coluna com topo arredondado e base reta."""
    if altura <= 0:
        return ""
    r = min(raio, altura, largura / 2)
    topo = y_base - altura
    return (f"M{x:.1f},{y_base:.1f} L{x:.1f},{topo + r:.1f} Q{x:.1f},{topo:.1f} {x + r:.1f},{topo:.1f} "
            f"L{x + largura - r:.1f},{topo:.1f} Q{x + largura:.1f},{topo:.1f} {x + largura:.1f},{topo + r:.1f} "
            f"L{x + largura:.1f},{y_base:.1f} Z")


def _barra_horizontal(x0, y, comprimento, espessura, raio=4):
    if comprimento <= 0:
        return ""
    r = min(raio, comprimento, espessura / 2)
    fim = x0 + comprimento
    return (f"M{x0:.1f},{y:.1f} L{fim - r:.1f},{y:.1f} Q{fim:.1f},{y:.1f} {fim:.1f},{y + r:.1f} "
            f"L{fim:.1f},{y + espessura - r:.1f} Q{fim:.1f},{y + espessura:.1f} {fim - r:.1f},{y + espessura:.1f} "
            f"L{x0:.1f},{y + espessura:.1f} Z")


def _passo(maximo):
    """Escala limpa para o eixo: 1, 2, 2,5 ou 5 × 10^n."""
    if maximo <= 0:
        return 1
    import math
    bruto = maximo / 4
    potencia = 10 ** math.floor(math.log10(bruto))
    for m in (1, 2, 2.5, 5, 10):
        if bruto <= m * potencia:
            return m * potencia
    return 10 * potencia


def colunas(itens, *, valor="total", rotulo="rotulo", formato=None, formato_eixo=None, altura=220, destaque_ultimo=True, titulo="", largura=640):
    """Colunas para série temporal curta (ex.: vendas por mês)."""
    n = len(itens)
    if not n:
        return mark_safe('<p class="texto-fraco">Sem dados no período.</p>')
    esq, dir_, topo, base = (56 if formato_eixo or formato else 28), 12, 22, 28
    area_w, area_h = largura - esq - dir_, altura - topo - base
    maximo = max(_n(i[valor]) for i in itens) or 1
    passo = _passo(maximo)
    if not formato:
        passo = max(1, round(passo))
    teto = passo * (int(maximo / passo) + (0 if maximo % passo == 0 else 1))
    banda = area_w / n
    esp = min(24, banda * 0.5)
    partes = [f'<svg class="grafico" style="max-width:{largura}px" viewBox="0 0 {largura} {altura}" role="img" aria-label="{escape(titulo)}" preserveAspectRatio="xMinYMid meet">']
    t = 0
    while t <= teto + 1e-9:
        y = topo + area_h - (t / teto) * area_h
        partes.append(f'<line class="g-grade" x1="{esq}" x2="{largura - dir_}" y1="{y:.1f}" y2="{y:.1f}"/>')
        partes.append(f'<text class="g-eixo" x="{esq - 8}" y="{y + 4:.1f}" text-anchor="end">{escape((formato_eixo or formato or _fmt)(t) if formato_eixo or formato else _fmt(t, None))}</text>')
        t += passo
    for k, item in enumerate(itens):
        v = _n(item[valor])
        h = v / teto * area_h
        x = esq + banda * k + (banda - esp) / 2
        y_base = topo + area_h
        cls = "g-marca" + (" g-marca-destaque" if destaque_ultimo and k == n - 1 else "")
        dica = f"{item[rotulo]}: {_fmt(v, formato)}" + (f" · {item['qtd']} venda(s)" if "qtd" in item else "")
        partes.append(f'<g><title>{escape(dica)}</title><rect class="g-alvo" x="{esq + banda * k:.1f}" y="{topo}" width="{banda:.1f}" height="{area_h}"/>'
                      f'<path class="{cls}" d="{_barra_vertical(x, y_base, esp, h)}"/></g>')
        if destaque_ultimo and k == n - 1 or v == maximo:
            partes.append(f'<text class="g-valor" x="{x + esp / 2:.1f}" y="{y_base - h - 6:.1f}" text-anchor="middle">{escape(_fmt(v, formato))}</text>')
        partes.append(f'<text class="g-eixo" x="{x + esp / 2:.1f}" y="{altura - 8}" text-anchor="middle">{escape(str(item[rotulo]))}</text>')
    partes.append(f'<line class="g-base" x1="{esq}" x2="{largura - dir_}" y1="{topo + area_h}" y2="{topo + area_h}"/></svg>')
    return mark_safe("".join(partes))


def barras(itens, *, valor="total", rotulo="rotulo", formato=None, classe=None, largura_rotulo=None, extra=None, titulo="", largura=640, valor_w=None):
    """Barras horizontais com rótulo à esquerda e valor na ponta."""
    if not itens:
        return mark_safe('<p class="texto-fraco">Sem dados no período.</p>')
    linha, esp = 34, 14
    largura_rotulo = largura_rotulo or round(largura * 0.34)
    valor_w = valor_w or (150 if extra else 110)
    limite = max(10, int(largura_rotulo / 7.6))
    area_w = largura - largura_rotulo - valor_w
    altura = linha * len(itens) + 6
    maximo = max(_n(i[valor]) for i in itens) or 1
    partes = [f'<svg class="grafico" style="max-width:{largura}px" viewBox="0 0 {largura} {altura}" role="img" aria-label="{escape(titulo)}" preserveAspectRatio="xMinYMid meet">']
    partes.append(f'<line class="g-base" x1="{largura_rotulo}" x2="{largura_rotulo}" y1="0" y2="{altura - 6}"/>')
    for k, item in enumerate(itens):
        v = _n(item[valor])
        y = k * linha + (linha - esp) / 2
        comp = v / maximo * area_w
        cls = classe(item) if callable(classe) else (classe or "g-marca")
        rot = str(item[rotulo])
        rot_curto = rot if len(rot) <= limite else rot[:limite - 1] + "…"
        texto_valor = _fmt(v, formato) + (f" {extra(item)}" if extra else "")
        partes.append(f'<g><title>{escape(rot)}: {escape(texto_valor)}</title>'
                      f'<rect class="g-alvo" x="0" y="{k * linha}" width="{largura}" height="{linha}"/>'
                      f'<text class="g-rotulo" x="{largura_rotulo - 10}" y="{y + esp / 2 + 4:.1f}" text-anchor="end">{escape(rot_curto)}</text>'
                      f'<path class="{cls}" d="{_barra_horizontal(largura_rotulo, y, comp, esp)}"/>'
                      f'<text class="g-valor" x="{largura_rotulo + comp + 8:.1f}" y="{y + esp / 2 + 4:.1f}">{escape(texto_valor)}</text></g>')
    partes.append("</svg>")
    return mark_safe("".join(partes))


def empilhada(partes_dados, *, titulo=""):
    """Uma barra 100% com segmentos de estado (ex.: situação dos documentos).

    partes_dados: lista de dicts {rotulo, total, classe}. Segmentos separados por 2px.
    """
    total = sum(_n(p["total"]) for p in partes_dados)
    if not total:
        return mark_safe('<p class="texto-fraco">Sem dados.</p>')
    largura, altura = 640, 26
    partes = [f'<svg class="grafico grafico-faixa" viewBox="0 0 {largura} {altura}" role="img" aria-label="{escape(titulo)}" preserveAspectRatio="none">']
    x = 0.0
    visiveis = [p for p in partes_dados if _n(p["total"])]
    for k, p in enumerate(visiveis):
        w = _n(p["total"]) / total * largura
        gap = 2 if k < len(visiveis) - 1 else 0
        partes.append(f'<rect class="{p["classe"]}" x="{x:.1f}" y="0" width="{max(w - gap, 1):.1f}" height="{altura}" rx="{4 if k in (0, len(visiveis) - 1) else 0}">'
                      f'<title>{escape(p["rotulo"])}: {int(_n(p["total"]))} ({round(_n(p["total"]) / total * 100)}%)</title></rect>')
        x += w
    partes.append("</svg>")
    return mark_safe("".join(partes))


def pontos_fap(linhas, *, titulo="", largura=640):
    """FAP de cada cliente numa régua de 0,5 a 2,0, com a linha do neutro e a meta."""
    if not linhas:
        return mark_safe('<p class="texto-fraco">Nenhum FAP lançado.</p>')
    esq, dir_, linha, topo, base = round(largura * 0.3), 70, 34, 20, 26
    area_w = largura - esq - dir_
    fundo = topo + linha * len(linhas)
    altura = fundo + base

    def px(f):
        return esq + (min(max(float(f), 0.5), 2.0) - 0.5) / 1.5 * area_w

    def br(v):
        return f"{float(v):.4f}".replace(".", ",")

    partes = [f'<svg class="grafico" style="max-width:{largura}px" viewBox="0 0 {largura} {altura}" role="img" aria-label="{escape(titulo)}" preserveAspectRatio="xMinYMid meet">']
    partes.append(f'<rect class="g-faixa-bonus" x="{esq}" y="0" width="{px(1) - esq:.1f}" height="{fundo}"/>')
    partes.append(f'<rect class="g-faixa-malus" x="{px(1):.1f}" y="0" width="{px(2) - px(1):.1f}" height="{fundo}"/>')
    partes.append(f'<text class="g-eixo" x="{esq + 6}" y="13">bônus</text><text class="g-eixo" x="{px(1) + 6:.1f}" y="13">malus</text>')
    for marca in (0.5, 1.0, 1.5, 2.0):
        partes.append(f'<line class="{"g-neutro" if marca == 1 else "g-grade"}" x1="{px(marca):.1f}" x2="{px(marca):.1f}" y1="0" y2="{fundo}"/>'
                      f'<text class="g-eixo" x="{px(marca):.1f}" y="{fundo + 17}" text-anchor="middle">{br(marca)}</text>')
    for k, x in enumerate(linhas):
        c, g = x["c"], x["gestao"]
        y = topo + k * linha + linha / 2
        nome = str(x["empresa"])
        lim = int(esq / 7.6)
        nome = nome if len(nome) <= lim else nome[:lim - 1] + "…"
        partes.append(f'<text class="g-rotulo" x="{esq - 10}" y="{y + 4:.1f}" text-anchor="end">{escape(nome)}</text>')
        if g.fap_meta:
            partes.append(f'<line class="g-meta-ligacao" x1="{px(g.fap_meta):.1f}" x2="{px(c.fap):.1f}" y1="{y:.1f}" y2="{y:.1f}"/>'
                          f'<circle class="g-meta" cx="{px(g.fap_meta):.1f}" cy="{y:.1f}" r="4"><title>Meta {br(g.fap_meta)}</title></circle>')
        nivel = c.nivel["codigo"] if c.nivel else "NEU"
        partes.append(f'<circle class="g-ponto g-nivel-{nivel}" cx="{px(c.fap):.1f}" cy="{y:.1f}" r="6"><title>{escape(str(x["empresa"]))}: FAP {br(c.fap)} · {escape(c.nivel["rotulo"])}</title></circle>'
                      f'<text class="g-valor" x="{largura - dir_ + 10}" y="{y + 4:.1f}">{br(c.fap)}</text>')
    partes.append("</svg>")
    return mark_safe("".join(partes))
