from django.contrib import admin

from .models import Campanha, Envio, Modelo


@admin.register(Modelo)
class ModeloAdmin(admin.ModelAdmin):
    list_display = ("etapa", "assunto")


@admin.register(Campanha)
class CampanhaAdmin(admin.ModelAdmin):
    list_display = ("rotulo", "tema", "envios_gerados_em", "emails_enviados_em")


@admin.register(Envio)
class EnvioAdmin(admin.ModelAdmin):
    list_display = ("lead", "campanha", "canal", "etapa", "status", "enviado_em", "aberto_em", "clicado_em")
    list_filter = ("canal", "etapa", "status")
