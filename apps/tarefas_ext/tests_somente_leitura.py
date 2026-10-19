"""O Tarefas é somente leitura de verdade: queryset, roteador, conexão e mensagem de erro (P9)."""
import json
import logging
import os
import subprocess
import sys
from unittest import mock

from django.conf import settings

from django.db import DatabaseError
from django.test import SimpleTestCase, override_settings

from . import servicos
from .models import Cliente
from .roteador import RoteadorTarefas
from .tests import TarefasTestCase


@override_settings(TAREFAS_ESCRITA_PARA_TESTES=False)
class EscritaBloqueadaTest(TarefasTestCase):
    @classmethod
    def setUpTestData(cls):
        with override_settings(TAREFAS_ESCRITA_PARA_TESTES=True):  # só a carga inicial escreve
            super().setUpTestData()

    def test_queryset_bloqueia_toda_escrita(self):
        qs = Cliente.objects.all()
        escritas = [
            lambda: qs.update(nome="x"),
            lambda: qs.delete(),
            lambda: Cliente.objects.bulk_create([Cliente(id=99, nome="n", cnpj="1", criado_em="2026-01-01T00:00:00Z")]),
            lambda: Cliente.objects.bulk_update(list(qs), ["nome"]),
            lambda: Cliente.objects.create(nome="n", cnpj="1", criado_em="2026-01-01T00:00:00Z"),
            lambda: Cliente.objects.get_or_create(nome="inexistente"),
            lambda: Cliente.objects.update_or_create(nome="inexistente"),
            lambda: Cliente.objects.get(pk=1).save(),
            lambda: Cliente.objects.get(pk=1).delete(),
        ]
        for escrever in escritas:
            with self.assertRaises(PermissionError):
                escrever()
        self.assertEqual(Cliente.objects.count(), 3)

    def test_leitura_continua_funcionando(self):
        self.assertEqual(Cliente.objects.filter(ativo=True).count(), 3)
        self.assertTrue(Cliente.objects.get(pk=1).tarefas.exists())


@override_settings(TAREFAS_ESCRITA_PARA_TESTES=False)
class RoteadorSomenteLeituraTest(SimpleTestCase):
    def test_roteador_nao_manda_escrita_para_o_alias_tarefas(self):
        roteador = RoteadorTarefas()
        self.assertEqual(roteador.db_for_read(Cliente), "tarefas")
        with self.assertRaises(PermissionError):
            roteador.db_for_write(Cliente)

    def test_roteador_nao_interfere_nos_outros_apps(self):
        from apps.empresas.models import Empresa

        self.assertIsNone(RoteadorTarefas().db_for_write(Empresa))


class ConfiguracaoTest(SimpleTestCase):
    """Carrega config.settings num processo à parte, com variáveis de ambiente controladas."""

    def configuracao(self, **ambiente):
        base = {k: v for k, v in os.environ.items() if k not in ("TAREFAS_DATABASE_URL", "DJANGO_TESTING", "DATABASE_URL")}
        base.update({"DJANGO_DEBUG": "True", "DJANGO_SETTINGS_MODULE": "config.settings", "PYTHONUTF8": "1"}, **ambiente)
        codigo = "import json; from config import settings as s; print(json.dumps([s.EM_TESTE, s.DATABASES.get('tarefas', {}).get('OPTIONS')]))"
        saida = subprocess.run([sys.executable, "-c", codigo], cwd=settings.BASE_DIR, env=base,
                               capture_output=True, text=True, check=True, timeout=60)
        return json.loads(saida.stdout.strip().splitlines()[-1])

    def test_postgres_do_tarefas_abre_a_sessao_somente_leitura(self):
        em_teste, opcoes = self.configuracao(TAREFAS_DATABASE_URL="postgres://u:p@h:5432/tarefas")
        self.assertFalse(em_teste)
        self.assertIn("default_transaction_read_only=on", opcoes["options"])

    def test_deteccao_de_teste_pela_variavel(self):
        self.assertTrue(self.configuracao(DJANGO_TESTING="1")[0])
        self.assertFalse(self.configuracao()[0])


class StatusGenericoTest(SimpleTestCase):
    databases = {"default", "tarefas"}

    def test_erro_aparece_generico_na_tela_e_detalhado_no_log(self):
        segredo = 'connection to server at "10.1.2.3", port 5432 failed: password authentication failed for user "tarefas_ro"'
        with mock.patch("apps.tarefas_ext.models.Cliente.objects") as objs, self.assertLogs(
            "apps.tarefas_ext.servicos", level=logging.ERROR
        ) as log:
            objs.exists.side_effect = DatabaseError(segredo)
            resultado = servicos.status()
        self.assertFalse(resultado["ok"])
        self.assertNotIn("10.1.2.3", resultado["erro"])
        self.assertNotIn("tarefas_ro", resultado["erro"])
        self.assertIn("10.1.2.3", "\n".join(log.output))
