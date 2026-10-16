from datetime import date, datetime, time, timedelta

from django.db import connections
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import TipoUsuario, User
from apps.crm.models import Lead
from apps.empresas.models import Empresa

from . import servicos
from .models import Cliente, Contato, Pessoa, Projeto, Tarefa, Turma

MODELOS = [Pessoa, Cliente, Contato, Projeto, Tarefa, Turma]


class TarefasTestCase(TestCase):
    """Cria as tabelas do Tarefas no SQLite de teste (no sistema real elas são do Tarefas)."""

    databases = {"default", "tarefas"}

    @classmethod
    def setUpClass(cls):
        with connections["tarefas"].schema_editor() as editor:
            for m in MODELOS:
                m._meta.managed = True
                editor.create_model(m)
                m._meta.managed = False
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connections["tarefas"].schema_editor() as editor:
            for m in reversed(MODELOS):
                editor.delete_model(m)

    @classmethod
    def setUpTestData(cls):
        agora = timezone.now()
        hoje = timezone.localdate()
        Pessoa.objects.bulk_create([Pessoa(id=1, nome="Camila Freitas", iniciais="CF", papel="Instrutora", ativa=True)])
        Cliente.objects.bulk_create([
            Cliente(id=1, nome="Metalúrgica Vale do Aço Ltda.", cnpj="48157263000135", ativo=True, criado_em=agora),
            Cliente(id=2, nome="Hospital Santa Clara", cnpj="30561892000160", ativo=True, criado_em=agora),
            Cliente(id=3, nome="Construtora Horizonte S.A.", cnpj="45997418000153", ativo=True, criado_em=agora),
        ])
        Contato.objects.bulk_create([Contato(id=1, cliente_id=1, nome="Fernanda Rocha", cargo="Gerente de RH", principal=True)])
        Projeto.objects.bulk_create([Projeto(id=1, nome="Turma in company", tipo="presencial", curso=True, ativo=True, cliente_id=1)])
        Tarefa.objects.bulk_create([
            Tarefa(id=1, numero=38, titulo="Enviar o cronograma", etapa="fazer", prioridade="alta", prazo=hoje - timedelta(days=1),
                   criada_em=agora, cliente_id=1, projeto_id=1, responsavel_id=1),
            Tarefa(id=2, numero=34, titulo="Atualizar os slides", etapa="andamento", prioridade="media", prazo=hoje + timedelta(days=5),
                   criada_em=agora, cliente_id=1, responsavel_id=1),
            Tarefa(id=3, numero=20, titulo="Relatório entregue", etapa="feito", prioridade="media", prazo=hoje,
                   criada_em=agora, concluida_em=agora, cliente_id=1, responsavel_id=1),
        ])
        Turma.objects.bulk_create([
            Turma(id=1, data=hoje + timedelta(days=10), tipo="presencial", hora_inicio=time(8), hora_fim=time(17), pessoas=14,
                  estado="confirmada", local="Ipatinga", cliente_id=1, projeto_id=1),
        ])
        cls.empresa = Empresa.objects.create(razao_social="Construtora Horizonte", cnpj="45.997.418/0001-53")
        cls.lead = Lead.objects.create(razao_social="Hospital Santa Clara", cnpj="30.561.892/0001-60")
        cls.comercial = User.objects.create_user("vendas", "vendas@teste.com.br", "x", tipo=TipoUsuario.INTERNO,
                                                 acesso_comercial=True, acesso_tecnico=False)


