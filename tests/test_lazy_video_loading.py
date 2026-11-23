import re
import unittest
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / 'web' / 'index.html').read_text(encoding='utf-8')


def function_body(name):  # mesma regra de tests/test_frontend_accessibility.py
    m = re.search(r'function %s\(' % re.escape(name), HTML)
    if not m:
        raise AssertionError(f'function {name}( não encontrada')
    nxt = re.search(r'\n\s*(?:async\s+)?function [A-Za-z_$][\w$]*\(', HTML[m.end():])
    return HTML[m.start():m.end() + nxt.start() if nxt else len(HTML)]


class TestLazyVideoLoading(unittest.TestCase):  # Tarefa 5
    def test_clearing_uses_remove_attribute_and_load(self):
        self.assertIn("removeAttribute('src')", HTML)
        self.assertIn('.load()', HTML)
        self.assertIn("removeAttribute('src')", function_body('loadTripVideos'))
        self.assertIn('dataset.lazySrc', function_body('loadTripVideos'))

    def test_never_assigns_empty_src(self):
        offenders = [l for l in HTML.splitlines() if re.search(r"\.src\s*=\s*''", l) and not l.strip().startswith('//')]
        self.assertEqual(offenders, [])

    def test_loads_on_demand_with_indicator(self):
        body = function_body('ensureVideoLoaded')
        self.assertIn("hasAttribute('src')", body)
        self.assertIn('dataset.lazySrc', body)
        self.assertIn('.hidden = false', body)
        listener = function_body('attachLazyLoadListener')
        self.assertIn("addEventListener('play'", listener)
        self.assertIn('ensureVideoLoaded(', listener)
        self.assertIn("attachLazyLoadListener(cameraVideo('front'))", HTML)
        self.assertIn("attachLazyLoadListener(cameraVideo('rear'))", HTML)

    def test_indicator_hidden_when_playing(self):
        self.assertIn('.hidden = true', function_body('hideLoading'))
        self.assertIn("addEventListener('playing', () => hideLoading(", HTML)

    def test_sync_bound_once_without_cloning(self):
        self.assertNotIn('cloneNode', HTML)
        self.assertEqual(HTML.count('linkVideos('), 1)


if __name__ == '__main__':
    unittest.main()
