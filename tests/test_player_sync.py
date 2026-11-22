import subprocess
import shutil
import unittest
from pathlib import Path


class TestLinkedVideoPlayback(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js necessário para validar o JavaScript')
    def test_play_seek_and_pause_follow_the_active_camera(self):
        script = r'''
const assert = require('assert');
const {linkVideos} = require('./web/video-sync.js');
class Video {
  constructor() { this.currentTime = 0; this.paused = true; this.dataset = {lazySrc:'video.mp4'}; this.attrs = {}; this.events = {}; }
  addEventListener(name, fn) { (this.events[name] ||= []).push(fn); }
  emit(name) { for (const fn of this.events[name] || []) fn({target:this}); }
  hasAttribute(name) { return !!this.attrs[name]; }
  set src(value) { this.attrs.src = value; }
  play() { this.paused = false; this.emit('play'); return Promise.resolve(); }
  pause() { this.paused = true; this.emit('pause'); }
}
const front = new Video(), rear = new Video();
const state = {mode: 'linked', activeVideo: null};
linkVideos(rear, front, state);
rear.currentTime = 25;
rear.play();
assert.equal(front.currentTime, 25);
assert.equal(front.paused, false);
rear.currentTime = 50; rear.emit('seeking');
assert.equal(front.currentTime, 50);
rear.pause();
assert.equal(front.paused, true);
state.mode = 'independent'; rear.play(); assert.equal(front.paused, true);
'''
        result = subprocess.run(['node', '-e', script], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


NODE_VIDEO = r'''
const assert = require('assert');
const {linkVideos} = require('./web/video-sync.js');
class Video {
  constructor() { this.currentTime = 0; this.paused = true; this.ended = false; this.duration = NaN; this.dataset = {lazySrc:'video.mp4'}; this.attrs = {}; this.events = {}; this.seekWrites = 0; }
  addEventListener(name, fn) { (this.events[name] ||= []).push(fn); }
  emit(name) { for (const fn of this.events[name] || []) fn({target:this}); }
  hasAttribute(name) { return !!this.attrs[name]; }
  set src(value) { this.attrs.src = value; }
  play() { this.paused = false; this.emit('play'); return Promise.resolve(); }
  pause() { this.paused = true; this.emit('pause'); }
}
// Pontos GPS espaçados 1 s; as câmeras têm deslocamento fixo e diferente (rear = t, front = t + 0.4).
const group = {video_sync: {rear: Array.from({length: 40}, (_, i) => i), front: Array.from({length: 40}, (_, i) => i + 0.4)}};
'''


class TestLinkedPlaybackEdgeCases(unittest.TestCase):
    def run_node(self, body):
        script = NODE_VIDEO + body
        result = subprocess.run(['node', '-e', script], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js necessário para validar o JavaScript')
    def test_natural_end_of_one_camera_does_not_pause_the_other(self):
        self.run_node(r'''
const rear = new Video(), front = new Video(), state = {mode: 'linked', activeVideo: null};
linkVideos(rear, front, state, () => group);
rear.currentTime = 10; rear.play();
assert.equal(front.paused, false);
// fim natural da traseira: o navegador dispara 'pause' com ended=true
rear.paused = true; rear.ended = true; rear.emit('pause'); rear.emit('ended');
assert.equal(front.paused, false, 'a outra câmera deve continuar até o próprio fim');
// ended por currentTime >= duration - epsilon, mesmo sem a flag
const rear2 = new Video(), front2 = new Video(), state2 = {mode: 'linked', activeVideo: null};
linkVideos(rear2, front2, state2, () => group);
rear2.currentTime = 10; rear2.play();
rear2.duration = 30; rear2.currentTime = 29.99; rear2.paused = true; rear2.emit('pause');
assert.equal(front2.paused, false);
''')

    @unittest.skipUnless(shutil.which('node'), 'Node.js necessário para validar o JavaScript')
    def test_user_pause_still_pauses_the_other_camera(self):
        self.run_node(r'''
const rear = new Video(), front = new Video(), state = {mode: 'linked', activeVideo: null};
linkVideos(rear, front, state, () => group);
rear.currentTime = 10; rear.play();
rear.duration = 30; rear.pause();
assert.equal(front.paused, true);
''')

    @unittest.skipUnless(shutil.which('node'), 'Node.js necessário para validar o JavaScript')
    def test_programmatic_seek_does_not_bounce_back_to_the_dragged_camera(self):
        self.run_node(r'''
const rear = new Video(), front = new Video(), state = {mode: 'linked', activeVideo: null};
// pontos GPS esparsos: 12.4 s da traseira cai no ponto 12 s (front 12.4) -> o retorno daria 12, divergindo 0,4 s
const sparse = {video_sync: {rear: [0, 4, 8, 12, 16], front: [0.4, 4.4, 8.4, 12.4, 16.4]}};
linkVideos(rear, front, state, () => sparse);
rear.currentTime = 12.4; rear.emit('seeking');          // usuário arrasta a traseira
assert.equal(front.currentTime, 12.4);                    // mapeado pelo ponto GPS mais próximo
front.emit('seeking');                                    // evento resultante do seek programático
assert.equal(rear.currentTime, 12.4, 'a câmera arrastada não pode ser re-buscada');
front.emit('seeked');
// seek do usuário na dianteira depois disso sincroniza a traseira normalmente
front.currentTime = 16.4; front.emit('seeking');
assert.equal(rear.currentTime, 16);
''')

    @unittest.skipUnless(shutil.which('node'), 'Node.js necessário para validar o JavaScript')
    def test_programmatic_mark_is_cleared_by_seeking_even_without_seeked(self):
        self.run_node(r'''
const rear = new Video(), front = new Video(), state = {mode: 'linked', activeVideo: null};
const sparse = {video_sync: {rear: [0, 4, 8, 12, 16], front: [0.4, 4.4, 8.4, 12.4, 16.4]}};
linkVideos(rear, front, state, () => sparse);
rear.currentTime = 12.4; rear.emit('seeking');
front.emit('seeking');                                    // consome a marca (sem 'seeked')
front.currentTime = 4.4; front.emit('seeking');           // seek do usuário
assert.equal(rear.currentTime, 4);
''')

    @unittest.skipUnless(shutil.which('node'), 'Node.js necessário para validar o JavaScript')
    def test_equal_time_does_not_leave_a_stale_mark(self):
        self.run_node(r'''
const rear = new Video(), front = new Video(), state = {mode: 'linked', activeVideo: null};
linkVideos(rear, front, state, () => group);
front.currentTime = 10.4;                                 // já está no tempo-alvo: nenhum seek ocorre
rear.currentTime = 10; rear.emit('seeking');
// nenhum evento 'seeking' em front; o primeiro seek real do usuário deve sincronizar
front.currentTime = 20.4; front.emit('seeking');
assert.equal(rear.currentTime, 20);
''')

    @unittest.skipUnless(shutil.which('node'), 'Node.js necessário para validar o JavaScript')
    def test_timeupdate_drift_correction_does_not_bounce_back(self):
        self.run_node(r'''
const rear = new Video(), front = new Video(), state = {mode: 'linked', activeVideo: null};
const sparse = {video_sync: {rear: [0, 4, 8, 12, 16], front: [0.4, 4.4, 8.4, 12.4, 16.4]}};
linkVideos(rear, front, state, () => sparse);
rear.currentTime = 1; rear.play();
rear.currentTime = 12.4; rear.emit('timeupdate');        // deriva > 0,75 s: corrige a dianteira
assert.equal(front.currentTime, 12.4);
front.emit('seeking');
assert.equal(rear.currentTime, 12.4);
''')
