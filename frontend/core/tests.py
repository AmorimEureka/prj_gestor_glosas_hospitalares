from datetime import date
from unittest.mock import patch

from django.contrib.staticfiles import finders
from django.test import RequestFactory, TestCase

from core.services import ApiError
from core.views import (
    ACOMPANHAMENTO_GLOSAS_CACHE_KEY,
    apply_dashboard_filters,
    attach_registros_glosa,
    build_acompanhamento_rows,
    build_acompanhamento_resumo,
    build_dashboard_indicadores,
    build_geral_indicators,
    build_recuperacao_indicators,
    contextualize_registro_glosa_error,
    DASHBOARD_GLOSAS_CACHE_KEY,
    disabled_convenio_ids,
    extract_api_error_message,
    get_dashboard_filters,
    is_enabled_convenio_registro,
    is_recebido_registro,
    subtract_months,
)


class ContaAtendimentoRegistroTests(TestCase):
    def _conta(self):
        return {
            'cd_remessa': 15588,
            'cd_atendimento': 265501,
            'cd_reg': 326615,
            'cd_pro_fat': '40304361',
            'nr_guia': 'G1',
        }

    def _registro(self, sn_glosado):
        return {
            'id': 77,
            'cd_remessa': 15588,
            'cd_atendimento': 265501,
            'conta': 326615,
            'procedimento': '40304361',
            'guia': 'G1',
            'sn_glosado': sn_glosado,
            'processo_controle_fatura_gab': '131313/2026',
            'processo_recurso': '16161616/2026',
            'data_glosa': '2026-07-03',
            'dt_pagamento': '2026-07-10',
            'dt_recurso': '2026-07-16',
            'motivo_glosa': '1016 - BENEFICIARIO COM ATENDIMENTO SUSPENSO',
            'qtd_glosada': 1,
            'valor_glosado': 31.92,
            'descricao_glosa': 'descricao teste',
        }

    @patch('core.views.get_cached_api_payload')
    def test_recusa_nao_preenche_dados_do_acato(self, get_cached_api_payload):
        contas = [self._conta()]
        get_cached_api_payload.return_value = {'glosas': [self._registro('true')]}

        attach_registros_glosa(contas, {})

        self.assertEqual(contas[0]['registro_recusa']['id'], 77)
        self.assertEqual(contas[0]['registro_acato'], {})
        self.assertEqual(contas[0]['registro_glosa_status'], 'true')

    @patch('core.views.get_cached_api_payload')
    def test_recusa_com_status_booleano_e_identificada(self, get_cached_api_payload):
        contas = [self._conta()]
        get_cached_api_payload.return_value = {'glosas': [self._registro(True)]}

        attach_registros_glosa(contas, {})

        self.assertEqual(contas[0]['registro_recusa']['id'], 77)
        self.assertEqual(contas[0]['registro_glosa_status'], 'true')

    @patch('core.views.get_cached_api_payload')
    def test_acato_nao_preenche_dados_da_recusa(self, get_cached_api_payload):
        contas = [self._conta()]
        get_cached_api_payload.return_value = {'glosas': [self._registro('not')]}

        attach_registros_glosa(contas, {})

        self.assertEqual(contas[0]['registro_acato']['id'], 77)
        self.assertEqual(contas[0]['registro_recusa'], {})
        self.assertEqual(contas[0]['registro_glosa_status'], 'not')

    @patch('core.views.get_cached_api_payload')
    def test_guia_vazia_e_hifen_casam_mesmo_registro(self, get_cached_api_payload):
        conta = {
            **self._conta(),
            'cd_pro_fat': '90438787',
            'nr_guia': '-',
        }
        registro = {
            **self._registro('true'),
            'id': 781,
            'procedimento': '90438787',
            'guia': None,
            'valor_glosado': 0.45,
        }
        get_cached_api_payload.return_value = {'glosas': [registro]}

        attach_registros_glosa([conta], {})

        self.assertEqual(conta['registro_recusa']['id'], 781)
        self.assertEqual(conta['registro_glosa_status'], 'true')

    @patch('core.views.get_cached_api_payload')
    def test_guia_divergente_casa_por_conta_atendimento_e_procedimento(
        self,
        get_cached_api_payload,
    ):
        conta = {**self._conta(), 'nr_guia': 'GUIA-CONTA'}
        registro = {**self._registro('true'), 'guia': 'GUIA-REGISTRO'}
        get_cached_api_payload.return_value = {'glosas': [registro]}

        attach_registros_glosa([conta], {})

        self.assertEqual(conta['registro_recusa']['id'], 77)
        self.assertEqual(conta['registro_glosa_status'], 'true')

    @patch('core.views.get_cached_api_payload')
    def test_guia_divergente_nao_casa_quando_chave_sem_guia_e_ambigua(
        self,
        get_cached_api_payload,
    ):
        conta = {**self._conta(), 'nr_guia': 'GUIA-CONTA'}
        get_cached_api_payload.return_value = {
            'glosas': [
                {**self._registro('true'), 'id': 77, 'guia': 'GUIA-1'},
                {**self._registro('true'), 'id': 78, 'guia': 'GUIA-2'},
            ]
        }

        attach_registros_glosa([conta], {})

        self.assertNotIn('registro_glosa_id', conta)
        self.assertEqual(conta['registro_recusa'], {})


