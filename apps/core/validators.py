"""Validadores de documentos brasileiros."""
import re

from django.core.exceptions import ValidationError


def somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def validar_cnpj(valor: str) -> None:
    cnpj = somente_digitos(valor)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        raise ValidationError("CNPJ invalido.")

    def digito(base: str, pesos: list[int]) -> str:
        soma = sum(int(d) * p for d, p in zip(base, pesos))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    if digito(cnpj[:12], pesos1) != cnpj[12] or digito(cnpj[:13], pesos2) != cnpj[13]:
        raise ValidationError("CNPJ invalido.")


def formatar_cnpj(valor: str) -> str:
    cnpj = somente_digitos(valor)
    if len(cnpj) != 14:
        return valor or ""
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
