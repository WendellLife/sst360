from django.urls import path

from .views import ApresentacaoIndicadoresView, BuscaView, DashboardView, HomeView, IndicadoresView

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("painel/", DashboardView.as_view(), name="dashboard"),
    path("busca/", BuscaView.as_view(), name="busca"),
    path("indicadores/", IndicadoresView.as_view(), name="indicadores"),
    path("indicadores/apresentacao.pptx", ApresentacaoIndicadoresView.as_view(), name="indicadores_pptx"),
]