class AcompanhamentoRowsTests(TestCase):
    def test_convenio_desabilitado_exclui_registro_do_acompanhamento(self):
        convenios_desabilitados = disabled_convenio_ids(
            [{'cd_convenio': 7, 'habilitado': False}]
        )

        self.assertFalse(
            is_enabled_convenio_registro(
                {'cd_convenio': 7},
                convenios_desabilitados,
            )
        )
        self.assertTrue(
            is_enabled_convenio_registro(
                {'cd_convenio': 8},
                convenios_desabilitados,
            )
        )

    def test_recebido_exige_data_valor_e_quantidade(self):
        self.assertTrue(
            is_recebido_registro(
                {
                    'dt_recebimento': '2026-07-20',
                    'valor_recebido': 10,
                    'qtd_recebida': 1,
                }
            )
        )
        self.assertFalse(
            is_recebido_registro(
                {
                    'dt_recebimento': '2026-07-20',
                    'valor_recebido': 10,
                    'qtd_recebida': None,
                }
            )
        )

    def test_build_acompanhamento_rows_inclui_campos_da_tabela(self):
        rows = build_acompanhamento_rows(
            [
                {
                    'id': 10,
                    'sn_glosado': 'true',
                    'processo_recurso': 'REC-1',
                    'processo_controle_fatura_gab': 'ORI-1',
                    'nm_paciente': 'Paciente Teste',
                    'data_glosa': '2026-07-03',
                    'dt_recebimento': '2026-07-15',
                    'qtd_registro': 4,
                    'qtd_glosada': 2,
                    'qtd_recebida': 1,
                    'valor': 200,
                    'valor_glosado': 80,
                    'valor_recebido': 50,
                }
            ]
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['data_glosa_formatada'], '03/07/2026')
        self.assertEqual(row['recebido_label'], 'Sim')
        self.assertEqual(row['valor_glosado_total_formatado'], 'R$ 200,00')
        self.assertEqual(row['valor_recurso_formatado'], 'R$ 80,00')
        self.assertEqual(row['valor_recebido_formatado'], 'R$ 50,00')
        self.assertEqual(row['qtd_glosada'], 4)
        self.assertEqual(row['qtd_recurso'], 2)
        self.assertEqual(row['qtd_recebida'], 1)
        self.assertEqual(row['dt_recebimento_modal'], '2026-07-15')
        self.assertEqual(row['valor_recebido_modal'], 'R$ 50,00')
        self.assertEqual(row['qtd_recebida_modal'], '1')

    def test_modal_de_recebimento_ignora_recebimento_incompleto(self):
        rows = build_acompanhamento_rows(
            [
                {
                    'id': 10,
                    'sn_glosado': 'true',
                    'processo_recurso': 'REC-1',
                    'processo_controle_fatura_gab': 'ORI-1',
                    'nm_paciente': 'Paciente Teste',
                    'data_glosa': '2026-07-03',
                    'dt_recebimento': '2026-07-15',
                    'qtd_recebida': 0,
                    'valor': 200,
                    'valor_glosado': 80,
                    'valor_recebido': 50,
                    'observacao_recebimento': 'Recebimento parcial inválido',
                }
            ]
        )

        row = rows[0]

        self.assertFalse(row['recebido'])
        self.assertEqual(row['recebido_label'], 'Não')
        self.assertEqual(row['dt_recebimento_formatada'], '15/07/2026')
        self.assertEqual(row['valor_recebido_formatado'], 'R$ 50,00')
        self.assertEqual(row['qtd_recebida'], 0)
        self.assertEqual(row['dt_recebimento_modal'], '')
        self.assertEqual(row['valor_recebido_modal'], '')
        self.assertEqual(row['qtd_recebida_modal'], '')
        self.assertEqual(row['observacao_recebimento_modal'], '')

    def test_resumo_em_aberto_exige_recebimento_completo(self):
        rows = [
            {
                'processo_recurso': 'REC-1',
                'processo_controle_fatura_gab': 'ORI-1',
                'valor_recurso': 100,
                'valor_recebido': 0,
                'qtd_recurso': 1,
                'data_glosa_formatada': '01/07/2026',
                'paciente_label': 'Paciente 1',
                'dt_recebimento': '',
            },
            {
                'processo_recurso': 'REC-2',
                'processo_controle_fatura_gab': 'ORI-2',
                'valor_recurso': 0.45,
                'valor_recebido': 0.45,
                'qtd_recurso': 1,
                'data_glosa_formatada': '01/07/2026',
                'paciente_label': 'Paciente 2',
                'dt_recebimento': '2026-07-20',
            },
            {
                'processo_recurso': 'REC-3',
                'processo_controle_fatura_gab': 'ORI-3',
                'valor_recurso': 20,
                'valor_recebido': 20,
                'qtd_recebida': 1,
                'qtd_recurso': 1,
                'data_glosa_formatada': '01/07/2026',
                'paciente_label': 'Paciente 3',
                'dt_recebimento': '2026-07-20',
            },
            {
                'processo_recurso': 'REC-4',
                'processo_controle_fatura_gab': 'ORI-4',
                'valor_recurso': 30,
                'valor_recebido': 30,
                'qtd_recebida': 1,
                'qtd_recurso': 1,
                'data_glosa_formatada': '01/07/2026',
                'paciente_label': 'Paciente 4',
                'dt_recebimento': '',
            },
        ]

        resumo = build_acompanhamento_resumo(rows)

        self.assertEqual(resumo['em_aberto'], 3)
        self.assertEqual(resumo['valor_em_aberto_total'], 130.45)
        self.assertEqual(resumo['recebidos'], 1)


