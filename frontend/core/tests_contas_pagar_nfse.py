from unittest.mock import patch

from django.test import TestCase

from core.access import RESTRICTED_KEYS, allowed_screen_keys
from core.services import ApiError

NOTA = {
    'chave': '11111111000111-123', 'prestador_cnpj': '11111111000111', 'prestador': 'Software SA',
    'numero_nfse': '123', 'codigo_verificacao': 'ABC', 'data_emissao': '2026-11-10',
    'competencia': '2026-11-01', 'valor_servicos': '1500.50', 'valor_liquido': '1400.00',
    'tomador_cnpj': '08711085000128', 'tomador': 'Hospital', 'cd_multi_empresa': 1,
    'discriminacao': 'Licença de software', 'cd_oficina': 2, 'ds_oficina': 'TECNOLOGIA DA INFORMACAO',
    'situacao': 'pendente', 'motivo': None, 'mv': None,
}
OFICINAS = [
    {'cd_oficina': 2, 'ds_oficina': 'TECNOLOGIA DA INFORMACAO', 'cd_setor': 1, 'cd_multi_empresa': 1},
    {'cd_oficina': 12, 'ds_oficina': 'CENTRAL DE RECEBIMENTO FISCAL', 'cd_setor': 68, 'cd_multi_empresa': 2},
]


class NfseAccessTests(TestCase):
    def test_telas_novas_sao_restritas(self):
        self.assertIn('contas_pagar_nfse_setor', RESTRICTED_KEYS)
        self.assertIn('contas_pagar_nfse_regras', RESTRICTED_KEYS)
        # Usuário legado sem lista explícita não recebe as telas novas.
        self.assertNotIn('contas_pagar_nfse_setor', allowed_screen_keys({'perfil': 'usuario'}))

    def test_sem_permissao_nao_abre(self):
        session = self.client.session
        session['api_access_token'] = 't'
        session['api_user'] = {'id': 3, 'perfil': 'usuario', 'telas_permitidas': ['contas_pagar_operacao']}
        session.save()

        response = self.client.get('/financeiro/contas-a-pagar/nfse-do-setor/')

        self.assertNotEqual(response.status_code, 200)


class NfseSetorViewTests(TestCase):
    def setUp(self):
        session = self.client.session
        session['api_access_token'] = 'token'
        session['api_user'] = {
            'id': 7, 'nome': 'Setor TI', 'perfil': 'usuario',
            'telas_permitidas': ['contas_pagar_nfse_setor'],
        }
        session.save()
        vinculo = patch('core.views._mv_vinculo', return_value=None)
        vinculo.start()
        self.addCleanup(vinculo.stop)

    @patch('core.views.api_get')
    def test_lista_notas_do_setor(self, api_get):
        api_get.return_value = {
            'desde': '2026-10-01', 'situacao': 'pendente',
            'oficinas': [{'cd_oficina': 2, 'ds_oficina': 'TECNOLOGIA DA INFORMACAO', 'cd_multi_empresa': 1,
                          'empresa': 'HOSPITAL PRONTOCARDIO', 'quantidade': 1, 'valor': '1500.50'}],
            'itens': [NOTA],
        }

        response = self.client.get('/financeiro/contas-a-pagar/nfse-do-setor/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Software SA')
        self.assertContains(response, 'A lançar')
        self.assertContains(response, '1.500,50')
        self.assertContains(response, '· HOSPITAL PRONTOCARDIO')
        api_get.assert_called_once_with(
            '/app_glosas/financeiro/contas-a-pagar/nfse/recebidas',
            {'situacao': 'pendente', 'cd_oficina': '', 'desde': ''},
        )

    @patch('core.views.api_get')
    def test_setor_nao_pode_pedir_notas_sem_setor(self, api_get):
        api_get.return_value = {'oficinas': [], 'itens': []}

        response = self.client.get('/financeiro/contas-a-pagar/nfse-do-setor/?situacao=a_classificar')

        self.assertEqual(api_get.call_args.args[1]['situacao'], 'pendente')
        self.assertNotContains(response, 'Sem setor</option>')

    @patch('core.views.api_get')
    def test_aviso_quando_extracao_ainda_nao_carregou(self, api_get):
        api_get.return_value = {'aviso': 'A extração de NFS-e recebidas ainda não carregou dados.', 'oficinas': [], 'itens': []}

        response = self.client.get('/financeiro/contas-a-pagar/nfse-do-setor/')

        self.assertContains(response, 'ainda não carregou dados')

    @patch('core.views.api_get', side_effect=ApiError('fora do ar'))
    def test_erro_da_api_vira_mensagem(self, _):
        response = self.client.get('/financeiro/contas-a-pagar/nfse-do-setor/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fora do ar')


