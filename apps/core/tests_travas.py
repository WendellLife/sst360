"""Travas dos comandos de dados de exemplo fora do modo de desenvolvimento (P8) e GET sem efeito (P6)."""
from io import StringIO

from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.empresas.models import Empresa


@override_settings(DEBUG=False, EM_TESTE=False)
class CommandsEmProducaoTest(TestCase):
    def test_seed_demo_recusa_sem_debug(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command("seed_demo", "--senha", "Forte-123-xyz", stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command("seed_demo", "--permitir-producao", stdout=StringIO())
        self.assertFalse(Empresa.objects.exists())

    def test_seed_demo_com_senha_e_permissao_explicitas(self):
        call_command("seed_demo", "--senha", "Forte-123-xyz", "--permitir-producao", verbosity=0, stdout=StringIO())
        self.assertTrue(User.objects.get(username="analista").check_password("Forte-123-xyz"))

    def test_limpar_exige_o_nome_do_banco(self):
        Empresa.objects.create(razao_social="Real", cnpj="04.252.011/0001-10")
        for args in (["--confirmar"], ["--confirmar", "--banco", "outro"], ["--banco", connection.settings_dict["NAME"]]):
            with self.assertRaises(CommandError):
                call_command("limpar_dados_demo", *args, stdout=StringIO())
        self.assertTrue(Empresa.objects.exists())
        call_command("limpar_dados_demo", "--confirmar", "--banco", connection.settings_dict["NAME"], stdout=StringIO())
        self.assertFalse(Empresa.objects.exists())


@override_settings(DEBUG=True)
class CommandsEmDesenvolvimentoTest(TestCase):
    def test_seed_demo_segue_livre_com_debug(self):
        call_command("seed_demo", verbosity=0, stdout=StringIO())
        self.assertTrue(User.objects.get(username="analista").check_password("sst360demo"))
