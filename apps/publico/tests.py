"""Fluxo público do diagnóstico: perguntas na sessão, resultado, contato, WhatsApp e lead no CRM."""
from urllib.parse import parse_qs, urlparse

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import TipoUsuario, User
from apps.crm.models import Estagio, Lead, OrigemLead
from apps.crm.models import Urgencia as UrgenciaLead

from .conteudo import PERGUNTAS_QUIZ, PONTUACAO_MAXIMA, TOTAL_PERGUNTAS
from .models import Diagnostico, Urgencia


def responder_tudo(client, escolher):
    """Responde o quiz inteiro; `escolher(pergunta)` devolve o índice da opção. Devolve a última resposta."""
    resposta = None
    for pergunta in PERGUNTAS_QUIZ:
        resposta = client.post(reverse("publico:quiz"), {"opcao": escolher(pergunta)})
    return resposta


def indice_pelo_valor(pergunta, alvo):
    """Índice da primeira opção cuja pontuação é a menor (alvo='min') ou maior (alvo='max')."""
    valores = [opcao[1] for opcao in pergunta["opcoes"]]
    return valores.index(min(valores) if alvo == "min" else max(valores))


class QuizTest(TestCase):
    def test_sao_as_perguntas_do_conteudo(self):
        # a especificação original falava em 8 perguntas; o conteúdo atual tem mais (ver relatório)
        self.assertEqual(TOTAL_PERGUNTAS, len(PERGUNTAS_QUIZ))
        self.assertGreaterEqual(TOTAL_PERGUNTAS, 8)
        self.assertEqual(len({p["chave"] for p in PERGUNTAS_QUIZ}), TOTAL_PERGUNTAS)

    def test_primeira_pergunta_abre_sem_login(self):
        r = self.client.get(reverse("publico:quiz"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["numero"], 1)
        self.assertEqual(r.context["total"], TOTAL_PERGUNTAS)
        self.assertFalse(r.context["pode_voltar"])
        self.assertContains(r, PERGUNTAS_QUIZ[0]["texto"])

    def test_avanca_uma_pergunta_por_vez_e_guarda_na_sessao(self):
        r = self.client.post(reverse("publico:quiz"), {"opcao": "0"})
        self.assertRedirects(r, reverse("publico:quiz"), fetch_redirect_response=False)
        r = self.client.get(reverse("publico:quiz"))
        self.assertEqual(r.context["numero"], 2)
        self.assertTrue(r.context["pode_voltar"])
        self.assertContains(r, PERGUNTAS_QUIZ[1]["texto"])
        self.assertEqual(Diagnostico.objects.count(), 0)

    def test_opcao_invalida_nao_avanca(self):
        for valor in ("", "abc", "-1", "99", "1.5"):
            with self.subTest(valor=valor):
                r = self.client.post(reverse("publico:quiz"), {"opcao": valor})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.context["numero"], 1)
                self.assertIn("Escolha uma das opções", r.context["erro"])
        self.assertEqual(Diagnostico.objects.count(), 0)

    def test_voltar_e_reiniciar(self):
        self.client.post(reverse("publico:quiz"), {"opcao": "0"})
        self.client.post(reverse("publico:quiz"), {"opcao": "0"})
        self.assertEqual(self.client.get(reverse("publico:quiz")).context["numero"], 3)
        r = self.client.post(reverse("publico:quiz_voltar"))
        self.assertRedirects(r, reverse("publico:quiz"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("publico:quiz")).context["numero"], 2)
        self.assertEqual(self.client.get(reverse("publico:quiz"), {"reiniciar": "1"}).context["numero"], 1)
        # voltar sem respostas não quebra
        self.client.post(reverse("publico:quiz_voltar"))
        self.assertEqual(self.client.get(reverse("publico:quiz")).context["numero"], 1)

    def test_voltar_so_aceita_post(self):
        self.assertEqual(self.client.get(reverse("publico:quiz_voltar")).status_code, 405)

    def test_ultima_resposta_cria_diagnostico_e_redireciona_ao_resultado(self):
        r = responder_tudo(self.client, lambda p: indice_pelo_valor(p, "max"))
        d = Diagnostico.objects.get()
        self.assertRedirects(r, reverse("publico:resultado", args=[d.token]), fetch_redirect_response=False)
        self.assertEqual(len(d.respostas), TOTAL_PERGUNTAS)
        self.assertEqual([x["chave"] for x in d.respostas], [p["chave"] for p in PERGUNTAS_QUIZ])
        self.assertEqual(d.pontuacao, sum(x["pontos"] for x in d.respostas))
        self.assertEqual(d.pontuacao, PONTUACAO_MAXIMA)
        self.assertEqual(d.urgencia, Urgencia.ALTA)
        self.assertFalse(d.tem_contato)
        # a sessão é limpa: o quiz recomeça
        self.assertEqual(self.client.get(reverse("publico:quiz")).context["numero"], 1)

    def test_urgencia_pelas_faixas_de_pontuacao(self):
        r = responder_tudo(self.client, lambda p: indice_pelo_valor(p, "min"))
        d = Diagnostico.objects.get()
        self.assertEqual(d.urgencia, Urgencia.da_pontuacao(d.pontuacao))
        self.assertEqual(Urgencia.da_pontuacao(0), Urgencia.BAIXA)
        self.assertEqual(Urgencia.da_pontuacao(PONTUACAO_MAXIMA * 0.25), Urgencia.MEDIA)
        self.assertEqual(Urgencia.da_pontuacao(PONTUACAO_MAXIMA * 0.25 - 1), Urgencia.BAIXA)
        self.assertEqual(Urgencia.da_pontuacao(PONTUACAO_MAXIMA * 0.5), Urgencia.ALTA)
        self.assertEqual(Urgencia.da_pontuacao(PONTUACAO_MAXIMA * 0.5 - 1), Urgencia.MEDIA)
        self.assertEqual(r.status_code, 302)

    def test_sessoes_diferentes_nao_se_misturam(self):
        outro = self.client_class()
        self.client.post(reverse("publico:quiz"), {"opcao": "0"})
        self.assertEqual(outro.get(reverse("publico:quiz")).context["numero"], 1)


