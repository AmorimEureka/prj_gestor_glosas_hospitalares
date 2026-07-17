from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.test import RequestFactory, TestCase

from core.services import ApiError
from core.views import (
    ACOMPANHAMENTO_GLOSAS_CACHE_KEY,
    apply_dashboard_filters,
    attach_registros_glosa,
    build_acompanhamento_rows,
    build_acompanhamento_resumo,
    build_conciliacao_faturamento_payload,
    build_edicao_conciliacao_payload,
    build_recebimento_remessa_payload,
    build_dashboard_indicadores,
    build_geral_indicators,
    build_recuperacao_indicators,
    CONCILIACAO_FATURAMENTO_PATH,
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

    @patch('core.views.get_cached_api_payload')
    def test_lancamento_diferencia_itens_da_mesma_conta(
        self,
        get_cached_api_payload,
    ):
        contas = [
            {**self._conta(), 'cd_lancamento': 1},
            {**self._conta(), 'cd_lancamento': 2},
        ]
        get_cached_api_payload.return_value = {
            'glosas': [
                {**self._registro('true'), 'id': 91, 'cd_lancamento': 1},
                {**self._registro('true'), 'id': 92, 'cd_lancamento': 2},
            ]
        }

        attach_registros_glosa(contas, {})

        self.assertEqual(contas[0]['registro_glosa_id'], 91)
        self.assertEqual(contas[1]['registro_glosa_id'], 92)


class AcompanhamentoRowsTests(TestCase):
    def test_glosa_da_conciliacao_agrupa_itens_sem_duplicar_valor(self):
        registros = [
            {
                'id': item_id,
                'sn_glosado': 'true',
                'conciliacao_remessa_id': 45,
                'cd_remessa': 987,
                'cd_atendimento': atendimento,
                'conta': conta,
                'cd_lancamento': lancamento,
                'data_glosa': '2026-07-15',
                'qtd_registro': 1,
                'valor': 60,
                'valor_glosa_origem': 20,
                'valor_glosa_pendente': 20,
            }
            for item_id, atendimento, conta, lancamento in (
                (1, 101, 1001, 1),
                (2, 102, 1002, 2),
            )
        ]

        rows = build_acompanhamento_rows(registros)
        resumo = build_acompanhamento_resumo(rows)

        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['tratativa_pendente'] for row in rows))
        self.assertTrue(
            all(
                row['idade_bucket'] == 'aguardando_tratativa'
                for row in rows
            )
        )
        self.assertEqual(resumo['processos'], 1)
        self.assertEqual(resumo['em_aberto'], 1)
        self.assertEqual(resumo['valor_em_aberto_total'], 20)

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
        self.assertEqual(row['recebido_label'], 'Parcial')
        self.assertFalse(row['recebido'])
        self.assertTrue(row['recebimento_parcial'])
        self.assertEqual(row['valor_em_aberto'], 30)
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

    def test_resumo_desconta_recebimento_parcial_do_valor_em_aberto(self):
        rows = build_acompanhamento_rows(
            [
                {
                    'id': 10,
                    'sn_glosado': 'true',
                    'processo_recurso': 'REC-PARCIAL',
                    'processo_controle_fatura_gab': 'ORI-1',
                    'data_glosa': '2026-07-03',
                    'qtd_registro': 1,
                    'qtd_recursado': 1,
                    'qtd_recebida': 1,
                    'valor': 100,
                    'valor_recursado': 100,
                    'valor_recebido': 40,
                    'dt_recebimento': '2026-07-15',
                }
            ]
        )

        resumo = build_acompanhamento_resumo(rows)

        self.assertEqual(resumo['em_aberto'], 1)
        self.assertEqual(resumo['recebidos'], 0)
        self.assertEqual(resumo['valor_em_aberto_total'], 60)
        self.assertEqual(resumo['valor_recebido_total'], 40)


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


