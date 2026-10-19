"""Redirecionamentos a partir de parâmetros vindos do formulário."""
from django.utils.http import url_has_allowed_host_and_scheme


def destino_seguro(request, padrao):
    """O `next` do pedido, só quando aponta para este mesmo site; senão, o destino padrão."""
    proximo = request.POST.get("next") or request.GET.get("next")
    if proximo and url_has_allowed_host_and_scheme(
        proximo, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return proximo
    return padrao
