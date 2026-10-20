"""Importação do plano de ação: conversores, leitura de .csv/.xlsx, prévia e políticas de duplicidade."""
import io
import shutil
import tempfile
from datetime import date, datetime
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from openpyxl import Workbook

from apps.accounts.models import TipoUsuario, User
from apps.empresas.models import Empresa

from .importacao import (
    PlanilhaInvalida, aplicar_importacao, converter_data, converter_prioridade, converter_risco,
    converter_status, converter_valor, ler_planilha, normalizar, planilha_modelo,
)
from .models import AcaoPlano, Gestao, ImportacaoPlano, Prioridade, StatusAcao, StatusImportacao, TipoRisco

CABECALHO = "Ação;Risco;Setor / GHE;Prioridade;Prazo;Responsável;Status;Custo estimado;Observações"


def csv_bytes(*linhas, cabecalho=CABECALHO, codificacao="utf-8-sig"):
    return "\n".join([cabecalho, *linhas]).encode(codificacao)


def xlsx_bytes(linhas):
    livro = Workbook()
    aba = livro.active
    for linha in linhas:
        aba.append(linha)
    fluxo = io.BytesIO()
    livro.save(fluxo)
    return fluxo.getvalue()


class ConversoresTest(SimpleTestCase):
    def test_normalizar(self):
        self.assertEqual(normalizar("  Setor / GHE "), "setor ghe")
        self.assertEqual(normalizar("Ação Corretiva"), "acao corretiva")
        self.assertEqual(normalizar(None), "")
        self.assertEqual(normalizar(12), "12")

    def test_valor(self):
        casos = {
            "1234.56": "1234.56", "1.234,56": "1234.56", "R$ 1.234,56": "1234.56", "1234,56": "1234.56",
            "1,234.56": "1234.56", "18.500,00": "18500.00", "-50,5": "-50.50",
        }
        for bruto, esperado in casos.items():
            self.assertEqual(converter_valor(bruto), Decimal(esperado), bruto)
        self.assertEqual(converter_valor(10), Decimal("10.00"))
        self.assertEqual(converter_valor(10.5), Decimal("10.50"))
        self.assertEqual(converter_valor(Decimal("3")), Decimal("3.00"))
        self.assertIsNone(converter_valor(None))
        self.assertIsNone(converter_valor("  "))

    def test_valor_invalido(self):
        for bruto in ("abc", "R$", "--", "1.2.3,4,5"):
            with self.subTest(bruto=bruto), self.assertRaises(ValueError):
                converter_valor(bruto)

    def test_data(self):
        esperado = date(2026, 12, 31)
        for bruto in ("31/12/2026", "31/12/26", "2026-12-31", "31-12-2026", "31.12.2026", " 31/12/2026 "):
            self.assertEqual(converter_data(bruto), esperado, bruto)
        self.assertEqual(converter_data(datetime(2026, 12, 31, 10, 30)), esperado)
        self.assertEqual(converter_data(esperado), esperado)
        self.assertIsNone(converter_data(None))
        self.assertIsNone(converter_data(""))

    def test_data_invalida(self):
        for bruto in ("31/02/2026", "amanhã", "2026/12/31", "13/13/2026"):
            with self.subTest(bruto=bruto), self.assertRaises(ValueError):
                converter_data(bruto)

    def test_risco_prioridade_status(self):
        self.assertEqual(converter_risco("Ruído"), TipoRisco.FISICO)
        self.assertEqual(converter_risco("Químico"), TipoRisco.QUIMICO)
        self.assertEqual(converter_risco("Ergonômico"), TipoRisco.ERGONOMICO)
        self.assertEqual(converter_risco(""), TipoRisco.ACIDENTE)
        self.assertEqual(converter_risco(None), TipoRisco.ACIDENTE)
        self.assertEqual(converter_prioridade("ALTA"), Prioridade.ALTA)
        self.assertEqual(converter_prioridade("Crítica"), Prioridade.ALTA)
        self.assertEqual(converter_prioridade("3"), Prioridade.BAIXA)
        self.assertEqual(converter_prioridade(None), Prioridade.MEDIA)
        self.assertEqual(converter_status("Em andamento"), StatusAcao.EM_ANDAMENTO)
        self.assertEqual(converter_status("Concluída"), StatusAcao.CONCLUIDA)
        self.assertEqual(converter_status("concluida em 10/10"), StatusAcao.CONCLUIDA)  # casa por prefixo
        self.assertEqual(converter_status(""), StatusAcao.NAO_INICIADA)

    def test_valores_nao_reconhecidos(self):
        for conversor, bruto in ((converter_risco, "marciano"), (converter_prioridade, "urgentíssima"),
                                 (converter_status, "talvez")):
            with self.subTest(bruto=bruto), self.assertRaises(ValueError):
                conversor(bruto)


