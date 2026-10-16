from django.contrib import admin

from .models import (
    AcaoPlano,
    Documento,
    EventoAcao,
    FichaFap,
    Gestao,
    ImportacaoPlano,
    Prazo,
    Registro,
    Treinamento,
)


class PrazoInline(admin.TabularInline):
    model = Prazo
    extra = 0
    fields = ("titulo", "base_legal", "data_inicio", "data_fim", "status", "responsavel")


class DocumentoInline(admin.TabularInline):
    model = Documento
    extra = 0
    fields = ("tipo", "titulo", "status", "emitido_em", "valido_ate", "visivel_cliente")


@admin.register(Gestao)
class GestaoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "empresa", "etapa", "modelo", "inicio", "responsavel", "encerrado_em")
    list_filter = ("etapa", "modelo", "certificacao_sgsst")
    search_fields = ("codigo", "empresa__razao_social", "empresa__cnpj")
    autocomplete_fields = ("empresa", "responsavel")
    date_hierarchy = "inicio"
    inlines = [DocumentoInline, PrazoInline]


@admin.register(Registro)
class RegistroAdmin(admin.ModelAdmin):
    list_display = ("data", "gestao", "tipo", "titulo", "visivel_cliente")
    list_filter = ("tipo", "visivel_cliente")
    search_fields = ("titulo", "descricao", "gestao__codigo")
    autocomplete_fields = ("gestao",)
    date_hierarchy = "data"


@admin.register(Prazo)
class PrazoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "gestao", "tipo", "data_fim", "status", "responsavel")
    list_filter = ("status", "tipo")
    search_fields = ("titulo", "gestao__codigo", "gestao__empresa__razao_social")
    autocomplete_fields = ("gestao", "responsavel")
    date_hierarchy = "data_fim"


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "gestao", "tipo", "status", "emitido_em", "valido_ate", "visivel_cliente")
    list_filter = ("tipo", "status", "visivel_cliente")
    search_fields = ("titulo", "gestao__codigo", "gestao__empresa__razao_social")
    autocomplete_fields = ("gestao",)


@admin.register(Treinamento)
class TreinamentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "gestao", "status", "realizado_em", "participantes", "valido_ate")
    list_filter = ("tipo", "status", "modalidade")
    search_fields = ("titulo", "gestao__codigo", "gestao__empresa__razao_social")
    autocomplete_fields = ("gestao",)


class EventoAcaoInline(admin.TabularInline):
    model = EventoAcao
    extra = 0
    fields = ("data", "descricao", "visivel_cliente")


@admin.register(AcaoPlano)
class AcaoPlanoAdmin(admin.ModelAdmin):
    list_display = ("descricao", "gestao", "risco", "setor", "prioridade", "prazo", "status")
    list_filter = ("risco", "prioridade", "status")
    search_fields = ("descricao", "setor", "gestao__codigo", "gestao__empresa__razao_social")
    autocomplete_fields = ("gestao",)
    inlines = [EventoAcaoInline]


@admin.register(ImportacaoPlano)
class ImportacaoPlanoAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "gestao", "status", "linhas_lidas", "criados", "atualizados", "ignorados", "enviado_por")
    list_filter = ("status",)
    search_fields = ("gestao__codigo", "mensagem")
    readonly_fields = (
        "gestao", "arquivo", "enviado_por", "status", "linhas_lidas",
        "linhas_validas", "criados", "atualizados", "ignorados", "mensagem",
    )

    def has_add_permission(self, request):
        return False


@admin.register(FichaFap)
class FichaFapAdmin(admin.ModelAdmin):
    list_display = ("gestao", "vigencia", "grau_rat", "fap_oficial", "bloqueio")
    list_filter = ("vigencia", "grau_rat")
    search_fields = ("gestao__codigo", "gestao__empresa__razao_social")
    autocomplete_fields = ("gestao",)
