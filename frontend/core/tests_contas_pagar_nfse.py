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
        self.assertContains(response, 'cp-nfse-setor__empresa">HOSPITAL PRONTOCARDIO')
        api_get.assert_called_once_with(
            '/app_glosas/financeiro/contas-a-pagar/nfse/recebidas',
            {'situacao': 'pendente', 'cd_oficina': '', 'desde': ''},
        )

    @patch('core.views.api_get')
    def test_pagina_dez_notas_por_vez_mantendo_filtros(self, api_get):
        itens = [{**NOTA, 'numero_nfse': f'9{n:03d}', 'chave': f'12345678000199-9{n:03d}', 'valor_liquido': '10.00'}
                 for n in range(23)]
        api_get.return_value = {'oficinas': [], 'itens': itens}

        response = self.client.get('/financeiro/contas-a-pagar/nfse-do-setor/?cd_oficina=2&page=3')

        self.assertEqual(response.context['pagination']['page'], 3)
        self.assertEqual(response.context['pagination']['total_pages'], 3)
        self.assertEqual([i['numero_nfse'] for i in response.context['itens']], ['9020', '9021', '9022'])
        self.assertContains(response, '21-23 de 23 notas exibidas')
        self.assertContains(response, 'R$ 230,00')
        self.assertContains(response, 'href="?situacao=pendente&amp;cd_oficina=2&amp;page=2"')
        self.assertContains(response, 'cd_oficina=2&amp;page=3&amp;nota=12345678000199-9020#boletos')

    @patch('core.views.api_get')
    def test_pagina_alem_do_fim_mostra_a_ultima(self, api_get):
        api_get.return_value = {'oficinas': [], 'itens': [NOTA]}

        response = self.client.get('/financeiro/contas-a-pagar/nfse-do-setor/?page=9')

        self.assertEqual(response.context['pagination']['page'], 1)
        self.assertEqual(len(response.context['itens']), 1)

    @patch('core.views.api_get')
    def test_mostra_status_do_iss_e_bloqueia_boleto_da_cancelada(self, api_get):
        normal = {**NOTA, 'status_nfse': 'NORMAL', 'status_nfse_consultado_em': '2026-11-18T11:40:00+00:00'}
        cancelada = {**NOTA, 'chave': '07530025000146-388581', 'numero_nfse': '388581', 'situacao': 'cancelada',
                     'status_nfse': 'CANCELADA', 'status_nfse_consultado_em': None}
        api_get.return_value = {'oficinas': [], 'itens': [normal, cancelada]}

        response = self.client.get('/financeiro/contas-a-pagar/nfse-do-setor/?situacao=todas')

        self.assertContains(response, 'Status ISS')
        self.assertContains(response, 'cp-nfse-status--normal">Normal')
        self.assertContains(response, '18/11/2026 08:40')  # UTC -> Fortaleza
        self.assertContains(response, 'cp-nfse-status--cancelada">Cancelada')
        self.assertContains(response, 'Cancelada no ISS</span>')
        self.assertNotContains(response, 'nota=07530025000146-388581#boletos')
        self.assertContains(response, 'is-cancelada')

    @patch('core.views.api_get')
    def test_status_nao_consultado(self, api_get):
        api_get.return_value = {'oficinas': [], 'itens': [{**NOTA, 'status_nfse': None}]}

        response = self.client.get('/financeiro/contas-a-pagar/nfse-do-setor/')

        self.assertContains(response, 'Não consultado')

    def test_filtro_canceladas_disponivel(self):
        from core.views import CP_NFSE_SITUACOES
        self.assertIn(('cancelada', 'Canceladas no ISS'), CP_NFSE_SITUACOES)

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


