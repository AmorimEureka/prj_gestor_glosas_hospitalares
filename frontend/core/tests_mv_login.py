import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.test import TestCase, override_settings

from core.services import ApiError

CAS = 'http://cas.test/mvautenticador-cas'
RETORNO = 'https://receitacerta.test/mv/login/retorno/'


@override_settings(MV_CAS_BASE_URL=CAS, MV_CAS_SERVICE_URL=RETORNO)
class MvLoginTests(TestCase):
    def setUp(self):
        session = self.client.session
        session['api_access_token'] = 'token'
        session['api_user'] = {'id': 7, 'nome': 'Ana', 'perfil': 'usuario', 'telas_permitidas': ['contas_pagar_nfse_setor']}
        session.save()

    def iniciar(self):
        response = self.client.get('/mv/login/')
        self.assertEqual(response.status_code, 302)
        destino = urlsplit(response.url)
        self.assertEqual(f'{destino.scheme}://{destino.netloc}{destino.path}', f'{CAS}/login')
        service = parse_qs(destino.query)['service'][0]
        self.assertTrue(service.startswith(RETORNO + '?state='))
        return service, parse_qs(urlsplit(service).query)['state'][0]

    def test_login_exige_sessao_do_receita_certa(self):
        self.client.session.flush()
        self.client.cookies.clear()
        response = self.client.get('/mv/login/')
        self.assertTrue(response.url.startswith('/login/'))

    @patch('core.views.api_post')
    def test_retorno_valida_ticket_com_o_mesmo_service(self, api_post):
        service, state = self.iniciar()
        api_post.return_value = {'cd_usuario_mv': 'RH000969', 'nm_usuario_mv': 'WIARA', 'pode_gravar_no_mv': True}

        response = self.client.get('/mv/login/retorno/', {'state': state, 'ticket': 'ST-1-abc'})

        api_post.assert_called_once_with('/mv/cas/validar', {'ticket': 'ST-1-abc', 'service': service})
        self.assertContains(response, 'Login MV vinculado')
        self.assertContains(response, 'RH000969')
        self.assertContains(response, 'ok: true')
        self.assertNotIn('mv_cas_state', self.client.session)

    @patch('core.views.api_post')
    def test_state_diferente_e_recusado_sem_chamar_a_api(self, api_post):
        self.iniciar()
        response = self.client.get('/mv/login/retorno/', {'state': 'forjado', 'ticket': 'ST-1'})

        api_post.assert_not_called()
        self.assertContains(response, 'não foi iniciado por esta tela')

    @patch('core.views.api_post')
    def test_retorno_sem_login_iniciado(self, api_post):
        response = self.client.get('/mv/login/retorno/', {'state': 'x', 'ticket': 'ST-1'})

        api_post.assert_not_called()
        self.assertContains(response, 'ok: false')

    @patch('core.views.api_post')
    def test_state_expirado(self, api_post):
        _, state = self.iniciar()
        session = self.client.session
        session['mv_cas_state']['criado'] = time.time() - 3600
        session.save()

        response = self.client.get('/mv/login/retorno/', {'state': state, 'ticket': 'ST-1'})

        api_post.assert_not_called()
        self.assertContains(response, 'expirou')

    @patch('core.views.api_post', side_effect=ApiError('{"detail":"O login MV RH000969 já está vinculado a outro usuário do Receita Certa."}', 409))
    def test_erro_da_api_aparece(self, _):
        _, state = self.iniciar()
        response = self.client.get('/mv/login/retorno/', {'state': state, 'ticket': 'ST-1'})

        self.assertContains(response, 'Não foi possível vincular')
        self.assertContains(response, 'já está vinculado a outro usuário')

    @patch('core.views.api_get')
    def test_tela_mostra_status_do_login_mv(self, api_get):
        def respostas(path, params=None):
            if path == '/mv/vinculo':
                return {'cd_usuario_mv': 'RH000969', 'origem': 'cas', 'pode_gravar_no_mv': True}
            return {'oficinas': [], 'itens': []}
        api_get.side_effect = respostas

        response = self.client.get('/financeiro/contas-a-pagar/nfse-do-setor/')

        self.assertContains(response, 'Login MV: RH000969 ✓')

    @patch('core.views.api_get')
    def test_tela_sem_vinculo_oferece_o_login(self, api_get):
        api_get.side_effect = lambda path, params=None: (
            {'cd_usuario_mv': None, 'origem': None, 'pode_gravar_no_mv': False} if path == '/mv/vinculo'
            else {'oficinas': [], 'itens': []}
        )

        response = self.client.get('/financeiro/contas-a-pagar/nfse-do-setor/')

        self.assertContains(response, 'Entrar com login MV')
        self.assertContains(response, '/mv/login/')
