import re
import unittest
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / 'web' / 'index.html').read_text(encoding='utf-8')


def function_body(name):
    m = re.search(r'function %s\(' % re.escape(name), HTML)
    if not m:
        raise AssertionError(f'function {name}( não encontrada')
    nxt = re.search(r'\n\s*(?:async\s+)?function [A-Za-z_$][\w$]*\(', HTML[m.end():])
    return HTML[m.start():m.end() + nxt.start() if nxt else len(HTML)]


class TestDocument(unittest.TestCase):  # Tarefa 5
    def test_language_and_focus(self):
        self.assertIn('<html lang="pt-BR">', HTML)
        self.assertRegex(HTML, r':focus-visible\s*\{[^}]*outline')

    def test_no_blocking_dialogs(self):
        self.assertNotRegex(HTML, r'\b(alert|confirm|prompt)\(')

    def test_dependencies(self):
        self.assertIn('leaflet/1.9.4', HTML)
        self.assertNotIn('chart.min.js', HTML)
        self.assertIn('<script src="trip-model.js"></script>', HTML)
        self.assertIn('<script src="video-sync.js"></script>', HTML)
        self.assertIn('Familjen+Grotesk', HTML)
        self.assertIn('Atkinson+Hyperlegible', HTML)

    def test_both_themes_and_phone_layout(self):
        self.assertIn('@media (prefers-color-scheme: dark)', HTML)
        self.assertIn(':root[data-theme="dark"]', HTML)
        self.assertIn('@media (max-width: 700px)', HTML)

    def test_no_debug_or_english_by_default(self):
        for text in ('id="videoStatus"', 'video-path', 'Loading database', 'No trips found', 'Video ended at'):
            self.assertNotIn(text, HTML)


class TestShell(unittest.TestCase):  # Tarefa 5
    def test_trip_picker_is_keyboard_operable_and_linkable(self):
        self.assertRegex(HTML, r'id="trip-picker"[^>]*aria-expanded=')
        body = function_body('renderTripPicker')
        self.assertIn("createElement('button')", body)
        self.assertIn('aria-current', body)
        self.assertIn('viagem-', function_body('initialTripIndex'))

    def test_empty_state(self):
        self.assertIn('Nenhuma viagem importada ainda', HTML)
        self.assertIn('python3 -m src.processing.trip_import', HTML)

    def test_videos_are_named_and_use_custom_controls(self):
        for side in ('front', 'rear'):
            self.assertRegex(HTML, rf'<video id="video-{side}"[^>]*aria-label=')
            self.assertNotRegex(HTML, rf'<video id="video-{side}"[^>]*\bcontrols\b')

    def test_missing_or_unplayable_video_messages(self):
        self.assertIn('Sem vídeo desta câmera', HTML)
        self.assertIn('Viagem sem vídeo', HTML)
        self.assertIn('Este navegador não conseguiu reproduzir o vídeo.', HTML)
        self.assertIn("addEventListener('error'", HTML)

    def test_camera_layout_and_sync_toggles_expose_state(self):
        for el in ('layout-side', 'camera-swap', 'sync-lock'):
            self.assertIn(f'id="{el}"', HTML)
        self.assertIn("setAttribute('aria-pressed'", function_body('updateLayoutButtons'))
        body = function_body('updateSyncLock')
        self.assertIn("setAttribute('aria-pressed'", body)
        self.assertIn('localStorage', body)

    def test_map_uses_themed_tiles_and_controls(self):
        # CARTO passou a exigir chave de API: tiles do OSM, com o visual de cada tema feito por filtro CSS.
        self.assertNotIn('basemaps.cartocdn.com', HTML)
        self.assertIn('tile.openstreetmap.org', HTML)
        self.assertGreaterEqual(HTML.count('--tile-filter:'), 3)  # :root + os dois blocos escuros
        self.assertRegex(HTML, r'\.leaflet-tile-pane\s*\{[^}]*filter:\s*var\(--tile-filter\)')
        for el in ('map-follow', 'map-fit', 'map-expand'):
            self.assertIn(f'id="{el}"', HTML)

    def test_chapters_are_buttons(self):
        self.assertIn('id="chapters"', HTML)
        self.assertIn("createElement('button')", function_body('renderChapters'))


