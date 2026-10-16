from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.PortalHomeView.as_view(), name="home"),
    path("plano/", views.PortalPlanoView.as_view(), name="plano"),
    path("documentos/", views.PortalDocumentosView.as_view(), name="documentos"),
    path("documentos/<int:pk>/enviar/", views.EnviarDocumentoView.as_view(), name="documento_enviar"),
    path("treinamentos/", views.PortalTreinamentosView.as_view(), name="treinamentos"),
    path("visitas/", views.PortalReunioesView.as_view(), name="reunioes"),
    path("conversa/", views.PortalConversaView.as_view(), name="conversa"),
    path("gestao/<int:pk>/", views.PortalGestaoView.as_view(), name="gestao"),
]
