"""Reproduções de bugs de produção ainda não corrigidos. NÃO entram na suíte (o nome não começa com `tests`).

Rodar uma a uma:  python manage.py test apps.core.bugs_conhecidos --noinput
Quando o Forja corrigir um bug, mova o teste para o app correspondente (tests*.py).
"""
import shutil
import tempfile

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import TipoUsuario, User
from apps.empresas.models import Empresa
from apps.gestao.models import Gestao
from apps.relacionamento.models import DocumentoSolicitado, StatusDocumento


class BugPortalEnvioSemArquivo(TestCase):
    """BUG-1: POST em portal:documento_enviar sem o campo `arquivo` dá HTTP 500.

    EnvioDocumentoForm.clean_arquivo usa `arquivo.size` mas o campo é blank=True, então `arquivo` pode ser None.
    Esperado: voltar ao portal com a mensagem de erro e status do pedido inalterado.
    """

    def test_post_sem_arquivo(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, True)
        with override_settings(MEDIA_ROOT=media):
            empresa = Empresa.objects.create(razao_social="Alfa", cnpj="11.222.333/0001-81")
            gestao = Gestao.objects.create(empresa=empresa)
            usuario = User.objects.create_user("cli", "c@x.com", "x", tipo=TipoUsuario.CLIENTE, empresa=empresa)
            pedido = DocumentoSolicitado.objects.create(gestao=gestao, titulo="Laudo")
            self.client.force_login(usuario)
            r = self.client.post(reverse("portal:documento_enviar", args=[pedido.pk]), {})
            self.assertEqual(r.status_code, 302)
            pedido.refresh_from_db()
            self.assertEqual(pedido.status, StatusDocumento.SOLICITADO)
