from django.urls import path

from . import views

app_name = "gestao"

urlpatterns = [
    path("", views.GestaoListView.as_view(), name="lista"),
    path("nova/", views.GestaoCreateView.as_view(), name="nova"),
    path("agenda/", views.AgendaPrazosView.as_view(), name="agenda"),
    path("vencimentos/", views.VencimentosView.as_view(), name="vencimentos"),
    path("<int:pk>/", views.GestaoDetailView.as_view(), name="detalhe"),
    path("<int:pk>/editar/", views.GestaoUpdateView.as_view(), name="editar"),
    path("<int:pk>/etapa/", views.EtapaView.as_view(), name="etapa"),
    path("<int:pk>/registros/novo/", views.RegistroCreateView.as_view(), name="registro_novo"),
    path("<int:pk>/prazos/novo/", views.PrazoCreateView.as_view(), name="prazo_novo"),
    path("<int:pk>/prazos/gerar/", views.GerarPrazosView.as_view(), name="prazos_gerar"),
    path("<int:pk>/documentos/novo/", views.DocumentoCreateView.as_view(), name="documento_novo"),
    path("<int:pk>/treinamentos/novo/", views.TreinamentoCreateView.as_view(), name="treinamento_novo"),
    path("<int:pk>/fap/", views.FichaFapSalvarView.as_view(), name="fap_salvar"),
    path("fap/", views.FapCarteiraView.as_view(), name="fap_carteira"),
    path("fap/<int:pk>/excluir/", views.FichaFapExcluirView.as_view(), name="fap_excluir"),
    path("<int:pk>/acoes/nova/", views.AcaoCreateView.as_view(), name="acao_nova"),
    path("<int:pk>/acoes/importar/", views.ImportarPlanoView.as_view(), name="plano_importar"),
    path("acoes/modelo.xlsx", views.ModeloPlanoView.as_view(), name="plano_modelo"),
    path(
        "acoes/importacoes/<int:pk>/confirmar/",
        views.ConfirmarImportacaoView.as_view(),
        name="plano_importar_confirmar",
    ),
    path("acoes/<int:pk>/evento/", views.AcaoEventoView.as_view(), name="acao_evento"),
    path("prazos/<int:pk>/concluir/", views.PrazoConcluirView.as_view(), name="prazo_concluir"),
]