class ServicosTest(TarefasTestCase):
    def test_cruza_pelo_cnpj(self):
        dados = servicos.painel()
        vinculos = {l["cliente"].nome: l["vinculo"] for l in dados["linhas"]}
        self.assertEqual(vinculos["Construtora Horizonte S.A."], "cliente")
        self.assertEqual(vinculos["Hospital Santa Clara"], "lead")
        self.assertEqual(vinculos["Metalúrgica Vale do Aço Ltda."], "sem_cadastro")
        self.assertEqual(dados["totais"]["oportunidades"], 1)
        self.assertEqual(dados["totais"]["turmas_60"], 1)
        metal = next(l for l in dados["linhas"] if l["vinculo"] == "sem_cadastro")
        self.assertEqual((metal["cliente"].abertas, metal["cliente"].atrasadas, metal["cliente"].concluidas_30), (2, 1, 1))
        self.assertEqual(metal["contato"].nome, "Fernanda Rocha")

    def test_resumo_da_empresa(self):
        r = servicos.resumo_por_cnpj("48.157.263/0001-35")
        self.assertEqual(r["total_abertas"], 2)
        self.assertEqual(r["atrasadas"], 1)
        self.assertEqual(r["abertas"][0].codigo, "RZ-038")
        self.assertTrue(r["abertas"][0].atrasada)
        self.assertEqual(len(r["turmas"]), 1)
        self.assertIsNone(servicos.resumo_por_cnpj("11.111.111/0001-11"))

    def test_cria_lead_uma_vez(self):
        lead, criado = servicos.criar_lead(1, self.comercial)
        self.assertTrue(criado)
        self.assertEqual(lead.cnpj, "48.157.263/0001-35")
        self.assertEqual(lead.contato_nome, "Fernanda Rocha")
        self.assertEqual(lead.atividades.count(), 1)
        de_novo, criado = servicos.criar_lead(1, self.comercial)
        self.assertFalse(criado)
        self.assertEqual(de_novo.pk, lead.pk)
        self.assertEqual(servicos.criar_lead(3, self.comercial), (None, False))  # já é empresa

    def test_somente_leitura(self):
        with self.assertRaises(PermissionError):
            Cliente.objects.get(pk=1).save()


class TelasTest(TarefasTestCase):
    def test_painel_comercial(self):
        self.client.force_login(self.comercial)
        r = self.client.get("/comercial/tarefas/")
        self.assertContains(r, "Metalúrgica Vale do Aço Ltda.")
        self.assertContains(r, "Criar lead")
        r = self.client.get("/comercial/tarefas/?vinculo=lead")
        self.assertContains(r, "Hospital Santa Clara")
        self.assertNotContains(r, 'principal">Metalúrgica Vale do Aço Ltda.')

    def test_criar_lead_pela_tela(self):
        self.client.force_login(self.comercial)
        r = self.client.post("/comercial/tarefas/clientes/1/criar-lead/")
        lead = Lead.objects.get(cnpj="48.157.263/0001-35")
        self.assertRedirects(r, lead.get_absolute_url(), fetch_redirect_response=False)

    def test_cartao_no_lead(self):
        self.client.force_login(self.comercial)
        r = self.client.get(self.lead.get_absolute_url())
        self.assertContains(r, "No sistema Tarefas")
        self.assertContains(r, "CL-002")

    def test_tecnico_nao_ve(self):
        tecnico = User.objects.create_user("tec", "tec@teste.com.br", "x", tipo=TipoUsuario.INTERNO, acesso_comercial=False, acesso_tecnico=True)
        self.client.force_login(tecnico)
        self.assertEqual(self.client.get("/comercial/tarefas/").status_code, 302)


class ImportacaoTest(TarefasTestCase):
    def test_importa_todos_sem_duplicar(self):
        r = servicos.importar_clientes(self.comercial)
        self.assertEqual([l.razao_social for l in r["criados"]], ["Metalúrgica Vale do Aço Ltda."])
        self.assertEqual(r["ja_existiam"], 2)  # Construtora (empresa) e Hospital (lead)
        self.assertEqual(servicos.importar_clientes(self.comercial)["criados"], [])

    def test_botao_da_tela(self):
        self.client.force_login(self.comercial)
        r = self.client.post("/comercial/tarefas/importar/")
        self.assertRedirects(r, "/comercial/tarefas/", fetch_redirect_response=False)
        self.assertTrue(Lead.objects.filter(cnpj="48.157.263/0001-35").exists())

    def test_comando(self):
        from io import StringIO

        from django.core.management import call_command

        saida = StringIO()
        call_command("importar_tarefas", "--responsavel", "vendas@teste.com.br", stdout=saida)
        self.assertIn("1 lead(s) criado(s)", saida.getvalue())
        self.assertEqual(Lead.objects.get(cnpj="48.157.263/0001-35").responsavel, self.comercial)
