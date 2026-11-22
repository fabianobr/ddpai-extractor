import shutil
import subprocess
import unittest
from pathlib import Path


class TestVideoTimeline(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js necessário para validar o JavaScript')
    def test_mapping_handles_gaps_unsorted_and_missing_coverage(self):
        script = r'''
const assert = require('assert');
const {pointAtVideoTime, timeForPoint} = require('./web/video-sync.js');
const group = {video_sync: {rear: [0, null, 10, 9.5, 30], front: [0, null, null, 8, 25]}};
assert.equal(pointAtVideoTime(group, 'rear', 9.7), 3);
assert.equal(pointAtVideoTime(group, 'rear', 20), null);
assert.equal(timeForPoint(group, 'front', 2), null);
assert.equal(timeForPoint(group, 'rear', 2), 10);
assert.equal(pointAtVideoTime(group, 'front', 25), 4);
'''
        result = subprocess.run(['node', '-e', script], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js necessário para validar o JavaScript')
    def test_linked_cameras_use_individual_mapped_times_and_pause_without_coverage(self):
        script = r'''
const assert = require('assert');
const {linkVideos} = require('./web/video-sync.js');
class Video {
 constructor() { this.currentTime=0; this.paused=true; this.dataset={lazySrc:'video.mp4'}; this.attrs={}; this.events={}; }
 addEventListener(name, fn) { (this.events[name] ||= []).push(fn); }
 emit(name) { (this.events[name] || []).forEach(fn => fn({target:this})); }
 hasAttribute(name) { return !!this.attrs[name]; }
 set src(value) { this.attrs.src=value; }
 play() { this.paused=false; this.emit('play'); return Promise.resolve(); }
 pause() { this.paused=true; this.emit('pause'); }
}
const rear=new Video(), front=new Video();
const group={video_sync:{rear:[0,10,20],front:[5,15,null]}};
const state={mode:'linked', activeVideo:null};
linkVideos(rear, front, state, () => group);
rear.currentTime=10; rear.play();
assert.equal(front.currentTime,15); assert.equal(front.paused,false);
rear.currentTime=20; rear.emit('timeupdate');
assert.equal(front.paused,true);
'''
        result = subprocess.run(['node', '-e', script], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
