"""Limite de tentativas, resposta uniforme do pedido de código e conferência atômica (P3 e P4)."""
import threading
from datetime import timedelta
from smtplib import SMTPException
from unittest import mock

from django.contrib.auth.hashers import make_password
from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts import limites
from apps.accounts.codigos import CodigoAcesso, MAX_TENTATIVAS
from apps.accounts.models import TipoUsuario, User
from apps.empresas.models import Empresa


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)


class LoginComLimiteTest(_Base):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("fulano", "f@t.com.br", "senha-certa-123")

    def tentar(self, nome="fulano", senha="errada", ip="10.0.0.1"):
        return self.client.post(reverse("accounts:login"), {"username": nome, "password": senha}, REMOTE_ADDR=ip)

    def test_bloqueia_o_usuario_depois_de_varias_falhas_mesmo_com_a_senha_certa(self):
        for _ in range(limites.LOGIN_POR_USUARIO):
            self.assertEqual(self.tentar().status_code, 200)
        r = self.tentar(senha="senha-certa-123", ip="10.0.0.2")
        self.assertEqual(r.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_bloqueia_o_ip_que_testa_muitos_usuarios(self):
        for i in range(limites.LOGIN_POR_IP):
            self.tentar(nome=f"usuario{i}", ip="10.9.9.9")
        r = self.tentar(nome="fulano", senha="senha-certa-123", ip="10.9.9.9")
        self.assertEqual(r.status_code, 429)
        # outro IP segue normal
        r = self.tentar(nome="fulano", senha="senha-certa-123", ip="10.1.1.1")
        self.assertEqual(r.status_code, 302)

    def test_login_certo_zera_a_contagem_do_usuario(self):
        for _ in range(limites.LOGIN_POR_USUARIO - 1):
            self.tentar()
        self.assertEqual(self.tentar(senha="senha-certa-123").status_code, 302)
        self.client.logout()
        for _ in range(limites.LOGIN_POR_USUARIO - 1):
            self.assertEqual(self.tentar().status_code, 200)

    def test_x_forwarded_for_so_vale_com_proxy_confiavel(self):
        for i in range(limites.LOGIN_POR_IP):
            self.client.post(reverse("accounts:login"), {"username": f"u{i}", "password": "x"},
                             REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR=f"1.1.1.{i}")
        r = self.client.post(reverse("accounts:login"), {"username": "fulano", "password": "senha-certa-123"},
                             REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="9.9.9.9")
        self.assertEqual(r.status_code, 429)  # IP forjado não escapa do limite


class PedirCodigoUniformeTest(_Base):
    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(razao_social="Empresa A", cnpj="04.252.011/0001-10")
        cls.cliente = User.objects.create_user(
            "cli", "cli@t.com.br", "x", tipo=TipoUsuario.CLIENTE, empresa=cls.empresa, telefone="(19) 99999-1234"
        )

    def pedir(self, contato, ip="10.0.0.1"):
        return self.client.post(reverse("accounts:codigo_pedir"), {"contato": contato}, REMOTE_ADDR=ip, follow=True)

    def textos(self, resposta):
        return [str(m) for m in resposta.context["messages"]]

    def test_contato_existente_e_inexistente_respondem_igual(self):
        a = self.pedir("cli@t.com.br")
        sessao_a = self.client.session.get("codigo_usuario_id")
        self.client.cookies.clear()
        b = self.pedir("ninguem@t.com.br")
        sessao_b = self.client.session.get("codigo_usuario_id")
        self.assertEqual(a.redirect_chain, b.redirect_chain)
        self.assertEqual(self.textos(a), self.textos(b))
        self.assertEqual(a.status_code, b.status_code)
        self.assertEqual(sessao_a, self.cliente.pk)
        self.assertEqual(sessao_b, 0)  # sessão presente nos dois casos, só muda o valor interno
        self.assertEqual(len(mail.outbox), 1)

    def test_limite_por_usuario_nao_denuncia_a_existencia_do_contato(self):
        respostas = []
        for _ in range(5):
            respostas.append(self.textos(self.pedir("cli@t.com.br", ip=f"10.0.1.{len(respostas)}")))
        self.assertEqual(len({tuple(r) for r in respostas}), 1)
        self.assertEqual(len(mail.outbox), 3)  # o 4º e o 5º foram contidos pelo limite do usuário

    def test_limite_por_ip_e_por_contato(self):
        for i in range(limites.CODIGO_POR_IP):
            self.client.post(reverse("accounts:codigo_pedir"), {"contato": f"x{i}@t.com.br"}, REMOTE_ADDR="10.5.5.5")
        r = self.client.post(reverse("accounts:codigo_pedir"), {"contato": "cli@t.com.br"}, REMOTE_ADDR="10.5.5.5")
        self.assertEqual(r.status_code, 429)
        for _ in range(limites.CODIGO_POR_CONTATO):
            self.client.post(reverse("accounts:codigo_pedir"), {"contato": "alvo@t.com.br"}, REMOTE_ADDR=f"10.6.6.{_}")
        r = self.client.post(reverse("accounts:codigo_pedir"), {"contato": "alvo@t.com.br"}, REMOTE_ADDR="10.7.7.7")
        self.assertEqual(r.status_code, 429)

    def test_falha_de_smtp_nao_vira_500_e_avisa(self):
        with mock.patch("apps.accounts.codigos.send_mail", side_effect=SMTPException("fora do ar")):
            r = self.pedir("cli@t.com.br")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any("Não conseguimos enviar" in t for t in self.textos(r)))
        self.assertEqual(CodigoAcesso.objects.filter(usuario=self.cliente).count(), 0)  # não gasta o limite

    def test_confirmacao_de_pedido_sem_usuario_imita_codigo_errado(self):
        self.pedir("ninguem@t.com.br")
        url = reverse("accounts:codigo_confirmar")
        textos = []
        for _ in range(MAX_TENTATIVAS + 1):
            textos.append(self.client.post(url, {"codigo": "123456"}, REMOTE_ADDR="10.0.0.1").context["erro"])
        self.assertIn("Restam 4", textos[0])
        self.assertIn("Tentativas demais", textos[-1])

        self.client.cookies.clear()
        self.pedir("cli@t.com.br", ip="10.0.0.2")
        real = self.client.post(url, {"codigo": "000000"}, REMOTE_ADDR="10.0.0.2").context["erro"]
        self.assertEqual(real, textos[0])


