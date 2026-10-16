"""Apaga os dados fictícios do seed_demo para começar a usar o SST360 com dados reais.

Remove empresas, gestões (prazos, documentos, treinamentos, plano de ação, FAP), leads, diagnósticos,
vendas, campanhas, relacionamento e avisos, além dos usuários de exemplo (analista, engenheiro, cliente)
e de todos os usuários de portal. Superusuários e demais pessoas da equipe interna continuam.

Uso: python manage.py limpar_dados_demo --confirmar
"""
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Ordem: quem aponta para os outros sai primeiro (há FKs com PROTECT).
APPS = ["campanhas", "vendas", "relacionamento", "notificacoes", "publico", "crm", "gestao"]
USUARIOS_DEMO = ["analista", "engenheiro", "cliente"]


class Command(BaseCommand):
    help = "Apaga os dados fictícios (seed_demo) e deixa o banco pronto para os dados reais."

    def add_arguments(self, parser):
        parser.add_argument("--confirmar", action="store_true", help="Obrigatório: confirma que os dados serão apagados.")

    def handle(self, *args, **opts):
        if not opts["confirmar"]:
            raise CommandError("Nada foi apagado. Rode de novo com --confirmar para apagar os dados de exemplo.")
        User = get_user_model()
        resumo = {}
        with transaction.atomic():
            for rotulo in APPS:
                for modelo in reversed(list(apps.get_app_config(rotulo).get_models())):
                    total, _ = modelo.objects.all().delete()
                    if total:
                        resumo[modelo._meta.verbose_name_plural] = resumo.get(modelo._meta.verbose_name_plural, 0) + total
            portal = User.objects.filter(tipo="CLIENTE")
            demo = User.objects.filter(username__in=USUARIOS_DEMO)
            usuarios = list(portal.values_list("username", flat=True)) + list(demo.values_list("username", flat=True))
            apps.get_model("accounts", "CodigoAcesso").objects.all().delete()
            portal.delete()
            demo.delete()
            empresas, _ = apps.get_model("empresas", "Empresa").objects.all().delete()
        for nome, total in resumo.items():
            self.stdout.write(f"  {nome}: {total}")
        self.stdout.write(f"  empresas e contatos: {empresas}")
        self.stdout.write(f"  usuários removidos: {', '.join(sorted(set(usuarios))) or 'nenhum'}")
        restantes = User.objects.filter(tipo="INTERNO", is_active=True).count()
        self.stdout.write(self.style.SUCCESS(f"Dados de exemplo apagados. Usuários internos que continuam: {restantes}."))
        if not User.objects.filter(is_superuser=True, is_active=True).exists():
            self.stdout.write(self.style.WARNING("Nenhum superusuário ativo: crie um com  python manage.py createsuperuser"))
