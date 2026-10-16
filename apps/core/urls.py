from django.urls import path

from .views import ApresentacaoIndicadoresView, DashboardView, HomeView, IndicadoresView

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("painel/", DashboardView.as_view(), name="dashboard"),
    path("indicadores/", IndicadoresView.as_view(), name="indicadores"),
    path("indicadores/apresentacao.pptx", ApresentacaoIndicadoresView.as_view(), name="indicadores_pptx"),
]
