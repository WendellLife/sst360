"""
Configuracao do projeto SST360.

Le variaveis de ambiente de um arquivo .env (veja .env.example).
"""
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
import os
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


CHAVE_DE_DESENVOLVIMENTO = "dev-insecure-key-trocar-em-producao"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", CHAVE_DE_DESENVOLVIMENTO)
# Desligado por padrão: o modo de desenvolvimento precisa ser pedido (DJANGO_DEBUG=True no .env).
DEBUG = env_bool("DJANGO_DEBUG", False)


def _em_teste() -> bool:
    """`manage.py test`, `python -m django test`, pytest ou DJANGO_TESTING=1."""
    if env_bool("DJANGO_TESTING", False):
        return True
    # Só o subcomando é "test" (manage.py test, python -m django test); `changepassword test` não conta.
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        return True
    programa = os.path.basename(sys.argv[0]).lower() if sys.argv else ""
    return "pytest" in sys.modules or programa.startswith(("pytest", "py.test")) or "PYTEST_CURRENT_TEST" in os.environ


EM_TESTE = _em_teste()
if not DEBUG and not EM_TESTE and (SECRET_KEY == CHAVE_DE_DESENVOLVIMENTO or len(SECRET_KEY) < 50):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "Em produção defina DJANGO_SECRET_KEY com pelo menos 50 caracteres aleatórios "
        "(gere com: python -c \"import secrets; print(secrets.token_urlsafe(64))\")."
    )
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.humanize",
    "django.contrib.staticfiles",
    # terceiros
    "widget_tweaks",
    # locais
    "apps.core",
    "apps.accounts",
    "apps.empresas",
    "apps.gestao",
    "apps.crm",
    "apps.portal",
    "apps.notificacoes",
    "apps.publico",
    "apps.relacionamento",
    "apps.vendas",
    "apps.campanhas",
    "apps.tarefas_ext",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.branding",
            ],
            "builtins": ["apps.core.templatetags.razach"],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = os.getenv("TIME_ZONE", "America/Sao_Paulo")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# O manifesto so existe depois do collectstatic, entao ele e opcional: ligue
# DJANGO_STATIC_MANIFEST=True no servidor, onde o collectstatic roda no deploy.
_ESTATICOS = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
    if env_bool("DJANGO_STATIC_MANIFEST", False)
    else "whitenoise.storage.CompressedStaticFilesStorage"
)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": _ESTATICOS},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Sistema Tarefas (Razach Tarefas Internas): banco próprio, lido pelo SST360 só para consulta.
# Sem TAREFAS_DATABASE_URL, a área "Sistema Tarefas" mostra como ligar. TAREFAS_URL abre o sistema no navegador.
if os.getenv("TAREFAS_DATABASE_URL"):
    DATABASES["tarefas"] = dj_database_url.parse(os.getenv("TAREFAS_DATABASE_URL"), conn_max_age=600)
    if DATABASES["tarefas"]["ENGINE"].endswith("postgresql"):
        # Segunda trava: mesmo que o código tentasse escrever, a sessão do Postgres recusa.
        # PgBouncer em modo transaction rejeita esse parâmetro de startup: use TAREFAS_DB_OPTIONS= (vazio)
        # e garanta a leitura só pelo GRANT SELECT do usuário (README).
        opcoes = os.getenv("TAREFAS_DB_OPTIONS", "-c default_transaction_read_only=on").strip()
        if opcoes:
            DATABASES["tarefas"].setdefault("OPTIONS", {})["options"] = opcoes