class FollowUpGlosasTests(TestCase):
    def setUp(self):
        session = self.client.session
        session['api_access_token'] = 'token-seguro'
        session['api_user'] = {
            'id': 1,
            'nome': 'Núcleo de Glosas',
            'email': 'glosas@teste.com',
            'perfil': 'usuario',
        }
        session.save()

    def _api_payload(self):
        return {
            'cards': [
                {
                    'conciliacao_remessa_id': 12,
                    'cd_remessa': 987,
                    'convenio': 'Convênio Teste',
                    'data_entrega': '2026-07-10',
                    'numero_nfse': 'NFS-5333',
                    'valor_remessa': '1000.00',
                    'valor_glosado': '150.00',
                    'valor_glosa_pendente': '100.00',
                    'valor_total_tratado': '50.00',
                    'pacientes': [
                        {
                            'codigo_paciente': 51,
                            'nm_paciente': 'Maria da Silva',
                            'itens': [
                                {
                                    'cd_paciente': 51,
                                    'nm_paciente': 'Maria da Silva',
                                    'cd_remessa': 987,
                                    'cd_atendimento': 789,
                                    'cd_reg': 456,
                                    'cd_lancamento': 3,
                                    'cd_prestador': 4,
                                    'nm_prestador': 'Hospital Prontocardio',
                                    'cd_convenio': 5,
                                    'nm_convenio': 'Convênio Teste',
                                    'tp_atendimento': 'Internação',
                                    'cd_pro_fat': 'PROC-10',
                                    'cd_gru_pro': 10,
                                    'ds_gru_pro': 'Diagnóstico',
                                    'cd_gru_fat': 1,
                                    'ds_gru_fat': 'EXAMES E DIAGNÓSTICOS',
                                    'descricao': 'Procedimento analítico',
                                    'nr_guia': 'GUIA-20',
                                    'dt_atendimento': '2026-07-01T08:00:00',
                                    'dt_alta': '2026-07-03T10:00:00',
                                    'dt_lancamento': '2026-07-02T09:30:00',
                                    'qt_lancamento': '2.00',
                                    'vl_total_conta': '150.00',
                                    'registro_glosa': {
                                        'id': 71,
                                        'sn_ativo': 'true',
                                        'sn_glosado': 'true',
                                        'processo_controle_fatura_gab': 'CONC-12',
                                        'processo_recurso': None,
                                        'data_glosa': '2026-07-10',
                                        'motivo_glosa': 'Pendente de classificação',
                                        'descricao_glosa': '',
                                        'qtd_recursado': None,
                                        'valor_recursado': None,
                                        'dt_recurso': None,
                                        'dt_pagamento': None,
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
            'total': 1,
            'valor_total_glosado': '150.00',
            'valor_total_pendente': '100.00',
            'valor_total_tratado': '50.00',
            'limit': 10,
            'offset': 0,
        }

    @patch('core.views.get_cached_api_payload')
    @patch('core.views.api_get')
    def test_listagem_carrega_detalhamento_somente_ao_expandir(
        self,
        api_get,
        get_cached_api_payload,
    ):
        api_get.return_value = self._api_payload()
        get_cached_api_payload.return_value = {'itens': []}

        response = self.client.get('/follow-up-glosas/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '#987')
        self.assertContains(
            response,
            'hx-get="/follow-up-glosas/?detalhar_vinculo=12"',
        )
        self.assertContains(response, 'hx-trigger="follow-up-load once"')
        self.assertContains(response, '>Expandir</button>')
        self.assertContains(response, '>Colapsar todos</button>')
        self.assertContains(response, '@expand-follow-up-level-1.window')
        self.assertContains(response, 'id="follow-up-page-select"')
        self.assertContains(response, '<option value="1" selected>1</option>')
        self.assertContains(response, '<span>de 1</span>')
        self.assertContains(response, 'Total tratado')
        self.assertContains(response, 'TOTAL TRATADO')
        self.assertContains(response, 'R$ 50,00', count=2)
        self.assertEqual(
            response.context['resumo']['valor_total_tratado'],
            50.0,
        )
        self.assertContains(
            response,
            'Carregando detalhamento da remessa...',
        )
        self.assertNotContains(response, 'Maria da Silva')
        self.assertEqual(response.context['cards'][0]['pacientes'], [])
        api_get.assert_called_once_with(
            '/app_glosas/financeiro/conciliacao-faturamento/glosas-pendentes',
            params={
                'limit': 10,
                'offset': 0,
                'incluir_detalhes': 'false',
            },
        )

    def test_lista_follow_up_preserva_altura_natural_dos_cards(self):
        css = Path(finders.find('css/app.css')).read_text()

        self.assertIn(
            '.follow-up-glosa-list {\n  display: block;\n}',
            css,
        )
        self.assertIn(
            '.follow-up-glosa-card {\n  margin-bottom: 12px;',
            css,
        )

        base_template = Path(
            finders.find('css/app.css')
        ).parent.parent.parent / 'templates' / 'base.html'
        self.assertIn(
            '?v=20260717-navbar-capitalizacao-1',
            base_template.read_text(),
        )

    @patch('core.views.get_cached_api_payload')
    @patch('core.views.api_get')
    def test_paginacao_preserva_filtro_e_exibe_navegacao_superior_e_inferior(
        self,
        api_get,
        get_cached_api_payload,
    ):
        payload = self._api_payload()
        payload.update({'total': 25, 'limit': 10, 'offset': 10})
        api_get.return_value = payload
        get_cached_api_payload.return_value = {'itens': []}

        response = self.client.get(
            '/follow-up-glosas/',
            {'q': 'IPM', 'page': '2'},
        )

        self.assertEqual(response.status_code, 200)
        pagination = response.context['pagination']
        self.assertEqual(pagination['previous_url'], '?q=IPM&page=1')
        self.assertEqual(pagination['next_url'], '?q=IPM&page=3')
        self.assertContains(response, '<option value="2" selected>2</option>')
        self.assertContains(response, 'Página 2 de 3')
        self.assertContains(response, 'href="?q=IPM&amp;page=1"', count=2)
        self.assertContains(response, 'href="?q=IPM&amp;page=3"', count=2)
        api_get.assert_called_once_with(
            '/app_glosas/financeiro/conciliacao-faturamento/glosas-pendentes',
            params={
                'limit': 10,
                'offset': 10,
                'incluir_detalhes': 'false',
                'q': 'IPM',
            },
        )

    @patch('core.views.get_cached_api_payload')
    @patch('core.views.api_get')
    def test_renderiza_remessa_pacientes_itens_e_menu(
        self,
        api_get,
        get_cached_api_payload,
    ):
        api_get.return_value = self._api_payload()
        get_cached_api_payload.return_value = {'itens': []}

        response = self.client.get(
            '/follow-up-glosas/',
            {'detalhar_vinculo': '12'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<span class="nav-label">Núcleo Gestor de Glosas</span>',
        )
        css = Path(finders.find('css/app.css')).read_text()
        nav_group_rule = css.split('.nav-group-toggle {', 1)[1].split(
            '}',
            1,
        )[0]
        self.assertIn('text-transform: none;', nav_group_rule)
        self.assertNotIn('text-transform: uppercase;', nav_group_rule)
        content = response.content.decode()
        self.assertLess(
            content.index('Follow-Up de Glosas'),
            content.index('title="Triagem"'),
        )
        for expected in (
            'REMESSA',
            '#987',
            'CONVÊNIO',
            'Convênio Teste',
            'DATA ENTREGA',
            '10/07/2026',
            'NFS-5333',
            'VALOR DA REMESSA',
            'R$ 1.000,00',
            'VALOR GLOSADO',
            'R$ 150,00',
            'TOTAL TRATADO',
            'R$ 50,00',
            'Maria da Silva',
            'Procedimento analítico',
            'Atendimento <strong>#789</strong>',
            'EXAMES E DIAGNÓSTICOS',
            'Data da alta',
            'DT Lanç.',
            'Tipo Atendimento',
            'Qtd Lanç.',
            'Recursar',
            '+ Acatar',
            'follow-up-glosa-records-scroll',
            '<template x-if="patientOpen">',
            '<template x-if="atdOpen">',
        ):
            self.assertContains(response, expected)
        self.assertNotContains(
            response,
            'Processo / N Controle / N Fatura / N GAB (Processo Original)',
        )
        self.assertNotContains(response, '<label>Data da glosa')
        self.assertNotContains(response, '<label>Dt pagamento')
        self.assertContains(
            response,
            'name="processo_controle_fatura_gab" value="CONC-12"',
        )
        self.assertContains(
            response,
            'name="data_glosa" value="2026-07-10"',
        )
        self.assertContains(
            response,
            'name="dt_pagamento" value="2026-07-10"',
        )
        paciente = response.context['cards'][0]['pacientes'][0]
        self.assertEqual(paciente['total_atendimentos'], 1)
        self.assertEqual(paciente['atendimentos'][0]['total_grupos'], 1)
        self.assertEqual(
            paciente['atendimentos'][0]['grupos_procedimento'][0][
                'cd_gru_fat'
            ],
            1,
        )
        api_get.assert_called_once_with(
            '/app_glosas/financeiro/conciliacao-faturamento/glosas-pendentes',
            params={
                'limit': 1,
                'offset': 0,
                'incluir_detalhes': 'true',
                'conciliacao_remessa_id': 12,
            },
        )

    @patch('core.views.api_put')
    def test_recursar_atualiza_registro_analitico_existente(self, api_put):
        api_put.return_value = {'id': 71, 'sn_glosado': 'true'}
        response = self.client.post(
            '/follow-up-glosas/',
            {
                'registro_glosa_id': '71',
                'cd_paciente': '51',
                'nm_paciente': 'Maria da Silva',
                'cd_remessa': '987',
                'cd_atendimento': '789',
                'cd_reg': '456',
                'cd_lancamento': '3',
                'cd_prestador': '4',
                'nm_prestador': 'Hospital Prontocardio',
                'cd_convenio': '5',
                'nm_convenio': 'Convênio Teste',
                'tp_atendimento': 'Internação',
                'cd_pro_fat': 'PROC-10',
                'cd_gru_pro': '10',
                'ds_gru_pro': 'Diagnóstico',
                'cd_gru_fat': '1',
                'ds_gru_fat': 'EXAMES E DIAGNÓSTICOS',
                'descricao': 'Procedimento analítico',
                'nr_guia': 'GUIA-20',
                'dt_atendimento': '2026-07-01T08:00:00',
                'dt_alta': '2026-07-03T10:00:00',
                'dt_lancamento': '2026-07-02T09:30:00',
                'qt_lancamento': '2',
                'vl_total_conta': '150.00',
                'sn_glosado': 'true',
                'processo_controle_fatura_gab': 'CONC-12',
                'data_glosa': '2026-07-10',
                'dt_pagamento': '2026-07-10',
                'motivo_glosa': '1016 - Motivo TISS',
                'processo_recurso': 'REC-71',
                'dt_recurso': '2026-07-11',
                'qtd_glosada': '1',
                'valor_glosado': 'R$ 75,00',
                'descricao_glosa': 'Recurso enviado',
                'form_action': 'salvar',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                'ok': True,
                'message': 'Recurso registrado no Follow-Up de Glosas.',
                'tag': 'success',
                'payload': {'id': 71, 'sn_glosado': 'true'},
            },
        )
        path, payload = api_put.call_args.args
        self.assertTrue(path.endswith('/71'))
        self.assertEqual(payload['processo_controle_fatura_gab'], 'CONC-12')
        self.assertEqual(payload['data_glosa'], '2026-07-10')
        self.assertEqual(payload['dt_pagamento'], '2026-07-10')
        self.assertEqual(payload['descricao_item'], 'Procedimento analítico')
        self.assertEqual(payload['cd_gru_pro'], 10)
        self.assertEqual(payload['ds_gru_pro'], 'Diagnóstico')
        self.assertEqual(payload['cd_gru_fat'], 1)
        self.assertEqual(payload['ds_gru_fat'], 'EXAMES E DIAGNÓSTICOS')
        self.assertEqual(payload['processo_recurso'], 'REC-71')
        self.assertEqual(payload['valor_recursado'], 75.0)


class ConciliacaoFaturamentoTests(TestCase):
    def setUp(self):
        cache.clear()
        session = self.client.session
        session['api_access_token'] = 'token-seguro'
        session['api_user'] = {
            'id': 1,
            'nome': 'Financeiro',
            'email': 'financeiro@teste.com',
            'perfil': 'usuario',
        }
        session.save()

    def test_monta_payload_com_remessa_e_notas(self):
        payload = build_conciliacao_faturamento_payload(
            {
                'cd_remessa': '10',
                'processo_recebimento': ' PROC-1 ',
                'notas_json': (
                    '[{"nfse_row_hash": "hash-1", '
                    '"valor_bruto_remessa": "100.00", '
                    '"sn_glosado": true, "valor_glosado": "20.00", '
                    '"data_previsao_recebimento": "2026-08-10"}]'
                ),
            }
        )

        self.assertEqual(payload['cd_remessa'], 10)
        self.assertEqual(payload['processo_recebimento'], 'PROC-1')
        self.assertEqual(payload['notas'][0]['nfse_row_hash'], 'hash-1')
        self.assertEqual(payload['notas'][0]['valor_alocado'], '80.00')
        self.assertNotIn('valor_bruto_remessa', payload['notas'][0])

    def test_impede_glosa_igual_ou_maior_que_parcela_da_remessa(self):
        with self.assertRaisesRegex(
            ValueError,
            'valor glosado deve ser menor',
        ):
            build_conciliacao_faturamento_payload(
                {
                    'cd_remessa': '10',
                    'processo_recebimento': 'PROC-1',
                    'notas_json': (
                        '[{"nfse_row_hash": "hash-1", '
                        '"valor_bruto_remessa": "20.00", '
                        '"sn_glosado": true, '
                        '"valor_glosado": "20.00"}]'
                    ),
                }
            )

    @patch('core.views.api_get')
    def test_renderiza_remessas_pendentes_e_menu_financeiro(self, api_get):
        def resposta(path, params=None):
            if path.endswith('/remessas'):
                return {
                    'remessas': [
                        {
                            'cd_remessa': 987,
                            'data_competencia': '2026-07-01',
                            'convenio': 'Convênio Teste',
                            'cnpj_convenio': '12345678000190',
                            'valor_remessa': '120.00',
                            'valor_conciliado': '80.00',
                            'valor_acatado': '0.00',
                            'valor_nao_conciliado': '40.00',
                            'valor_recurso_disponivel': '20.00',
                            'valor_disponivel_conciliacao': '20.00',
                            'processo_recebimento': 'PROC-987',
                            'historico': [
                                {
                                    'numero_nfse': '12345',
                                    'data_emissao': '2026-07-10T10:00:00',
                                    'valor_alocado': '80.00',
                                    'valor_glosado': '20.00',
                                    'data_previsao_recebimento': '2026-08-10',
                                    'data_recebimento': None,
                                }
                            ],
                        }
                    ],
                    'total': 250,
                    'valor_total_nao_conciliado': '123456.78',
                    'limit': 25,
                    'offset': 0,
                }
            return {'contas': []}

        api_get.side_effect = resposta

        response = self.client.get(
            '/financeiro/conciliacao-fiscal-faturamento/'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Conciliação (Faturamento X Fiscal)')
        self.assertContains(response, '987')
        self.assertContains(response, '12345')
        self.assertContains(response, 'Convênio Teste')
        self.assertContains(response, 'Financeiro')
        self.assertContains(response, '<span>TOTAL REMESSAS</span>')
        self.assertContains(response, '<span>SALDO NÃO CONCILIADO</span>')
        self.assertContains(response, '<strong>R$ 123.456,78</strong>')
        self.assertNotContains(response, '250 pendentes')
        self.assertNotContains(response, 'Página atual')
        self.assertNotContains(response, 'Regra da conciliação')
        self.assertContains(response, '<div class="pagination-control">')
        self.assertContains(response, 'class="page-select-form"')
        self.assertContains(response, '<option value="1" selected>1</option>')
        self.assertContains(response, '<span>Pagina 1 de 10</span>')
        self.assertContains(response, 'href="?page=2">Proxima</a>')
        self.assertContains(response, 'Operação Não Permitida')
        self.assertContains(response, 'novalidate')
        self.assertContains(response, 'form.checkValidity()')
        self.assertContains(
            response,
            '<button class="btn btn-primary" type="submit">'
            'Conciliar remessa</button>',
        )
        self.assertContains(response, 'panel filter-panel finance-search-bar')
        self.assertContains(response, 'panel finance-results-panel')
        self.assertContains(response, 'results-toolbar finance-results-toolbar')
        self.assertContains(response, '<small>Número remessa</small>')
        self.assertContains(response, '<small>Data competência</small>')
        self.assertContains(response, '<small>Valor da remessa</small>')
        self.assertContains(response, '<small>Valor conciliado</small>')
        self.assertContains(response, '<small>Valor não conciliado</small>')
        self.assertContains(response, '<span>GLOSAR?</span>')
        self.assertContains(response, 'Conciliações anteriores da remessa')
        self.assertContains(response, 'Valor da remessa nesta NFS-e *')
        self.assertContains(response, 'Data previsão recebimento *')
        self.assertContains(response, 'Data recebimento')
        self.assertContains(response, 'finance-money-input')
        self.assertContains(
            response,
            "updateMoney(nota, 'valor_bruto_remessa'",
        )
        self.assertContains(response, 'valorLiquidoNota(nota)')
        self.assertContains(response, 'Saldo disponível após conciliação')
        self.assertContains(
            response,
            'this.valorDisponivel - this.totalComprometido',
        )
        self.assertNotContains(
            response,
            'this.valorNaoConciliado - this.totalComprometido',
        )
        self.assertContains(response, 'this.notaResults.filter(')
        self.assertContains(response, "this.searchTerm = '';")
        self.assertContains(
            response,
            'A soma das parcelas vinculadas excede o saldo '
            'disponível da remessa.',
        )

    @patch('core.views.api_get')
    def test_paginacao_mantem_filtro_da_pesquisa(self, api_get):
        def resposta(path, params=None):
            if path.endswith('/remessas'):
                return {
                    'remessas': [],
                    'total': 250,
                    'valor_total_nao_conciliado': '123456.78',
                    'limit': 25,
                    'offset': 25,
                }
            return {'contas': []}

        api_get.side_effect = resposta

        response = self.client.get(
            '/financeiro/conciliacao-fiscal-faturamento/',
            {'q': 'Convênio A', 'page': 2},
        )

        self.assertEqual(response.status_code, 200)
        pagination = response.context['pagination']
        self.assertEqual(
            pagination['previous_url'],
            '?q=Conv%C3%AAnio+A&page=1',
        )
        self.assertEqual(
            pagination['next_url'],
            '?q=Conv%C3%AAnio+A&page=3',
        )
        self.assertEqual(
            api_get.call_args_list[0].args[1],
            {'q': 'Convênio A', 'limit': 25, 'offset': 25},
        )
        self.assertContains(
            response,
            '<input type="hidden" name="q" value="Convênio A">',
        )
        self.assertContains(response, '<option value="2" selected>2</option>')

    @patch('core.views.api_post')
    def test_envia_conciliacao_para_api(self, api_post):
        response = self.client.post(
            '/financeiro/conciliacao-fiscal-faturamento/',
            {
                'cd_remessa': '10',
                'processo_recebimento': 'PROC-1',
                'notas_json': (
                    '[{"nfse_row_hash": "hash-1", '
                    '"valor_bruto_remessa": "100.00", '
                    '"sn_glosado": true, "valor_glosado": "20.00", '
                    '"data_previsao_recebimento": "2026-08-10"}]'
                ),
            },
        )

        self.assertRedirects(
            response,
            '/financeiro/conciliacao-fiscal-faturamento/',
            fetch_redirect_response=False,
        )
        path, sent_payload = api_post.call_args.args
        self.assertTrue(path.endswith('/remessas/10/conciliar'))
        self.assertEqual(sent_payload['notas'][0]['nfse_row_hash'], 'hash-1')
        self.assertEqual(sent_payload['notas'][0]['valor_alocado'], '80.00')
        self.assertEqual(sent_payload['notas'][0]['valor_glosado'], '20.00')

    @patch('core.views.api_get')
    def test_reutiliza_cache_na_listagem_de_remessas(self, api_get):
        api_get.side_effect = lambda path, params=None: (
            {
                'remessas': [],
                'total': 0,
                'valor_total_nao_conciliado': '0.00',
                'limit': 25,
                'offset': 0,
            }
            if path.endswith('/remessas')
            else {'contas': []}
        )

        self.client.get('/financeiro/conciliacao-fiscal-faturamento/')
        self.client.get('/financeiro/conciliacao-fiscal-faturamento/')

        self.assertEqual(api_get.call_count, 2)
        paths = [call.args[0] for call in api_get.call_args_list]
        self.assertEqual(paths.count(CONCILIACAO_FATURAMENTO_PATH + '/remessas'), 1)
        self.assertEqual(paths.count('/app_glosas/financeiro/contas-bancarias'), 1)

    @patch('core.views.api_post')
    @patch('core.views.api_get')
    def test_atualiza_card_em_cache_apos_conciliar(
        self,
        api_get,
        api_post,
    ):
        api_get.side_effect = lambda path, params=None: (
            {
                'remessas': [
                    {
                        'cd_remessa': 987,
                        'valor_nao_conciliado': '100.00',
                    }
                ],
                'total': 1,
                'valor_total_nao_conciliado': '100.00',
                'limit': 25,
                'offset': 0,
            }
            if path.endswith('/remessas')
            else {'contas': []}
        )
        url = (
            '/financeiro/conciliacao-fiscal-faturamento/'
            '?q=987&page=1'
        )
        self.client.get(url)
        api_get.reset_mock()
        api_post.return_value = {
            'cd_remessa': 987,
            'valor_nao_conciliado': '0.00',
            'remessa': {
                'cd_remessa': 987,
                'valor_nao_conciliado': '0.00',
            },
        }

        response = self.client.post(
            url,
            {
                'cd_remessa': '987',
                'processo_recebimento': 'PROC-987',
                'notas_json': (
                    '[{"nfse_row_hash": "hash-1", '
                    '"valor_bruto_remessa": "100.00", '
                    '"sn_glosado": false, "valor_glosado": "0.00", '
                    '"data_previsao_recebimento": "2026-08-10"}]'
                ),
            },
        )

        self.assertRedirects(
            response,
            url,
            fetch_redirect_response=False,
        )
        refreshed = self.client.get(url)
        remessas_paths = [
            call.args[0]
            for call in api_get.call_args_list
            if call.args[0].endswith('/remessas')
        ]
        self.assertEqual(remessas_paths, [])
        self.assertEqual(refreshed.context['remessas'], [])
        self.assertEqual(refreshed.context['total_remessas'], 0)
        self.assertEqual(refreshed.context['valor_total_pendente'], '0.00')


class ConciliacoesSemRecebimentoTests(TestCase):
    def setUp(self):
        cache.clear()
        session = self.client.session
        session['api_access_token'] = 'token-seguro'
        session['api_user'] = {
            'id': 1,
            'nome': 'Financeiro',
            'email': 'financeiro@teste.com',
            'perfil': 'usuario',
        }
        session.save()

    @patch('core.views.api_get')
    def test_renderiza_conciliacoes_sem_recebimento(self, api_get):
        conciliacoes_payload = {
            'conciliacoes': [
                {
                    'cd_remessa': 987,
                    'convenio': 'Convênio Teste',
                    'cnpj_convenio': '98765432000110',
                    'processo_recebimento': 'PROC-100',
                    'data_competencia': '2026-07-01',
                    'valor_remessa': '140.00',
                    'quantidade_nfses_sem_recebimento': 2,
                    'valor_total_glosas': '20.00',
                    'valor_recebido': '20.00',
                    'valor_pendente': '100.00',
                    'situacao': 'recebimento_parcial',
                    'em_atraso': True,
                    'dias_em_atraso': 3,
                    'notas': [
                        {
                            'id': 10,
                            'numero_nfse': 'NF-100',
                            'tp_conciliacao': 'faturamento',
                            'data_previsao_recebimento': '2026-07-10',
                            'data_criacao': '2026-07-01T10:00:00',
                            'valor_nfse': '100.00',
                            'valor_vinculado_remessa': '80.00',
                            'valor_glosado': '20.00',
                            'valor_pendente': '60.00',
                            'situacao': 'recebimento_parcial',
                            'em_atraso': True,
                            'dias_em_atraso': 3,
                        },
                        {
                            'id': 11,
                            'numero_nfse': 'NF-101',
                            'tp_conciliacao': 'faturamento',
                            'data_previsao_recebimento': '2026-07-11',
                            'data_criacao': '2026-07-02T10:00:00',
                            'valor_nfse': '40.00',
                            'valor_vinculado_remessa': '40.00',
                            'valor_glosado': '0.00',
                            'valor_pendente': '40.00',
                            'situacao': 'recebimento_parcial',
                            'em_atraso': True,
                            'dias_em_atraso': 2,
                        },
                    ],
                }
            ],
            'total': 1,
            'total_remessas_sem_recebimento': 1,
            'valor_total_pendente': '100.00',
            'limit': 25,
            'offset': 0,
        }
        api_get.side_effect = lambda path, params=None: (
            conciliacoes_payload
            if path.endswith('/sem-recebimento')
            else {
                'contas': [
                    {
                        'id': 7,
                        'banco': 'Banco Teste',
                        'agencia': '1234',
                        'conta': '56789',
                    }
                ]
            }
        )

        response = self.client.get(
            '/financeiro/conciliacoes-sem-recebimento/'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Conciliações sem recebimento')
        self.assertContains(response, '<span>REMESSAS PENDENTES</span>')
        self.assertContains(response, '<span>VALOR PENDENTE</span>')
        self.assertContains(response, 'NF-100')
        self.assertContains(response, 'NF-101')
        self.assertContains(response, 'Convênio Teste')
        self.assertContains(response, 'PROC-100')
        self.assertContains(response, 'RECEBIMENTO PARCIAL')
        self.assertContains(response, 'EM ATRASO · 3 DIAS')
        self.assertContains(response, '<small>Remessa</small>')
        self.assertContains(response, '<strong>987</strong>')
        self.assertContains(response, '<small>NFS-e pendentes</small>')
        self.assertContains(response, '<strong>2</strong>')
        self.assertContains(response, 'R$ 100,00')
        self.assertContains(
            response,
            'class="finance-note-card finance-pending-card"',
            count=1,
        )
        self.assertContains(response, "'Receber'")
        self.assertContains(response, 'Data do recebimento *')
        self.assertContains(response, 'Valor recebido *')
        self.assertContains(response, 'readonly aria-readonly="true"')
        self.assertContains(
            response,
            'O valor recebido deve ser exatamente',
        )
        self.assertContains(response, 'Conta bancária *')
        self.assertContains(response, 'Conta do plano de contas')
        self.assertContains(response, 'Conta do centro de custo')
        self.assertContains(response, 'Lançamento no extrato')
        self.assertContains(response, 'Banco Teste · Ag. 1234 · C/C 56789')
        self.assertContains(response, 'recebimentoPendenteForm(')
        self.assertContains(response, 'loadLancamentos()')
        self.assertNotContains(response, 'Editar conciliação')
        self.assertNotContains(response, 'Inativar conciliação')
        self.assertNotContains(response, '>Editar</button>')
        self.assertNotContains(response, '>Excluir</button>')
        self.assertContains(
            response,
            'Esta conciliação já possui recebimento parcial.',
        )
        self.assertContains(
            response,
            'class="nav-subitem is-active" '
            'href="/financeiro/conciliacoes-sem-recebimento/"',
        )
        self.assertEqual(
            api_get.call_args_list[0].args[1],
            {'q': None, 'limit': 25, 'offset': 0},
        )

    @patch('core.views.api_get')
    def test_paginacao_mantem_filtro(self, api_get):
        conciliacoes_payload = {
            'conciliacoes': [],
            'total': 250,
            'total_remessas_sem_recebimento': 250,
            'valor_total_pendente': '5000.00',
            'limit': 25,
            'offset': 25,
        }
        api_get.side_effect = lambda path, params=None: (
            conciliacoes_payload
            if path.endswith('/sem-recebimento')
            else {'contas': []}
        )

        response = self.client.get(
            '/financeiro/conciliacoes-sem-recebimento/',
            {'q': '987', 'page': 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['pagination']['previous_url'],
            '?q=987&page=1',
        )
        self.assertEqual(
            response.context['pagination']['next_url'],
            '?q=987&page=3',
        )
        self.assertEqual(
            api_get.call_args_list[0].args[1],
            {'q': '987', 'limit': 25, 'offset': 25},
        )
        self.assertContains(
            response,
            '<input type="hidden" name="q" value="987">',
        )
        self.assertContains(response, '<option value="2" selected>2</option>')

    def test_monta_payload_de_recebimento(self):
        payload = build_recebimento_remessa_payload(
            {
                'cd_remessa': '987',
                'numero_nfse': ' NF-100 ',
                'data_recebimento': '2026-07-13',
                'valor_recebido': 'R$ 1.234,56',
                'conta_bancaria_id': '7',
                'conta_plano_contas': ' 1.1.1 ',
                'conta_centro_custo': ' CC-10 ',
                'lancamento_extrato_id': '22',
            }
        )

        self.assertEqual(payload['cd_remessa'], 987)
        self.assertEqual(payload['numero_nfse'], 'NF-100')
        self.assertEqual(payload['valor_recebido'], '1234.56')
        self.assertEqual(payload['conta_bancaria_id'], 7)
        self.assertEqual(payload['conta_plano_contas'], '1.1.1')
        self.assertEqual(payload['conta_centro_custo'], 'CC-10')
        self.assertEqual(payload['lancamento_extrato_id'], 22)

    def test_monta_payload_de_edicao(self):
        payload = build_edicao_conciliacao_payload(
            {
                'processo_recebimento': ' PROC-EDITADO ',
                'data_previsao_recebimento': '2026-08-15',
                'cd_remessa': ['987'],
                'valor_glosado_987': 'R$ 10,00',
                'valor_recebido_987': 'R$ 90,00',
            }
        )

        self.assertEqual(payload['processo_recebimento'], 'PROC-EDITADO')
        self.assertEqual(
            payload['data_previsao_recebimento'],
            '2026-08-15',
        )
        self.assertEqual(
            payload['remessas'],
            [
                {
                    'cd_remessa': 987,
                    'valor_glosado': '10.00',
                    'valor_recebido': '90.00',
                }
            ],
        )

    @patch('core.views.clear_filter_caches')
    @patch('core.views.api_put')
    def test_edita_conciliacao_pendente(
        self,
        api_put,
        clear_filter_caches,
    ):
        response = self.client.post(
            '/financeiro/conciliacoes-sem-recebimento/?q=987',
            {
                'form_action': 'editar_conciliacao',
                'conciliacao_id': '10',
                'processo_recebimento': 'PROC-NOVO',
                'data_previsao_recebimento': '2026-08-15',
                'cd_remessa': '987',
                'valor_glosado_987': 'R$ 10,00',
                'valor_recebido_987': 'R$ 90,00',
            },
        )

        self.assertRedirects(
            response,
            '/financeiro/conciliacoes-sem-recebimento/?q=987',
            fetch_redirect_response=False,
        )
        api_put.assert_called_once_with(
            CONCILIACAO_FATURAMENTO_PATH + '/conciliacoes/10',
            {
                'processo_recebimento': 'PROC-NOVO',
                'data_previsao_recebimento': '2026-08-15',
                'remessas': [
                    {
                        'cd_remessa': 987,
                        'valor_glosado': '10.00',
                        'valor_recebido': '90.00',
                    }
                ],
            },
        )
        clear_filter_caches.assert_called_once_with()

    @patch('core.views.api_get')
    def test_edicao_exibe_valores_da_remessa(self, api_get):
        api_get.side_effect = lambda path, params=None: (
            {
                'conciliacoes': [
                    {
                        'cd_remessa': 987,
                        'convenio': 'Convênio Teste',
                        'cnpj_convenio': '98765432000110',
                        'processo_recebimento': 'PROC-100',
                        'data_competencia': '2026-07-01',
                        'valor_remessa': '100.00',
                        'quantidade_nfses_sem_recebimento': 1,
                        'valor_total_glosas': '10.00',
                        'valor_recebido': '0.00',
                        'valor_pendente': '90.00',
                        'situacao': 'sem_recebimento',
                        'em_atraso': False,
                        'dias_em_atraso': 0,
                        'notas': [
                            {
                                'id': 10,
                                'numero_nfse': 'NF-100',
                                'tp_conciliacao': 'faturamento',
                                'data_previsao_recebimento': '2026-08-15',
                                'data_criacao': '2026-07-01T10:00:00',
                                'valor_nfse': '100.00',
                                'valor_vinculado_remessa': '100.00',
                                'valor_glosado': '10.00',
                                'valor_pendente': '90.00',
                                'situacao': 'sem_recebimento',
                                'em_atraso': False,
                                'dias_em_atraso': 0,
                            }
                        ],
                    }
                ],
                'total': 1,
                'total_remessas_sem_recebimento': 1,
                'valor_total_pendente': '90.00',
            }
            if path.endswith('/sem-recebimento')
            else {'contas': []}
        )

        response = self.client.get(
            '/financeiro/conciliacoes-sem-recebimento/'
        )

        self.assertContains(response, 'finance-pending-invoice-actions')
        self.assertContains(response, "'Receber'")
        self.assertContains(response, "'Editar'")
        self.assertContains(response, '>Excluir</button>')
        self.assertNotContains(response, 'Registrar recebimento')
        self.assertNotContains(response, 'Editar conciliação</button>')
        self.assertNotContains(response, 'Inativar conciliação')
        self.assertContains(response, 'Valor glosa *')
        self.assertContains(response, 'Valor recebido *', count=2)
        self.assertContains(response, 'name="valor_glosado_987"')
        self.assertContains(response, 'value="R$ 10,00"')
        self.assertContains(response, 'name="valor_recebido_987"')
        self.assertContains(response, 'value="R$ 90,00"')

    @patch('core.views.clear_filter_caches')
    @patch('core.views.api_delete')
    def test_inativa_conciliacao_pendente(
        self,
        api_delete,
        clear_filter_caches,
    ):
        response = self.client.post(
            '/financeiro/conciliacoes-sem-recebimento/?page=2',
            {
                'form_action': 'inativar_conciliacao',
                'conciliacao_id': '10',
            },
        )

        self.assertRedirects(
            response,
            '/financeiro/conciliacoes-sem-recebimento/?page=2',
            fetch_redirect_response=False,
        )
        api_delete.assert_called_once_with(
            CONCILIACAO_FATURAMENTO_PATH + '/conciliacoes/10'
        )
        clear_filter_caches.assert_called_once_with()

    @patch('core.views.api_post')
    def test_registra_recebimento_e_preserva_filtros(self, api_post):
        response = self.client.post(
            '/financeiro/conciliacoes-sem-recebimento/?q=987&page=2',
            {
                'cd_remessa': '987',
                'numero_nfse': 'NF-100',
                'data_recebimento': '2026-07-13',
                'valor_recebido': 'R$ 100,00',
                'conta_bancaria_id': '7',
                'conta_plano_contas': '1.1.1',
                'conta_centro_custo': 'CC-10',
                'lancamento_extrato_id': '22',
            },
        )

        self.assertRedirects(
            response,
            '/financeiro/conciliacoes-sem-recebimento/?q=987&page=2',
            fetch_redirect_response=False,
        )
        path, payload = api_post.call_args.args
        self.assertTrue(path.endswith('/recebimentos-remessas'))
        self.assertEqual(payload['cd_remessa'], 987)
        self.assertEqual(payload['valor_recebido'], '100.00')
        self.assertEqual(payload['conta_bancaria_id'], 7)
        self.assertEqual(payload['lancamento_extrato_id'], 22)


class ConciliacoesFinanceirasTests(TestCase):
    def setUp(self):
        cache.clear()
        session = self.client.session
        session['api_access_token'] = 'token-seguro'
        session['api_user'] = {
            'id': 1,
            'nome': 'Financeiro',
            'email': 'financeiro@teste.com',
            'perfil': 'usuario',
        }
        session.save()

    @patch('core.views.api_get')
    def test_consulta_conciliacao_recebimento_e_auditoria(self, api_get):
        api_get.side_effect = lambda path, params=None: (
            {
                'conciliacoes': [
                    {
                        'cd_remessa': 987,
                        'data_competencia': '2026-06-01',
                        'valor_remessa': '120.00',
                        'valor_alocado_nfse': '100.00',
                        'valor_glosado': '20.00',
                        'convenio': 'Convênio Teste',
                        'cnpj_convenio': '98765432000110',
                        'processo_recebimento': 'PROC-100',
                        'ativo': True,
                        'situacao_recebimento': 'recebido',
                        'notas': [
                            {
                                'id': 10,
                                'numero_nfse': 'NF-100',
                                'tipo_conciliacao': 'faturamento',
                                'valor_nfse': '100.00',
                                'valor_vinculado_remessa': '120.00',
                                'valor_alocado_nfse': '100.00',
                                'valor_glosado': '20.00',
                                'data_previsao_recebimento': '2026-07-10',
                                'data_recebimento': '2026-07-13',
                                'data_criacao': '2026-07-01T10:00:00',
                                'data_atualizacao': '2026-07-13T09:30:00',
                                'data_inativacao': None,
                                'ativo': True,
                                'situacao_recebimento': 'recebido',
                                'usuario_criacao': {
                                    'id': 1,
                                    'nome': 'Ana Financeiro',
                                    'email': 'ana@teste.com',
                                },
                                'usuario_atualizacao': {
                                    'id': 2,
                                    'nome': 'Bruno Recebimento',
                                    'email': 'bruno@teste.com',
                                },
                                'usuario_inativacao': None,
                                'recebimentos': [
                                    {
                                        'id': 5,
                                        'cd_remessa': 987,
                                        'data_recebimento': '2026-07-13',
                                        'valor_recebido': '100.00',
                                        'conta_bancaria_id': 7,
                                        'conta_plano_contas': '1.1.1',
                                        'conta_centro_custo': 'CC-10',
                                        'lancamento_extrato_id': 22,
                                        'data_registro': (
                                            '2026-07-13T09:30:00'
                                        ),
                                        'usuario': {
                                            'id': 2,
                                            'nome': 'Bruno Recebimento',
                                            'email': 'bruno@teste.com',
                                        },
                                    }
                                ],
                            }
                        ],
                        'auditoria': [
                            {
                                'id': 1,
                                'conciliacao_origem_id': 9,
                                'acao': 'criacao',
                                'usuario': {
                                    'id': 1,
                                    'nome': 'Ana Financeiro',
                                    'email': 'ana@teste.com',
                                },
                                'data_operacao': '2026-07-01T10:00:00',
                            },
                            {
                                'id': 2,
                                'conciliacao_origem_id': 10,
                                'acao': 'edicao',
                                'usuario': {
                                    'id': 2,
                                    'nome': 'Bruno Recebimento',
                                    'email': 'bruno@teste.com',
                                },
                                'dados_anteriores': {
                                    'processo_recebimento': 'PROC-ANTIGO',
                                    'data_previsao_recebimento': '2026-07-09',
                                    'ativo': True,
                                    'remessas': [
                                        {
                                            'cd_remessa': 987,
                                            'valor_alocado_nfse': '90.00',
                                            'valor_glosado': '30.00',
                                        }
                                    ],
                                },
                                'dados_novos': {
                                    'processo_recebimento': 'PROC-100',
                                    'data_previsao_recebimento': '2026-07-10',
                                    'ativo': True,
                                    'remessas': [
                                        {
                                            'cd_remessa': 987,
                                            'valor_alocado_nfse': '100.00',
                                            'valor_glosado': '20.00',
                                        }
                                    ],
                                },
                                'data_operacao': '2026-07-10T08:30:00',
                            },
                            {
                                'id': 3,
                                'conciliacao_origem_id': 10,
                                'acao': 'recebimento',
                                'usuario': {
                                    'id': 2,
                                    'nome': 'Bruno Recebimento',
                                    'email': 'bruno@teste.com',
                                },
                                'data_operacao': '2026-07-13T09:30:00',
                            },
                            {
                                'id': 4,
                                'conciliacao_origem_id': 9,
                                'acao': 'inativacao',
                                'usuario': {
                                    'id': 1,
                                    'nome': 'Ana Financeiro',
                                    'email': 'ana@teste.com',
                                },
                                'data_operacao': '2026-07-14T11:00:00',
                            },
                        ],
                    }
                ],
                'total': 1,
                'total_ativas': 1,
                'total_inativas': 0,
                'total_recebidas': 1,
                'total_sem_recebimento': 0,
                'limit': 25,
                'offset': 0,
            }
            if path.endswith('/conciliacoes')
            else {
                'contas': [
                    {
                        'id': 7,
                        'banco': 'Banco Teste',
                        'agencia': '1234',
                        'conta': '56789',
                        'digito': '0',
                    }
                ]
            }
        )

        response = self.client.get(
            '/financeiro/conciliacoes/',
            {
                'q': '987',
                'situacao': 'recebido',
                'incluir_inativas': '1',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Consultar conciliações')
        self.assertContains(response, '<span class="nav-label">Auditória</span>')
        self.assertContains(response, 'Remessa 987')
        self.assertContains(response, 'Notas fiscais vinculadas')
        self.assertContains(response, 'NF-100')
        self.assertContains(response, 'PROC-100')
        self.assertContains(response, 'Ana Financeiro')
        self.assertContains(response, 'Bruno Recebimento')
        self.assertContains(response, 'Banco Teste · Ag. 1234 · C/C 56789-0')
        self.assertContains(response, 'Conciliação criada')
        self.assertContains(response, 'Conciliação editada')
        self.assertContains(response, 'Recebimento registrado')
        self.assertContains(response, 'Conciliação inativada')
        self.assertContains(response, 'finance-history-event is-created')
        self.assertContains(response, 'finance-history-event is-updated')
        self.assertContains(response, 'finance-history-event is-received')
        self.assertContains(response, 'finance-history-event is-deleted')
        self.assertContains(response, '>INCLUSÃO</small>')
        self.assertContains(response, '>MODIFICAÇÃO</small>')
        self.assertContains(response, '>RECEBIMENTO</small>')
        self.assertContains(response, '>EXCLUSÃO</small>')
        self.assertContains(response, 'VÍNCULO ANTERIOR')
        self.assertContains(response, 'Valor recebido · remessa 987')
        self.assertContains(response, 'R$ 90,00')
        self.assertContains(response, 'R$ 100,00')
        self.assertContains(
            response,
            'class="nav-subitem is-active" '
            'href="/financeiro/conciliacoes/"',
        )
        self.assertEqual(
            api_get.call_args_list[0].kwargs['params'],
            {
                'q': '987',
                'situacao': 'recebido',
                'incluir_inativas': 'true',
                'limit': 25,
                'offset': 0,
            },
        )
        self.client.get(
            '/financeiro/conciliacoes/',
            {
                'q': '987',
                'situacao': 'recebido',
                'incluir_inativas': '1',
            },
        )
        chamadas_historico = [
            chamada
            for chamada in api_get.call_args_list
            if chamada.args[0].endswith('/conciliacoes')
        ]
        self.assertEqual(len(chamadas_historico), 2)