class DashboardIndicadoresTests(TestCase):
    def test_dashboard_e_acompanhamento_compartilham_cache_de_glosas(self):
        self.assertEqual(ACOMPANHAMENTO_GLOSAS_CACHE_KEY, DASHBOARD_GLOSAS_CACHE_KEY)

    def test_extract_api_error_message_remove_payload_bruto_da_validacao(self):
        exc = ApiError(
            '{"detail":[{"type":"value_error","loc":["body"],'
            '"msg":"Value error, O valor glosado/acatado nao pode exceder o valor do registro.",'
            '"input":{"codigo_paciente":107821,"valor_glosado":86.0}}]}',
            422,
        )

        self.assertEqual(
            extract_api_error_message(exc),
            'O valor glosado/acatado nao pode exceder o valor do registro.',
        )

    def test_contextualize_registro_glosa_error_usa_valor_recursado(self):
        self.assertEqual(
            contextualize_registro_glosa_error(
                'O valor glosado/acatado nao pode exceder o valor do registro.',
                is_acatar=False,
            ),
            'O valor recursado nao pode exceder o valor do registro.',
        )

    def test_contextualize_registro_glosa_error_usa_valor_acatado(self):
        self.assertEqual(
            contextualize_registro_glosa_error(
                'O valor glosado/acatado nao pode exceder o valor do registro.',
                is_acatar=True,
            ),
            'O valor acatado nao pode exceder o valor do registro.',
        )

    def test_dashboard_filters_aplica_periodo_padrao_de_doze_meses(self):
        request = RequestFactory().get('/indicadores/')
        today = date.today()

        filtros = get_dashboard_filters(request)

        self.assertEqual(
            filtros['periodo_inicio'],
            subtract_months(today, 11).strftime('%Y-%m-%d'),
        )
        self.assertEqual(filtros['periodo_fim'], today.strftime('%Y-%m-%d'))

    def test_dashboard_filters_preserva_periodo_informado(self):
        request = RequestFactory().get(
            '/indicadores/',
            {
                'periodo_inicio': '2026-01-10',
                'periodo_fim': '2026-03-20',
            },
        )

        filtros = get_dashboard_filters(request)

        self.assertEqual(filtros['periodo_inicio'], '2026-01-10')
        self.assertEqual(filtros['periodo_fim'], '2026-03-20')

    def test_dashboard_filters_aceita_multiplos_valores(self):
        request = RequestFactory().get(
            '/indicadores/',
            {
                'convenio': ['AMIL', 'BACEN'],
                'prestador': ['Prestador A', 'Prestador B'],
                'tipo_atendimento': ['Urgência', 'Internação'],
                'motivo_glosa': ['Motivo A', 'Motivo B'],
            },
        )

        filtros = get_dashboard_filters(request)

        self.assertEqual(filtros['convenio'], ['AMIL', 'BACEN'])
        self.assertEqual(filtros['prestador'], ['Prestador A', 'Prestador B'])
        self.assertEqual(filtros['tipo_atendimento'], ['Urgência', 'Internação'])
        self.assertEqual(filtros['motivo_glosa'], ['Motivo A', 'Motivo B'])

    def test_dashboard_filters_aplica_multiplos_valores(self):
        rows = [
            {
                'data_glosa': '2026-01-10',
                'convenio': 'AMIL',
                'prestador': 'Prestador A',
                'tp_atendimento': 'Urgência',
                'motivo_glosa': 'Motivo A',
                'sn_glosado': 'true',
            },
            {
                'data_glosa': '2026-01-10',
                'convenio': 'BACEN',
                'prestador': 'Prestador B',
                'tp_atendimento': 'Internação',
                'motivo_glosa': 'Motivo B',
                'sn_glosado': 'true',
            },
            {
                'data_glosa': '2026-01-10',
                'convenio': 'BRADESCO',
                'prestador': 'Prestador C',
                'tp_atendimento': 'Externo',
                'motivo_glosa': 'Motivo C',
                'sn_glosado': 'true',
            },
        ]

        filtered = apply_dashboard_filters(
            rows,
            {
                'periodo_inicio': '2026-01-01',
                'periodo_fim': '2026-01-31',
                'convenio': ['AMIL', 'BACEN'],
                'prestador': ['Prestador A', 'Prestador B'],
                'tipo_atendimento': ['Urgência', 'Internação'],
                'motivo_glosa': ['Motivo A', 'Motivo B'],
                'tratativa': '',
            },
        )

        self.assertEqual(len(filtered), 2)
        self.assertEqual([row['convenio'] for row in filtered], ['AMIL', 'BACEN'])

    def test_recuperacao_exibe_todos_motivos_com_valor(self):
        rows = [
            {
                'sn_ativo': 'true',
                'sn_glosado': 'true',
                'processo_recurso': f'REC-{index}',
                'dt_recurso': '2026-01-10',
                'data_glosa': '2026-01-01',
                'motivo_glosa': f'Motivo {index:02d}',
	                'convenio': 'Convenio A',
	                'valor_glosado': 1000 + index,
	                'valor_recebido': 500,
	                'qtd_recebida': 1,
	                'dt_recebimento': '2026-01-20',
	            }
            for index in range(13)
        ]

        indicadores = build_recuperacao_indicators(rows)

        self.assertEqual(indicadores['total_motivos'], 13)
        self.assertEqual(len(indicadores['scatter']), 13)

    def test_recuperacao_mensal_usa_periodo_informado(self):
        indicadores = build_recuperacao_indicators(
            [
                {
                    'sn_ativo': 'true',
                    'sn_glosado': 'true',
                    'processo_recurso': 'REC-1',
                    'dt_recurso': '2026-02-10',
                    'data_glosa': '2026-02-01',
                    'motivo_glosa': 'Motivo teste',
	                    'convenio': 'Convenio A',
	                    'valor_glosado': 1000,
	                    'valor_recebido': 500,
	                    'qtd_recebida': 1,
	                    'dt_recebimento': '2026-02-20',
	                }
            ],
            '2026-01-10',
            '2026-03-20',
        )

        self.assertEqual(
            indicadores['mensal']['months'],
            ['01/2026', '02/2026', '03/2026'],
        )
        self.assertEqual(indicadores['mensal']['month_count'], 3)
        self.assertEqual(indicadores['mensal']['period_label'], '01/2026 a 03/2026')

    def test_dashboard_kpi_em_aberto_usa_mesma_regra_do_acompanhamento(self):
        registros = [
            {
                'id': 1,
                'sn_ativo': 'true',
                'sn_glosado': 'true',
                'processo_recurso': 'REC-1',
                'dt_recurso': '2026-01-10',
                'data_glosa': '2026-01-01',
                'valor_glosado': 100,
            },
            {
                'id': 2,
                'sn_ativo': 'true',
                'sn_glosado': 'true',
                'processo_recurso': 'REC-2',
                'dt_recurso': '2026-01-10',
                'data_glosa': '2026-01-01',
                'valor_glosado': 0.45,
                'valor_recebido': 0.45,
                'dt_recebimento': '2026-01-20',
            },
            {
                'id': 3,
                'sn_ativo': 'true',
                'sn_glosado': 'true',
                'processo_recurso': 'REC-3',
                'dt_recurso': '2026-01-10',
                'data_glosa': '2026-01-01',
                'valor_glosado': 20,
                'valor_recebido': 20,
                'qtd_recebida': 1,
                'dt_recebimento': '2026-01-20',
            },
        ]

        indicadores = build_dashboard_indicadores(registros)
        resumo = build_acompanhamento_resumo(build_acompanhamento_rows(registros))

        self.assertEqual(
            indicadores['kpis']['total_sem_recuperacao'],
            resumo['em_aberto'],
        )
        self.assertEqual(
            indicadores['kpis']['total_sem_recuperacao_valor'],
            resumo['valor_em_aberto_total'],
        )
        self.assertEqual(resumo['valor_em_aberto_total'], 100.45)

    def test_recuperacao_tooltip_usa_legenda_de_eficiencia_operacional(self):
        indicadores = build_recuperacao_indicators(
            [
                {
                    'sn_ativo': 'true',
                    'sn_glosado': 'true',
                    'processo_recurso': 'REC-1',
                    'dt_recurso': '2026-01-10',
                    'data_glosa': '2026-01-01',
                    'motivo_glosa': 'Motivo teste',
	                    'convenio': 'Convenio A',
	                    'valor_glosado': 1000,
	                    'valor_recebido': 500,
	                    'qtd_recebida': 1,
	                    'dt_recebimento': '2026-01-20',
	                }
            ]
        )

        tooltip = indicadores['scatter'][0]['tooltip']

        self.assertIn(
            'Taxa Eficiência Op. (vl. recuperado / vl. recursado): 50.0%',
            tooltip,
        )
        self.assertNotIn('Taxa de sucesso do recurso', tooltip)

    def test_geral_consolida_funil_por_convenio_e_taxas_mensais(self):
        indicadores = build_geral_indicators(
            [
                {
                    'sn_ativo': 'true',
                    'sn_glosado': 'true',
                    'processo_recurso': 'REC-1',
                    'dt_recurso': '2026-01-10',
                    'data_glosa': '2026-01-01',
                    'motivo_glosa': 'Motivo A',
                    'convenio': 'Convenio A',
	                    'valor': 10000,
	                    'valor_glosado': 1000,
	                    'valor_recebido': 500,
	                    'qtd_recebida': 1,
	                    'dt_recebimento': '2026-01-20',
	                },
                {
                    'sn_ativo': 'true',
                    'sn_glosado': 'not',
                    'processo_recurso': 'AC-1',
                    'dt_recurso': '2026-01-12',
                    'data_glosa': '2026-01-01',
                    'motivo_glosa': 'Motivo B',
                    'convenio': 'Convenio B',
                    'valor': 5000,
                    'valor_glosado': 250,
                    'valor_recebido': 0,
                },
            ],
            '2026-01-01',
            '2026-01-31',
        )

        self.assertEqual(indicadores['totals']['fatura'], 15000)
        self.assertEqual(indicadores['totals']['glosa'], 1250)
        self.assertEqual(indicadores['totals']['recursado'], 1000)
        self.assertEqual(indicadores['totals']['acato'], 250)
        self.assertEqual(indicadores['funnel'][0]['label'], '1. Fatura Total')
        self.assertEqual(len(indicadores['funnel'][0]['segments']), 2)
        self.assertEqual(indicadores['funnel'][3]['reference_key'], 'recursado')
        self.assertEqual(indicadores['funnel'][3]['reference_label'], 'Recursos')
        self.assertEqual(indicadores['funnel'][3]['conversion'], 50.0)
        self.assertEqual(indicadores['funnel'][4]['reference_key'], 'recursado')
        self.assertEqual(indicadores['funnel'][4]['reference_label'], 'Recursos')
        self.assertEqual(indicadores['funnel'][4]['conversion'], 25.0)
        self.assertEqual(indicadores['mensal'][0]['taxa_glosa'], 8.3)
        self.assertEqual(indicadores['mensal'][0]['taxa_acato'], 20.0)
        self.assertIn('Motivo B: 1 acato', indicadores['mensal'][0]['motivos_tooltip'])


