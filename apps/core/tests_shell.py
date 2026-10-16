from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User


class ShellLifeLaboralTest(TestCase):
    """Shell no padrão Life Laboral: menu lateral, trilha do cabeçalho e busca global."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_shell_interno(self):
        self.client.force_login(User.objects.get(username="analista"))
        html = self.client.get("/painel/").content.decode()
        self.assertIn('class="sidebar"', html)
        self.assertIn("img/lifelaboral/logo-horizontal.png", html)
        self.assertIn("Life Laboral / <b>Painel</b>", html)
        self.assertIn('class="menu__item ativo"', html)

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
        self.assertIn("cartao-publico__hero", html)
        self.client.force_login(User.objects.get(username="cliente"))
        html = self.client.get("/portal/").content.decode()
        self.assertIn("portal-nav", html)
        self.assertNotIn("razach", html)