class LeituraTest(SimpleTestCase):
    def test_csv_valido_ponto_e_virgula(self):
        dados = csv_bytes(
            "Enclausurar compressor;Físico;Produção;Alta;30/11/2026;Manutenção;Em andamento;18.500,00;Ruído",
            "Instalar exaustão;Químico;Solda;Média;15/12/2026;Engenharia;Não iniciada;42.000,00;",
        )
        r = ler_planilha(io.BytesIO(dados), "plano.csv")
        self.assertEqual(len(r.linhas), 2)
        self.assertEqual(len(r.validas), 2)
        a = r.linhas[0]
        self.assertEqual(a.linha, 2)
        self.assertEqual(a.descricao, "Enclausurar compressor")
        self.assertEqual(a.risco, TipoRisco.FISICO)
        self.assertEqual(a.setor, "Produção")
        self.assertEqual(a.prioridade, Prioridade.ALTA)
        self.assertEqual(a.prazo, date(2026, 11, 30))
        self.assertEqual(a.status, StatusAcao.EM_ANDAMENTO)
        self.assertEqual(a.custo_estimado, Decimal("18500.00"))
        self.assertEqual(r.alta_prioridade, 1)
        self.assertEqual(r.colunas_encontradas["descricao"], 0)
        self.assertEqual(r.colunas_ignoradas, [])

    def test_csv_virgula_latin1_e_colunas_fora_de_ordem(self):
        texto = "Prioridade,Ação,Coluna Extra\nAlta,Trocar extintores,x\nBaixa,Pintar faixas,y"
        r = ler_planilha(io.BytesIO(texto.encode("latin-1")), "plano.csv")
        self.assertEqual([(l.descricao, l.prioridade) for l in r.linhas],
                         [("Trocar extintores", Prioridade.ALTA), ("Pintar faixas", Prioridade.BAIXA)])
        self.assertEqual(r.colunas_ignoradas, ["Coluna Extra"])

    def test_arquivo_em_texto_e_extensao_maiuscula(self):
        r = ler_planilha(io.StringIO("Ação\nUma ação"), "PLANO.CSV")
        self.assertEqual(r.linhas[0].descricao, "Uma ação")

    def test_xlsx_valido(self):
        dados = xlsx_bytes([
            ["Ação", "Risco", "Setor / GHE", "Prioridade", "Prazo", "Custo estimado", "Status"],
            ["Instalar guarda-corpo", "Acidente", "Almoxarifado", "Alta", datetime(2026, 11, 20), 1500.5, "Concluída"],
            ["Revisar PGR", "Gestão", "Todos", None, "15/12/2026", "2.000,00", None],
            [None, None, None, None, None, None, None],  # linha em branco é descartada
        ])
        r = ler_planilha(io.BytesIO(dados), "plano.xlsx")
        self.assertEqual(len(r.linhas), 2)
        a, b = r.linhas
        self.assertEqual((a.prazo, a.custo_estimado, a.status), (date(2026, 11, 20), Decimal("1500.50"), StatusAcao.CONCLUIDA))
        self.assertEqual((b.prazo, b.custo_estimado, b.prioridade), (date(2026, 12, 15), Decimal("2000.00"), Prioridade.MEDIA))
        self.assertEqual(b.linha, 3)

    def test_planilha_modelo_gerada_pelo_sistema_e_legivel(self):
        r = ler_planilha(io.BytesIO(planilha_modelo()), "modelo-plano-de-acao.xlsx")
        self.assertEqual(len(r.linhas), 5)
        self.assertEqual(len(r.validas), 5)
        self.assertEqual(r.alta_prioridade, 3)

    def test_linhas_com_erro_sao_apontadas(self):
        dados = csv_bytes(
            ";Físico;Produção;Alta;30/11/2026;;;;",  # sem ação
            "Ação com data ruim;Físico;;;31/02/2026;;;;",
            "Ação com risco ruim;Marciano;;;;;;;",
            "Ação com custo ruim;;;;;;;abc;",
            "Ação boa;;;;;;;;",
        )
        r = ler_planilha(io.BytesIO(dados), "plano.csv")
        self.assertEqual(len(r.linhas), 5)
        self.assertEqual([l.linha for l in r.invalidas], [2, 3, 4, 5])
        self.assertIn("linha sem ação", r.linhas[0].erros)
        self.assertIn("data invalida", r.linhas[1].erros[0])
        self.assertIn("risco não reconhecido", r.linhas[2].erros[0])
        self.assertIn("valor inválido", r.linhas[3].erros[0])
        self.assertEqual([l.descricao for l in r.validas], ["Ação boa"])

    def test_descricao_longa_e_truncada(self):
        r = ler_planilha(io.BytesIO(csv_bytes("x" * 400 + ";;;;;;;;")), "plano.csv")
        self.assertEqual(len(r.linhas[0].descricao), 250)

    def test_arquivo_invalido(self):
        casos = [
            (io.BytesIO(b""), "vazio.csv", "vazia"),
            (io.BytesIO(b"\n\n;;\n"), "branco.csv", "vazia"),
            (io.BytesIO(b"Risco;Setor\nFisico;Producao"), "sem-acao.csv", "cabecalho"),
            (io.BytesIO("Ação".encode()), "so-cabecalho.csv", "nenhuma linha"),
            (io.BytesIO(b"conteudo"), "plano.pdf", "Formato não suportado"),
            (io.BytesIO(b"nao sou um zip"), "quebrado.xlsx", "Não foi possível abrir"),
        ]
        for arquivo, nome, trecho in casos:
            with self.subTest(nome=nome):
                with self.assertRaises(PlanilhaInvalida) as ctx:
                    ler_planilha(arquivo, nome)
                self.assertIn(trecho, str(ctx.exception))


