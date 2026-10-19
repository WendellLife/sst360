"""Relacionamento (lado interno): pedir documento, conferir, marcar visita, responder, e permissão por módulo."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import TipoUsuario, User
from apps.empresas.models import Empresa
from apps.gestao.models import Gestao

from .models import DocumentoSolicitado, Mensagem, Reuniao, StatusDocumento, StatusReuniao


class RelacionamentoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tecnico = User.objects.create_user("tec", "tec@exemplo.com.br", "x", tipo=TipoUsuario.INTERNO,
                                               acesso_tecnico=True, acesso_comercial=False)
        cls.comercial = User.objects.create_user("com", "com@exemplo.com.br", "x", tipo=TipoUsuario.INTERNO,
                                                 acesso_comercial=True, acesso_tecnico=False)
        cls.empresa = Empresa.objects.create(razao_social="Empresa Alfa", cnpj="11.222.333/0001-81")
        cls.gestao = Gestao.objects.create(empresa=cls.empresa)
        cls.cliente = User.objects.create_user("cli", "cli@alfa.com", "x", tipo=TipoUsuario.CLIENTE, empresa=cls.empresa)
        cls.pedido = DocumentoSolicitado.objects.create(gestao=cls.gestao, titulo="Laudo ergonômico",
                                                        status=StatusDocumento.RECEBIDO)

    def painel(self):
        return reverse("relacionamento:painel", args=[self.gestao.pk])

    # ------------------------------------------------------------ técnico pode
    def test_painel_abre_e_marca_mensagens_do_cliente_como_lidas(self):
        mensagem = Mensagem.objects.create(gestao=self.gestao, autor=self.cliente, texto="Bom dia")
        self.client.force_login(self.tecnico)
        r = self.client.get(self.painel())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["nao_lidas"], 1)
        mensagem.refresh_from_db()
        self.assertIsNotNone(mensagem.lida_em)
        self.assertEqual(self.client.get(self.painel()).context["nao_lidas"], 0)

    def test_solicitar_documento(self):
        self.client.force_login(self.tecnico)
        r = self.client.post(reverse("relacionamento:documento_solicitar", args=[self.gestao.pk]),
                             {"titulo": "PGR vigente", "motivo": "Auditoria", "prazo": "2026-12-15"})
        self.assertRedirects(r, self.painel(), fetch_redirect_response=False)
        pedido = DocumentoSolicitado.objects.get(titulo="PGR vigente")
        self.assertEqual((pedido.gestao, pedido.solicitado_por, pedido.status),
                         (self.gestao, self.tecnico, StatusDocumento.SOLICITADO))

    def test_solicitar_documento_sem_titulo_nao_grava(self):
        self.client.force_login(self.tecnico)
        self.client.post(reverse("relacionamento:documento_solicitar", args=[self.gestao.pk]), {"titulo": ""})
        self.assertEqual(DocumentoSolicitado.objects.count(), 1)

    def test_conferir_documento(self):
        self.client.force_login(self.tecnico)
        r = self.client.post(reverse("relacionamento:documento_conferir", args=[self.pedido.pk]),
                             {"status": StatusDocumento.RECUSADO, "observacao_equipe": "Ilegível, reenviar"})
        self.assertRedirects(r, self.painel(), fetch_redirect_response=False)
        self.pedido.refresh_from_db()
        self.assertEqual((self.pedido.status, self.pedido.observacao_equipe), (StatusDocumento.RECUSADO, "Ilegível, reenviar"))

    def test_conferir_com_status_invalido_nao_altera(self):
        self.client.force_login(self.tecnico)
        self.client.post(reverse("relacionamento:documento_conferir", args=[self.pedido.pk]), {"status": "XXXX"})
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, StatusDocumento.RECEBIDO)

    def test_registrar_reuniao(self):
        self.client.force_login(self.tecnico)
        quando = (timezone.localtime() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
        r = self.client.post(reverse("relacionamento:reuniao_nova", args=[self.gestao.pk]), {
            "tipo": "VIS", "titulo": "Visita técnica à linha 2", "quando": quando, "duracao_minutos": "90",
            "status": StatusReuniao.AGENDADA, "visivel_cliente": "on",
        })
        self.assertRedirects(r, self.painel(), fetch_redirect_response=False)
        reuniao = Reuniao.objects.get()
        self.assertEqual((reuniao.gestao, reuniao.duracao_minutos, reuniao.visivel_cliente), (self.gestao, 90, True))
        self.assertTrue(reuniao.futura)

    def test_reuniao_aceita_data_no_formato_brasileiro(self):
        self.client.force_login(self.tecnico)
        self.client.post(reverse("relacionamento:reuniao_nova", args=[self.gestao.pk]), {
            "tipo": "REU", "titulo": "Reunião", "quando": "20/11/2026 14:30", "duracao_minutos": "60",
            "status": StatusReuniao.AGENDADA,
        })
        self.assertEqual(timezone.localtime(Reuniao.objects.get().quando).strftime("%d/%m/%Y %H:%M"), "20/11/2026 14:30")

    def test_reuniao_invalida_nao_grava(self):
        self.client.force_login(self.tecnico)
        self.client.post(reverse("relacionamento:reuniao_nova", args=[self.gestao.pk]),
                         {"tipo": "VIS", "titulo": "", "quando": "ontem"})
        self.assertEqual(Reuniao.objects.count(), 0)

    def test_responder_cliente(self):
        self.client.force_login(self.tecnico)
        r = self.client.post(reverse("relacionamento:responder", args=[self.gestao.pk]), {"texto": "Recebemos o arquivo."})
        self.assertRedirects(r, self.painel(), fetch_redirect_response=False)
        mensagem = Mensagem.objects.get()
        self.assertEqual((mensagem.gestao, mensagem.autor, mensagem.texto, mensagem.da_equipe),
                         (self.gestao, self.tecnico, "Recebemos o arquivo.", True))

    def test_resposta_vazia_nao_grava(self):
        self.client.force_login(self.tecnico)
        self.client.post(reverse("relacionamento:responder", args=[self.gestao.pk]), {"texto": ""})
        self.assertEqual(Mensagem.objects.count(), 0)

    def test_gestao_ou_pedido_inexistente_da_404(self):
        self.client.force_login(self.tecnico)
        self.assertEqual(self.client.get(reverse("relacionamento:painel", args=[99999])).status_code, 404)
        self.assertEqual(self.client.post(reverse("relacionamento:responder", args=[99999]), {"texto": "x"}).status_code, 404)
        self.assertEqual(self.client.post(reverse("relacionamento:documento_conferir", args=[99999]), {"status": "VAL"}).status_code, 404)

    # ------------------------------------------------------------ permissão negada
    def posts_protegidos(self):
        g = self.gestao.pk
        quando = "2026-12-01T10:00"
        return [
            (reverse("relacionamento:documento_solicitar", args=[g]), {"titulo": "Invasor"}),
            (reverse("relacionamento:documento_conferir", args=[self.pedido.pk]), {"status": StatusDocumento.VALIDADO}),
            (reverse("relacionamento:reuniao_nova", args=[g]), {"tipo": "VIS", "titulo": "Invasor", "quando": quando,
                                                               "duracao_minutos": "60", "status": "AGEN"}),
            (reverse("relacionamento:responder", args=[g]), {"texto": "Invasor"}),
        ]

    def confere_nada_mudou(self):
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, StatusDocumento.RECEBIDO)
        self.assertEqual(DocumentoSolicitado.objects.count(), 1)
        self.assertEqual(Reuniao.objects.count(), 0)
        self.assertEqual(Mensagem.objects.count(), 0)

    def test_comercial_sem_modulo_tecnico_nao_acessa(self):
        self.client.force_login(self.comercial)
        for url, dados in self.posts_protegidos():
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, dados).status_code, 302)
        self.assertEqual(self.client.get(self.painel()).status_code, 302)
        self.confere_nada_mudou()

    def test_cliente_do_portal_recebe_403(self):
        self.client.force_login(self.cliente)
        for url, dados in self.posts_protegidos():
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, dados).status_code, 403)
        self.assertEqual(self.client.get(self.painel()).status_code, 403)
        self.confere_nada_mudou()

    def test_anonimo_vai_para_o_login(self):
        for url, dados in self.posts_protegidos():
            r = self.client.post(url, dados)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/conta/entrar", r["Location"])
        self.confere_nada_mudou()
