from django.urls import path

from . import views

app_name = "tarefas_ext"

urlpatterns = [
    path("", views.PainelTarefasView.as_view(), name="painel"),
    path("importar/", views.ImportarTodosView.as_view(), name="importar"),
    path("clientes/<int:pk>/criar-lead/", views.CriarLeadView.as_view(), name="criar_lead"),
]
