from unittest.mock import patch

import requests
from django.test import TestCase

from core import services

URL = '/financeiro/contas-a-pagar/nfse-do-setor/?situacao=todas&page=2'


def _resposta(status, corpo):
    r = requests.Response()
    r.status_code = status
    r._content = corpo.encode()
    r.headers['Content-Type'] = 'application/json'
    return r


class SessaoExpiradaTests(TestCase):
    def setUp(self):
        session = self.client.session
        session['api_access_token'] = 'token-vencido'
        session['api_user'] = {'id': 4, 'nome': 'Amoras', 'perfil': 'usuario',
                               'telas_permitidas': ['contas_pagar_nfse_setor', 'contas_pagar_nfse_regras']}
        session.save()

    @patch('core.services.requests.request', return_value=_resposta(401, '{"detail":"Could not validate credentials"}'))
    def test_token_vencido_leva_ao_login_e_volta_para_a_tela(self, _):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('/login/?'))
        self.assertIn('sessao=expirada', response['Location'])
        self.assertIn('next=%2Ffinanceiro%2Fcontas-a-pagar%2Fnfse-do-setor%2F%3Fsituacao%3Dtodas%26page%3D2', response['Location'])
        self.assertNotIn('api_access_token', self.client.session)

    @patch('core.services.requests.request', return_value=_resposta(401, '{"detail":"Could not validate credentials"}'))
    def test_post_volta_para_a_pagina_de_origem(self, _):
        response = self.client.post('/financeiro/contas-a-pagar/nfse-do-setor/', {'acao': 'excluir_boleto', 'boleto_id': '1'},
                                    HTTP_REFERER='https://receitacerta.test' + URL)
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=%2Ffinanceiro%2Fcontas-a-pagar%2Fnfse-do-setor%2F%3Fsituacao%3Dtodas%26page%3D2', response['Location'])

    @patch('core.services.requests.request', return_value=_resposta(401, '{"detail":"Ticket do CAS recusado."}'))
    def test_outro_401_nao_derruba_a_sessao(self, _):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertIn('api_access_token', self.client.session)

    def test_login_avisa_que_a_sessao_expirou(self):
        self.client.session.flush()
        response = self.client.get('/login/?next=/financeiro/contas-a-pagar/nfse-do-setor/&sessao=expirada')
        self.assertContains(response, 'Sua sessão expirou')
        self.assertContains(response, 'value="/financeiro/contas-a-pagar/nfse-do-setor/"', html=False)

    def test_marcacao_vale_so_para_a_requisicao(self):
        contexto = services.set_request_api_token('t')
        try:
            self.assertFalse(services.token_api_recusado())
            services._marcar_token_recusado(_resposta(401, '{"detail":"Could not validate credentials"}'), None)
            self.assertTrue(services.token_api_recusado())
        finally:
            services.reset_request_api_token(contexto)
        self.assertFalse(services.token_api_recusado())

    def test_token_explicito_nao_marca(self):
        contexto = services.set_request_api_token('t')
        try:
            services._marcar_token_recusado(_resposta(401, '{"detail":"Could not validate credentials"}'), 'outro-token')
            self.assertFalse(services.token_api_recusado())
        finally:
            services.reset_request_api_token(contexto)
