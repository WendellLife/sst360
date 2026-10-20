"""Limite de tentativas com bloqueio temporário, guardado no cache do Django.

Janela fixa: a primeira falha abre a janela e, ao passar do máximo, a chave fica bloqueada até ela fechar.
O cache padrão (LocMem) é por processo; com vários workers, aponte DJANGO_CACHE_DIR para uma pasta
compartilhada (veja o README) para o limite valer para o conjunto.
"""
import hashlib

from django.conf import settings
from django.core.cache import cache

JANELA_SEGUNDOS = 15 * 60

LOGIN_POR_IP = 20
LOGIN_POR_USUARIO = 5
CODIGO_POR_IP = 10
CODIGO_POR_CONTATO = 5
CONFIRMAR_POR_IP = 30


def ip_do_pedido(request) -> str:
    """IP do cliente. X-Forwarded-For só vale com NUM_PROXIES_CONFIAVEIS > 0 (proxy próprio na frente)."""
    proxies = int(getattr(settings, "NUM_PROXIES_CONFIAVEIS", 0) or 0)
    if proxies > 0:
        cadeia = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        if len(cadeia) >= proxies:
            return cadeia[-proxies]
    return request.META.get("REMOTE_ADDR", "") or "desconhecido"


def _chave(escopo: str, valor: str) -> str:
    return "limite:" + escopo + ":" + hashlib.sha256(valor.strip().lower().encode()).hexdigest()[:32]


def bloqueado(escopo: str, valor: str, maximo: int) -> bool:
    return (cache.get(_chave(escopo, valor)) or 0) >= maximo


def registrar(escopo: str, valor: str, janela: int = JANELA_SEGUNDOS) -> int:
    chave = _chave(escopo, valor)
    if cache.add(chave, 1, janela):
        return 1
    try:
        return cache.incr(chave)
    except ValueError:  # expirou entre o add e o incr
        cache.set(chave, 1, janela)
        return 1


def zerar(escopo: str, valor: str) -> None:
    cache.delete(_chave(escopo, valor))
