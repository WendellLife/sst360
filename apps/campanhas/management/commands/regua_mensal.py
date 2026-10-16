"""Roda a régua do mês: cria a campanha, gera os envios e, com --enviar, manda os e-mails.

Agendar no servidor para o dia 1º de cada mês, por exemplo no cron:
    0 9 1 * *  cd /caminho/sst360 && python manage.py regua_mensal --enviar
O WhatsApp fica na fila do painel (Campanhas) para o comercial enviar.
"""
from django.core.management.base import BaseCommand

from apps.campanhas import regua
from apps.campanhas.models import Canal


class Command(BaseCommand):
    help = "Gera os envios da campanha do mês e, com --enviar, manda os e-mails."

    def add_arguments(self, parser):
        parser.add_argument("--enviar", action="store_true", help="Envia os e-mails pendentes.")
        parser.add_argument("--mes", help="AAAA-MM (padrão: mês atual).")

    def handle(self, *args, **opcoes):
        if opcoes.get("mes"):
            ano, mes = (int(x) for x in opcoes["mes"].split("-"))
            campanha = regua.garantir_campanha(ano, mes)
        else:
            campanha = regua.campanha_atual()
        regua.garantir_modelos()
        novos = regua.gerar_envios(campanha)
        self.stdout.write(f"Campanha de {campanha.rotulo}: {novos[Canal.EMAIL]} e-mail(s) e {novos[Canal.WHATSAPP]} WhatsApp novos na fila.")
        if opcoes["enviar"]:
            t = regua.enviar_emails(campanha)
            self.stdout.write(self.style.SUCCESS(f"E-mails: {t['enviados']} enviado(s), {t['falhas']} falha(s), {t['pulados']} pulado(s)."))