class NfseRegrasViewTests(TestCase):
    def setUp(self):
        session = self.client.session
        session['api_access_token'] = 'token'
        session['api_user'] = {
            'id': 1, 'nome': 'Financeiro', 'perfil': 'usuario',
            'telas_permitidas': ['contas_pagar_nfse_regras'],
        }
        session.save()
        vinculo = patch('core.views._mv_vinculo', return_value=None)
        vinculo.start()
        self.addCleanup(vinculo.stop)

    @staticmethod
    def respostas(path, params=None):
        if path.endswith('/oficinas'):
            return {'oficinas': OFICINAS}
        if path.endswith('/regras'):
            return {'resumo': {'definida': 400, 'a_classificar': 1}, 'regras': [{
                'cnpj': '22222222000122', 'cd_multi_empresa': 2, 'nm_fornecedor': 'Dividido LTDA',
                'cd_oficina': None, 'ds_oficina': None, 'status': 'a_classificar', 'origem': 'historico',
                'motivo': 'Histórico dividido entre setores: CAFA 50%, MARKETING 50%', 'atualizado_em': None,
            }]}
        if path.endswith('/recebidas'):
            return {'itens': [{**NOTA, 'situacao': 'a_classificar', 'cd_oficina': None, 'ds_oficina': None,
                               'motivo': 'Fornecedor sem entradas de serviço nesta empresa no histórico do MV'}]}
        if path == '/usuarios/':
            return {'usuarios': [{'id': 7, 'nome': 'Setor TI', 'email': 'ti@x'}]}
        if path.endswith('/usuarios/7/oficinas'):
            return {'oficinas': [{'cd_oficina': 2}]}
        if path.endswith('/usuarios/7/mv'):
            return {'cd_usuario_mv': 'RH000969'}
        raise AssertionError(path)

    @patch('core.views.api_get')
    def test_mostra_notas_sem_setor_com_oficinas_da_empresa_da_nota(self, api_get):
        api_get.side_effect = self.respostas

        response = self.client.get('/financeiro/contas-a-pagar/setores-dos-fornecedores/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Software SA')
        self.assertContains(response, 'CAFA 50%')
        conteudo = response.content.decode()
        # A nota é da empresa 1: oferece a oficina 2 e não a 12 (empresa 2).
        trecho_nota = conteudo.split('NFS-e recebidas sem setor', 1)[1].split('Regras por fornecedor', 1)[0]
        self.assertIn('value="2"', trecho_nota)
        self.assertNotIn('value="12"', trecho_nota)

    @patch('core.views.api_get')
    def test_vinculos_do_usuario_selecionado(self, api_get):
        api_get.side_effect = self.respostas

        response = self.client.get('/financeiro/contas-a-pagar/setores-dos-fornecedores/?usuario=7')

        self.assertContains(response, 'value="RH000969"')
        self.assertContains(response, 'value="2" checked')

    @patch('core.views.api_put')
    def test_classificar_fornecedor(self, api_put):
        api_put.return_value = {}

        response = self.client.post('/financeiro/contas-a-pagar/setores-dos-fornecedores/', {
            'acao': 'classificar', 'cnpj': '11.111.111/0001-11', 'cd_multi_empresa': '1',
            'cd_oficina': '2', 'nm_fornecedor': 'Software SA', 'status': 'a_classificar',
        })

        self.assertEqual(response.status_code, 302)
        api_put.assert_called_once_with(
            '/app_glosas/financeiro/contas-a-pagar/nfse/regras/1/11111111000111',
            {'cd_oficina': 2, 'nm_fornecedor': 'Software SA', 'observacao': None},
        )

    @patch('core.views.api_post')
    def test_recalcular(self, api_post):
        api_post.return_value = {'meses_historico': 24, 'definida': 400, 'a_classificar': 14}

        response = self.client.post('/financeiro/contas-a-pagar/setores-dos-fornecedores/', {'acao': 'recalcular'}, follow=False)

        self.assertEqual(response.status_code, 302)
        api_post.assert_called_once_with('/app_glosas/financeiro/contas-a-pagar/nfse/regras/recalcular', {})

    @patch('core.views.api_put')
    def test_vincular_oficinas_e_login_mv(self, api_put):
        api_put.return_value = {}
        url = '/financeiro/contas-a-pagar/setores-dos-fornecedores/'

        self.client.post(url, {'acao': 'vincular_oficinas', 'usuario_id': '7', 'oficinas': ['2', '12']})
        self.client.post(url, {'acao': 'vincular_mv', 'usuario_id': '7', 'cd_usuario_mv': 'rh000969'})

        api_put.assert_any_call('/app_glosas/financeiro/contas-a-pagar/nfse/usuarios/7/oficinas', {'oficinas': [2, 12]})
        api_put.assert_any_call('/app_glosas/financeiro/contas-a-pagar/nfse/usuarios/7/mv', {'cd_usuario_mv': 'rh000969'})

    @patch('core.views.api_put', side_effect=ApiError('Login MV RH000969 já vinculado a outro usuário do Receita Certa.'))
    def test_erro_ao_salvar_aparece_para_o_usuario(self, _):
        response = self.client.post('/financeiro/contas-a-pagar/setores-dos-fornecedores/', {
            'acao': 'vincular_mv', 'usuario_id': '7', 'cd_usuario_mv': 'RH000969',
        }, follow=True)

        self.assertContains(response, 'já vinculado a outro usuário')


