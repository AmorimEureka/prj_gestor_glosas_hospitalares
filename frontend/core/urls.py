from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("esqueci-senha/", views.forgot_password, name="forgot_password"),
    path("redefinir-senha/", views.reset_password, name="reset_password"),
    path(
        "autenticacao/redefinir-senha/",
        views.reset_password,
        name="reset_password_auth",
    ),
    path("", views.dashboard, name="dashboard"),
    path("administrativo/prazos-recurso/", views.prazos_recurso_convenio, name="prazos_recurso_convenio"),
    path("administrativo/acessos/", views.user_access_management, name="user_access_management"),
    path("follow-up-glosas/", views.follow_up_glosas, name="follow_up_glosas"),
    path("conta-atendimento/", views.conta_atendimento, name="conta_atendimento"),
    path("acompanhamento/", views.acompanhamento, name="acompanhamento"),
    path("glosas/", views.glosas, name="glosas"),
    path("remessas/", views.remessas, name="remessas"),
    path("recursos/", views.recursos, name="recursos"),
    path("recebimentos/", views.recebimentos, name="recebimentos"),
    path(
        "financeiro/conciliacao-fiscal-faturamento/",
        views.conciliacao_faturamento,
        name="conciliacao_faturamento",
    ),
    path(
        "financeiro/conciliacoes-sem-recebimento/",
        views.conciliacoes_sem_recebimento,
        name="conciliacoes_sem_recebimento",
    ),
    path(
        "financeiro/conciliacao-fiscal-faturamento/remessas/<str:nfse_row_hash>/",
        views.conciliacao_faturamento_remessas,
        name="conciliacao_faturamento_remessas",
    ),
    path(
        "financeiro/conciliacao-fiscal-faturamento/lancamentos-extrato/",
        views.conciliacao_faturamento_lancamentos,
        name="conciliacao_faturamento_lancamentos",
    ),
    path("conciliacao/", views.conciliacao, name="conciliacao"),
]
