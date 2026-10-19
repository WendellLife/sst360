"""Varredura antes de produção: todas as telas abrem para cada perfil, nenhum link leva a uma área
que o perfil não pode abrir, e os ajustes da auditoria continuam valendo."""
import re
from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from django.core.management import call_command
from django.test import TestCase
from django.urls import URLPattern, URLResolver, Resolver404, get_resolver, resolve, reverse

from apps.accounts.models import TipoUsuario, User
from apps.crm.models import Estagio, Lead
from apps.empresas.models import Empresa
from apps.gestao.models import Gestao, Prazo, StatusPrazo


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs, self.mortos, self.acoes = [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a":
            href = (a.get("href") or "").strip()
            if href in ("", "#") or href.startswith("javascript:"):
                self.mortos.append(a)
            else:
                self.hrefs.append(href)
        elif tag == "form" and (a.get("method") or "").lower() == "post" and a.get("action"):
            self.acoes.append(a["action"])
        elif tag == "button" and a.get("formaction"):
            self.acoes.append(a["formaction"])


def _rotas(resolver=None, ns=None):
    for p in (resolver or get_resolver()).url_patterns:
        if isinstance(p, URLResolver):
            if p.namespace == "admin":
                continue
            yield from _rotas(p, p.namespace or ns)
        elif isinstance(p, URLPattern) and p.name:
            yield f"{ns}:{p.name}" if ns else p.name, str(p.pattern)


class VarreduraTest(TestCase):
    databases = {"default", "tarefas"}

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)
        cls.comercial = User.objects.create_user(
            "so_comercial", "comercial@exemplo.com.br", "x", tipo=TipoUsuario.INTERNO,
            acesso_comercial=True, acesso_tecnico=False, acesso_admin=False,
        )
        cls.perfis = {
            "admin": User.objects.get(username="analista"),
            "comercial": cls.comercial,
            "tecnico": User.objects.get(username="engenheiro"),
            "cliente": User.objects.get(username="cliente"),
        }

    def _urls(self):
        cliente = self.perfis["cliente"]
        gestao_cliente = Gestao.objects.filter(empresa_id=cliente.empresa_id).first()
        for nome, padrao in _rotas():
            if nome in ("accounts:logout",) or "<uuid" in padrao or padrao.endswith((".pptx", ".xlsx", ".gif")):
                continue
            if "<int:pk>" not in padrao:
                if "<" not in padrao:
                    yield reverse(nome)
                continue
            app = nome.split(":")[0]
            pk = {
                "crm": Lead.objects.values_list("pk", flat=True).first(),
                "empresas": Empresa.objects.values_list("pk", flat=True).first(),
                "gestao": Gestao.objects.values_list("pk", flat=True).first(),
                "relacionamento": Gestao.objects.values_list("pk", flat=True).first(),
                "portal": getattr(gestao_cliente, "pk", None),
                "accounts": User.objects.values_list("pk", flat=True).first(),
            }.get(app)
            if pk and nome.split(":")[1] in ("detalhe", "editar", "painel", "gestao", "usuario_editar"):
                yield reverse(nome, kwargs={"pk": pk})

    def _pode_abrir(self, usuario, caminho):
        try:
            vc = getattr(resolve(caminho).func, "view_class", None)
        except Resolver404:
            return None
        if vc is None or not hasattr(vc, "test_func") or not hasattr(vc, "modulo"):
            return True
        mods = vc.modulo if isinstance(vc.modulo, (tuple, list)) else (vc.modulo,)
        return usuario.is_interno and any(usuario.tem_modulo(m) for m in mods)

    def test_telas_abrem_e_links_respeitam_o_perfil(self):
        problemas = []
        for perfil, usuario in self.perfis.items():
            self.client.force_login(usuario)
            for url in self._urls():
                r = self.client.get(url)
                self.assertLess(r.status_code, 500, f"{perfil} {url}")
                if r.status_code != 200 or "text/html" not in r.get("Content-Type", ""):
                    continue
                p = _Links()
                p.feed(r.content.decode())
                for a in p.mortos:
                    problemas.append(f"{perfil} {url}: link sem destino {a}")
                for href in p.hrefs + p.acoes:
                    alvo = urlparse(urljoin(url, href))
                    if alvo.netloc or alvo.scheme in ("mailto", "tel") or alvo.path.startswith(("/static/", "/media/")):
                        continue
                    ok = self._pode_abrir(usuario, alvo.path)
                    if ok is None:
                        problemas.append(f"{perfil} {url}: link para rota inexistente {alvo.path}")
                    elif not ok:
                        problemas.append(f"{perfil} {url}: link para área sem acesso {alvo.path}")
            self.client.logout()
        self.assertEqual(sorted(set(problemas)), [])


