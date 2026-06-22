from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("esqueci-senha/", views.forgot_password, name="forgot_password"),
    path("redefinir-senha/", views.reset_password, name="reset_password"),
    path("", views.dashboard, name="dashboard"),
    path("administrativo/prazos-recurso/", views.prazos_recurso_convenio, name="prazos_recurso_convenio"),
    path("administrativo/acessos/", views.user_access_management, name="user_access_management"),
    path("conta-atendimento/", views.conta_atendimento, name="conta_atendimento"),
    path("acompanhamento/", views.acompanhamento, name="acompanhamento"),
    path("glosas/", views.glosas, name="glosas"),
    path("remessas/", views.remessas, name="remessas"),
    path("recursos/", views.recursos, name="recursos"),
    path("recebimentos/", views.recebimentos, name="recebimentos"),
    path("conciliacao/", views.conciliacao, name="conciliacao"),
]
