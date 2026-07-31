from pathlib import Path

from django.contrib.staticfiles import finders
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
            '1.1rem minmax(0, 0.72fr) minmax(0, 1.7fr)\n'
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
