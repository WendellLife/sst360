from django.urls import path

from . import views

app_name = "publico"

urlpatterns = [
    path("metodo/", views.MetodoView.as_view(), name="metodo"),
    path("diagnostico/", views.QuizView.as_view(), name="quiz"),
    path("diagnostico/voltar/", views.VoltarPerguntaView.as_view(), name="quiz_voltar"),
    path("diagnostico/<uuid:token>/", views.ResultadoView.as_view(), name="resultado"),
    path("diagnostico/<uuid:token>/whatsapp/", views.WhatsAppDiagnosticoView.as_view(), name="whatsapp"),
]
