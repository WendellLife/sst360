from django.urls import path

from . import views

app_name = "vendas"

urlpatterns = [
    path("", views.VendaListView.as_view(), name="lista"),
    path("nova/", views.VendaCreateView.as_view(), name="nova"),
    path("<int:pk>/editar/", views.VendaUpdateView.as_view(), name="editar"),
    path("<int:pk>/status/", views.VendaStatusView.as_view(), name="status"),
]
