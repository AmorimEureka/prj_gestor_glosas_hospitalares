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
            '1.1rem minmax(5.1rem, 0.8fr) minmax(0, 1.7fr)\n'
            '    minmax(0, 0.95fr) minmax(0, 0.85fr)\n'
            '    minmax(0, 0.8fr) minmax(6rem, auto);',
            css,
        )
        self.assertIn(
            '.workflow-request-status\n'
            '  ) {\n'
            '  overflow: hidden;',
            css,
        )

    def test_calendario_exibe_todas_as_semanas_sem_rolagem_interna(self):
        css = Path(finders.find('css/app.css')).read_text()

        self.assertIn(
            '.particular-dashboard-page--daily {\n'
            '  height: 100%;\n'
            '  grid-template-rows: auto auto auto;\n'
            '  overflow-y: auto;',
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
            '  overflow-y: hidden;\n'
            '  scrollbar-gutter: auto;',
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
            '  font-size: 0.48rem;\n'
            '  letter-spacing: 0.025em;\n'
            '  line-height: 1.15;\n'
            '  overflow-wrap: normal;\n'
            '  word-break: normal;',
            css,
        )
        self.assertIn(
            '.particular-dashboard-page--daily '
            '.workflow-request-header strong {\n'
            '  font-size: 0.61rem;\n'
            '  line-height: 1.25;\n'
            '  overflow-wrap: break-word;',
            css,
        )
