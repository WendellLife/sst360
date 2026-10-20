"""CRM: POSTs principais do funil e permissão por módulo."""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import TipoUsuario, User
from apps.empresas.models import Empresa, SituacaoEmpresa

from .models import Atividade, Estagio, Lead, TipoAtividade


class CrmTest(TestCase):
    databases = {"default", "tarefas"}

    @classmethod
    def setUpTestData(cls):
        cls.comercial = User.objects.create_user("com", "com@exemplo.com.br", "x", tipo=TipoUsuario.INTERNO,
                                                 acesso_comercial=True, acesso_tecnico=False)
        cls.tecnico = User.objects.create_user("tec", "tec@exemplo.com.br", "x", tipo=TipoUsuario.INTERNO,
                                               acesso_comercial=False, acesso_tecnico=True)
        cls.sem_modulo = User.objects.create_user("nada", "nada@exemplo.com.br", "x", tipo=TipoUsuario.INTERNO,
                                                  acesso_comercial=False, acesso_tecnico=False)
        cls.cliente = User.objects.create_user(
            "cli", "cli@exemplo.com.br", "x", tipo=TipoUsuario.CLIENTE,
            empresa=Empresa.objects.create(razao_social="Cliente", cnpj="00.000.000/0001-91"),
        )
        cls.lead = Lead.objects.create(razao_social="Transportes Alfa", contato_nome="Carla", contato_email="c@alfa.com",
                                       cnpj="11.222.333/0001-81", contato_telefone="19999990000")

    def novo_lead_dados(self, **extra):
        dados = {
            "razao_social": "Metalúrgica Nova", "porte": "EPP", "origem": "ATIV", "situacao_sst": "SEM",
            "servico_interesse": "GES", "estagio": Estagio.NOVO, "urgencia": "NA",
            "aceita_email": "on", "aceita_whatsapp": "on",
        }
        dados.update(extra)
        return dados

    # ------------------------------------------------------------ comercial pode
    def test_criar_lead(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("crm:novo"), self.novo_lead_dados(contato_nome="Ana", valor_estimado="1500.50"))
        lead = Lead.objects.get(razao_social="Metalúrgica Nova")
        self.assertRedirects(r, lead.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(lead.contato_nome, "Ana")

    def test_criar_lead_sem_razao_social_mostra_erro(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("crm:novo"), self.novo_lead_dados(razao_social=""))
        self.assertEqual(r.status_code, 200)
        self.assertIn("razao_social", r.context["form"].errors)
        self.assertEqual(Lead.objects.count(), 1)

    def test_editar_lead(self):
        self.client.force_login(self.comercial)
        dados = self.novo_lead_dados(razao_social="Transportes Alfa SA", proximo_contato="2026-12-01")
        r = self.client.post(reverse("crm:editar", args=[self.lead.pk]), dados)
        self.assertRedirects(r, self.lead.get_absolute_url(), fetch_redirect_response=False)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.razao_social, "Transportes Alfa SA")
        self.assertEqual(self.lead.proximo_contato, date(2026, 12, 1))

    def test_registrar_atividade(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("crm:atividade_nova", args=[self.lead.pk]),
                             {"data": "2026-10-10", "tipo": TipoAtividade.LIGACAO, "titulo": "Primeira ligação"})
        self.assertRedirects(r, self.lead.get_absolute_url(), fetch_redirect_response=False)
        atividade = Atividade.objects.get()
        self.assertEqual((atividade.lead, atividade.autor, atividade.titulo), (self.lead, self.comercial, "Primeira ligação"))

    def test_atividade_invalida_nao_grava(self):
        self.client.force_login(self.comercial)
        self.client.post(reverse("crm:atividade_nova", args=[self.lead.pk]), {"data": "xx", "tipo": "LIG", "titulo": ""})
        self.assertEqual(Atividade.objects.count(), 0)

    def test_mover_estagio(self):
        self.client.force_login(self.comercial)
        self.client.post(reverse("crm:mover", args=[self.lead.pk]), {"estagio": Estagio.PROPOSTA})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.estagio, Estagio.PROPOSTA)

    def test_mover_para_estagio_inexistente_nao_altera(self):
        self.client.force_login(self.comercial)
        self.client.post(reverse("crm:mover", args=[self.lead.pk]), {"estagio": "INVENTADO"})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.estagio, Estagio.NOVO)

    def test_mover_respeita_next_do_proprio_site(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("crm:mover", args=[self.lead.pk]), {"estagio": Estagio.CONTATO, "next": reverse("crm:funil")})
        self.assertRedirects(r, reverse("crm:funil"), fetch_redirect_response=False)

    def test_converter_lead_em_empresa(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("crm:converter", args=[self.lead.pk]))
        self.lead.refresh_from_db()
        empresa = self.lead.empresa
        self.assertRedirects(r, empresa.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual((empresa.razao_social, empresa.situacao), ("Transportes Alfa", SituacaoEmpresa.CLIENTE))
        self.assertEqual(self.lead.estagio, Estagio.GANHO)
        self.assertEqual(empresa.contatos.get().nome, "Carla")

    def test_converter_duas_vezes_nao_duplica_empresa(self):
        self.client.force_login(self.comercial)
        self.client.post(reverse("crm:converter", args=[self.lead.pk]))
        total = Empresa.objects.count()
        r = self.client.post(reverse("crm:converter", args=[self.lead.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Empresa.objects.count(), total)

    def test_lead_inexistente_da_404(self):
        self.client.force_login(self.comercial)
        self.assertEqual(self.client.post(reverse("crm:mover", args=[99999]), {"estagio": "NOVO"}).status_code, 404)
        self.assertEqual(self.client.post(reverse("crm:converter", args=[99999])).status_code, 404)
        self.assertEqual(self.client.get(reverse("crm:detalhe", args=[99999])).status_code, 404)

    def test_telas_de_leitura_abrem_para_o_comercial(self):
        self.client.force_login(self.comercial)
        for url in (reverse("crm:funil"), reverse("crm:lista"), reverse("crm:detalhe", args=[self.lead.pk]),
                    reverse("crm:editar", args=[self.lead.pk]), reverse("crm:novo"), reverse("crm:diagnosticos")):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_busca_na_lista(self):
        self.client.force_login(self.comercial)
        r = self.client.get(reverse("crm:lista"), {"q": "alfa"})
        self.assertEqual(r.context["paginator"].count, 1)
        self.assertEqual(self.client.get(reverse("crm:lista"), {"q": "zzz"}).context["paginator"].count, 0)

    # ------------------------------------------------------------ permissão negada
    def posts_protegidos(self):
        pk = self.lead.pk
        return [
            (reverse("crm:novo"), self.novo_lead_dados(razao_social="Invasor")),
            (reverse("crm:editar", args=[pk]), self.novo_lead_dados(razao_social="Invasor")),
            (reverse("crm:atividade_nova", args=[pk]), {"data": "2026-10-10", "tipo": "LIG", "titulo": "Invasor"}),
            (reverse("crm:mover", args=[pk]), {"estagio": Estagio.GANHO}),
            (reverse("crm:converter", args=[pk]), {}),
        ]

    def confere_nada_mudou(self):
        self.lead.refresh_from_db()
        self.assertEqual((self.lead.razao_social, self.lead.estagio, self.lead.empresa_id), ("Transportes Alfa", Estagio.NOVO, None))
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(Atividade.objects.count(), 0)
        self.assertEqual(Empresa.objects.filter(razao_social="Transportes Alfa").count(), 0)

    def test_perfis_sem_o_modulo_comercial_nao_alteram_nada(self):
        for usuario in (self.tecnico, self.sem_modulo):
            self.client.force_login(usuario)
            for url, dados in self.posts_protegidos():
                with self.subTest(usuario=usuario.username, url=url):
                    r = self.client.post(url, dados)
                    self.assertEqual(r.status_code, 302)
                    self.assertNotIn(self.lead.get_absolute_url() + "?", r["Location"])
            self.confere_nada_mudou()
            for url in (reverse("crm:funil"), reverse("crm:lista"), reverse("crm:detalhe", args=[self.lead.pk])):
                with self.subTest(usuario=usuario.username, get=url):
                    self.assertEqual(self.client.get(url).status_code, 302)

    def test_cliente_do_portal_recebe_403(self):
        self.client.force_login(self.cliente)
        for url, dados in self.posts_protegidos():
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, dados).status_code, 403)
        self.confere_nada_mudou()

    def test_anonimo_vai_para_o_login(self):
        for url, dados in self.posts_protegidos():
            with self.subTest(url=url):
                r = self.client.post(url, dados)
                self.assertEqual(r.status_code, 302)
                self.assertIn("/conta/entrar", r["Location"])
        self.confere_nada_mudou()

    def test_usuario_inativo_nao_tem_modulo(self):
        User.objects.filter(pk=self.comercial.pk).update(is_active=False)
        self.assertFalse(self.client.login(username="com", password="x"))
        self.assertEqual(self.client.post(reverse("crm:mover", args=[self.lead.pk]), {"estagio": "GANHO"}).status_code, 302)
        self.confere_nada_mudou()
