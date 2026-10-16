from django.urls import path

from . import views

app_name = "relacionamento"

urlpatterns = [
    path("gestao/<int:pk>/", views.RelacionamentoView.as_view(), name="painel"),
    path("gestao/<int:pk>/documentos/", views.SolicitarDocumentoView.as_view(), name="documento_solicitar"),
    path("documentos/<int:pk>/conferir/", views.ConferirDocumentoView.as_view(), name="documento_conferir"),
    path("gestao/<int:pk>/reunioes/", views.ReuniaoCreateView.as_view(), name="reuniao_nova"),
    path("gestao/<int:pk>/responder/", views.ResponderView.as_view(), name="responder"),
]