class LoginFlowTests(TestCase):
    def test_renderiza_tela_de_login(self):
        response = self.client.get('/login/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gestão de Glosas')
        self.assertContains(response, 'login-brand-slogan')
        self.assertContains(response, 'Hospital Prontocardio')
        self.assertIsNotNone(finders.find('img/roger.jpeg'))

    def test_redireciona_visitante_para_login(self):
        response = self.client.get('/')

        self.assertRedirects(
            response,
            '/login/?next=%2F',
            fetch_redirect_response=False,
        )

    @patch('core.views.api_get')
    @patch('core.views.api_authenticate')
    def test_login_armazena_token_e_usuario(self, authenticate, api_get):
        authenticate.return_value = {
            'access_token': 'token-seguro',
            'token_type': 'Bearer',
        }
        api_get.return_value = {
            'id': 1,
            'nome': 'Usuário Teste',
            'email': 'usuario@teste.com',
        }

        response = self.client.post(
            '/login/',
            {
                'email': 'usuario@teste.com',
                'password': 'senha',
                'next': '/',
            },
        )

        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assertEqual(
            self.client.session['api_access_token'],
            'token-seguro',
        )
        self.assertEqual(
            self.client.session['api_user']['nome'],
            'Usuário Teste',
        )
        api_get.assert_called_once_with('/usuarios/me', token='token-seguro')

    @patch('core.views.api_get')
    @patch('core.views.api_authenticate')
    def test_login_rejeita_redirecionamento_externo(self, authenticate, api_get):
        authenticate.return_value = {'access_token': 'token-seguro'}
        api_get.return_value = {
            'id': 1,
            'nome': 'Usuário Teste',
            'email': 'usuario@teste.com',
        }

        response = self.client.post(
            '/login/',
            {
                'email': 'usuario@teste.com',
                'password': 'senha',
                'next': 'https://site-malicioso.example',
            },
        )

        self.assertRedirects(response, '/', fetch_redirect_response=False)

    def test_logout_limpa_sessao(self):
        session = self.client.session
        session['api_access_token'] = 'token-seguro'
        session['api_user'] = {'nome': 'Usuário Teste'}
        session.save()

        response = self.client.post('/logout/')

        self.assertRedirects(
            response,
            '/login/',
            fetch_redirect_response=False,
        )
        self.assertNotIn('api_access_token', self.client.session)

    @patch('core.views.api_post')
    def test_solicita_recuperacao_de_senha(self, api_post):
        response = self.client.post(
            '/esqueci-senha/', {'email': 'usuario@teste.com'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Verifique seu e-mail')
        api_post.assert_called_once_with(
            '/autenticacao/esqueci-senha',
            {'email': 'usuario@teste.com'},
        )

    @patch('core.views.api_post')
    def test_redefine_senha_com_token(self, api_post):
        response = self.client.post(
            '/redefinir-senha/',
            {
                'token': 'token-seguro-com-tamanho-suficiente',
                'password': 'nova-senha-segura',
                'password_confirmation': 'nova-senha-segura',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Senha atualizada')
        api_post.assert_called_once()

    def test_rota_redefinicao_compativel_com_api(self):
        response = self.client.get(
            '/autenticacao/redefinir-senha/',
            {'token': 'token-seguro-com-tamanho-suficiente'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Crie uma nova senha')

    def test_bloqueia_gestao_de_acessos_para_usuario_comum(self):
        session = self.client.session
        session['api_access_token'] = 'token-seguro'
        session['api_user'] = {
            'nome': 'Usuário',
            'perfil': 'usuario',
        }
        session.save()

        response = self.client.get('/administrativo/acessos/')

        self.assertRedirects(response, '/', fetch_redirect_response=False)