if EM_TESTE:
    # Nos testes, o Tarefas é um SQLite em memória com as tabelas criadas pelo próprio teste.
    DATABASES["tarefas"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:", "TEST": {"NAME": ":memory:"}}
# Só os testes (que montam um SQLite próprio para o Tarefas) podem gravar nos models de tarefas_ext.
TAREFAS_ESCRITA_PARA_TESTES = EM_TESTE
# Envio do código de acesso fora do pedido (iguala o tempo de resposta); nos testes roda na hora.
CODIGO_ENVIO_EM_THREAD = not EM_TESTE
DATABASE_ROUTERS = ["apps.tarefas_ext.roteador.RoteadorTarefas"]
TAREFAS_URL = os.getenv("TAREFAS_URL", "")

AUTHENTICATION_BACKENDS = ["apps.accounts.backends.UsuarioOuEmailBackend"]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "accounts:login"

MESSAGE_TAGS = {
    10: "debug",
    20: "info",
    25: "success",
    30: "warning",
    40: "error",
}

# Prazos: quantos dias antes do vencimento um prazo entra no alerta do painel.
PRAZO_ALERTA_DIAS = int(os.getenv("PRAZO_ALERTA_DIAS", "15"))

# Endereco publico do sistema, usado nos links dos e-mails.
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")

# E-mail. Sem SMTP configurado, as mensagens saem no terminal (util em dev).
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "SST360 <nao-responda@localhost>")
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend",
)

# Quem recebe os avisos de prazos sem responsavel definido.
NOTIFICACOES_SUPERVISAO = env_list("NOTIFICACOES_SUPERVISAO")

# Como o codigo de acesso do portal e enviado: "email" (padrao) ou "nenhum"
# enquanto um canal de WhatsApp nao estiver contratado.
CANAL_CODIGO_ACESSO = os.getenv("CANAL_CODIGO_ACESSO", "email")

# Numero de WhatsApp da consultoria, so digitos com DDI (ex.: 5519999998888).
WHATSAPP_NUMERO = os.getenv("WHATSAPP_NUMERO", "").strip()

# Identidade: nome do sistema e da consultoria que o opera.
SISTEMA_NOME = os.getenv("SISTEMA_NOME", "SST360")
CONSULTORIA_NOME = os.getenv("CONSULTORIA_NOME", "Universo FX · Life Laboral")
CONSULTORIA_SITE = os.getenv("CONSULTORIA_SITE", "www.universofx.com.br · www.lifelaboral.com.br")

# Documentos e treinamentos entram no alerta de vencimento com esta antecedencia.
VENCIMENTO_ALERTA_DIAS = int(os.getenv("VENCIMENTO_ALERTA_DIAS", "60"))

if not DEBUG and not EM_TESTE:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", str(60 * 60 * 24 * 30)))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_SUBDOMINIOS", False)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_REFERRER_POLICY = "same-origin"

# Erros e avisos saem no terminal (o servidor de aplicação ou o systemd guardam o registro).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simples": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simples"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"), "propagate": False},
        # 404 e 403 são do dia a dia; erros 500 continuam no registro.
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
# Quem recebe por e-mail os erros 500 em produção (separe por vírgula: "Nome <email>" ou só o e-mail).
ADMINS = [(e.split("<")[0].strip() or e, e.split("<")[-1].strip(">").strip()) for e in env_list("DJANGO_ADMINS")]

# Cache do limite de tentativas de login/código. O padrão (memória) vale por processo; com vários workers do
# gunicorn defina DJANGO_CACHE_DIR para uma pasta compartilhada (cache em arquivos) e o limite vale para todos.
if os.getenv("DJANGO_CACHE_DIR"):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": os.getenv("DJANGO_CACHE_DIR"),
        }
    }
# Quantos proxies confiáveis (nginx, balanceador) ficam entre o cliente e o Django: com 1, o IP vem do X-Forwarded-For.
# Deixe 0 se o Django recebe as conexões direto; assim ninguém forja o IP e escapa do limite.
NUM_PROXIES_CONFIAVEIS = int(os.getenv("DJANGO_NUM_PROXIES", "0"))


if EM_TESTE:
    # Hash rápido só nos testes (o PBKDF2 padrão deixa a suíte lenta); produção não passa por aqui.
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
