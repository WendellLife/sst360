"""Alertas de prazos: janela, destinatários, deduplicação por AvisoPrazo, envio e comando."""
from datetime import date, timedelta
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import TipoUsuario, User
from apps.empresas.models import Empresa
from apps.gestao.models import Gestao, Prazo, StatusPrazo

from .models import AvisoPrazo
from .services import enviar_alertas, montar_resumos, prazos_em_alerta

HOJE = date(2026, 10, 15)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    NOTIFICACOES_SUPERVISAO=["supervisao@exemplo.com.br"],
    PRAZO_ALERTA_DIAS=15,
    SITE_URL="https://sst360.exemplo",
)
class AlertaPrazosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user("ana", "ana@exemplo.com.br", "x", tipo=TipoUsuario.INTERNO,
                                           first_name="Ana", last_name="Souza")
        cls.beto = User.objects.create_user("beto", "beto@exemplo.com.br", "x", tipo=TipoUsuario.INTERNO)
        cls.sem_email = User.objects.create_user("semmail", "", "x", tipo=TipoUsuario.INTERNO)
        empresa = Empresa.objects.create(razao_social="Metalúrgica Teste", cnpj="11.222.333/0001-81")
        cls.gestao = Gestao.objects.create(empresa=empresa)

    def prazo(self, titulo, dias, responsavel=None, status=StatusPrazo.PENDENTE):
        return Prazo.objects.create(gestao=self.gestao, titulo=titulo, data_fim=HOJE + timedelta(days=dias),
                                    responsavel=responsavel, status=status)

    # ------------------------------------------------------------ prazos_em_alerta
    def test_janela_inclui_atrasados_e_limite_e_exclui_o_resto(self):
        atrasado = self.prazo("atrasado", -30)
        hoje = self.prazo("hoje", 0)
        limite = self.prazo("limite", 15)
        fora = self.prazo("fora", 16)
        self.prazo("cumprido", -2, status=StatusPrazo.CUMPRIDO)
        ids = list(prazos_em_alerta(hoje=HOJE).values_list("pk", flat=True))
        self.assertEqual(ids, [atrasado.pk, hoje.pk, limite.pk])
        self.assertNotIn(fora.pk, ids)

    def test_dias_explicito_e_padrao_das_configuracoes(self):
        p = self.prazo("em 20 dias", 20)
        self.assertNotIn(p.pk, [x.pk for x in prazos_em_alerta(hoje=HOJE)])
        self.assertIn(p.pk, [x.pk for x in prazos_em_alerta(dias=20, hoje=HOJE)])
        with override_settings(PRAZO_ALERTA_DIAS=30):
            self.assertIn(p.pk, [x.pk for x in prazos_em_alerta(hoje=HOJE)])

    def test_sem_data_informada_usa_hoje_local(self):
        p = self.prazo("amanhã", 0)
        Prazo.objects.filter(pk=p.pk).update(data_fim=timezone.localdate() + timedelta(days=1))
        self.assertIn(p.pk, [x.pk for x in prazos_em_alerta()])

    # ------------------------------------------------------------ resumos
    def test_resumo_agrupa_por_destinatario_e_classifica(self):
        self.prazo("a1", -3, self.ana)
        self.prazo("a2", 0, self.ana)
        self.prazo("a3", 5, self.ana)
        self.prazo("b1", 2, self.beto)
        resumos = {r.email: r for r in montar_resumos(hoje=HOJE)}
        self.assertEqual(set(resumos), {"ana@exemplo.com.br", "beto@exemplo.com.br"})
        ana = resumos["ana@exemplo.com.br"]
        self.assertEqual(ana.nome, "Ana Souza")
        self.assertEqual([p.titulo for p in ana.atrasados], ["a1"])
        self.assertEqual([p.titulo for p in ana.vencem_hoje], ["a2"])
        self.assertEqual([p.titulo for p in ana.proximos], ["a3"])
        self.assertEqual(ana.total, 3)
        self.assertEqual(resumos["beto@exemplo.com.br"].nome, "beto")
        self.assertTrue(ana.assunto.endswith("Prazos de SST: 1 atrasado(s), 1 vence(m) hoje, 1 a vencer"))

    def test_sem_responsavel_ou_sem_email_vai_para_a_supervisao(self):
        self.prazo("órfão", 1)
        self.prazo("responsável sem e-mail", 1, self.sem_email)
        resumos = montar_resumos(hoje=HOJE)
        self.assertEqual([r.email for r in resumos], ["supervisao@exemplo.com.br"])
        self.assertEqual(resumos[0].nome, "Supervisao")
        self.assertEqual(resumos[0].total, 2)

    def test_sem_supervisao_e_sem_responsavel_ninguem_recebe(self):
        self.prazo("órfão", 1)
        with override_settings(NOTIFICACOES_SUPERVISAO=[]):
            self.assertEqual(montar_resumos(hoje=HOJE), [])
            self.assertEqual(enviar_alertas(hoje=HOJE), [])
        self.assertEqual(len(mail.outbox), 0)

    # ------------------------------------------------------------ envio
    def test_envia_um_email_por_destinatario_e_registra_aviso(self):
        a = self.prazo("Vence hoje", 0, self.ana)
        b = self.prazo("Atrasado", -4, self.ana)
        c = self.prazo("Do Beto", 3, self.beto)
        enviados = enviar_alertas(hoje=HOJE)
        self.assertEqual(len(enviados), 2)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["ana@exemplo.com.br", "beto@exemplo.com.br"])
        msg = next(m for m in mail.outbox if m.to == ["ana@exemplo.com.br"])
        self.assertIn("Prazos de SST", msg.subject)
        self.assertIn("Vence hoje", msg.body)
        self.assertIn("Atrasado", msg.body)
        self.assertNotIn("Do Beto", msg.body)
        self.assertEqual(msg.alternatives[0][1], "text/html")
        self.assertEqual(set(AvisoPrazo.objects.values_list("prazo_id", "destinatario")),
                         {(a.pk, "ana@exemplo.com.br"), (b.pk, "ana@exemplo.com.br"), (c.pk, "beto@exemplo.com.br")})

    def test_nao_repete_no_mesmo_dia_mas_avisa_o_que_e_novo(self):
        self.prazo("primeiro", 1, self.ana)
        enviar_alertas(hoje=HOJE)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(enviar_alertas(hoje=HOJE), [])
        self.assertEqual(len(mail.outbox), 1)
        self.prazo("segundo", 2, self.ana)
        enviados = enviar_alertas(hoje=HOJE)
        self.assertEqual([p.titulo for p in enviados[0].prazos], ["segundo"])
        self.assertEqual(len(mail.outbox), 2)
        self.assertNotIn("primeiro", mail.outbox[1].body)

    def test_no_dia_seguinte_avisa_de_novo(self):
        self.prazo("pendente", 5, self.ana)
        enviar_alertas(hoje=HOJE)
        enviar_alertas(hoje=HOJE + timedelta(days=1))
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(AvisoPrazo.objects.count(), 2)

    def test_constraint_impede_aviso_duplicado(self):
        p = self.prazo("x", 1, self.ana)
        AvisoPrazo.objects.create(prazo=p, destinatario="ana@exemplo.com.br", data=HOJE)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AvisoPrazo.objects.create(prazo=p, destinatario="ana@exemplo.com.br", data=HOJE)

    def test_simular_nao_envia_nem_registra(self):
        self.prazo("p", 1, self.ana)
        enviados = enviar_alertas(simular=True, hoje=HOJE)
        self.assertEqual(len(enviados), 1)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AvisoPrazo.objects.count(), 0)
        # simular não consome o aviso: o envio real ainda acontece
        self.assertEqual(len(enviar_alertas(hoje=HOJE)), 1)

    def test_simular_ignora_o_que_ja_foi_avisado(self):
        self.prazo("p", 1, self.ana)
        enviar_alertas(hoje=HOJE)
        self.assertEqual(len(enviar_alertas(simular=True, hoje=HOJE)), 1)

    def test_para_redireciona_e_registra_o_destinatario_original(self):
        p = self.prazo("p", 1, self.ana)
        enviados = enviar_alertas(para="teste@exemplo.com.br", hoje=HOJE)
        self.assertEqual(mail.outbox[0].to, ["teste@exemplo.com.br"])
        self.assertIn("redirecionado de ana@exemplo.com.br", enviados[0].nome)
        self.assertTrue(AvisoPrazo.objects.filter(prazo=p, destinatario="ana@exemplo.com.br").exists())

    def test_falha_de_um_envio_nao_derruba_os_outros(self):
        self.prazo("da Ana", 1, self.ana)
        self.prazo("do Beto", 1, self.beto)
        original = EmailMultiAlternatives.send

        def send(msg, *a, **k):
            if msg.to == ["ana@exemplo.com.br"]:
                raise OSError("SMTP fora do ar")
            return original(msg, *a, **k)

        with mock.patch.object(EmailMultiAlternatives, "send", send), self.assertLogs("apps.notificacoes.services", "ERROR"):
            enviados = enviar_alertas(hoje=HOJE)
        self.assertEqual([r.email for r in enviados], ["beto@exemplo.com.br"])
        self.assertEqual([m.to[0] for m in mail.outbox], ["beto@exemplo.com.br"])
        # quem falhou não é marcado como avisado e será tentado de novo
        self.assertFalse(AvisoPrazo.objects.filter(destinatario="ana@exemplo.com.br").exists())
        self.assertEqual([r.email for r in enviar_alertas(hoje=HOJE)], ["ana@exemplo.com.br"])

    def test_prazo_cumprido_depois_nao_volta(self):
        p = self.prazo("p", 1, self.ana)
        Prazo.objects.filter(pk=p.pk).update(status=StatusPrazo.CUMPRIDO)
        self.assertEqual(enviar_alertas(hoje=HOJE), [])

    # ------------------------------------------------------------ comando
    def test_comando_sem_prazos(self):
        saida = StringIO()
        call_command("alertar_prazos", stdout=saida)
        self.assertIn("Nenhum prazo a comunicar hoje.", saida.getvalue())
        self.assertEqual(len(mail.outbox), 0)

    def test_comando_envia_e_depois_nao_repete(self):
        # data relativa a hoje real: o comando não aceita a data como argumento
        Prazo.objects.create(gestao=self.gestao, titulo="p", data_fim=timezone.localdate() + timedelta(days=1),
                             responsavel=self.ana)
        saida = StringIO()
        call_command("alertar_prazos", stdout=saida)
        texto = saida.getvalue()
        self.assertIn("Enviado para ana@exemplo.com.br: 1 prazo(s)", texto)
        self.assertIn("1 e-mail(s), 1 prazo(s).", texto)
        self.assertEqual(len(mail.outbox), 1)
        saida = StringIO()
        call_command("alertar_prazos", stdout=saida)
        self.assertIn("Nenhum prazo a comunicar hoje.", saida.getvalue())
        self.assertEqual(len(mail.outbox), 1)

    def test_comando_simular_lista_sem_enviar(self):
        Prazo.objects.create(gestao=self.gestao, titulo="Renovar PGR", data_fim=timezone.localdate() + timedelta(days=1),
                             responsavel=self.ana)
        saida = StringIO()
        call_command("alertar_prazos", "--simular", stdout=saida)
        texto = saida.getvalue()
        self.assertIn("Seria enviado para ana@exemplo.com.br", texto)
        self.assertIn("Renovar PGR", texto)
        self.assertIn("Modo simulacao: nada foi enviado.", texto)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AvisoPrazo.objects.count(), 0)

    def test_comando_dias_e_para(self):
        Prazo.objects.create(gestao=self.gestao, titulo="longe", data_fim=timezone.localdate() + timedelta(days=40),
                             responsavel=self.ana)
        saida = StringIO()
        call_command("alertar_prazos", stdout=saida)
        self.assertEqual(len(mail.outbox), 0)
        call_command("alertar_prazos", "--dias", "60", "--para", "teste@exemplo.com.br", stdout=saida)
        self.assertEqual(mail.outbox[0].to, ["teste@exemplo.com.br"])
