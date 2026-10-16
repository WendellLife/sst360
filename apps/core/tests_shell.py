from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User


class ShellRazachTest(TestCase):
    """Shell no padrão Razach Tarefas Internas: barra lateral, barra superior e busca global."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_shell_interno(self):
        self.client.force_login(User.objects.get(username="analista"))
        html = self.client.get("/painel/").content.decode()
        self.assertIn('class="sb"', html)
        self.assertIn("razach/img/razach-combinado-gradiente.png", html)
        self.assertIn('<span class="tb-pagina">Painel</span>', html)
        self.assertIn("01 · Comercial", html)
        self.assertIn('class="sb-link is-active"', html)
        self.assertIn('class="ic"', html)

    def test_busca_global(self):
        self.client.force_login(User.objects.get(username="analista"))
        r = self.client.get("/busca/", {"q": "metal"})
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.context["total"], 0)
        self.assertContains(r, "Metalúrgica Exemplo")
        self.assertEqual(self.client.get("/busca/", {"q": "x"}).context.get("total"), None)

    def test_busca_fechada_para_cliente(self):
        self.client.force_login(User.objects.get(username="cliente"))
        self.assertNotEqual(self.client.get("/busca/", {"q": "metal"}).status_code, 200)

    def test_portal_e_login(self):
        html = self.client.get("/conta/entrar/").content.decode()
        self.assertIn("lg-art", html)
        self.client.force_login(User.objects.get(username="cliente"))
        html = self.client.get("/portal/").content.decode()
        self.assertIn("portal-nav", html)
        self.assertIn("razach-combinado-gradiente.png", html)
        self.assertIn("sb-link is-active", html)