class NfseBoletoViewTests(TestCase):
    URL = '/financeiro/contas-a-pagar/nfse-do-setor/'

    def setUp(self):
        session = self.client.session
        session['api_access_token'] = 'token'
        session['api_user'] = {'id': 7, 'nome': 'Setor TI', 'perfil': 'usuario',
                               'telas_permitidas': ['contas_pagar_nfse_setor']}
        session.save()
        vinculo = patch('core.views._mv_vinculo', return_value=None)
        vinculo.start()
        self.addCleanup(vinculo.stop)

    @staticmethod
    def pdf(nome='boleto.pdf'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(nome, b'%PDF-1.4 conteudo', content_type='application/pdf')

    @patch('core.views.api_post_files')
    def test_anexar_boleto_envia_multipart(self, api_post_files):
        api_post_files.return_value = {'divergencias': []}

        response = self.client.post(self.URL, {
            'acao': 'anexar_boleto', 'cnpj': '11.111.111/0001-11', 'numero': '123',
            'arquivo': self.pdf(), 'situacao': 'pendente', 'nota': '11111111000111-123',
        }, follow=True)

        path, files, dados = api_post_files.call_args.args
        self.assertEqual(path, '/app_glosas/financeiro/contas-a-pagar/nfse/recebidas/11111111000111/123/boletos')
        self.assertEqual(files['arquivo'][0], 'boleto.pdf')
        self.assertEqual(dados, {})
        self.assertContains(response, 'pronta para o financeiro')

    @patch('core.views.api_post_files')
    def test_linha_digitada_e_vencimento_vao_junto(self, api_post_files):
        api_post_files.return_value = {'divergencias': ['Boleto vencido.']}

        response = self.client.post(self.URL, {
            'acao': 'anexar_boleto', 'cnpj': '11111111000111', 'numero': '123', 'arquivo': self.pdf(),
            'linha_digitavel': ' 34191.09008 ', 'vencimento': '2026-12-10',
        }, follow=True)

        self.assertEqual(api_post_files.call_args.args[2],
                         {'linha_digitavel': '34191.09008', 'vencimento': '2026-12-10'})
        self.assertContains(response, 'divergências: Boleto vencido.')

    @patch('core.views.api_post_files', side_effect=ApiError('{"detail":"Envie o boleto em PDF."}', 422))
    def test_erro_da_api_ao_anexar(self, _):
        response = self.client.post(self.URL, {
            'acao': 'anexar_boleto', 'cnpj': '11111111000111', 'numero': '123', 'arquivo': self.pdf(),
        }, follow=True)

        self.assertContains(response, 'Não foi possível salvar o boleto')

    @patch('core.views.api_delete')
    def test_excluir_boleto(self, api_delete):
        response = self.client.post(self.URL, {'acao': 'excluir_boleto', 'boleto_id': '9', 'nota': '11111111000111-123'})

        self.assertEqual(response.status_code, 302)
        self.assertIn('nota=11111111000111-123', response.url)
        api_delete.assert_called_once_with('/app_glosas/financeiro/contas-a-pagar/nfse/boletos/9')

    @patch('core.views.api_get')
    def test_painel_da_nota_lista_boletos_e_formulario(self, api_get):
        def respostas(path, params=None):
            if path.endswith('/boletos'):
                return {'nota': {'prestador_cnpj': '11111111000111', 'numero_nfse': '123',
                                 'prestador_razao_social': 'Software SA'},
                        'boletos': [{'id': 9, 'vencimento': '2026-12-01', 'valor': '1500.50', 'banco': '341',
                                     'linha_digitavel': '3419' + '0' * 43, 'origem_leitura': 'pdf',
                                     'divergencias': ['Boleto vencido.']}],
                        'resumo': {'quantidade': 1, 'soma': '1500.50', 'valor_liquido': '1500.50', 'pronta': False}}
            return {'oficinas': [], 'itens': [{**NOTA, 'boletos': {'quantidade': 1, 'soma': '1500.50',
                    'primeiro_vencimento': '2026-12-01', 'com_divergencia': True}, 'pronta': False}]}
        api_get.side_effect = respostas

        response = self.client.get(self.URL + '?nota=11111111000111-123')

        self.assertContains(response, 'Boletos da NFS-e 123')
        self.assertContains(response, 'Boleto vencido.')
        self.assertContains(response, 'Boleto com divergência')
        self.assertContains(response, '/financeiro/contas-a-pagar/boletos/9/pdf/')
        self.assertContains(response, 'enctype="multipart/form-data"')

    @patch('core.views.api_get')
    def test_chave_de_nota_invalida_e_ignorada(self, api_get):
        api_get.return_value = {'oficinas': [], 'itens': []}

        self.client.get(self.URL + '?nota=../../usuarios')

        self.assertEqual(api_get.call_count, 1)

    @patch('core.views.api_get')
    def test_filtro_prontas(self, api_get):
        api_get.return_value = {'oficinas': [], 'itens': [{**NOTA, 'pronta': True,
                                'boletos': {'quantidade': 1, 'soma': '1500.50', 'primeiro_vencimento': '2026-12-01',
                                            'com_divergencia': False}}]}

        response = self.client.get(self.URL + '?situacao=pronta')

        self.assertEqual(api_get.call_args.args[1]['situacao'], 'pronta')
        self.assertContains(response, 'Pronta para o financeiro')

    @patch('core.views.api_get_stream')
    def test_proxy_do_pdf(self, api_get_stream):
        upstream = api_get_stream.return_value
        upstream.iter_content.return_value = [b'%PDF', b'-1.4']
        upstream.headers = {'Content-Disposition': 'inline; filename="boleto.pdf"'}

        response = self.client.get('/financeiro/contas-a-pagar/boletos/9/pdf/')

        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.4')
        api_get_stream.assert_called_once_with('/app_glosas/financeiro/contas-a-pagar/nfse/boletos/9/arquivo')
