from django.urls import path

from . import views

app_name = "campanhas"

urlpatterns = [
    path("campanhas/", views.CampanhasView.as_view(), name="painel"),
    path("campanhas/gerar/", views.GerarEnviosView.as_view(), name="gerar"),
    path("campanhas/enviar-emails/", views.EnviarEmailsView.as_view(), name="enviar_emails"),
    path("campanhas/conteudo/", views.ConteudoView.as_view(), name="conteudo"),
    path("campanhas/modelos/", views.ModelosView.as_view(), name="modelos"),
    path("campanhas/envios/<int:pk>/whatsapp/", views.WhatsappView.as_view(), name="whatsapp"),
    path("campanhas/envios/<int:pk>/pular/", views.PularEnvioView.as_view(), name="pular"),
    path("campanhas/envios/<int:pk>/previa/", views.PreviaEmailView.as_view(), name="previa"),
    # públicas, sem login: links que vão nas mensagens
    path("r/<uuid:token>/", views.PropostaView.as_view(), name="proposta"),
    path("r/<uuid:token>/sair/", views.DescadastrarView.as_view(), name="descadastrar"),
    path("r/<uuid:token>/a.gif", views.PixelView.as_view(), name="pixel"),
]