class AjustesDaAuditoriaTest(TestCase):
    databases = {"default", "tarefas"}

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)
        cls.analista = User.objects.get(username="analista")
        cls.tecnico = User.objects.get(username="engenheiro")

    def test_next_externo_nao_redireciona_para_fora(self):
        self.client.force_login(self.analista)
        lead = Lead.objects.first()
        r = self.client.post(reverse("crm:mover", args=[lead.pk]), {"estagio": Estagio.CONTATO, "next": "https://exemplo.invalid/"})
        self.assertEqual(r["Location"], lead.get_absolute_url())
        prazo = Prazo.objects.filter(status=StatusPrazo.PENDENTE).first()
        r = self.client.post(reverse("gestao:prazo_concluir", args=[prazo.pk]), {"next": "//exemplo.invalid/x"})
        self.assertEqual(r["Location"], prazo.gestao.get_absolute_url())

    def test_prazo_cumprido_por_formulario(self):
        self.client.force_login(self.tecnico)
        prazo = Prazo.objects.filter(status=StatusPrazo.PENDENTE).first()
        html = self.client.get(prazo.gestao.get_absolute_url()).content.decode()
        self.assertIn(f'action="{reverse("gestao:prazo_concluir", args=[prazo.pk])}"', html)
        self.assertNotIn("hx-post", html)
        self.assertNotIn("cdn.jsdelivr.net", html)
        r = self.client.post(reverse("gestao:prazo_concluir", args=[prazo.pk]), {"next": prazo.gestao.get_absolute_url() + "#prazos"})
        self.assertRedirects(r, prazo.gestao.get_absolute_url() + "#prazos", fetch_redirect_response=False)
        prazo.refresh_from_db()
        self.assertEqual(prazo.status, StatusPrazo.CUMPRIDO)

    def test_datas_aparecem_no_formato_do_campo_de_data(self):
        self.client.force_login(self.analista)
        lead = Lead.objects.exclude(proximo_contato=None).first()
        html = self.client.get(reverse("crm:editar", args=[lead.pk])).content.decode()
        self.assertIn(f'value="{lead.proximo_contato.isoformat()}"', html)
        self.assertIsNone(re.search(r'type="date"[^>]*value="\d{2}/\d{2}/\d{4}"', html))

    def test_filtro_de_contato_atrasado_e_paginacao_com_filtro(self):
        self.client.force_login(self.analista)
        ontem = date.today() - timedelta(days=1)
        Lead.objects.update(proximo_contato=ontem, estagio=Estagio.CONTATO)
        Lead.objects.filter(pk=Lead.objects.first().pk).update(proximo_contato=date.today() + timedelta(days=5))
        r = self.client.get(reverse("crm:lista"), {"atrasados": "1"})
        self.assertEqual(r.context["paginator"].count, Lead.objects.count() - 1)
        for i in range(30):
            Lead.objects.create(razao_social=f"Lead {i}", estagio=Estagio.CONTATO, proximo_contato=ontem)
        html = self.client.get(reverse("crm:lista"), {"atrasados": "1", "estagio": Estagio.CONTATO}).content.decode()
        self.assertIn("atrasados=1", re.search(r'class="paginacao".*?</nav>', html, re.S).group(0))

    def test_contato_da_empresa_volta_para_a_pagina(self):
        self.client.force_login(self.analista)
        empresa = Empresa.objects.first()
        r = self.client.post(empresa.get_absolute_url(), {"nome": "Ana Teste", "cargo": "RH", "email": "ana@exemplo.com.br", "telefone": "19999990000"})
        self.assertRedirects(r, empresa.get_absolute_url(), fetch_redirect_response=False)
        self.assertTrue(empresa.contatos.filter(nome="Ana Teste").exists())

    def test_tecnico_nao_ve_vendas_e_entra_pelas_gestoes(self):
        self.client.force_login(self.tecnico)
        html = self.client.get(Empresa.objects.first().get_absolute_url()).content.decode()
        self.assertNotIn('id="vendas"', html)
        self.assertIn(f'href="{reverse("gestao:lista")}" class="sb-marca"', html)
        self.assertIn(reverse("accounts:password_change"), html)

    def test_paginas_de_erro_em_portugues(self):
        self.client.force_login(self.analista)
        r = self.client.get("/nao-existe/")
        self.assertContains(r, "Página não encontrada", status_code=404)


class EntradaDoClienteTest(TestCase):
    """O cliente entra no portal com o código de uso único e continua logado."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_codigo_leva_ao_portal_e_mantem_a_sessao(self):
        from django.core import mail

        cliente = User.objects.get(username="cliente")
        self.client.post(reverse("accounts:codigo_pedir"), {"contato": cliente.email})
        codigo = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        r = self.client.post(reverse("accounts:codigo_confirmar"), {"codigo": codigo}, follow=True)
        self.assertEqual(r.redirect_chain, [(reverse("portal:home"), 302)])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["user"], cliente)

    def test_equipe_entra_com_email(self):
        r = self.client.post(reverse("accounts:login"), {"username": "ANALISTA@exemplo.com.br", "password": "sst360demo"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 200)