@override_settings(WHATSAPP_NUMERO="5511999990000")
class ResultadoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente_http = None

    def setUp(self):
        responder_tudo(self.client, lambda p: indice_pelo_valor(p, "max"))
        self.d = Diagnostico.objects.get()
        self.url = reverse("publico:resultado", args=[self.d.token])

    def test_resultado_abre_sem_login_e_mostra_o_diagnostico(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["diagnostico"], self.d)
        self.assertEqual(r.context["prazo"], "30 minutos")
        self.assertTrue(r.context["riscos"])
        self.assertFalse(r.context["ja_enviou"])
        self.assertGreater(r.context["exposicao"]["maximo"], 0)
        self.assertContains(r, "Exposição alta")

    def test_token_desconhecido_da_404(self):
        self.assertEqual(self.client.get(reverse("publico:resultado", args=["00000000-0000-4000-8000-000000000000"])).status_code, 404)
        self.assertEqual(self.client.get("/diagnostico/nao-e-uuid/").status_code, 404)

    def test_contato_exige_telefone_ou_email(self):
        r = self.client.post(self.url, {"nome": "Rita", "empresa": "Alfa"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Informe ao menos um telefone ou um e-mail", str(r.context["form"].non_field_errors()))
        self.d.refresh_from_db()
        self.assertIsNone(self.d.contato_em)
        self.assertFalse(r.context["ja_enviou"])

    def test_email_invalido_e_rejeitado(self):
        r = self.client.post(self.url, {"nome": "Rita", "email": "nao-e-email"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("email", r.context["form"].errors)
        self.d.refresh_from_db()
        self.assertFalse(self.d.tem_contato)

    def test_contato_valido_registra_e_confirma(self):
        r = self.client.post(self.url, {"nome": "Rita Lorenzo", "empresa": "Alfa Ltda", "telefone": "19 99999-0000",
                                        "email": "rita@alfa.com.br"}, follow=True)
        self.assertRedirects(r, self.url)
        self.d.refresh_from_db()
        self.assertTrue(self.d.tem_contato)
        self.assertEqual((self.d.nome, self.d.empresa, self.d.telefone, self.d.email),
                         ("Rita Lorenzo", "Alfa Ltda", "19 99999-0000", "rita@alfa.com.br"))
        self.assertTrue(r.context["ja_enviou"])
        self.assertContains(r, "Contato registrado. Retorno da equipe técnica em até 30 minutos.")
        self.assertEqual(Diagnostico.objects.count(), 1)

    def test_post_nao_altera_respostas_nem_pontuacao(self):
        antes = (self.d.pontuacao, self.d.urgencia, list(self.d.respostas))
        self.client.post(self.url, {"nome": "X", "email": "x@x.com", "pontuacao": "0", "urgencia": "BAIXA",
                                    "respostas": "[]", "lead": "1", "token": "00000000-0000-4000-8000-000000000000"})
        self.d.refresh_from_db()
        self.assertEqual((self.d.pontuacao, self.d.urgencia, list(self.d.respostas)), antes)
        self.assertEqual(str(self.d.token), self.url.split("/")[-2])

    def test_whatsapp_registra_clique_e_redireciona_com_resumo(self):
        r = self.client.get(reverse("publico:whatsapp", args=[self.d.token]))
        self.assertEqual(r.status_code, 302)
        url = urlparse(r["Location"])
        self.assertEqual((url.scheme, url.netloc, url.path), ("https", "wa.me", "/5511999990000"))
        texto = parse_qs(url.query)["text"][0]
        self.assertIn("Diagnóstico de SST", texto)
        self.assertIn(self.d.referencia, texto)
        self.d.refresh_from_db()
        self.assertIsNotNone(self.d.whatsapp_em)

    @override_settings(WHATSAPP_NUMERO="")
    def test_whatsapp_sem_numero_configurado(self):
        r = self.client.get(reverse("publico:whatsapp", args=[self.d.token]))
        self.assertTrue(r["Location"].startswith("https://wa.me/?text="))

    def test_whatsapp_token_desconhecido(self):
        r = self.client.get(reverse("publico:whatsapp", args=["00000000-0000-4000-8000-000000000000"]))
        self.assertEqual(r.status_code, 404)

    def test_resumo_traz_riscos_e_servicos(self):
        texto = self.d.resumo_texto()
        self.assertIn("O que está inadequado", texto)
        self.assertIn("Serviços indicados", texto)
        self.assertTrue(self.d.servicos_indicados)
        exp = self.d.exposicao
        self.assertEqual(exp["riscos"], len(self.d.riscos_identificados))
        self.assertLessEqual(exp["minimo"], exp["maximo"])


class DiagnosticoViraLeadTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.comercial = User.objects.create_user("com", "com@exemplo.com.br", "x", tipo=TipoUsuario.INTERNO,
                                                 acesso_comercial=True, acesso_tecnico=False)
        cls.tecnico = User.objects.create_user("tec", "tec@exemplo.com.br", "x", tipo=TipoUsuario.INTERNO,
                                               acesso_comercial=False, acesso_tecnico=True)

    def setUp(self):
        publico = self.client_class()
        responder_tudo(publico, lambda p: indice_pelo_valor(p, "max"))
        self.d = Diagnostico.objects.get()
        publico.post(reverse("publico:resultado", args=[self.d.token]),
                     {"nome": "Rita", "empresa": "Alfa Ltda", "telefone": "19999990000", "email": "rita@alfa.com.br"})
        self.d.refresh_from_db()

    def test_comercial_cria_lead_a_partir_do_diagnostico(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("crm:diagnostico_lead", args=[self.d.pk]))
        lead = Lead.objects.get()
        self.assertRedirects(r, lead.get_absolute_url(), fetch_redirect_response=False)
        self.d.refresh_from_db()
        self.assertEqual(self.d.lead, lead)
        self.assertEqual(self.d.atendido_por, self.comercial)
        self.assertIsNotNone(self.d.atendido_em)
        self.assertEqual((lead.razao_social, lead.contato_nome, lead.contato_email, lead.contato_telefone),
                         ("Alfa Ltda", "Rita", "rita@alfa.com.br", "19999990000"))
        self.assertEqual((lead.origem, lead.estagio, lead.responsavel), (OrigemLead.SITE, Estagio.NOVO, self.comercial))
        self.assertEqual(lead.urgencia, UrgenciaLead.ALTA)
        self.assertIsNotNone(lead.proximo_contato)
        self.assertNotIn("*", lead.observacoes)
        self.assertEqual(lead.atividades.count(), 1)

    def test_nao_cria_lead_duplicado(self):
        self.client.force_login(self.comercial)
        self.client.post(reverse("crm:diagnostico_lead", args=[self.d.pk]))
        r = self.client.post(reverse("crm:diagnostico_lead", args=[self.d.pk]))
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(r.status_code, 302)

    def test_diagnostico_sem_nome_nem_empresa_usa_referencia(self):
        outro = Diagnostico.objects.create(respostas=[], pontuacao=0, urgencia=Urgencia.BAIXA)
        self.client.force_login(self.comercial)
        self.client.post(reverse("crm:diagnostico_lead", args=[outro.pk]))
        self.assertEqual(Lead.objects.get(diagnostico=outro).razao_social, f"Diagnóstico #{outro.pk}")

    def test_marcar_contato_nao_cria_lead(self):
        self.client.force_login(self.comercial)
        r = self.client.post(reverse("crm:diagnostico_contato", args=[self.d.pk]))
        self.assertRedirects(r, reverse("crm:diagnosticos"), fetch_redirect_response=False)
        self.d.refresh_from_db()
        self.assertEqual(self.d.atendido_por, self.comercial)
        self.assertEqual(Lead.objects.count(), 0)

    def test_lista_filtra_abertos(self):
        self.client.force_login(self.comercial)
        r = self.client.get(reverse("crm:diagnosticos"))
        self.assertEqual(r.context["total_abertos"], 1)
        self.client.post(reverse("crm:diagnostico_lead", args=[self.d.pk]))
        r = self.client.get(reverse("crm:diagnosticos"))
        self.assertEqual(r.context["total_abertos"], 0)
        self.assertEqual(len(r.context["diagnosticos"]), 0)
        r = self.client.get(reverse("crm:diagnosticos"), {"filtro": "ALTA"})
        self.assertEqual(len(r.context["diagnosticos"]), 1)

    def test_sem_modulo_comercial_nao_cria_lead_nem_lista(self):
        self.client.force_login(self.tecnico)
        self.assertEqual(self.client.post(reverse("crm:diagnostico_lead", args=[self.d.pk])).status_code, 302)
        self.assertEqual(self.client.post(reverse("crm:diagnostico_contato", args=[self.d.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse("crm:diagnosticos")).status_code, 302)
        self.assertEqual(Lead.objects.count(), 0)
        self.d.refresh_from_db()
        self.assertIsNone(self.d.atendido_em)

    def test_anonimo_nao_cria_lead(self):
        r = self.client.post(reverse("crm:diagnostico_lead", args=[self.d.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/conta/entrar", r["Location"])
        self.assertEqual(Lead.objects.count(), 0)
