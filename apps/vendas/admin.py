from django.contrib import admin

from .models import Venda


@admin.register(Venda)
class VendaAdmin(admin.ModelAdmin):
    list_display = ("data", "empresa", "servico", "descricao", "quantidade", "valor_unitario", "cobranca", "status", "vendedor")
    list_filter = ("status", "servico", "cobranca")
    search_fields = ("descricao", "empresa__razao_social", "empresa__nome_fantasia")
    date_hierarchy = "data"