class TestStoryBar(unittest.TestCase):  # Tarefa 6
    def test_transport_controls(self):
        self.assertRegex(HTML, r'id="play"[^>]*aria-label=')
        self.assertRegex(HTML, r'id="back10"[^>]*aria-label="Voltar 10 segundos"')
        self.assertRegex(HTML, r'id="fwd10"[^>]*aria-label="Avançar 10 segundos"')
        for rate in ('1', '2', '4'):
            self.assertIn(f'data-rate="{rate}"', HTML)
        self.assertIn('id="clock"', HTML)
        self.assertIn('id="elapsed"', HTML)

    def test_timeline_is_a_slider_with_real_time(self):
        self.assertRegex(HTML, r'id="timeline"[^>]*role="slider"')
        self.assertIn("setAttribute('aria-valuetext'", function_body('updatePlayhead'))

    def test_tracks_are_named_and_downsampled(self):
        self.assertRegex(HTML, r'(?i)role="img"[^>]*aria-label="[^"]*velocidade')
        self.assertRegex(HTML, r'(?i)role="img"[^>]*aria-label="[^"]*altitude')
        self.assertIn('TripModel.downsample(', HTML)

    def test_video_drives_position_through_sync_mapping(self):
        self.assertIn('pointAtVideoTime(', function_body('onVideoTimeUpdate'))

    def test_shortcuts_respect_focus(self):
        body = function_body('handleShortcut')
        self.assertIn('defaultPrevented', body)
        for token in ('isContentEditable', "'INPUT'", "'BUTTON'", 'preventDefault',
                      "' '", "'k'", "'j'", "'l'", "'i'", "'o'", "'m'", "'c'",
                      "'ArrowLeft'", "'ArrowRight'", "'Escape'"):
            self.assertIn(token, body)


class TestReviewFixes(unittest.TestCase):  # correções da revisão das Tarefas 5-7
    def test_play_overlay_on_stage(self):
        self.assertRegex(HTML, r'id="stage-play"[^>]*aria-label="Reproduzir"')

    def test_trip_switch_does_not_wake_the_other_camera(self):
        self.assertIn('beginVideoSwitch(', function_body('loadTripVideos'))
        self.assertIn('videoSwitch', function_body('onVideoTimeUpdate'))


class TestSelectionAndQuality(unittest.TestCase):  # Tarefa 7
    def test_export(self):
        self.assertIn('geometria', HTML)
        self.assertRegex(HTML, r'id="route-message"[^>]*role="status"')
        body = function_body('exportRoute')
        self.assertIn('route-message', body)
        self.assertIn('TripModel.buildGpx(', body)
        self.assertIn('TripModel.buildKml(', body)
        self.assertIn('Marque dois pontos diferentes (início e fim) para definir o trecho.', HTML)
        for el in ('route-chip', 'route-gpx', 'route-kml', 'route-clear'):
            self.assertIn(f'id="{el}"', HTML)

    def test_selection_handles_are_sliders(self):
        self.assertRegex(HTML, r'id="sel-start"[^>]*role="slider"')
        self.assertRegex(HTML, r'id="sel-end"[^>]*role="slider"')

    def test_coordinate_copy(self):
        self.assertIn('id="copy-map-coordinate"', HTML)
        self.assertIn('TripModel.decimalToDms(', HTML)

    def test_quality_pill_in_plain_language(self):
        self.assertIn('id="quality-pill"', HTML)
        for text in ('Vídeo e GPS alinhados', 'Sincronização parcial', 'Sincronização aproximada',
                     'Sincronização incerta', 'Sem sincronização fina'):
            self.assertIn(text, HTML)
        self.assertIn('syncConfidenceWarning(', function_body('qualityFor'))

    def test_technical_details_hidden_in_menu(self):
        self.assertIn('Detalhes técnicos', HTML)
        self.assertRegex(HTML, r'id="more-button"[^>]*aria-expanded=')
        self.assertIn('id="tech-details"', HTML)
        self.assertIn('video_notes', function_body('renderTechDetails'))


if __name__ == '__main__':
    unittest.main()
