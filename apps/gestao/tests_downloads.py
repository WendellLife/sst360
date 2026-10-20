"""Download autenticado e validação de upload (P1 e P2 do diagnóstico)."""
import shutil
import tempfile
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import TipoUsuario, User
from apps.core.arquivos import nome_uuid
from apps.empresas.models import Empresa
from apps.gestao.importacao import MAX_LINHAS, PlanilhaInvalida, ler_planilha
from apps.gestao.models import Documento, Gestao, ImportacaoPlano
from apps.relacionamento.models import DocumentoSolicitado, StatusDocumento

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
MEDIA = tempfile.mkdtemp(prefix="sst360-teste-")


def tearDownModule():
    shutil.rmtree(MEDIA, ignore_errors=True)


@override_settings(MEDIA_ROOT=MEDIA)
class DownloadAutenticadoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa_a = Empresa.objects.create(razao_social="Empresa A", cnpj="04.252.011/0001-10")
        cls.empresa_b = Empresa.objects.create(razao_social="Empresa B", cnpj="11.222.333/0001-81")
        cls.gestao_a = Gestao.objects.create(empresa=cls.empresa_a)
        cls.gestao_b = Gestao.objects.create(empresa=cls.empresa_b)
        cls.cliente_a = User.objects.create_user("cli_a", "a@t.com.br", "x", tipo=TipoUsuario.CLIENTE, empresa=cls.empresa_a)
        cls.cliente_b = User.objects.create_user("cli_b", "b@t.com.br", "x", tipo=TipoUsuario.CLIENTE, empresa=cls.empresa_b)
        cls.tecnico = User.objects.create_user("tec", "t@t.com.br", "x", acesso_tecnico=True, acesso_comercial=False)
        cls.comercial = User.objects.create_user("com", "c@t.com.br", "x", acesso_comercial=True, acesso_tecnico=False)

    def setUp(self):
        self.doc = Documento.objects.create(gestao=self.gestao_a, titulo="PGR 2026")
        self.doc.arquivo.save("laudo.pdf", ContentFile(PDF))
        self.oculto = Documento.objects.create(gestao=self.gestao_a, titulo="Interno", visivel_cliente=False)
        self.oculto.arquivo.save("interno.pdf", ContentFile(PDF))
        self.pedido = DocumentoSolicitado.objects.create(gestao=self.gestao_a, titulo="ASO")
        self.pedido.arquivo.save("aso.pdf", ContentFile(PDF))
        self.importacao = ImportacaoPlano.objects.create(gestao=self.gestao_a)
        self.importacao.arquivo.save("plano.csv", ContentFile(b"Acao\nx\n"))

    def url_doc(self, d=None):
        return reverse("core:arquivo_documento", args=[(d or self.doc).pk])

    def test_cliente_baixa_o_proprio_arquivo_como_anexo(self):
        self.client.force_login(self.cliente_a)
        r = self.client.get(self.url_doc())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), PDF)
        self.assertTrue(r["Content-Disposition"].startswith("attachment"))
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertIn("PGR 2026", r["Content-Disposition"])

    def test_cliente_de_outra_empresa_nao_baixa(self):
        self.client.force_login(self.cliente_b)
        self.assertEqual(self.client.get(self.url_doc()).status_code, 404)
        self.assertEqual(self.client.get(reverse("core:arquivo_solicitado", args=[self.pedido.pk])).status_code, 404)

    def test_cliente_nao_baixa_documento_nao_visivel_nem_importacao(self):
        self.client.force_login(self.cliente_a)
        self.assertEqual(self.client.get(self.url_doc(self.oculto)).status_code, 404)
        self.assertEqual(self.client.get(reverse("core:arquivo_importacao", args=[self.importacao.pk])).status_code, 404)

    def test_anonimo_vai_para_o_login(self):
        for nome, obj in [("core:arquivo_documento", self.doc), ("core:arquivo_solicitado", self.pedido),
                          ("core:arquivo_importacao", self.importacao)]:
            r = self.client.get(reverse(nome, args=[obj.pk]))
            self.assertEqual(r.status_code, 302, nome)
            self.assertIn(reverse("accounts:login"), r["Location"])

    def test_equipe_so_com_o_modulo_tecnico(self):
        self.client.force_login(self.comercial)
        self.assertEqual(self.client.get(self.url_doc()).status_code, 404)
        self.client.force_login(self.tecnico)
        self.assertEqual(self.client.get(self.url_doc(self.oculto)).status_code, 200)
        self.assertEqual(self.client.get(reverse("core:arquivo_solicitado", args=[self.pedido.pk])).status_code, 200)
        r = self.client.get(reverse("core:arquivo_importacao", args=[self.importacao.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")

    def test_arquivo_ausente_no_disco_vira_404(self):
        self.doc.arquivo.storage.delete(self.doc.arquivo.name)
        self.client.force_login(self.tecnico)
        self.assertEqual(self.client.get(self.url_doc()).status_code, 404)

    def test_extensao_fora_da_lista_sai_como_binario(self):
        legado = Documento.objects.create(gestao=self.gestao_a, titulo="Antigo")
        legado.arquivo.save("pagina.html", ContentFile(b"<script>alert(1)</script>"))
        self.client.force_login(self.cliente_a)
        r = self.client.get(self.url_doc(legado))
        self.assertEqual(r["Content-Type"], "application/octet-stream")
        self.assertTrue(r["Content-Disposition"].startswith("attachment"))

    def test_novo_upload_ganha_nome_uuid_com_a_extensao(self):
        nome = self.doc.arquivo.name
        self.assertTrue(nome.startswith(f"gestoes/documentos/{self.gestao_a.pk}/"), nome)
        self.assertNotIn("laudo", nome)
        self.assertTrue(nome.endswith(".pdf"))
        self.assertRegex(nome_uuid("A B.PDF"), r"^[0-9a-f]{32}\.pdf$")

    def test_templates_usam_a_view_de_download(self):
        self.client.force_login(self.cliente_a)
        html = self.client.get(reverse("portal:documentos")).content.decode()
        self.assertIn(self.url_doc(), html)
        self.assertNotIn("/media/", html)
        self.client.force_login(self.tecnico)
        html = self.client.get(reverse("gestao:detalhe", args=[self.gestao_a.pk])).content.decode()
        self.assertIn(self.url_doc(), html)
        self.assertNotIn("/media/", html)
        html = self.client.get(reverse("relacionamento:painel", args=[self.gestao_a.pk])).content.decode()
        self.assertIn(reverse("core:arquivo_solicitado", args=[self.pedido.pk]), html)
        self.assertNotIn("/media/", html)


@override_settings(MEDIA_ROOT=MEDIA)
class ValidacaoDeUploadTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(razao_social="Empresa A", cnpj="04.252.011/0001-10")
        cls.gestao = Gestao.objects.create(empresa=cls.empresa)
        cls.cliente = User.objects.create_user("cli_a", "a@t.com.br", "x", tipo=TipoUsuario.CLIENTE, empresa=cls.empresa)
        cls.tecnico = User.objects.create_user("tec", "t@t.com.br", "x", acesso_tecnico=True)

    def setUp(self):
        self.pedido = DocumentoSolicitado.objects.create(gestao=self.gestao, titulo="ASO")
        self.client.force_login(self.cliente)
        self.url = reverse("portal:documento_enviar", args=[self.pedido.pk])

    def enviar(self, nome, conteudo):
        return self.client.post(self.url, {"arquivo": SimpleUploadedFile(nome, conteudo)})

    def test_aceita_pdf_valido(self):
        self.enviar("aso.pdf", PDF)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, StatusDocumento.RECEBIDO)
        self.assertTrue(self.pedido.arquivo.name.endswith(".pdf"))

    def test_recusa_html_svg_e_executaveis(self):
        for nome, dados in [("a.html", b"<script>1</script>"), ("a.svg", b"<svg onload=alert(1)>"), ("a.exe", b"MZ"), ("a", PDF)]:
            self.enviar(nome, dados)
            self.pedido.refresh_from_db()
            self.assertFalse(self.pedido.arquivo, nome)
            self.assertEqual(self.pedido.status, StatusDocumento.SOLICITADO, nome)

    def test_recusa_conteudo_que_nao_bate_com_a_extensao(self):
        self.enviar("foto.png", b"<html><script>1</script></html>")
        self.enviar("laudo.pdf", b"<html></html>")
        self.enviar("notas.txt", b"abc\x00def")
        self.pedido.refresh_from_db()
        self.assertFalse(self.pedido.arquivo)

    def test_nao_aceita_reenvio_depois_de_validado(self):
        self.enviar("aso.pdf", PDF)
        DocumentoSolicitado.objects.filter(pk=self.pedido.pk).update(status=StatusDocumento.VALIDADO)
        self.pedido.refresh_from_db()
        antes = self.pedido.arquivo.name
        r = self.enviar("outro.pdf", PDF + b"x")
        self.assertEqual(r.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.arquivo.name, antes)
        self.assertEqual(self.pedido.status, StatusDocumento.VALIDADO)

    def test_reenvio_continua_valido_quando_recusado(self):
        self.enviar("aso.pdf", PDF)
        DocumentoSolicitado.objects.filter(pk=self.pedido.pk).update(status=StatusDocumento.RECUSADO)
        self.enviar("aso2.pdf", PDF + b"x")
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, StatusDocumento.RECEBIDO)

    def test_importacao_recusa_extensao_e_conteudo(self):
        self.client.force_login(self.tecnico)
        url = reverse("gestao:plano_importar", args=[self.gestao.pk])
        r = self.client.post(url, {"arquivo": SimpleUploadedFile("p.html", b"<b>x</b>"), "politica": "atualizar"})
        self.assertContains(r, "xlsx")
        self.client.post(url, {"arquivo": SimpleUploadedFile("p.csv", b"A\x00B"), "politica": "atualizar"})
        self.assertFalse(ImportacaoPlano.objects.exists())

    def test_planilha_com_linhas_demais_e_recusada(self):
        csv_grande = "Ação;Setor\n" + "x;y\n" * MAX_LINHAS
        with self.assertRaises(PlanilhaInvalida):
            ler_planilha(BytesIO(csv_grande.encode()), "grande.csv")
        csv_ok = "Ação;Setor\n" + "x;y\n" * 10
        self.assertEqual(len(ler_planilha(BytesIO(csv_ok.encode()), "ok.csv").linhas), 10)
