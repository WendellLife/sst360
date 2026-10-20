"""Acelera a suíte inteira sem tocar na configuração de produção.

O Django importa todos os módulos de teste antes de executar qualquer teste; este módulo troca, só
nesse processo, o hash de senha (PBKDF2, caro de propósito) por MD5. Cada create_user/login dos testes
custa então microssegundos. Não afeta o servidor nem o `check --deploy`.
Rodando um único módulo (ex.: `manage.py test apps.campanhas`) este arquivo não é importado e a suíte
volta ao hash padrão: continua correta, só mais lenta.
"""
from django.test import override_settings

_RAPIDO = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
_RAPIDO.enable()
