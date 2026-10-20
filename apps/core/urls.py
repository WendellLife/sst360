from django.urls import path

from . import downloads
from .views import ApresentacaoIndicadoresView, BuscaView, DashboardView, HomeView, IndicadoresView

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("painel/", DashboardView.as_view(), name="dashboard"),
    path("busca/", BuscaView.as_view(), name="busca"),
    path("indicadores/", IndicadoresView.as_view(), name="indicadores"),
    path("arquivos/documento/<int:pk>/", downloads.documento, name="arquivo_documento"),
    path("arquivos/solicitado/<int:pk>/", downloads.documento_solicitado, name="arquivo_solicitado"),
    path("arquivos/importacao/<int:pk>/", downloads.importacao_plano, name="arquivo_importacao"),
    path("indicadores/apresentacao.pptx", ApresentacaoIndicadoresView.as_view(), name="indicadores_pptx"),
]
