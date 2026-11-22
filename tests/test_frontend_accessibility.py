import re
import unittest
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / 'web' / 'index.html').read_text(encoding='utf-8')


def function_body(name):
    start = HTML.index(f'function {name}(')
    nxt = HTML.find('\n        function ', start + 1)
    return HTML[start:nxt if nxt != -1 else len(HTML)]


class TestFrontendAccessibility(unittest.TestCase):
    def test_document_language_is_portuguese(self):
        self.assertIn('<html lang="pt-BR">', HTML)

    def test_export_does_not_use_blocking_alert(self):
        self.assertNotIn('alert(', HTML)
        self.assertIn('id="route-message"', HTML)
        self.assertRegex(HTML, r'id="route-message"[^>]*role="status"')
        self.assertIn('route-message', function_body('exportRoute'))

    def test_export_text_does_not_promise_navigable_route(self):
        self.assertIn('geometria', HTML)

    def test_trip_items_are_keyboard_operable(self):
        body = function_body('renderTripList')
        self.assertIn("setAttribute('role', 'button')", body)
        self.assertIn("tabIndex = 0", body)
        self.assertIn("'keydown'", body)
        self.assertIn('aria-current', body)

    def test_visible_focus_style_exists(self):
        self.assertRegex(HTML, r':focus-visible\s*\{[^}]*outline')

    def test_sync_mode_buttons_expose_pressed_state(self):
        self.assertIn("setAttribute('aria-pressed'", function_body('updateSyncModeButtonStyles'))

    def test_overlay_play_buttons_hidden_from_assistive_tech(self):
        for side in ('rear', 'front'):
            self.assertRegex(HTML, rf'id="{side}-play-btn"[^>]*aria-hidden="true"')

    def test_videos_and_charts_have_accessible_names(self):
        for side in ('rear', 'front'):
            self.assertRegex(HTML, rf'<video id="video-{side}"[^>]*aria-label=')
        for chart in ('speed', 'altitude'):
            self.assertRegex(HTML, rf'<canvas id="chart-{chart}"[^>]*role="img"[^>]*aria-label=')

    def test_user_visible_status_messages_are_portuguese(self):
        for text in ('Loading database', 'No trips found', 'Video ended at', '<b>▶ Video:'):
            self.assertNotIn(text, HTML)

    def test_cameras_stay_side_by_side_on_tablet_width(self):
        # O conceito "câmeras lado a lado" só empilha em telas realmente estreitas.
        m = re.search(r'@media \(max-width: 1024px\) \{(.*?)\n        \}', HTML, re.S)
        assert m is not None, 'bloco @media (max-width: 1024px) não encontrado'
        self.assertNotIn('videos-grid', m.group(1))
        self.assertRegex(HTML, r'@media \(max-width: (6\d\d|7[0-4]\d)px\)[^{]*\{[^@]*\.videos-grid')


if __name__ == '__main__':
    unittest.main()
