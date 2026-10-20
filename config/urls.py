from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("", include("apps.publico.urls")),
    path("conta/", include("apps.accounts.urls")),
    path("comercial/tarefas/", include("apps.tarefas_ext.urls")),
    path("empresas/", include("apps.empresas.urls")),
    path("gestao/", include("apps.gestao.urls")),
    path("prospeccao/", include("apps.crm.urls")),
    path("portal/", include("apps.portal.urls")),
    path("relacionamento/", include("apps.relacionamento.urls")),
    path("vendas/", include("apps.vendas.urls")),
    path("", include("apps.campanhas.urls")),
]

# /media/ público só existe com DEBUG=True (desenvolvimento). Em produção (DEBUG=False) os arquivos saem
# apenas pelas views autenticadas de apps.core (/arquivos/...); não exponha a pasta no proxy.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
