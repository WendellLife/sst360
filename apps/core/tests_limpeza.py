from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.crm.models import Lead
from apps.empresas.models import Empresa
from apps.gestao.models import Gestao


class LimparDadosDemoTest(TestCase):
    def test_apaga_o_seed_e_mantem_o_admin(self):
        call_command("seed_demo", verbosity=0, stdout=StringIO())
        admin = User.objects.create_superuser("admin", "admin@empresa.com.br", "x")
        self.assertTrue(Empresa.objects.exists() and Lead.objects.exists() and Gestao.objects.exists())
        with self.assertRaises(CommandError):
            call_command("limpar_dados_demo", stdout=StringIO())
        self.assertTrue(Empresa.objects.exists())
        call_command("limpar_dados_demo", "--confirmar", stdout=StringIO())
        self.assertFalse(Empresa.objects.exists() or Lead.objects.exists() or Gestao.objects.exists())
        self.assertEqual(list(User.objects.values_list("username", flat=True)), ["admin"])
        self.client.force_login(admin)
        for url in ["/painel/", "/indicadores/", "/prospeccao/", "/gestao/", "/empresas/", "/campanhas/", "/vendas/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
