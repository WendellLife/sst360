"""Testes de interface: ícones, escape dos componentes Razach, campo acessível, mensagens e tabelas."""

import re
from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.messages.storage.base import Message
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from apps.core import icones

RAIZ_TEMPLATES = Path(settings.BASE_DIR) / "templates"
ICONE_LITERAL = re.compile(r"""\{%\s*icone\s+["']([^"']+)["']""")


class IconesTest(SimpleTestCase):
    def test_todo_icone_literal_dos_templates_tem_svg(self):
        faltando = {}
        for arquivo in RAIZ_TEMPLATES.rglob("*.html"):
            for nome in ICONE_LITERAL.findall(arquivo.read_text(encoding="utf-8")):
                if not icones.existe(nome):
                    faltando.setdefault(nome, []).append(arquivo.relative_to(RAIZ_TEMPLATES).as_posix())
        self.assertEqual(faltando, {}, "Ícones sem arquivo em static/razach/icons/")

    def test_nome_invalido_cai_no_icone_reserva(self):
        self.assertIn("<svg", icones.svg("../segredo"))
        self.assertFalse(icones.existe("../segredo"))


class ComponentesEscapamentoTest(SimpleTestCase):
    def _renderiza(self, componente, **contexto):
        return render_to_string(f"razach/componentes/{componente}.html", contexto)

    def test_attrs_em_texto_mantem_atributos_validos_e_escapa_valores(self):
        html = self._renderiza("iconbutton", icone="x", rotulo="Fechar", attrs="data-fechar")
        self.assertIn(" data-fechar>", html)
        html = self._renderiza("badge", texto="a", attrs='data-x="1&quot; onmouseover=&quot;alert(1)"')
        self.assertNotIn('" onmouseover="', html)

    def test_attrs_dict_escapa_valor(self):
        html = self._renderiza("badge", texto="ok", attrs={"data-x": '"><script>alert(1)</script>'})
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_attrs_descarta_manipulador_e_nome_invalido(self):
        for componente, extra in (("badge", {"texto": "t"}), ("tag", {"texto": "t"}), ("card", {})):
            html = self._renderiza(componente, attrs={"onclick": "x()", 'a"b': "1", "data-ok": "2"}, **extra)
            self.assertNotIn("onclick", html)
            self.assertNotIn('a"b', html)
            self.assertIn('data-ok="2"', html)

    def test_attrs_descarta_url_perigosa_em_atributos_de_url(self):
        for nome in ("href", "src", "action", "formaction"):
            for valor in ("javascript:alert(1)", "  JavaScript:alert(1)", "data:text/html,x", "	DATA:x"):
                html = self._renderiza("badge", texto="t", attrs={nome: valor, "data-ok": "1"})
                self.assertNotIn(valor.strip(), html, (nome, valor))
                self.assertIn('data-ok="1"', html)
        html = self._renderiza("badge", texto="t", attrs={"href": "/ok/", "data-url": "javascript:x"})
        self.assertIn('href="/ok/"', html)
        self.assertIn('data-url="javascript:x"', html)

    def test_attrs_descarta_so_manipuladores_on_evento(self):
        html = self._renderiza("badge", texto="t", attrs={"onClick": "x()", "one-x": "1", "on": "2"})
        self.assertNotIn("onClick", html)
        self.assertIn('one-x="1"', html)
        self.assertIn('on="2"', html)

    def test_attrs_com_tag_solta_nao_vira_html(self):
        html = self._renderiza("button", texto="Ir", attrs="<img src=x onerror=alert(1)>")
        self.assertNotIn("<img", html)
        self.assertNotIn("onerror", html)

    def test_nenhum_componente_usa_safe_em_attrs(self):
        for arquivo in (RAIZ_TEMPLATES / "razach" / "componentes").glob("*.html"):
            self.assertNotIn("attrs|safe", arquivo.read_text(encoding="utf-8"), arquivo.name)


class FormularioTeste(forms.Form):
    nome = forms.CharField(label="Nome", help_text="Como no documento.")
    obs = forms.CharField(label="Observação", required=False)
    aceito = forms.BooleanField(label="Aceito")
    texto = forms.CharField(label="Texto", widget=forms.Textarea)


