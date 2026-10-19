"""Vendas: lançamento, edição, mudança de status, filtros e permissão por módulo."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import TipoUsuario, User
from apps.empresas.models import Empresa
from apps.gestao.models import Gestao, Servico

from .models import Cobranca, StatusVenda, Venda


class VendasTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.comercial = User.objects.create_user("com", "com@exemplo.com.br", "x", tipo=TipoUsuario.INTERNO,
                                                 acesso_comercial=True, acesso_tecnico=False)
        cls.tecnico = User.objects.create_user("tec", "tec@exemplo.com.br", "x", tipo=TipoUsuario.INTERNO,
                                               acesso_comercial=False, acesso_tecnico=True)
        cls.empresa = Empresa.objects.create(razao_social="Empresa Alfa", cnpj="11.222.333/0001-81")
        cls.outra = Empresa.objects.create(razao_social="Empresa Beta", cnpj="00.000.000/0001-91")
        cls.gestao = Gestao.objects.create(empresa=cls.empresa)
        cls.gestao_outra = Gestao.objects.create(empresa=cls.outra)
        cls.venda = Venda.objects.create(empresa=cls.empresa, servico=Servico.choices[0][0], descricao="Treinamento NR-35",
                                         quantidade=2, valor_unitario=Decimal("150.00"), vendedor=cls.comercial)

    def dados(self, **extra):
        dados = {
            "empresa": self.empresa.pk, "data": timezone.localdate().isoformat(), "servico": Servico.choices[0][0],
            "descricao": "Venda nova", "quantidade": "3", "valor_unitario": "100.00", "cobranca": Cobranca.UNICA,
            "status": StatusVenda.FECHADA, "vendedor": self.comercial.pk,
        }
        dados.update(extra)
        return dados

    # ------------------------------------------------------------ comercial pode
    def test_total_da_venda(self):
        self.assertEqual(self.venda.total, Decimal("300.00"))

    def test_criar_venda(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("vendas:nova"), self.dados(gestao=self.gestao.pk))
        venda = Venda.objects.get(descricao="Venda nova")
        self.assertRedirects(r, self.empresa.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual((venda.total, venda.gestao, venda.empresa), (Decimal("300.00"), self.gestao, self.empresa))

    def test_criar_respeita_next_do_proprio_site(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("vendas:nova"), self.dados(next=reverse("vendas:lista")))
        self.assertRedirects(r, reverse("vendas:lista"), fetch_redirect_response=False)

    def test_criar_ignora_next_externo(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("vendas:nova"), self.dados(next="https://exemplo.invalid/"))
        self.assertEqual(r["Location"], self.empresa.get_absolute_url())

    def test_valida_campos_obrigatorios(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("vendas:nova"), self.dados(descricao="", valor_unitario="", servico="XXX"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual({"descricao", "valor_unitario", "servico"}, set(r.context["form"].errors))
        self.assertEqual(Venda.objects.count(), 1)

    def test_gestao_de_outra_empresa_e_rejeitada(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("vendas:nova"), self.dados(gestao=self.gestao_outra.pk))
        self.assertEqual(r.status_code, 200)
        self.assertIn("gestao", r.context["form"].errors)
        self.assertEqual(Venda.objects.count(), 1)

    def test_erro_vindo_da_pagina_da_empresa_volta_com_mensagem(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("vendas:nova"), self.dados(descricao="", origem="empresa"), follow=True)
        self.assertEqual(Venda.objects.count(), 1)
        self.assertContains(r, "Venda não registrada")

    def test_vendedor_precisa_ser_da_equipe_interna(self):
        cliente = User.objects.create_user("cli", "c@x.com", "x", tipo=TipoUsuario.CLIENTE, empresa=self.outra)
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("vendas:nova"), self.dados(vendedor=cliente.pk))
        self.assertIn("vendedor", r.context["form"].errors)

    def test_editar_venda(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("vendas:editar", args=[self.venda.pk]),
                             self.dados(descricao="Treinamento NR-35 (revisado)", quantidade="5"))
        self.assertEqual(r.status_code, 302)
        self.venda.refresh_from_db()
        self.assertEqual((self.venda.descricao, self.venda.quantidade), ("Treinamento NR-35 (revisado)", 5))

    def test_mudar_status(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("vendas:status", args=[self.venda.pk]), {"status": StatusVenda.RECEBIDA})
        self.assertRedirects(r, self.empresa.get_absolute_url(), fetch_redirect_response=False)
        self.venda.refresh_from_db()
        self.assertEqual(self.venda.status, StatusVenda.RECEBIDA)

    def test_status_invalido_nao_altera(self):
        self.client.force_login(self.comercial)
        self.client.post(reverse("vendas:status", args=[self.venda.pk]), {"status": "VIRA-VINHO"})
        self.venda.refresh_from_db()
        self.assertEqual(self.venda.status, StatusVenda.FECHADA)

    def test_venda_cancelada_sai_do_total_da_lista(self):
        Venda.objects.create(empresa=self.empresa, servico=Servico.choices[0][0], descricao="Cancelada",
                             quantidade=1, valor_unitario=Decimal("1000"), status=StatusVenda.CANCELADA)
        self.client.force_login(self.comercial)
        r = self.client.get(reverse("vendas:lista"))
        self.assertEqual(len(r.context["vendas"]), 2)
        self.assertEqual(sum(x["total"] for x in r.context["por_servico"]), Decimal("300.00"))

    def test_lista_filtra_por_periodo_busca_e_status(self):
        antiga = Venda.objects.create(empresa=self.outra, servico=Servico.choices[0][0], descricao="Antiga",
                                      valor_unitario=Decimal("10"), data=date(2025, 1, 10))
        self.client.force_login(self.comercial)
        self.assertEqual([v.pk for v in self.client.get(reverse("vendas:lista")).context["vendas"]], [self.venda.pk])
        r = self.client.get(reverse("vendas:lista"), {"de": "2025-01-01", "ate": "2025-01-31"})
        self.assertEqual([v.pk for v in r.context["vendas"]], [antiga.pk])
        r = self.client.get(reverse("vendas:lista"), {"de": "2020-01-01", "ate": timezone.localdate().isoformat(), "q": "beta"})
        self.assertEqual([v.pk for v in r.context["vendas"]], [antiga.pk])
        r = self.client.get(reverse("vendas:lista"), {"de": "2020-01-01", "status": StatusVenda.RECEBIDA})
        self.assertEqual(len(r.context["vendas"]), 0)
        # data inválida cai no padrão em vez de quebrar
        self.assertEqual(self.client.get(reverse("vendas:lista"), {"de": "lixo", "ate": "lixo"}).status_code, 200)

    def test_venda_inexistente_da_404(self):
        self.client.force_login(self.comercial)
        self.assertEqual(self.client.post(reverse("vendas:status", args=[99999]), {"status": "REC"}).status_code, 404)
        self.assertEqual(self.client.get(reverse("vendas:editar", args=[99999])).status_code, 404)

    # ------------------------------------------------------------ permissão negada
    def posts_protegidos(self):
        return [
            (reverse("vendas:nova"), self.dados(descricao="Invasor")),
            (reverse("vendas:editar", args=[self.venda.pk]), self.dados(descricao="Invasor")),
            (reverse("vendas:status", args=[self.venda.pk]), {"status": StatusVenda.CANCELADA}),
        ]

    def confere_nada_mudou(self):
        self.venda.refresh_from_db()
        self.assertEqual((self.venda.descricao, self.venda.status), ("Treinamento NR-35", StatusVenda.FECHADA))
        self.assertEqual(Venda.objects.count(), 1)

    def test_tecnico_sem_modulo_comercial_nao_mexe_em_vendas(self):
        self.client.force_login(self.tecnico)
        for url, dados in self.posts_protegidos():
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, dados).status_code, 302)
        self.assertEqual(self.client.get(reverse("vendas:lista")).status_code, 302)
        self.confere_nada_mudou()

    def test_cliente_do_portal_recebe_403(self):
        cliente = User.objects.create_user("cli", "c@x.com", "x", tipo=TipoUsuario.CLIENTE, empresa=self.empresa)
        self.client.force_login(cliente)
        for url, dados in self.posts_protegidos():
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, dados).status_code, 403)
        self.assertEqual(self.client.get(reverse("vendas:lista")).status_code, 403)
        self.confere_nada_mudou()

    def test_anonimo_vai_para_o_login(self):
        for url, dados in self.posts_protegidos():
            r = self.client.post(url, dados)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/conta/entrar", r["Location"])
        self.confere_nada_mudou()
