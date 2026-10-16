from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import TipoUsuario, User
from apps.empresas.models import Empresa


def usuario(username, **acesso):
    campos = {"acesso_comercial": False, "acesso_tecnico": False, "acesso_admin": False, **acesso}
    u = User.objects.create_user(username, f"{username}@teste.com.br", "senha-forte-123", tipo=TipoUsuario.INTERNO, **campos)
    return u


class PermissoesPorModuloTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.comercial = usuario("comercial", acesso_comercial=True)
        cls.tecnico = usuario("tecnico", acesso_tecnico=True)
        cls.admin = usuario("admin", acesso_admin=True)
        cls.empresa = Empresa.objects.create(razao_social="Empresa Teste", cnpj="04.252.011/0001-10")
        cls.cliente = User.objects.create_user("cli", "cli@teste.com.br", "x", tipo=TipoUsuario.CLIENTE, empresa=cls.empresa)

    def test_painel_so_para_comercial(self):
        self.client.force_login(self.comercial)
        self.assertEqual(self.client.get("/painel/").status_code, 200)
        self.client.force_login(self.tecnico)
        r = self.client.get("/painel/")
        self.assertRedirects(r, reverse("gestao:lista"), fetch_redirect_response=False)

    def test_captacao_bloqueada_para_tecnico(self):
        self.client.force_login(self.tecnico)
        for url in ["/prospeccao/", "/prospeccao/leads/", "/vendas/", "/campanhas/", "/gestao/fap/", "/comercial/tarefas/"]:
            self.assertEqual(self.client.get(url).status_code, 302, url)
        self.assertEqual(self.client.get("/gestao/").status_code, 200)

    def test_gestao_bloqueada_para_comercial(self):
        self.client.force_login(self.comercial)
        self.assertEqual(self.client.get("/gestao/").status_code, 302)
        self.assertEqual(self.client.get("/empresas/").status_code, 200)  # empresas: qualquer módulo

    def test_menu_mostra_so_os_modulos_liberados(self):
        self.client.force_login(self.tecnico)
        html = self.client.get("/gestao/").content.decode()
        self.assertIn("Gestões de SST", html)
        self.assertNotIn(">Funil<", html)
        self.assertNotIn("Usuários e acessos", html)

    def test_pagina_inicial_por_acesso(self):
        self.assertEqual(self.comercial.pagina_inicial(), "core:dashboard")
        self.assertEqual(self.tecnico.pagina_inicial(), "gestao:lista")
        self.assertEqual(self.admin.pagina_inicial(), "accounts:usuarios")
        self.assertEqual(self.cliente.pagina_inicial(), "portal:home")
        self.assertEqual(self.cliente.modulos, [])

    def test_cliente_do_portal_nao_entra_no_painel(self):
        self.client.force_login(self.cliente)
        self.assertNotEqual(self.client.get("/painel/").status_code, 200)

    def test_entrar_com_email(self):
        r = self.client.post("/conta/entrar/", {"username": "COMERCIAL@teste.com.br", "password": "senha-forte-123"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.comercial.pk)


class GestaoDeUsuariosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = usuario("admin", acesso_admin=True)
        cls.comercial = usuario("comercial", acesso_comercial=True)
        cls.empresa = Empresa.objects.create(razao_social="Empresa Teste", cnpj="04.252.011/0001-10")

    def test_so_administracao_ve_usuarios(self):
        self.client.force_login(self.comercial)
        self.assertEqual(self.client.get("/conta/usuarios/").status_code, 302)
        self.client.force_login(self.admin)
        r = self.client.get("/conta/usuarios/")
        self.assertContains(r, "Usuários e acessos")
        self.assertContains(r, "comercial@teste.com.br")

    def base(self, **extra):
        dados = {"first_name": "Ana", "last_name": "Souza", "email": "ana@teste.com.br", "username": "ana",
                 "cargo": "Vendas", "telefone": "", "tipo": "INTERNO", "senha": "Senha-Forte-2026", "is_active": "on"}
        dados.update(extra)
        return dados

    def test_cria_usuario_comercial(self):
        self.client.force_login(self.admin)
        r = self.client.post("/conta/usuarios/novo/", self.base(acesso_comercial="on"))
        self.assertRedirects(r, "/conta/usuarios/", fetch_redirect_response=False)
        ana = User.objects.get(username="ana")
        self.assertEqual(ana.modulos, ["comercial"])
        self.assertTrue(ana.check_password("Senha-Forte-2026"))

    def test_interno_precisa_de_um_modulo(self):
        self.client.force_login(self.admin)
        r = self.client.post("/conta/usuarios/novo/", self.base())
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="ana").exists())

    def test_cliente_precisa_de_empresa_e_nao_ganha_modulos(self):
        self.client.force_login(self.admin)
        r = self.client.post("/conta/usuarios/novo/", self.base(tipo="CLIENTE", acesso_comercial="on"))
        self.assertEqual(r.status_code, 200)
        r = self.client.post("/conta/usuarios/novo/", self.base(tipo="CLIENTE", acesso_comercial="on", empresa=self.empresa.pk))
        self.assertEqual(r.status_code, 302)
        ana = User.objects.get(username="ana")
        self.assertFalse(ana.acesso_comercial)
        self.assertEqual(ana.empresa, self.empresa)

    def test_edita_sem_trocar_senha(self):
        self.client.force_login(self.admin)
        dados = self.base(email="comercial@teste.com.br", username="comercial", senha="", acesso_tecnico="on")
        r = self.client.post(f"/conta/usuarios/{self.comercial.pk}/", dados)
        self.assertEqual(r.status_code, 302)
        self.comercial.refresh_from_db()
        self.assertEqual(self.comercial.modulos, ["tecnico"])
        self.assertTrue(self.comercial.check_password("senha-forte-123"))

    def test_nao_tira_o_proprio_acesso(self):
        self.client.force_login(self.admin)
        dados = self.base(email="admin@teste.com.br", username="admin", senha="", acesso_comercial="on")
        r = self.client.post(f"/conta/usuarios/{self.admin.pk}/", dados)
        self.assertEqual(r.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.acesso_admin)

    def test_email_repetido(self):
        self.client.force_login(self.admin)
        r = self.client.post("/conta/usuarios/novo/", self.base(email="COMERCIAL@teste.com.br", acesso_comercial="on"))
        self.assertContains(r, "Já existe um usuário com esse e-mail.")