class ConfereAtomicoTest(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user("cli", "cli@t.com.br", "x")
        self.registro = CodigoAcesso.objects.create(
            usuario=self.user, codigo_hash=make_password("123456"), expira_em=timezone.now() + timedelta(minutes=10)
        )

    def test_codigo_certo_so_entra_uma_vez(self):
        self.assertTrue(CodigoAcesso.objects.get(pk=self.registro.pk).confere("123456"))
        self.assertFalse(CodigoAcesso.objects.get(pk=self.registro.pk).confere("123456"))

    def test_tentativas_nao_se_perdem_e_valem_ate_o_maximo(self):
        for _ in range(MAX_TENTATIVAS):
            self.assertFalse(CodigoAcesso.objects.get(pk=self.registro.pk).confere("000000"))
        self.assertEqual(CodigoAcesso.objects.get(pk=self.registro.pk).tentativas, MAX_TENTATIVAS)
        self.assertFalse(CodigoAcesso.objects.get(pk=self.registro.pk).confere("123456"))

    def test_concorrencia_com_o_codigo_certo_aceita_um_so(self):
        if connection.vendor != "postgresql":
            self.skipTest("a trava de linha só tem efeito no PostgreSQL")
        resultados, erros = [], []
        barreira = threading.Barrier(8)

        def tentar():
            try:
                registro = CodigoAcesso.objects.get(pk=self.registro.pk)
                barreira.wait(timeout=10)
                resultados.append(registro.confere("123456"))
            except Exception as erro:  # pragma: no cover
                erros.append(erro)
            finally:
                connection.close()

        fios = [threading.Thread(target=tentar) for _ in range(8)]
        [f.start() for f in fios]
        [f.join(30) for f in fios]
        self.assertEqual(erros, [])
        self.assertEqual(resultados.count(True), 1)

    def test_concorrencia_com_codigo_errado_conta_todas_as_tentativas(self):
        if connection.vendor != "postgresql":
            self.skipTest("a trava de linha só tem efeito no PostgreSQL")
        barreira = threading.Barrier(MAX_TENTATIVAS)

        def tentar():
            try:
                registro = CodigoAcesso.objects.get(pk=self.registro.pk)
                barreira.wait(timeout=10)
                registro.confere("000000")
            finally:
                connection.close()

        fios = [threading.Thread(target=tentar) for _ in range(MAX_TENTATIVAS)]
        [f.start() for f in fios]
        [f.join(30) for f in fios]
        self.assertEqual(CodigoAcesso.objects.get(pk=self.registro.pk).tentativas, MAX_TENTATIVAS)
