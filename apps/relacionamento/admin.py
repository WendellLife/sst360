from django.contrib import admin

from .models import DocumentoSolicitado, Mensagem, Reuniao


@admin.register(DocumentoSolicitado)
class DocumentoSolicitadoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "gestao", "status", "prazo", "enviado_em")
    list_filter = ("status",)
    search_fields = ("titulo", "gestao__codigo")
    autocomplete_fields = ("gestao",)


@admin.register(Reuniao)
class ReuniaoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "tipo", "gestao", "quando", "status", "visivel_cliente")
    list_filter = ("tipo", "status", "visivel_cliente")
    search_fields = ("titulo", "gestao__codigo")
    autocomplete_fields = ("gestao",)
    date_hierarchy = "quando"


@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "gestao", "autor", "texto")
    search_fields = ("texto", "gestao__codigo")
    autocomplete_fields = ("gestao", "autor")