class BaseImportacao(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tecnico = User.objects.create_user("tec", "tec@exemplo.com.br", "x", tipo=TipoUsuario.INTERNO,
                                               acesso_tecnico=True, acesso_comercial=False)
        cls.comercial = User.objects.create_user("com", "com@exemplo.com.br", "x", tipo=TipoUsuario.INTERNO,
                                                 acesso_comercial=True, acesso_tecnico=False)
        empresa = Empresa.objects.create(razao_social="Metalúrgica Teste", cnpj="11.222.333/0001-81")
        cls.gestao = Gestao.objects.create(empresa=empresa)

    def setUp(self):
        self._media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._media, True)
        sobrescrita = override_settings(MEDIA_ROOT=self._media)
        sobrescrita.enable()
        self.addCleanup(sobrescrita.disable)

    def importacao(self, dados, nome="plano.csv"):
        return ImportacaoPlano.objects.create(
            gestao=self.gestao, enviado_por=self.tecnico, arquivo=SimpleUploadedFile(nome, dados),
        )

    def aplicar(self, dados, politica):
        imp = self.importacao(dados)
        resultado = ler_planilha(io.BytesIO(dados), "plano.csv")
        return imp, aplicar_importacao(imp, resultado, politica)


class AplicarImportacaoTest(BaseImportacao):
    BASE = csv_bytes("Enclausurar compressor;Físico;Produção;Alta;30/11/2026;Manutenção;Em andamento;100,00;obs 1")

    def test_cria_acoes_e_resume_na_importacao(self):
        dados = csv_bytes(
            "Ação A;Físico;Produção;Alta;30/11/2026;Manutenção;;100,00;",
            "Ação B;Químico;Solda;;;;;;",
            "Ação inválida;Marciano;;;;;;;",
        )
        imp, numeros = self.aplicar(dados, "atualizar")
        self.assertEqual(numeros, {"criados": 2, "atualizados": 0, "ignorados": 0, "com_erro": 1})
        self.assertEqual(self.gestao.acoes.count(), 2)
        a = self.gestao.acoes.get(descricao="Ação A")
        self.assertEqual((a.risco, a.setor, a.prioridade, a.prazo, a.custo_estimado),
                         (TipoRisco.FISICO, "Produção", Prioridade.ALTA, date(2026, 11, 30), Decimal("100.00")))
        imp.refresh_from_db()
        self.assertEqual(imp.status, StatusImportacao.CONCLUIDA)
        self.assertEqual((imp.linhas_lidas, imp.linhas_validas, imp.criados, imp.atualizados, imp.ignorados),
                         (3, 2, 2, 0, 1))
        self.assertIn("2 ação(ões) criada(s)", imp.mensagem)

    def test_politica_atualizar_altera_a_existente_sem_zerar_campos_vazios(self):
        self.aplicar(self.BASE, "atualizar")
        novo = csv_bytes("ENCLAUSURAR  compressor;;produção;Média;;;Concluída;;")
        _, numeros = self.aplicar(novo, "atualizar")
        self.assertEqual(numeros, {"criados": 0, "atualizados": 1, "ignorados": 0, "com_erro": 0})
        self.assertEqual(self.gestao.acoes.count(), 1)
        acao = self.gestao.acoes.get()
        self.assertEqual(acao.descricao, "Enclausurar compressor")
        self.assertEqual(acao.prioridade, Prioridade.MEDIA)  # mudou
        self.assertEqual(acao.status, StatusAcao.CONCLUIDA)  # mudou
        self.assertEqual(acao.prazo, date(2026, 11, 30))  # vazio na planilha: mantido
        self.assertEqual(acao.custo_estimado, Decimal("100.00"))
        self.assertEqual(acao.responsavel_empresa, "Manutenção")
        self.assertEqual(acao.observacoes, "obs 1")

    def test_politica_ignorar_mantem_a_existente(self):
        self.aplicar(self.BASE, "atualizar")
        novo = csv_bytes(
            "Enclausurar compressor;;Produção;Baixa;;;;;",
            "Outra ação;;Produção;;;;;;",
        )
        _, numeros = self.aplicar(novo, "ignorar")
        self.assertEqual(numeros, {"criados": 1, "atualizados": 0, "ignorados": 1, "com_erro": 0})
        self.assertEqual(self.gestao.acoes.count(), 2)
        self.assertEqual(self.gestao.acoes.get(descricao="Enclausurar compressor").prioridade, Prioridade.ALTA)

    def test_politica_duplicar_cria_de_novo(self):
        self.aplicar(self.BASE, "atualizar")
        _, numeros = self.aplicar(self.BASE, "duplicar")
        self.assertEqual(numeros["criados"], 1)
        self.assertEqual(self.gestao.acoes.filter(descricao="Enclausurar compressor").count(), 2)

    def test_mesmo_descricao_em_setor_diferente_nao_e_duplicidade(self):
        self.aplicar(self.BASE, "atualizar")
        _, numeros = self.aplicar(csv_bytes("Enclausurar compressor;;Solda;;;;;;"), "atualizar")
        self.assertEqual((numeros["criados"], numeros["atualizados"]), (1, 0))

    def test_repeticao_dentro_da_mesma_planilha_com_ignorar(self):
        dados = csv_bytes("Mesma ação;;Setor;;;;;;", "Mesma ação;;Setor;Alta;;;;;")
        _, numeros = self.aplicar(dados, "ignorar")
        self.assertEqual((numeros["criados"], numeros["ignorados"]), (1, 1))
        self.assertEqual(self.gestao.acoes.count(), 1)

    def test_repeticao_dentro_da_mesma_planilha_com_duplicar(self):
        dados = csv_bytes("Mesma ação;;Setor;;;;;;", "Mesma ação;;Setor;Alta;;;;;")
        _, numeros = self.aplicar(dados, "duplicar")
        self.assertEqual(numeros["criados"], 2)
        self.assertEqual(self.gestao.acoes.count(), 2)

    def test_repeticao_dentro_da_mesma_planilha_com_atualizar(self):
        """Linha repetida na planilha, ação ainda não gravada, política padrão."""
        dados = csv_bytes("Mesma ação;;Setor;;;;;;", "Mesma ação;;Setor;Alta;;;;;")
        _, numeros = self.aplicar(dados, "atualizar")
        self.assertEqual(self.gestao.acoes.count(), 1)
        self.assertEqual(numeros["criados"], 1)

    def test_nao_mistura_gestoes(self):
        outra = Gestao.objects.create(empresa=Empresa.objects.create(razao_social="Outra", cnpj="00.000.000/0001-91"))
        self.aplicar(self.BASE, "atualizar")
        imp = ImportacaoPlano.objects.create(gestao=outra, arquivo=SimpleUploadedFile("p.csv", self.BASE))
        aplicar_importacao(imp, ler_planilha(io.BytesIO(self.BASE), "p.csv"), "atualizar")
        self.assertEqual(self.gestao.acoes.count(), 1)
        self.assertEqual(outra.acoes.count(), 1)


