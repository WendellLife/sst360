"""Validadores de documentos brasileiros."""
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.core.validators import formatar_cnpj, somente_digitos, validar_cnpj


class CnpjTest(SimpleTestCase):
    def test_somente_digitos(self):
        self.assertEqual(somente_digitos("11.222.333/0001-81"), "11222333000181")
        self.assertEqual(somente_digitos(None), "")
        self.assertEqual(somente_digitos("abc"), "")

    def test_cnpj_valido_com_e_sem_mascara(self):
        validar_cnpj("11.222.333/0001-81")
        validar_cnpj("11222333000181")
        validar_cnpj("00.000.000/0001-91")  # Banco do Brasil

    def test_cnpj_invalido(self):
        invalidos = [
            "", None, "123", "11.222.333/0001-82",  # dígito errado
            "11222333000180", "1122233300018",  # dígito errado / um a menos
            "112223330001811",  # um a mais
            "00000000000000", "11111111111111",  # repetidos
            "abcdefghijklmn",
        ]
        for valor in invalidos:
            with self.subTest(valor=valor), self.assertRaises(ValidationError):
                validar_cnpj(valor)

    def test_formatar_cnpj(self):
        self.assertEqual(formatar_cnpj("11222333000181"), "11.222.333/0001-81")
        self.assertEqual(formatar_cnpj("11.222.333/0001-81"), "11.222.333/0001-81")
        self.assertEqual(formatar_cnpj("123"), "123")
        self.assertEqual(formatar_cnpj(None), "")
