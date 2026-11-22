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
