"""Travas dos comandos que mexem em dados em massa: fora do modo de desenvolvimento exigem confirmação extra."""
from django.conf import settings
from django.core.management.base import CommandError
from django.db import connection


def ambiente_livre() -> bool:
    """Desenvolvimento (DEBUG) ou suíte de testes: os comandos rodam sem confirmação extra."""
    return bool(settings.DEBUG or getattr(settings, "EM_TESTE", False))


def exigir_para_seed(senha_explicita: bool, permitir_producao: bool) -> None:
    if ambiente_livre():
        return
    if not (senha_explicita and permitir_producao):
        raise CommandError(
            "seed_demo cria usuários internos com senha conhecida e não roda com DEBUG=False. "
            "Para forçar (não recomendado em produção real), passe --senha <senha forte> e --permitir-producao."
        )


def exigir_para_limpeza(banco_informado: str | None) -> None:
    if ambiente_livre():
        return
    nome = connection.settings_dict["NAME"]
    if not banco_informado or banco_informado != str(nome):
        raise CommandError(
            "Com DEBUG=False, limpar_dados_demo apaga dados reais e exige --banco <nome do banco configurado> "
            f"além de --confirmar (banco atual: {nome})."
        )
