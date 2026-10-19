"""Envio de documento pelo portal sem arquivo: erro de formulário, nunca 500."""
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import TipoUsuario, User
from apps.empresas.models import Empresa
from apps.gestao.models import Gestao

from .forms import EnvioDocumentoForm
from .models import DocumentoSolicitado, StatusDocumento


class EnvioSemArquivoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        empresa = Empresa.objects.create(razao_social="Empresa A", cnpj="04.252.011/0001-10")
        gestao = Gestao.objects.create(empresa=empresa)
        cls.cliente = User.objects.create_user("cli", "c@t.com.br", "x", tipo=TipoUsuario.CLIENTE, empresa=empresa)
        cls.pedido = DocumentoSolicitado.objects.create(gestao=gestao, titulo="ASO")

    def test_formulario_pede_o_arquivo(self):
        form = EnvioDocumentoForm({}, {}, instance=self.pedido)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["arquivo"], ["Selecione um arquivo."])

    def test_post_sem_arquivo_nao_da_500_e_avisa(self):
        self.client.force_login(self.cliente)
        r = self.client.post(reverse("portal:documento_enviar", args=[self.pedido.pk]), {})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(any("Não foi possível enviar" in str(m) for m in get_messages(r.wsgi_request)))
        self.pedido.refresh_from_db()
        self.assertNotEqual(self.pedido.status, StatusDocumento.RECEBIDO)
