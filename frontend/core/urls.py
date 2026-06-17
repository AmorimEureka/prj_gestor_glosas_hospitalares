from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("administrativo/prazos-recurso/", views.prazos_recurso_convenio, name="prazos_recurso_convenio"),
    path("conta-atendimento/", views.conta_atendimento, name="conta_atendimento"),
    path("acompanhamento/", views.acompanhamento, name="acompanhamento"),
    path("glosas/", views.glosas, name="glosas"),
    path("remessas/", views.remessas, name="remessas"),
    path("recursos/", views.recursos, name="recursos"),
    path("recebimentos/", views.recebimentos, name="recebimentos"),
    path("conciliacao/", views.conciliacao, name="conciliacao"),
]
