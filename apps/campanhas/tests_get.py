"""GET sem efeito colateral (P6): WhatsApp só por POST, mês distante não é criado, prefetch não marca."""
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.crm.models import Lead
from apps.publico.models import Diagnostico

from . import regua
from .models import Campanha, Canal, Envio, StatusEnvio


class GetSemEfeitoTest(TestCase):
    def setUp(self):
        User.objects.create_user("equipe", password="x", email="r@e.com")
        self.client.login(username="equipe", password="x")

    def test_painel_nao_cria_campanha_de_mes_distante_por_get(self):
        self.client.get("/campanhas/?mes=2031-05")
        self.assertFalse(Campanha.objects.filter(ano=2031, mes=5).exists())
        self.client.post("/campanhas/gerar/", {"mes": "2031-05"})
        self.assertTrue(Campanha.objects.filter(ano=2031, mes=5).exists())

    def test_painel_usa_form_post_para_o_whatsapp(self):
        Lead.objects.create(razao_social="Alfa", contato_email="a@a.com", contato_telefone="(19) 99812-3344", renovacao_mes=timezone.localdate().month)
        regua.gerar_envios(regua.campanha_atual())
        envio = Envio.objects.get(canal=Canal.WHATSAPP)
        html = self.client.get("/campanhas/").content.decode()
        self.assertIn(f'method="post" action="/campanhas/envios/{envio.pk}/whatsapp/"', html)
        self.assertNotIn(f'href="/campanhas/envios/{envio.pk}/whatsapp/"', html)
        self.assertEqual(envio.status, StatusEnvio.PENDENTE)

    def test_whatsapp_do_diagnostico_so_grava_em_post(self):
        d = Diagnostico.objects.create(urgencia="ALTA")
        url = f"/diagnostico/{d.token}/whatsapp/"
        for extra in ({}, {"HTTP_SEC_PURPOSE": "prefetch"}):
            self.assertEqual(self.client.get(url, **extra).status_code, 302)
        d.refresh_from_db()
        self.assertIsNone(d.whatsapp_em)
        self.assertEqual(self.client.post(url).status_code, 302)
        d.refresh_from_db()
        primeira = d.whatsapp_em
        self.assertIsNotNone(primeira)
        self.client.post(url)
        d.refresh_from_db()
        self.assertEqual(d.whatsapp_em, primeira)

    def test_resultado_usa_form_post_com_csrf_para_o_whatsapp(self):
        from django.template.loader import get_template
        fonte = get_template("publico/resultado.html").template.source
        self.assertNotIn('href="{{ whatsapp }}"', fonte)
        self.assertIn('method="post" action="{{ whatsapp }}"', fonte)