class NfseMenuTests(TestCase):
    def entrar(self, telas, perfil='usuario'):
        session = self.client.session
        session['api_access_token'] = 'token'
        session['api_user'] = {'id': 3, 'nome': 'X', 'perfil': perfil, 'telas_permitidas': telas}
        session.save()

    @patch('core.views._mv_vinculo', return_value=None)
    @patch('core.views.api_get', return_value={'oficinas': [], 'itens': []})
    def test_setor_ve_so_nfse_do_setor(self, *_):
        self.entrar(['contas_pagar_nfse_setor'])
        html = self.client.get('/financeiro/contas-a-pagar/nfse-do-setor/').content.decode()

        self.assertIn('4. NFS-e do setor', html)
        self.assertNotIn('5. Setores dos fornecedores', html)

    @patch('core.views._mv_vinculo', return_value=None)
    @patch('core.views.api_get', return_value={'oficinas': [], 'itens': []})
    def test_financeiro_ve_os_dois_itens(self, *_):
        self.entrar(['contas_pagar_nfse_regras'])
        html = self.client.get('/financeiro/contas-a-pagar/nfse-do-setor/').content.decode()

        self.assertIn('4. NFS-e do setor', html)
        self.assertIn('5. Setores dos fornecedores', html)
        self.assertIn('/financeiro/contas-a-pagar/setores-dos-fornecedores/', html)

    @patch('core.views.get_cached_api_payload', return_value={'fornecedores': [], 'resumo': {}, 'historico': [], 'opcoes_classificacao': []})
    def test_sem_as_telas_novas_o_menu_nao_mostra(self, *_):
        self.entrar(['contas_pagar_operacao'])
        response = self.client.get('/financeiro/contas-a-pagar/operacao/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('1. Operação', html)

        self.assertNotIn('4. NFS-e do setor', html)
        self.assertNotIn('5. Setores dos fornecedores', html)


SIMULACAO = {
    'simulacao': True, 'apta': True, 'assinatura': '60f46a25dfb4a358498c', 'gravacao_habilitada': True,
    'importacao_registrada': None, 'pendencias': [], 'avisos': ['Há 2 cadastros com este CNPJ; usado o 3373, do último lançamento.'],
    'escolhas': {
        'usuario_mv': 'RH000938', 'fornecedor': {'cd_fornecedor': 3373, 'nm_fornecedor': 'HAPVIDA'},
        'oficina': {'cd_oficina': 22, 'ds_oficina': 'CENTRAL DE RECEBIMENTO FISCAL', 'cd_setor': 68},
        'servico': {'cd_servico': 10106, 'nm_servico': 'PLANO DE SAUDE'}, 'conta_fornecedor': {'cd_reduzido': 241},
        'modelo': {'cd_ent_serv': 12292, 'nr_documento': '5.949', 'cd_usuario': 'RH001185'},
    },
    'gravacoes': [
        {'ordem': 1, 'tabela': 'ENT_SERV', 'operacao': 'INSERT', 'campos': {
            'vl_total': {'valor': '2708.73', 'origem': 'NFS-e'},
            'dt_emissao': {'valor': '2026-11-01', 'origem': 'NFS-e'},
            'hr_entrada': {'valor': '2026-11-18T10:36:36', 'origem': 'hora da importação'},
            'vl_percentual_iss': {'valor': '0', 'origem': 'sem retenção'},
            'cd_justifica': {'valor': None, 'origem': 'modelo'}}},
        {'ordem': 2, 'tabela': 'DUPLICATA', 'operacao': 'INSERT', 'campos': {
            'vl_parcela': {'valor': '2708.73', 'origem': 'boleto 4'}}},
    ],
    'importacao': {'chamada': 'DBAMV.FNC_IMPORTA_MGES_FNFI_SERV',
                   'parametros': {'p_cd_fornecedor': 3373, 'p_nr_documento': '93125822', 'p_nr_serie': 'A', 'p_cd_multi_empresa': 2},
                   'titulo_previsto': {'tabela': 'CON_PAG', 'tp_con_pag': 'ES', 'vl_bruto_conta': '2708.73', 'cd_reduzido': 241,
                                       'cd_setor': 68, 'cd_usuario_ins': 'RH000938',
                                       'parcelas': [{'nr_parcela': 1, 'dt_vencimento': '2026-11-25', 'vl_duplicata': '2708.73'}]}},
}
BOLETOS = {'nota': {'prestador_cnpj': '63554067000198', 'numero_nfse': '93125822', 'prestador_razao_social': 'HAPVIDA'},
           'boletos': [], 'resumo': {'quantidade': 1, 'soma': '2708.73', 'valor_liquido': '2708.73', 'pronta': True}}


class SimulacaoImportacaoTests(TestCase):
    URL = '/financeiro/contas-a-pagar/nfse-do-setor/?situacao=pronta&nota=63554067000198-93125822'

    def _entrar(self, telas):
        session = self.client.session
        session['api_access_token'] = 'token'
        session['api_user'] = {'id': 4, 'nome': 'Amoras', 'perfil': 'usuario', 'telas_permitidas': telas}
        session.save()

    def _api_get(self, path, params=None):
        return BOLETOS if path.endswith('/boletos') else {'oficinas': [], 'itens': []}

    @patch('core.views._mv_vinculo', return_value={'pode_gravar_no_mv': True})
    @patch('core.views.api_post', return_value=SIMULACAO)
    @patch('core.views.api_get')
    def test_financeiro_simula_e_ve_o_que_seria_gravado(self, api_get, api_post, _):
        self._entrar(['contas_pagar_nfse_setor', 'contas_pagar_nfse_regras'])
        api_get.side_effect = self._api_get

        response = self.client.get(self.URL + '&simular=1')

        api_post.assert_called_once_with(
            '/app_glosas/financeiro/contas-a-pagar/nfse/recebidas/63554067000198/93125822/importacao/simulacao', {})
        self.assertContains(response, 'Apta para importar.')
        self.assertContains(response, 'INSERT ENT_SERV')
        self.assertContains(response, 'R$ 2.708,73')
        self.assertContains(response, '01/11/2026')
        self.assertContains(response, '18/11/2026 10:36')
        self.assertContains(response, 'DBAMV.FNC_IMPORTA_MGES_FNFI_SERV')
        self.assertContains(response, '1ª · 25/11/2026 · R$ 2.708,73')
        self.assertContains(response, 'usado o 3373')
        self.assertContains(response, '<td>0 %</td>', html=False)

    @patch('core.views._mv_vinculo', return_value={'pode_gravar_no_mv': True})
    @patch('core.views.api_post')
    @patch('core.views.api_get')
    def test_pendencias_aparecem_com_o_codigo_do_mv(self, api_get, api_post, _):
        self._entrar(['contas_pagar_nfse_setor', 'contas_pagar_nfse_regras'])
        api_get.side_effect = self._api_get
        api_post.return_value = {**SIMULACAO, 'apta': False, 'gravacoes': [], 'importacao': {},
                                 'pendencias': [{'codigo': '-20003', 'mensagem': 'Fornecedor sem conta contábil.'}]}

        response = self.client.get(self.URL + '&simular=1')

        self.assertContains(response, 'Não pode ser importada ainda.')
        self.assertContains(response, '<code>-20003</code> Fornecedor sem conta contábil.', html=False)

    @patch('core.views._mv_vinculo', return_value={'pode_gravar_no_mv': True})
    @patch('core.views.api_post')
    @patch('core.views.api_get')
    def test_setor_nao_ve_nem_dispara_a_simulacao(self, api_get, api_post, _):
        self._entrar(['contas_pagar_nfse_setor'])
        api_get.side_effect = self._api_get

        response = self.client.get(self.URL + '&simular=1')

        api_post.assert_not_called()
        self.assertNotContains(response, 'Importação para o MV')

    @patch('core.views._mv_vinculo', return_value={'pode_gravar_no_mv': False})
    @patch('core.views.api_post')
    @patch('core.views.api_get')
    def test_sem_login_mv_pede_para_entrar(self, api_get, api_post, _):
        self._entrar(['contas_pagar_nfse_setor', 'contas_pagar_nfse_regras'])
        api_get.side_effect = self._api_get

        response = self.client.get(self.URL)

        api_post.assert_not_called()
        self.assertContains(response, 'Entre com o seu login MV')
        self.assertNotContains(response, 'Simular importação no MV')

    @patch('core.views._mv_vinculo', return_value={'pode_gravar_no_mv': True})
    @patch('core.views.api_post', side_effect=ApiError('Entre com o seu login MV antes.', status_code=412))
    @patch('core.views.api_get')
    def test_erro_da_api_vira_mensagem(self, api_get, api_post, _):
        self._entrar(['contas_pagar_nfse_setor', 'contas_pagar_nfse_regras'])
        api_get.side_effect = self._api_get

        response = self.client.get(self.URL + '&simular=1')

        self.assertContains(response, 'Não foi possível simular a importação')


class ImportacaoMvTests(TestCase):
    URL = '/financeiro/contas-a-pagar/nfse-do-setor/?situacao=pronta&nota=63554067000198-93125822'

    def setUp(self):
        session = self.client.session
        session['api_access_token'] = 'token'
        session['api_user'] = {'id': 4, 'nome': 'Amoras', 'perfil': 'usuario',
                               'telas_permitidas': ['contas_pagar_nfse_setor', 'contas_pagar_nfse_regras']}
        session.save()
        vinculo = patch('core.views._mv_vinculo', return_value={'pode_gravar_no_mv': True})
        vinculo.start()
        self.addCleanup(vinculo.stop)

    def _api_get(self, path, params=None):
        return BOLETOS if path.endswith('/boletos') else {'oficinas': [], 'itens': []}

    def _post(self, **extra):
        dados = {'acao': 'importar_mv', 'cnpj': '63554067000198', 'numero': '93125822',
                 'assinatura': '60f46a25dfb4a358498c', 'conferido': '1', 'situacao': 'pronta',
                 'nota': '63554067000198-93125822', **extra}
        return self.client.post('/financeiro/contas-a-pagar/nfse-do-setor/', dados, follow=True)

    @patch('core.views.api_post', return_value=SIMULACAO)
    @patch('core.views.api_get')
    def test_botao_importar_aparece_so_quando_apta(self, api_get, api_post):
        api_get.side_effect = self._api_get
        response = self.client.get(self.URL + '&simular=1')
        self.assertContains(response, 'Importar no MV')
        self.assertContains(response, 'name="assinatura" value="60f46a25dfb4a358498c"', html=False)

        api_post.return_value = {**SIMULACAO, 'apta': False, 'pendencias': [{'codigo': 'x', 'mensagem': 'y'}]}
        response = self.client.get(self.URL + '&simular=1')
        self.assertNotContains(response, 'Importar no MV')

    @patch('core.views.api_post', return_value={**SIMULACAO, 'gravacao_habilitada': False})
    @patch('core.views.api_get')
    def test_gravacao_desligada(self, api_get, api_post):
        api_get.side_effect = self._api_get
        response = self.client.get(self.URL + '&simular=1')
        self.assertNotContains(response, 'Importar no MV')
        self.assertContains(response, 'A gravação no MV está desligada')

    @patch('core.views.api_post', return_value={**SIMULACAO, 'apta': False, 'importacao_registrada': {
        'status': 'importada', 'cd_usuario_mv': 'RH000938', 'cd_ent_serv': 12500, 'cd_con_pag': 108700,
        'concluido_em': '2026-11-18T14:10:00+00:00', 'iniciado_em': '2026-11-18T14:09:58+00:00'}})
    @patch('core.views.api_get')
    def test_mostra_importacao_ja_feita(self, api_get, api_post):
        api_get.side_effect = self._api_get
        response = self.client.get(self.URL + '&simular=1')
        self.assertContains(response, 'Já importada no MV')
        self.assertContains(response, 'título 108700')

    @patch('core.views.api_post', return_value={'importada': True, 'cd_usuario_mv': 'RH000938',
                                                'cd_ent_serv': 12500, 'cd_con_pag': 108700})
    @patch('core.views.api_get')
    def test_importa_com_a_assinatura_conferida(self, api_get, api_post):
        api_get.side_effect = self._api_get
        response = self._post()
        api_post.assert_called_once_with(
            '/app_glosas/financeiro/contas-a-pagar/nfse/recebidas/63554067000198/93125822/importacao',
            {'assinatura': '60f46a25dfb4a358498c'})
        self.assertContains(response, 'importada no MV por RH000938')
        self.assertContains(response, 'título 108700')

    @patch('core.views.api_post')
    @patch('core.views.api_get')
    def test_sem_confirmar_nao_importa(self, api_get, api_post):
        api_get.side_effect = self._api_get
        response = self._post(conferido='')
        api_post.assert_not_called()
        self.assertContains(response, 'Confirme que conferiu')

    @patch('core.views.api_post', side_effect=ApiError('O MV recusou a importação; nada foi gravado. ORA-20007: x', status_code=422))
    @patch('core.views.api_get')
    def test_recusa_do_mv_vira_mensagem(self, api_get, api_post):
        api_get.side_effect = self._api_get
        response = self._post()
        self.assertContains(response, 'A NFS-e não foi importada')
        self.assertContains(response, 'ORA-20007')