class ImportarPorTelaTest(BaseImportacao):
    def url(self):
        return reverse("gestao:plano_importar", args=[self.gestao.pk])

    def enviar(self, dados, nome="plano.csv", politica="atualizar"):
        return self.client.post(self.url(), {"arquivo": SimpleUploadedFile(nome, dados), "politica": politica})

    def test_previa_nao_grava_acoes_e_confirmacao_grava(self):
        self.client.force_login(self.tecnico)
        dados = csv_bytes("Ação A;Físico;Produção;Alta;30/11/2026;;;;", "Ação B;Marciano;;;;;;;")
        r = self.enviar(dados)
        self.assertEqual(r.status_code, 200)
        resultado = r.context["resultado"]
        self.assertEqual((len(resultado.validas), len(resultado.invalidas)), (1, 1))
        self.assertContains(r, "Ação A")
        self.assertEqual(self.gestao.acoes.count(), 0)
        imp = r.context["importacao"]
        self.assertEqual(imp.status, StatusImportacao.PENDENTE)
        self.assertEqual((imp.linhas_lidas, imp.linhas_validas), (2, 1))

        r = self.client.post(reverse("gestao:plano_importar_confirmar", args=[imp.pk]), {"politica": "atualizar"})
        self.assertRedirects(r, self.gestao.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(list(self.gestao.acoes.values_list("descricao", flat=True)), ["Ação A"])
        imp.refresh_from_db()
        self.assertEqual(imp.status, StatusImportacao.CONCLUIDA)

    def test_confirmar_com_politica_invalida_cai_em_atualizar(self):
        self.client.force_login(self.tecnico)
        self.aplicar(csv_bytes("Ação A;;Setor;Alta;;;;;"), "atualizar")
        imp = self.importacao(csv_bytes("Ação A;;Setor;Baixa;;;;;"))
        self.client.post(reverse("gestao:plano_importar_confirmar", args=[imp.pk]), {"politica": "apagar-tudo"})
        self.assertEqual(self.gestao.acoes.count(), 1)
        self.assertEqual(self.gestao.acoes.get().prioridade, Prioridade.BAIXA)

    def test_xlsx_pela_tela(self):
        self.client.force_login(self.tecnico)
        r = self.enviar(planilha_modelo(), "modelo.xlsx")
        self.assertEqual(len(r.context["resultado"].validas), 5)

    def test_arquivos_rejeitados(self):
        self.client.force_login(self.tecnico)
        casos = [
            (b"x", "plano.pdf", "Envie um arquivo .xlsx ou .csv"),
            (b"Risco;Setor\nA;B", "plano.csv", "cabecalho"),
            (b"", "vazio.csv", "vazio"),
        ]
        for dados, nome, trecho in casos:
            with self.subTest(nome=nome):
                r = self.enviar(dados, nome)
                self.assertEqual(r.status_code, 200)
                self.assertIn("arquivo", r.context["form"].errors)
                self.assertIn(trecho, str(r.context["form"].errors["arquivo"]))
        self.assertEqual(ImportacaoPlano.objects.count(), 0)

    def test_modelo_xlsx_baixa(self):
        self.client.force_login(self.tecnico)
        r = self.client.get(reverse("gestao:plano_modelo"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])
        ler_planilha(io.BytesIO(r.content), "modelo.xlsx")

    def test_so_o_tecnico_importa(self):
        dados = csv_bytes("Ação A;;;;;;;;")
        imp = self.importacao(dados)
        # sem login: vai para o login
        r = self.client.get(self.url())
        self.assertEqual(r.status_code, 302)
        self.assertIn("/conta/entrar", r["Location"])
        # comercial sem módulo técnico: redirecionado, nada é gravado
        self.client.force_login(self.comercial)
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        self.assertEqual(self.enviar(dados).status_code, 302)
        r = self.client.post(reverse("gestao:plano_importar_confirmar", args=[imp.pk]), {"politica": "atualizar"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.gestao.acoes.count(), 0)
        self.assertEqual(ImportacaoPlano.objects.count(), 1)
        self.assertEqual(self.client.get(reverse("gestao:plano_modelo")).status_code, 302)
