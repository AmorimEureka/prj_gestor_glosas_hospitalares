from unittest.mock import patch

from django.test import TestCase

from core.services import ApiError

TROCA = '{"detail":{"codigo":"TROCA_SENHA_OBRIGATORIA","mensagem":"Defina uma nova senha para continuar."}}'


class PrimeiroAcessoTests(TestCase):
    @patch('core.views.api_authenticate', side_effect=ApiError(TROCA, 403))
    def test_login_com_senha_temporaria_leva_ao_primeiro_acesso(self, _):
        response = self.client.post('/login/', {'email': 'Raffaekk', 'password': 'temporaria1'})

        self.assertRedirects(response, '/primeiro-acesso/', fetch_redirect_response=False)
        self.assertEqual(self.client.session['primeiro_acesso']['usuario'], 'raffaekk')

    def test_tela_e_publica_e_traz_o_usuario(self):
        session = self.client.session
        session['primeiro_acesso'] = {'usuario': 'raffaekk', 'next': '/financeiro/'}
        session.save()

        response = self.client.get('/primeiro-acesso/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="raffaekk"')
        self.assertContains(response, 'Crie a sua senha')

    @patch('core.views.api_post')
    def test_define_senha_e_volta_ao_login(self, api_post):
        session = self.client.session
        session['primeiro_acesso'] = {'usuario': 'raffaekk', 'next': '/financeiro/'}
        session.save()

        response = self.client.post('/primeiro-acesso/', {
            'usuario': 'raffaekk', 'senha_atual': 'temporaria1', 'nova_senha': 'MinhaSenha#2026',
            'confirmacao': 'MinhaSenha#2026',
        })

        api_post.assert_called_once_with('/autenticacao/primeiro-acesso', {
            'usuario': 'raffaekk', 'senha_temporaria': 'temporaria1', 'nova_senha': 'MinhaSenha#2026'})
        self.assertContains(response, 'Senha definida')
        self.assertContains(response, '/login/?next=%2Ffinanceiro%2F')
        self.assertNotIn('primeiro_acesso', self.client.session)

    @patch('core.views.api_post')
    def test_validacoes_locais_nao_chamam_a_api(self, api_post):
        casos = [
            ({'nova_senha': 'curta', 'confirmacao': 'curta'}, 'pelo menos 8'),
            ({'nova_senha': 'MinhaSenha#1', 'confirmacao': 'Outra#1234'}, 'não confere'),
            ({'nova_senha': 'temporaria1', 'confirmacao': 'temporaria1'}, 'diferente da senha atual'),
        ]
        for dados, mensagem in casos:
            response = self.client.post('/primeiro-acesso/', {'usuario': 'raffaekk', 'senha_atual': 'temporaria1', **dados})
            self.assertContains(response, mensagem)
        api_post.assert_not_called()

    @patch('core.views.api_post', side_effect=ApiError('{"detail":"Usuário ou senha temporária incorretos."}', 401))
    def test_senha_atual_errada(self, _):
        response = self.client.post('/primeiro-acesso/', {
            'usuario': 'raffaekk', 'senha_atual': 'errada123', 'nova_senha': 'MinhaSenha#2026', 'confirmacao': 'MinhaSenha#2026'})

        self.assertContains(response, 'Usuário ou senha atual incorretos.')

    @patch('core.views.api_authenticate', side_effect=ApiError('erro', 500))
    def test_outros_erros_mantem_a_mensagem_generica(self, _):
        response = self.client.post('/login/', {'email': 'a@b.c', 'password': 'x'})

        self.assertContains(response, 'Não foi possível acessar o sistema agora')