class CampoAcessivelTest(SimpleTestCase):
    def _html(self, dados=None):
        form = FormularioTeste(dados) if dados is not None else FormularioTeste()
        return "".join(render_to_string("partials/campo.html", {"campo": campo}) for campo in form)

    def test_ajuda_vira_aria_describedby(self):
        html = self._html()
        self.assertIn('id="id_nome_helptext"', html)
        self.assertIn('aria-describedby="id_nome_helptext"', html)
        self.assertIn('aria-required="true"', html)
        self.assertNotIn("aria-invalid", html)

    def test_erro_gera_id_aria_invalid_e_describedby(self):
        html = self._html({"nome": "", "obs": "", "aceito": ""})
        self.assertIn('id="id_nome_error"', html)
        self.assertIn('aria-invalid="true"', html)
        self.assertIn('aria-describedby="id_nome_helptext id_nome_error"', html)
        self.assertIn('aria-describedby="id_aceito_error"', html)

    def test_campo_opcional_nao_tem_aria_required(self):
        html = render_to_string("partials/campo.html", {"campo": FormularioTeste()["obs"]})
        self.assertNotIn("aria-required", html)
        self.assertNotIn("aria-describedby", html)


class MensagensTest(SimpleTestCase):
    def _html(self, nivel, texto):
        return Template('{% include "partials/messages.html" %}').render(Context({"messages": [Message(nivel, texto)]}))

    def test_erro_e_alerta_usam_role_alert(self):
        self.assertIn('role="alert"', self._html(messages.ERROR, "falhou"))
        self.assertIn('role="alert"', self._html(messages.WARNING, "atenção"))

    def test_sucesso_e_info_usam_role_status(self):
        self.assertIn('role="status"', self._html(messages.SUCCESS, "ok"))
        self.assertIn('role="status"', self._html(messages.INFO, "oi"))

    def test_debug_usa_estilo_de_info(self):
        self.assertIn("aviso--info", self._html(messages.DEBUG, "dbg"))


class TabelasTest(SimpleTestCase):
    def test_th_com_scope_e_rolagem_acessivel(self):
        sem_scope, sem_regiao, sem_wrapper = [], [], []
        for arquivo in RAIZ_TEMPLATES.rglob("*.html"):
            rel = arquivo.relative_to(RAIZ_TEMPLATES).as_posix()
            if rel.startswith(("razach/", "campanhas/email")):
                continue
            texto = arquivo.read_text(encoding="utf-8")
            if re.search(r"<th(?![a-z])(?![^>]*\bscope=)", texto):
                sem_scope.append(rel)
            # Exceção documentada: a tabela alternativa do gráfico fica dentro de <details>, sem wrapper.
            tabelas = len(re.findall(r"<table[\s>]", texto))
            if rel == "core/indicadores.html":
                tabelas -= len(re.findall(r'<details class="tabela-grafico"', texto))
            if tabelas != len(re.findall(r'<div class="tabela[\s"]', texto)):
                sem_wrapper.append(rel)
            for m in re.finditer(r'<div class="tabela[^"]*"([^>]*)>', texto):
                if 'role="region"' not in m.group(1) or "tabindex" not in m.group(1) or "aria-label" not in m.group(1):
                    sem_regiao.append(rel)
        self.assertEqual(sorted(set(sem_scope)), [])
        self.assertEqual(sorted(set(sem_regiao)), [])


class CodigoConfirmarTest(SimpleTestCase):
    def test_campo_aceita_codigo_colado_com_espaco_ou_hifen(self):
        html = render_to_string("accounts/codigo_confirmar.html", {"form": None, "email": "a@b.com"})
        campo = re.search(r'<input[^>]*name="codigo"[^>]*>', html, re.S).group(0)
        self.assertIn(r'pattern="[0-9 \-]*"', campo)
        self.assertIn('inputmode="numeric"', campo)
        self.assertNotIn("maxlength", campo)


class QuizTest(SimpleTestCase):
    def test_progresso_e_grupo(self):
        html = render_to_string(
            "publico/quiz.html",
            {"bloco_numero": 1, "bloco": "Bloco", "numero": 2, "total": 10, "percentual": 20,
             "pergunta": type("P", (), {"texto": "Pergunta?", "ajuda": "Dica"})(), "opcoes": [(0, ("Sim",))]},
        )
        self.assertIn('role="progressbar"', html)
        self.assertIn('aria-valuenow="2"', html)
        self.assertIn("<fieldset", html)
        self.assertIn("<legend>", html)

    def test_textarea_obrigatorio_tem_aria_required(self):
        html = render_to_string("partials/campo.html", {"campo": FormularioTeste()["texto"]})
        self.assertIn('aria-required="true"', html)
