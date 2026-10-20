"""Régua de relacionamento: etapas, geração, e-mail, WhatsApp, cotação e descadastro."""
from datetime import date

from django.core import mail
from django.utils import timezone
from django.test import TestCase, override_settings

from apps.accounts.models import TipoUsuario, User
from apps.crm.models import Estagio, Lead

from . import regua
from .models import Campanha, Canal, Envio, Etapa, Modelo, StatusEnvio


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SITE_URL="https://sst360.exemplo")
class ReguaTest(TestCase):
    def setUp(self):
        self.equipe = User.objects.create_user("equipe", password="x", tipo=TipoUsuario.INTERNO,
                                               first_name="Rita", last_name="Lorenzo", email="rita@exemplo.com")
        self.lead = Lead.objects.create(razao_social="Transportes Alfa", contato_nome="Carla Nunes", contato_email="carla@alfa.com",
                                        contato_telefone="(19) 99812-3344", renovacao_mes=11, responsavel=self.equipe)
        self.sem_mes = Lead.objects.create(razao_social="Escola Beta", contato_email="b@beta.com")
        self.cliente = Lead.objects.create(razao_social="Cliente Gama", contato_email="g@gama.com", estagio=Estagio.GANHO)
        self.campanha = regua.garantir_campanha(2026, 10)
        self.client.login(username="equipe", password="x")

    # ------------------------------------------------------------ regras
    def test_etapa_pela_distancia_ate_a_renovacao(self):
        casos = {8: Etapa.R90, 9: Etapa.R60, 10: Etapa.R30, 11: Etapa.R0, 12: Etapa.MENSAL, 7: Etapa.MENSAL}
        for mes, esperado in casos.items():
            self.assertEqual(regua.etapa_do_lead(self.lead, 2026, mes), esperado, mes)
        self.lead.renovacao_mes = 1  # virada de ano: dezembro está a 1 mês de janeiro
        self.assertEqual(regua.etapa_do_lead(self.lead, 2026, 12), Etapa.R30)
        self.assertEqual(regua.etapa_do_lead(self.sem_mes, 2026, 10), Etapa.MENSAL)

    def test_proxima_renovacao_e_lista(self):
        self.assertEqual(regua.proxima_renovacao(self.lead, date(2026, 10, 16)), date(2026, 11, 1))
        self.lead.renovacao_mes = 3
        self.assertEqual(regua.proxima_renovacao(self.lead, date(2026, 10, 16)), date(2027, 3, 1))

    def test_telefone_whatsapp(self):
        self.assertEqual(regua.telefone_whatsapp("(19) 99812-3344"), "5519998123344")
        self.assertEqual(regua.telefone_whatsapp("+55 11 3333-4444"), "551133334444")
        self.assertEqual(regua.telefone_whatsapp("123"), "")

    def test_publico_exclui_clientes_e_descadastrados(self):
        self.lead.descadastrado_em = timezone.now()
        self.lead.save()
        nomes = set(regua.publico().values_list("razao_social", flat=True))
        self.assertEqual(nomes, {"Escola Beta"})

    def test_gerar_envios_sem_duplicar(self):
        n = regua.gerar_envios(self.campanha)
        self.assertEqual(n[Canal.EMAIL], 2)
        self.assertEqual(n[Canal.WHATSAPP], 1)  # Escola Beta não tem telefone
        self.assertEqual(Envio.objects.get(lead=self.lead, canal=Canal.EMAIL).etapa, Etapa.R30)
        regua.gerar_envios(self.campanha)
        self.assertEqual(Envio.objects.count(), 3)

    # ------------------------------------------------------------ e-mail
    def test_envio_de_email_com_descadastro_e_atividade(self):
        regua.gerar_envios(self.campanha)
        total = regua.enviar_emails(self.campanha, self.equipe)
        self.assertEqual(total["enviados"], 2)
        msg = next(m for m in mail.outbox if m.to == ["carla@alfa.com"])
        self.assertIn("novembro", msg.subject.lower() + msg.body.lower())
        self.assertIn("Carla", msg.body)
        self.assertIn("List-Unsubscribe", msg.extra_headers)
        html = msg.alternatives[0][0]
        self.assertIn("Não quero mais receber", html)
        self.assertIn("https://sst360.exemplo/r/", html)
        self.assertEqual(Envio.objects.filter(status=StatusEnvio.ENVIADO).count(), 2)
        self.assertTrue(self.lead.atividades.filter(titulo__startswith="E-mail da campanha").exists())
        # rodar de novo não reenvia
        self.assertEqual(regua.enviar_emails(self.campanha)["enviados"], 0)

    def test_campo_desconhecido_no_modelo_nao_quebra(self):
        regua.garantir_modelos()
        Modelo.objects.filter(etapa=Etapa.R30).update(assunto="Olá {campo_que_nao_existe} {empresa}")
        regua.gerar_envios(self.campanha)
        regua.enviar_emails(self.campanha)
        assunto = next(m.subject for m in mail.outbox if m.to == ["carla@alfa.com"])
        self.assertEqual(assunto, "Olá {campo_que_nao_existe} Transportes Alfa")

    # ------------------------------------------------------------ links públicos
    def test_proposta_get_so_registra_clique_e_post_registra_pedido(self):
        regua.gerar_envios(self.campanha)
        envio = Envio.objects.get(lead=self.lead, canal=Canal.EMAIL)
        self.client.logout()
        r = self.client.get(f"/r/{envio.token}/")
        self.assertEqual(r.status_code, 200)
        envio.refresh_from_db()
        self.lead.refresh_from_db()
        self.assertIsNotNone(envio.clicado_em)
        self.assertIsNone(self.lead.cotacao_pedida_em)  # robô de e-mail que só abre o link não conta como pedido
        r = self.client.post(f"/r/{envio.token}/")
        self.lead.refresh_from_db()
        self.assertContains(r, "Pedido recebido")
        self.assertIsNotNone(self.lead.cotacao_pedida_em)
        self.assertEqual(self.lead.estagio, Estagio.DIAGNOSTICO)
        self.assertTrue(self.lead.atividades.filter(titulo="Pediu para participar da cotação").exists())
        self.assertTrue(any(m.to == ["rita@exemplo.com"] and "Pedido de cotação" in m.subject for m in mail.outbox))

    def test_descadastro_confirmado_e_um_clique(self):
        regua.gerar_envios(self.campanha)
        envio = Envio.objects.get(lead=self.lead, canal=Canal.EMAIL)
        self.client.logout()
        self.client.get(f"/r/{envio.token}/sair/")
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.descadastrado_em)
        cliente_sem_csrf = self.client_class(enforce_csrf_checks=True)
        r = cliente_sem_csrf.post(f"/r/{envio.token}/sair/", {"List-Unsubscribe": "One-Click"})
        self.assertEqual(r.status_code, 200)
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.descadastrado_em)
        self.assertFalse(Envio.objects.filter(lead=self.lead, status=StatusEnvio.PENDENTE).exists())
        self.assertNotIn(self.lead, list(regua.publico()))

    def test_pixel_marca_abertura(self):
        regua.gerar_envios(self.campanha)
        envio = Envio.objects.get(lead=self.lead, canal=Canal.EMAIL)
        self.client.logout()
        r = self.client.get(f"/r/{envio.token}/a.gif")
        self.assertEqual(r["Content-Type"], "image/gif")
        envio.refresh_from_db()
        self.assertIsNotNone(envio.aberto_em)

    def test_token_invalido(self):
        self.client.logout()
        self.assertEqual(self.client.get("/r/00000000-0000-0000-0000-000000000000/").status_code, 404)

    # ------------------------------------------------------------ painel
    def test_whatsapp_abre_conversa_e_marca_enviado(self):
        regua.gerar_envios(self.campanha)
        envio = Envio.objects.get(lead=self.lead, canal=Canal.WHATSAPP)
        # GET (prefetch, robôs) não grava: volta ao painel e o envio segue pendente
        r = self.client.get(f"/campanhas/envios/{envio.pk}/whatsapp/")
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("wa.me", r["Location"])
        envio.refresh_from_db()
        self.assertEqual(envio.status, StatusEnvio.PENDENTE)
        r = self.client.post(f"/campanhas/envios/{envio.pk}/whatsapp/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("https://wa.me/5519998123344?text="))
        envio.refresh_from_db()
        self.assertEqual(envio.status, StatusEnvio.ENVIADO)
        self.assertEqual(envio.enviado_por, self.equipe)

    def test_paginas_do_painel(self):
        for url in ["/campanhas/", "/campanhas/?mes=2026-10", "/campanhas/?mes=xx", "/campanhas/modelos/", f"/prospeccao/leads/{self.lead.pk}/", "/painel/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.client.post("/campanhas/gerar/", {"mes": "2026-10"})
        envio = Envio.objects.filter(canal=Canal.EMAIL).first()
        self.assertContains(self.client.get(f"/campanhas/envios/{envio.pk}/previa/"), "Não quero mais receber")
        r = self.client.post("/campanhas/enviar-emails/", {"mes": "2026-10"}, follow=True)
        self.assertContains(r, "e-mail(s) enviado(s)")

    def test_modelo_exige_link_no_whatsapp(self):
        regua.garantir_modelos()
        self.client.post("/campanhas/modelos/", {"etapa": "MEN", "assunto": "A", "email": "B", "whatsapp": "sem link"})
        self.assertNotEqual(Modelo.objects.get(etapa="MEN").whatsapp, "sem link")
        self.client.post("/campanhas/modelos/", {"etapa": "MEN", "assunto": "A", "email": "B", "whatsapp": "Oi {link_proposta}"})
        self.assertEqual(Modelo.objects.get(etapa="MEN").whatsapp, "Oi {link_proposta}")

    def test_conteudo_do_mes(self):
        self.client.post("/campanhas/conteudo/", {"mes": "2026-10", "tema": "Tema novo", "conteudo": "Texto novo"})
        self.campanha.refresh_from_db()
        self.assertEqual(self.campanha.tema, "Tema novo")

    def test_cliente_do_portal_nao_acessa(self):
        User.objects.create_user("portal", password="x", tipo=TipoUsuario.CLIENTE)
        self.client.logout()
        self.client.login(username="portal", password="x")
        self.assertEqual(self.client.get("/campanhas/").status_code, 403)

    def test_comando_mensal(self):
        from django.core.management import call_command

        call_command("regua_mensal", "--mes", "2026-10", "--enviar", verbosity=0)
        self.assertEqual(Campanha.objects.get(ano=2026, mes=10).envios.filter(status=StatusEnvio.ENVIADO, canal=Canal.EMAIL).count(), 2)
