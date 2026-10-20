"""Isolamento do portal: o cliente A nunca vê nem altera dados da empresa B, nem entra na área interna."""
import shutil
import tempfile
from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import TipoUsuario, User
from apps.empresas.models import Empresa
from apps.gestao.models import AcaoPlano, Documento, Gestao, Prazo, Registro, Treinamento, TipoTreinamento
from apps.relacionamento.models import DocumentoSolicitado, Mensagem, Reuniao, StatusDocumento


class IsolamentoDoPortalTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.emp_a = Empresa.objects.create(razao_social="Empresa Alfa", cnpj="11.222.333/0001-81")
        cls.emp_b = Empresa.objects.create(razao_social="Empresa Beta", cnpj="00.000.000/0001-91")
        cls.gestao_a = Gestao.objects.create(empresa=cls.emp_a)
        cls.gestao_b = Gestao.objects.create(empresa=cls.emp_b)
        cls.cli_a = User.objects.create_user("cli_a", "a@alfa.com", "x", tipo=TipoUsuario.CLIENTE, empresa=cls.emp_a)
        cls.cli_b = User.objects.create_user("cli_b", "b@beta.com", "x", tipo=TipoUsuario.CLIENTE, empresa=cls.emp_b)
        cls.equipe = User.objects.create_user("equipe", "e@x.com", "x", tipo=TipoUsuario.INTERNO,
                                              acesso_tecnico=True, acesso_comercial=True)

        # dados de A e de B com textos que não podem vazar
        for sufixo, gestao, autor in (("ALFA", cls.gestao_a, cls.cli_a), ("BETA", cls.gestao_b, cls.cli_b)):
            AcaoPlano.objects.create(gestao=gestao, descricao=f"Ação secreta {sufixo}")
            Registro.objects.create(gestao=gestao, titulo=f"Registro secreto {sufixo}")
            Prazo.objects.create(gestao=gestao, titulo=f"Prazo secreto {sufixo}", data_fim=date.today() + timedelta(days=5))
            Documento.objects.create(gestao=gestao, titulo=f"Documento técnico {sufixo}")
            Treinamento.objects.create(gestao=gestao, tipo=TipoTreinamento.NR35, titulo=f"Treino secreto {sufixo}")
            Reuniao.objects.create(gestao=gestao, titulo=f"Reunião secreta {sufixo}",
                                   quando=timezone.now() + timedelta(days=2))
            Mensagem.objects.create(gestao=gestao, autor=autor, texto=f"Conversa secreta {sufixo}")
            DocumentoSolicitado.objects.create(gestao=gestao, titulo=f"Pedido secreto {sufixo}")
        cls.pedido_a = DocumentoSolicitado.objects.get(gestao=cls.gestao_a)
        cls.pedido_b = DocumentoSolicitado.objects.get(gestao=cls.gestao_b)

    def setUp(self):
        self._media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._media, True)
        sobrescrita = override_settings(MEDIA_ROOT=self._media)
        sobrescrita.enable()
        self.addCleanup(sobrescrita.disable)

    # ------------------------------------------------------------ telas do portal
    def test_cada_tela_do_portal_mostra_so_a_propria_empresa(self):
        self.client.force_login(self.cli_a)
        for nome in ("home", "plano", "documentos", "treinamentos", "reunioes", "conversa"):
            with self.subTest(tela=nome):
                r = self.client.get(reverse(f"portal:{nome}"))
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.context["gestao"], self.gestao_a)
                html = r.content.decode()
                self.assertNotIn("BETA", html)
                self.assertNotIn("Empresa Beta", html)

    def test_dados_proprios_aparecem(self):
        self.client.force_login(self.cli_a)
        self.assertContains(self.client.get(reverse("portal:plano")), "Ação secreta ALFA")
        self.assertContains(self.client.get(reverse("portal:documentos")), "Pedido secreto ALFA")
        self.assertContains(self.client.get(reverse("portal:conversa")), "Conversa secreta ALFA")
        self.assertContains(self.client.get(reverse("portal:reunioes")), "Reunião secreta ALFA")

    def test_cliente_b_ve_so_o_que_e_dele(self):
        self.client.force_login(self.cli_b)
        html = self.client.get(reverse("portal:plano")).content.decode()
        self.assertIn("Ação secreta BETA", html)
        self.assertNotIn("ALFA", html)

    def test_linha_do_tempo_da_gestao_de_outra_empresa_da_404(self):
        self.client.force_login(self.cli_a)
        r = self.client.get(reverse("portal:gestao", args=[self.gestao_b.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertNotIn("BETA", r.content.decode())
        r = self.client.get(reverse("portal:gestao", args=[self.gestao_a.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "BETA")
        self.assertEqual(self.client.get(reverse("portal:gestao", args=[999999])).status_code, 404)

    def test_filtro_do_plano_nao_atravessa_empresas(self):
        self.client.force_login(self.cli_a)
        r = self.client.get(reverse("portal:plano"), {"risco": "ACI", "gestao": self.gestao_b.pk, "gestao_id": self.gestao_b.pk})
        self.assertNotContains(r, "BETA")

    # ------------------------------------------------------------ conversa
    def test_mensagem_vai_sempre_para_a_gestao_do_proprio_usuario(self):
        self.client.force_login(self.cli_a)
        r = self.client.post(reverse("portal:conversa"), {"texto": "Olá equipe", "gestao": self.gestao_b.pk,
                                                         "gestao_id": self.gestao_b.pk, "autor": self.cli_b.pk})
        self.assertRedirects(r, reverse("portal:conversa"), fetch_redirect_response=False)
        mensagem = Mensagem.objects.get(texto="Olá equipe")
        self.assertEqual((mensagem.gestao, mensagem.autor), (self.gestao_a, self.cli_a))
        self.assertFalse(Mensagem.objects.filter(gestao=self.gestao_b, texto="Olá equipe").exists())

    def test_mensagem_vazia_nao_grava(self):
        self.client.force_login(self.cli_a)
        antes = Mensagem.objects.count()
        r = self.client.post(reverse("portal:conversa"), {"texto": "  "})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Mensagem.objects.count(), antes)

    def test_equipe_responde_so_na_gestao_certa_e_cliente_a_nao_ve_a_resposta_de_b(self):
        self.client.force_login(self.equipe)
        self.client.post(reverse("relacionamento:responder", args=[self.gestao_b.pk]), {"texto": "Resposta para Beta"})
        self.client.force_login(self.cli_a)
        self.assertNotContains(self.client.get(reverse("portal:conversa")), "Resposta para Beta")
        self.client.force_login(self.cli_b)
        self.assertContains(self.client.get(reverse("portal:conversa")), "Resposta para Beta")

    # ------------------------------------------------------------ envio de documento
    def test_nao_envia_arquivo_para_pedido_de_outra_empresa(self):
        self.client.force_login(self.cli_a)
        r = self.client.post(reverse("portal:documento_enviar", args=[self.pedido_b.pk]),
                             {"arquivo": SimpleUploadedFile("laudo.pdf", b"%PDF-1.4")})
        self.assertEqual(r.status_code, 404)
        self.pedido_b.refresh_from_db()
        self.assertEqual(self.pedido_b.status, StatusDocumento.SOLICITADO)
        self.assertFalse(self.pedido_b.arquivo)

    def test_envia_arquivo_para_o_proprio_pedido(self):
        self.client.force_login(self.cli_a)
        r = self.client.post(reverse("portal:documento_enviar", args=[self.pedido_a.pk]),
                             {"arquivo": SimpleUploadedFile("laudo.pdf", b"%PDF-1.4")})
        self.assertRedirects(r, reverse("portal:documentos"), fetch_redirect_response=False)
        self.pedido_a.refresh_from_db()
        self.assertEqual(self.pedido_a.status, StatusDocumento.RECEBIDO)
        self.assertTrue(self.pedido_a.arquivo.name.startswith(f"solicitacoes/{self.gestao_a.pk}/"))
        self.assertIsNotNone(self.pedido_a.enviado_em)

    def test_envio_so_aceita_post(self):
        self.client.force_login(self.cli_a)
        self.assertEqual(self.client.get(reverse("portal:documento_enviar", args=[self.pedido_a.pk])).status_code, 405)

    # ------------------------------------------------------------ cliente fora da área interna
    def urls_internas(self):
        g = self.gestao_a.pk
        return [
            reverse("gestao:lista"), reverse("gestao:detalhe", args=[g]), reverse("gestao:fap_carteira"),
            reverse("gestao:plano_importar", args=[g]), reverse("gestao:plano_modelo"),
            reverse("gestao:acao_nova", args=[g]), reverse("gestao:documento_novo", args=[g]),
            reverse("relacionamento:painel", args=[g]), reverse("relacionamento:painel", args=[self.gestao_b.pk]),
            reverse("empresas:lista"), reverse("empresas:detalhe", args=[self.emp_b.pk]),
            reverse("crm:funil"), reverse("crm:lista"), reverse("crm:diagnosticos"),
            reverse("vendas:lista"), reverse("core:dashboard"), "/indicadores/", "/busca/?q=Beta",
        ]

    def test_cliente_nao_abre_nenhuma_tela_interna(self):
        self.client.force_login(self.cli_a)
        for url in self.urls_internas():
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertIn(r.status_code, (302, 403, 404), url)
                if r.status_code == 302:
                    self.assertFalse(r["Location"].startswith("/gestao/"), r["Location"])
                self.assertNotIn("Empresa Beta", r.content.decode())

    def test_cliente_nao_altera_pela_area_interna(self):
        self.client.force_login(self.cli_a)
        g = self.gestao_a.pk
        posts = [
            (reverse("relacionamento:responder", args=[g]), {"texto": "invasão"}),
            (reverse("relacionamento:documento_solicitar", args=[g]), {"titulo": "invasão"}),
            (reverse("relacionamento:documento_conferir", args=[self.pedido_a.pk]), {"status": StatusDocumento.VALIDADO}),
            (reverse("gestao:acao_nova", args=[g]), {"descricao": "invasão"}),
            (reverse("gestao:prazo_novo", args=[g]), {"titulo": "invasão", "data_fim": "2026-12-01"}),
            (reverse("vendas:nova"), {"descricao": "invasão"}),
            (reverse("crm:novo"), {"razao_social": "invasão"}),
        ]
        for url, dados in posts:
            with self.subTest(url=url):
                self.assertIn(self.client.post(url, dados).status_code, (302, 403, 404))
        self.pedido_a.refresh_from_db()
        self.assertEqual(self.pedido_a.status, StatusDocumento.SOLICITADO)
        self.assertFalse(Mensagem.objects.filter(texto="invasão").exists())
        self.assertFalse(AcaoPlano.objects.filter(descricao="invasão").exists())
        self.assertFalse(Prazo.objects.filter(titulo="invasão").exists())

    def test_anonimo_vai_para_o_login(self):
        for nome in ("home", "plano", "documentos", "treinamentos", "reunioes", "conversa"):
            r = self.client.get(reverse(f"portal:{nome}"))
            self.assertEqual(r.status_code, 302, nome)
            self.assertIn("/conta/entrar", r["Location"])
        self.assertEqual(self.client.get(reverse("portal:gestao", args=[self.gestao_a.pk])).status_code, 302)
        self.assertEqual(self.client.post(reverse("portal:documento_enviar", args=[self.pedido_a.pk])).status_code, 302)

    def test_equipe_interna_nao_usa_o_portal(self):
        self.client.force_login(self.equipe)
        for nome in ("home", "plano", "documentos", "conversa"):
            self.assertEqual(self.client.get(reverse(f"portal:{nome}")).status_code, 403, nome)
        self.assertEqual(self.client.get(reverse("portal:gestao", args=[self.gestao_a.pk])).status_code, 403)

    def test_cliente_sem_empresa_vinculada_nao_entra(self):
        sem = User.objects.create_user("sem", "s@x.com", "x", tipo=TipoUsuario.CLIENTE)
        self.client.force_login(sem)
        self.assertEqual(self.client.get(reverse("portal:home")).status_code, 403)

    def test_cliente_inativo_nao_entra(self):
        User.objects.filter(pk=self.cli_a.pk).update(is_active=False)
        self.assertFalse(self.client.login(username="cli_a", password="x"))
        self.assertEqual(self.client.get(reverse("portal:home")).status_code, 302)

    def test_portal_de_empresa_sem_gestao_nao_quebra(self):
        vazia = Empresa.objects.create(razao_social="Sem Gestão", cnpj="45.723.174/0001-10")
        usuario = User.objects.create_user("vazio", "v@x.com", "x", tipo=TipoUsuario.CLIENTE, empresa=vazia)
        self.client.force_login(usuario)
        for nome in ("home", "plano", "documentos", "treinamentos", "reunioes", "conversa"):
            self.assertEqual(self.client.get(reverse(f"portal:{nome}")).status_code, 200, nome)
        r = self.client.post(reverse("portal:conversa"), {"texto": "oi"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Mensagem.objects.filter(texto="oi").count(), 0)
