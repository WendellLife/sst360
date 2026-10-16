from decimal import Decimal

from .models import Cobranca, StatusVenda


def totais(vendas) -> dict:
    """Totais de uma lista de vendas, sem contar as canceladas."""
    ativas = [v for v in vendas if v.status != StatusVenda.CANCELADA]
    soma = lambda lista: sum((v.total for v in lista), Decimal("0"))  # noqa: E731
    return {
        "quantidade": len(ativas),
        "total": soma(ativas),
        "recebido": soma([v for v in ativas if v.status == StatusVenda.RECEBIDA]),
        "a_receber": soma([v for v in ativas if v.status in (StatusVenda.FECHADA, StatusVenda.FATURADA)]),
        "recorrente": soma([v for v in ativas if v.cobranca == Cobranca.MENSAL]),
        "canceladas": len(vendas) - len(ativas),
    }
