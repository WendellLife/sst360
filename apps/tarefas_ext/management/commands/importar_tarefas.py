"""Traz os clientes do sistema Tarefas para o funil do SST360 como leads (somente leitura no Tarefas).

Cada cliente ativo do Tarefas que ainda não é empresa nem lead no SST360 (cruzamento pelo CNPJ) vira
um lead com o contato principal, origem "Cliente da carteira atual". Rodar de novo não duplica.

Uso: python manage.py importar_tarefas [--responsavel email@empresa.com.br] [--incluir-inativos]
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.tarefas_ext import servicos


class Command(BaseCommand):
    help = "Importa os clientes do sistema Tarefas como leads do SST360."

    def add_arguments(self, parser):
        parser.add_argument("--responsavel", help="E-mail ou usuário de quem fica responsável pelos leads.")
        parser.add_argument("--incluir-inativos", action="store_true", help="Também importa clientes inativos no Tarefas.")

    def handle(self, *args, **opts):
        st = servicos.status()
        if not st["ok"]:
            raise CommandError("Sistema Tarefas não ligado. Configure TAREFAS_DATABASE_URL." if st["motivo"] == "nao_configurado"
                               else f"Não foi possível ler o Tarefas: {st.get('erro', '')}")
        responsavel = None
        if opts["responsavel"]:
            User = get_user_model()
            responsavel = User.objects.filter(email__iexact=opts["responsavel"]).first() or User.objects.filter(username=opts["responsavel"]).first()
            if responsavel is None:
                raise CommandError(f"Usuário {opts['responsavel']} não encontrado.")
        r = servicos.importar_clientes(responsavel, incluir_inativos=opts["incluir_inativos"])
        for lead in r["criados"]:
            self.stdout.write(f"  + {lead.razao_social} ({lead.cnpj})")
        self.stdout.write(self.style.SUCCESS(
            f"{len(r['criados'])} lead(s) criado(s). Já estavam no SST360: {r['ja_existiam']}. Ignorados (inativos): {r['inativos']}."
        ))
