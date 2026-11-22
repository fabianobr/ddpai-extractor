const assert = require('assert');
const M = require('../web/trip-model.js');
const TZ = 'America/Sao_Paulo';

const cases = {
    time() {
        const t0 = Date.UTC(2026, 10, 21, 12, 3, 22);
        assert.strictEqual(M.parseUtc('2026-11-21T12:03:22'), t0);
        assert.strictEqual(M.parseUtc('2026-11-21T12:03:22Z'), t0);
        assert.strictEqual(M.parseUtc('2026-11-21T09:03:22-03:00'), t0);
        assert.strictEqual(M.parseUtc(null), null);
        assert.strictEqual(M.parseUtc('xx'), null);

        const trip = {start_timestamp: '2026-11-21T12:03:22', duration_min: 1,
            points: [[0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 1], [0, 0, 0, 0, 0, 2], [0, 0, 0, 0, 0, 10], [0, 0, 0, 0, 0, 11]]};
        const legacy = {start_timestamp: '2026-11-21T12:03:22', duration_min: 1, points: [[0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [0, 0, 0, 0, 0]]};
        assert.strictEqual(M.elapsedAt(trip, 3), 10);
        assert.strictEqual(M.elapsedAt(legacy, 1), 30);
        assert.strictEqual(M.wallClockAt(trip, 3), t0 + 10000);
        assert.strictEqual(M.wallClockAt(legacy, 1), t0 + 30000);
        assert.strictEqual(M.wallClockAt({points: trip.points}, 1), null);

        assert.strictEqual(M.formatClock(t0, TZ), '09:03:22');
        assert.strictEqual(M.formatClock(null, TZ), '--:--:--');

        assert.strictEqual(M.formatDuration(10320), '2 h 52 min');
        assert.strictEqual(M.formatDuration(360), '6 min');
        assert.strictEqual(M.formatDuration(3600), '1 h');
        assert.strictEqual(M.formatDuration(45), '45 s');

        const at = (ts) => ({start_timestamp: ts, points: []});
        assert.strictEqual(M.tripTitle(trip, TZ), 'Sábado de manhã');
        assert.strictEqual(M.tripTitle(at('2026-11-21T17:30:00'), TZ), 'Sábado à tarde');
        assert.strictEqual(M.tripTitle(at('2026-11-21T23:18:00'), TZ), 'Sábado à noite');
        assert.strictEqual(M.tripTitle(at('2026-11-21T02:30:00'), TZ), 'Sexta-feira à noite');
        assert.strictEqual(M.tripTitle(at('2026-11-21T06:00:00'), TZ), 'Sábado de madrugada');
        assert.strictEqual(M.tripTitle({label: '21/11 09:03 → 21/11 11:54', points: []}, TZ), '21/11 09:03 → 21/11 11:54');

        assert.strictEqual(M.indexAtElapsed(trip, 5), 2);
        assert.strictEqual(M.indexAtElapsed(trip, 10), 3);
        assert.strictEqual(M.indexAtElapsed(trip, -3), 0);
        assert.strictEqual(M.indexAtElapsed(trip, 100), 4);
        assert.strictEqual(M.indexAtElapsed(legacy, 30), 1);
    },
    geometry() {
        const km = M.cumulativeKm([[0, 0], [0, 1], [0, 1]]);
        assert.strictEqual(km.length, 3);
        assert.strictEqual(km[0], 0);
        assert.ok(Math.abs(km[1] - 111.195) < 0.01);
        assert.strictEqual(km[2], km[1]);

        assert.deepStrictEqual(M.downsample([1, 5, 2, 8, 3, 3], 3, 'max'), [5, 8, 3]);
        assert.deepStrictEqual(M.downsample([1, 5, 2, 8, 3, 3], 3, 'mean'), [3, 5, 3]);
        assert.deepStrictEqual(M.downsample([1, 2], 5, 'max'), [1, 2]);

        const d = M.routeThumbPath([[0, 0], [0, 0.5], [0.2, 1]], 100, 50, 10);
        assert.ok(d.startsWith('M'));
        const nums = d.match(/-?\d+(\.\d+)?/g).map(Number);
        for (let i = 0; i < nums.length; i += 2) {
            assert.ok(nums[i] >= 0 && nums[i] <= 100);
            assert.ok(nums[i + 1] >= 0 && nums[i + 1] <= 50);
        }
        assert.ok(nums[nums.length - 2] > nums[0]);   // termina a leste (à direita)
        assert.ok(nums[nums.length - 1] < nums[1]);   // e ao norte (acima)
        assert.ok((d.match(/L/g) || []).length <= 9);
        assert.ok(!/NaN|Infinity/.test(M.routeThumbPath([[0, 0], [0, 1]], 100, 50, 10)));  // linha reta leste-oeste
        assert.ok(!/NaN|Infinity/.test(M.routeThumbPath([[1, 1]], 100, 50, 10)));          // ponto único
        assert.ok((M.routeThumbPath(Array.from({length: 1000}, (_, i) => [i * 0.001, i * 0.001]), 100, 50, 60).match(/[ML]/g) || []).length <= 60);

        assert.strictEqual(M.decimalToDms(-27.565393, 'lat'), `27° 33' 55.41" S`);
        assert.strictEqual(M.decimalToDms(-48.51551, 'lon'), `48° 30' 55.84" W`);

        const pts = [[-27.5, -48.5, 0, 0, 0, 0], [-27.6, -48.6, 0, 0, 0, 1]];
        assert.strictEqual(M.buildGpx(pts), '<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="DDpai" xmlns="http://www.topografix.com/GPX/1/1"><trk><name>Trecho DDpai</name><trkseg><trkpt lat="-27.5" lon="-48.5"></trkpt><trkpt lat="-27.6" lon="-48.6"></trkpt></trkseg></trk></gpx>');
        assert.strictEqual(M.buildKml(pts), '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>Trecho DDpai</name><LineString><coordinates>-48.5,-27.5 -48.6,-27.6</coordinates></LineString></Placemark></Document></kml>');
    },
    chapters() {
        const n = 300;
        const alt = (i) => i <= 100 ? 100 : i < 150 ? 100 + (i - 100) * 7 : i <= 250 ? 450 : i < 270 ? 450 - (i - 250) * 15 : 150;
        const points = Array.from({length: n}, (_, i) => [0, i * 0.001, i === 200 ? 90.4 : 50, alt(i), 0, i]);
        const rear = points.map((_, i) => (i >= 220 && i <= 259) ? null : i);
        const trip = {start_timestamp: '2026-11-21T12:00:00', duration_min: 299 / 60, points,
            idle_segments: [{start_index: 60, end_index: 80, duration_s: 360, distance_km: 0}],
            video_front: 'f.mp4', video_rear: 'r.mp4',
            video_sync: {front: points.map((_, i) => i), rear, status: 'partial', confidence: 'high'}};

        assert.deepStrictEqual(M.cameraGaps(trip, 'rear'), [{startIndex: 220, endIndex: 259}]);
        assert.deepStrictEqual(M.cameraGaps(trip, 'front'), []);
        assert.deepStrictEqual(M.cameraGaps(trip, 'rear', 60), []);
        assert.deepStrictEqual(M.cameraGaps({...trip, video_rear: null}, 'rear'), []);
        assert.deepStrictEqual(M.cameraGaps({...trip, video_sync: undefined}, 'rear'), []);

        const ch = M.deriveChapters(trip);
        assert.deepStrictEqual(ch.map((c) => [c.type, c.index, c.endIndex === undefined ? null : c.endIndex, c.title]), [
            ['start', 0, null, 'Partida'],
            ['stop', 60, 80, 'Parada de 6 min'],
            ['climb', 90, 150, 'Subida de 350 m'],
            ['max', 200, null, 'Velocidade máxima 90 km/h'],
            ['descent', 210, 270, 'Descida de 300 m'],
            ['gap', 220, 259, 'Sem vídeo traseiro'],
            ['end', 299, null, 'Chegada'],
        ]);
        assert.strictEqual(ch[2].detail, 'De 100 m a 450 m');

        const legacy = {points: [[0, 0, 10, 5, 0], [0, 0.001, 20, 5, 0], [0, 0.002, 15, 5, 0]], duration_min: 1};
        assert.deepStrictEqual(M.deriveChapters(legacy).map((c) => c.type), ['start', 'max', 'end']);
    },
};

const group = process.argv[2];
if (!cases[group]) { console.error(`grupo desconhecido: ${group}`); process.exit(2); }
cases[group]();
