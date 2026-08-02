from pathlib import Path

from django.contrib.staticfiles import finders
from django.template.loader import get_template
from django.test import SimpleTestCase


class AcompanhamentoParticularResponsivoTests(SimpleTestCase):
    def test_calendario_e_fila_limitam_conteudo_aos_containers(self):
        css = Path(finders.find('css/app.css')).read_text()

        self.assertIn(
            '.particular-dashboard-page--daily '
            '.particular-calendar-day {\n'
            '  min-width: 0;\n'
            '  container-type: inline-size;\n'
            '  overflow: hidden;',
            css,
        )
        self.assertIn(
            'width: calc(100% - 0.7rem);\n'
            '  max-width: 100%;\n'
            '  min-width: 0;',
            css,
        )
        self.assertIn(
            'font-size: clamp(0.48rem, 11cqi, 0.58rem);\n'
            '  text-align: center;\n'
            '  text-overflow: clip;\n'
            '  white-space: nowrap;',
            css,
        )
        self.assertIn(
            'max-width: calc(100% - 0.8rem);',
            css,
        )
        self.assertIn(
            '.particular-dashboard-page--daily '
            '.particular-calendar-grid {\n'
            '  overflow-x: hidden;',
            css,
        )
        self.assertIn(
            '1rem minmax(4rem, 0.55fr) minmax(8rem, 2.15fr)\n'
            '    minmax(0, 0.46fr) minmax(4.25rem, 0.64fr)\n'
            '    minmax(0, 0.54fr) minmax(4.25rem, 0.62fr)\n'
            '    8.25rem;',
            css,
        )
        self.assertIn(
            '.workflow-request-status\n'
            '  ) {\n'
            '  overflow: hidden;',
            css,
        )

    def test_calendario_exibe_todas_as_semanas_sem_rolagem_ou_corte(self):
        css = Path(finders.find('css/app.css')).read_text()

        self.assertIn(
            '.particular-dashboard-page--daily {\n'
            '  height: 100%;\n'
            '  grid-template-rows: auto auto minmax(0, 1fr);\n'
            '  overflow: hidden;\n'
            '  scrollbar-gutter: auto;',
            css,
        )
        self.assertIn(
            '--particular-calendar-workspace-height: 41.5rem;',
            css,
        )
        self.assertIn(
            '.particular-daily-workspace--28-days {\n'
            '  --particular-calendar-workspace-height: 29.5rem;',
            css,
        )
        self.assertIn(
            '.particular-daily-workspace--35-days {\n'
            '  --particular-calendar-workspace-height: 35.5rem;',
            css,
        )
        self.assertIn(
            '.particular-daily-workspace--42-days {\n'
            '  --particular-calendar-workspace-height: 41.5rem;',
            css,
        )
        self.assertIn(
            '.particular-dashboard-page--daily '
            '.particular-calendar-grid {\n'
            '  grid-auto-rows: minmax(0, 1fr);\n'
            '  overflow-y: hidden;\n'
            '  scrollbar-gutter: auto;',
            css,
        )
        self.assertIn(
            '.particular-dashboard-page--daily '
            '.particular-calendar-day {\n'
            '  min-height: 0;',
            css,
        )

        template = Path(
            get_template('acompanhamento_particular.html').origin.name
        ).read_text()
        self.assertIn(
            'particular-daily-workspace--{{ dias_grade|length }}-days',
            template,
        )

    def test_fila_usa_tipografia_compacta_sem_quebrar_rotulos(self):
        css = Path(finders.find('css/app.css')).read_text()
        template = Path(
            get_template('_workflow_solicitacao_cards.html').origin.name
        ).read_text()

        self.assertIn(
            '.particular-queue-panel .panel-title {\n'
            '  font-size: 0.8rem;',
            css,
        )
        self.assertIn(
            '.particular-queue-panel .results-subtitle {\n'
            '  font-size: 0.58rem;',
            css,
        )
        self.assertIn(
            '.particular-queue-panel .page-select-form .form-select {\n'
            '  width: 3.75rem;\n'
            '  min-height: 2rem;\n'
            '  font-size: 0.62rem;',
            css,
        )
        self.assertIn(
            '.particular-dashboard-page--daily '
            '.workflow-request-header small {\n'
            '  overflow: hidden;\n'
            '  font-size: 0.44rem;\n'
            '  letter-spacing: 0.025em;\n'
            '  line-height: 1.15;\n'
            '  overflow-wrap: normal;\n'
            '  text-overflow: ellipsis;\n'
            '  white-space: nowrap;\n'
            '  word-break: normal;',
            css,
        )
        self.assertIn(
            '.workflow-request-header > .workflow-request-field {\n'
            '  min-height: 1.38rem;\n'
            '  grid-template-rows: 0.54rem 0.68rem;\n'
            '  align-content: center;',
            css,
        )
        self.assertIn(
            '.particular-dashboard-page--daily '
            '.workflow-request-status {\n'
            '  grid-area: status;\n'
            '  align-self: center;\n'
            '  width: 100%;\n'
            '  max-width: 100%;\n'
            '  justify-content: center;\n'
            '  justify-self: stretch;',
            css,
        )
        self.assertIn(
            '.particular-dashboard-page--daily '
            '.workflow-request-header strong {\n'
            '  overflow: hidden;\n'
            '  font-size: 0.56rem;\n'
            '  line-height: 1.2;\n'
            '  overflow-wrap: normal;\n'
            '  text-overflow: ellipsis;\n'
            '  white-space: nowrap;',
            css,
        )
        self.assertIn(
            '{% if workflow_mode == "acompanhamento" or '
            'workflow_mode == "validacao" or workflow_mode == "emissao" %}'
            'Tipo{% else %}Tipo atendimento{% endif %}',
            template,
        )

    def test_dia_separa_rotulo_de_atendimentos_das_bolinhas(self):
        css = Path(finders.find('css/app.css')).read_text()

        self.assertIn(
            '.particular-calendar-day-count {\n'
            '  top: 40%;\n'
            '  gap: 0.06rem;',
            css,
        )
        self.assertIn(
            '.particular-calendar-day-total {\n'
            '  font-size: clamp(0.98rem, 24cqi, 1.28rem);',
            css,
        )
        self.assertIn(
            '.particular-calendar-day-count > span {\n'
            '  font-size: clamp(0.48rem, 10cqi, 0.54rem);\n'
            '  line-height: 1;',
            css,
        )
        self.assertIn(
            '.particular-patient-bubbles {\n'
            '  bottom: 0.22rem;\n'
            '  min-height: 1.08rem;',
            css,
        )
        self.assertIn(
            '.particular-patient-bubble {\n'
            '  width: 1.08rem;\n'
            '  height: 1.08rem;\n'
            '  margin-left: -0.34rem;',
            css,
        )
        self.assertIn(
            '.particular-patient-bubble:first-child {\n'
            '  margin-left: 0;',
            css,
        )

    def test_velocimetro_exibe_legenda_abaixo_da_agulha(self):
        css = Path(finders.find('css/app.css')).read_text()
        template = Path(
            get_template('acompanhamento_particular.html').origin.name
        ).read_text()

        self.assertIn(
            '.particular-billing-gauge-readout {\n'
            '  position: static;\n'
            '  display: flex;',
            css,
        )
        self.assertIn(
            'margin-top: 0.18rem;\n'
            '  padding-top: 0.28rem;\n'
            '  border-top: 1px solid #d7e5ea;',
            css,
        )
        self.assertNotIn(
            '.particular-billing-gauge > div {\n'
            '  position: absolute;',
            css,
        )
        self.assertIn(
            '<span>NFS-e emitidas</span>',
            template,
        )
        self.assertNotIn('<span>emitido</span>', template)

    def test_resumo_posiciona_validados_abaixo_de_sem_solicitacao(self):
        css = Path(finders.find('css/app.css')).read_text()

        self.assertIn(
            '.particular-month-overview {\n'
            '  display: grid;\n'
            '  grid-template-columns: '
            'minmax(0, 1.45fr) minmax(23rem, 0.85fr);',
            css,
        )
        self.assertIn(
            '.particular-month-overview .particular-monitor-summary {\n'
            '  grid-template-columns: repeat(2, minmax(0, 1fr));',
            css,
        )
        self.assertIn(
            '.particular-month-overview\n'
            '  .particular-summary-card--validada {\n'
            '  grid-row: 2;\n'
            '  grid-column: 2;',
            css,
        )

    def test_primeira_rolagem_oculta_resumo_e_depois_segue_livre(self):
        template = Path(
            get_template('acompanhamento_particular.html').origin.name
        ).read_text()

        self.assertIn(
            "const hideMonthlyOverview = () => {",
            template,
        )
        self.assertIn(
            "page.addEventListener('wheel', (event) => {",
            template,
        )
        self.assertIn(
            "event.preventDefault();\n    hideMonthlyOverview();",
            template,
        )
        self.assertIn(
            "if (event.deltaY <= 0 || overviewHidden "
            "|| page.scrollTop > 2) return;",
            template,
        )
        self.assertIn(
            "if (page.scrollTop <= 2) {\n"
            "      overviewHidden = false;",
            template,
        )

    def test_janela_baixa_preserva_altura_dos_dias(self):
        css = Path(finders.find('css/app.css')).read_text()

        self.assertIn(
            '@media (max-height: 900px) and (min-width: 1101px) {\n'
            '  .particular-dashboard-page--daily {\n'
            '    grid-template-rows: auto auto auto;\n'
            '    overflow-y: auto;\n'
            '    scrollbar-gutter: stable;',
            css,
        )
        self.assertIn(
            '  .particular-daily-workspace {\n'
            '    height: var(--particular-calendar-workspace-height);\n'
            '    min-height: var(--particular-calendar-workspace-height);',
            css,
        )

    def test_painel_de_emissao_permanece_visivel_durante_rolagem(self):
        css = Path(finders.find('css/app.css')).read_text()

        self.assertIn(
            '.particular-dashboard-page--daily '
            '> .particular-dashboard-toolbar {\n'
            '  position: sticky;\n'
            '  top: 0;\n'
            '  z-index: 30;\n'
            '  background: var(--panel);',
            css,
        )
