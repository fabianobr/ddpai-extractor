/* Núcleo compartilhado dos 3 protótipos de redesign.
 * Só lógica (sem estilo): relógio de reprodução simulado, geometria da rota, quadros das câmeras,
 * marcos derivados, cenário de mapa gerado, atalhos de teclado e pequenos utilitários de UI.
 * Depende de window.MOCK_TRIPS (mock-data.js). Cada opção desenha a própria interface por cima disto. */
(function () {
    'use strict';
    const P = window.Proto = {};
    const RAW = window.MOCK_TRIPS || [];

    /* A reprodução do protótipo é acelerada para que o marcador ande de forma visível.
     * Na página real, 1× é tempo real e o relógio vem do <video>. */
    P.DEMO = 60;
    P.reduced = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);

    /* ---------- formatação pt-BR ---------- */
    const pad = (n) => String(n).padStart(2, '0');
    P.num = (v, d = 0) => Number(v).toLocaleString('pt-BR', {minimumFractionDigits: d, maximumFractionDigits: d});
    P.hms = (sec) => {
        sec = Math.max(0, Math.round(sec));
        const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
        return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
    };
    P.dur = (min) => {
        min = Math.round(min);
        const h = Math.floor(min / 60), m = min % 60;
        return h ? (m ? `${h} h ${m} min` : `${h} h`) : `${m} min`;
    };
    P.clockOf = (secOfDay, withSec = true) => {
        secOfDay = ((Math.round(secOfDay) % 86400) + 86400) % 86400;
        const h = Math.floor(secOfDay / 3600), m = Math.floor(secOfDay % 3600 / 60), s = secOfDay % 60;
        return withSec ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(h)}:${pad(m)}`;
    };
    P.clock = (t, f, withSec = true) => P.clockOf(t.start + f * t.elapsed_s, withSec);
    const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
    P.cap = cap;

    /* ---------- preparação das viagens ---------- */
    function hash(str) { let h = 2166136261; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
    function rng(seed) { let a = seed >>> 0; return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
    P.rng = rng;

    function bboxOf(pts) {
        let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
        for (const [x, y] of pts) { if (x < x0) x0 = x; if (y < y0) y0 = y; if (x > x1) x1 = x; if (y > y1) y1 = y; }
        return {x0, y0, x1, y1, w: x1 - x0, h: y1 - y0, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2};
    }
    P.bboxOf = bboxOf;

    const FRAMES = {
        /* pares do mesmo instante; ordem escolhida para que ~35% da viagem 1 mostre o par 1 */
        day: [
            {front: 'frames/day-front-3.jpg', rear: 'frames/day-rear-2.jpg'},
            {front: 'frames/day-front-2.jpg', rear: 'frames/day-rear-2.jpg'},
            {front: 'frames/day-front-1.jpg', rear: 'frames/day-rear-1.jpg'},
        ],
        night: [{front: 'frames/night-front-1.jpg', rear: 'frames/night-rear-1.jpg'}],
    };

    P.trips = RAW.map(function (t, i) {
        const m = /(\d{2}):(\d{2})/.exec(t.label || '');
        const start = m ? (+m[1]) * 3600 + (+m[2]) * 60 : 0;
        const r = t.route, cum = [0];
        for (let k = 1; k < r.length; k++) cum.push(cum[k - 1] + Math.hypot(r[k][0] - r[k - 1][0], r[k][1] - r[k - 1][1]));
        const len = cum[cum.length - 1] || 1;
        const gaps = {front: ((t.camera_gaps || {}).front || []).slice(), rear: ((t.camera_gaps || {}).rear || []).slice()};
        /* Lacuna ilustrativa (não existe nos dados reais): mostra o estado "sem vídeo" de uma câmera. */
        if (i === 0 && !gaps.rear.length) gaps.rear.push({from: 0.64, to: 0.668, example: true});
        const hour = start / 3600;
        const date = new Date(t.date + 'T12:00:00');
        return Object.assign({}, t, {
            index: i, start, end: start + t.elapsed_s, cum, len, kmPerUnit: t.distance_km / len,
            gaps, bbox: bboxOf(r), night: hour >= 18 || hour < 6,
            period: hour < 12 ? 'manhã' : hour < 18 ? 'tarde' : 'noite',
            weekday: date.toLocaleDateString('pt-BR', {weekday: 'long'}),
            dayLong: date.toLocaleDateString('pt-BR', {weekday: 'long', day: 'numeric', month: 'long'}),
            dayShort: date.toLocaleDateString('pt-BR', {day: '2-digit', month: '2-digit'}),
            gpsPoints: i === 0 ? 8752 : Math.round(t.elapsed_s * 0.85),
            frames: (hour >= 18 || hour < 6) ? FRAMES.night : FRAMES.day,
            files: {front: `merged_videos/${t.id}_front.mp4`, rear: `merged_videos/${t.id}_rear.mp4`},
        });
    });
    P.trips.forEach((t) => { t.marks = deriveMarks(t); t.title = cap(t.weekday) + {'manhã': ' de manhã', 'tarde': ' à tarde', 'noite': ' à noite'}[t.period]; });

    /* ---------- amostragem ---------- */
    P.val = function (series, f) {
        const n = series.length - 1, x = Math.min(Math.max(f, 0), 1) * n, i = Math.floor(x), k = x - i;
        return i >= n ? series[n] : series[i] * (1 - k) + series[i + 1] * k;
    };
    P.pos = function (t, f) {
        const r = t.route, n = r.length - 1, x = Math.min(Math.max(f, 0), 1) * n, i = Math.min(Math.floor(x), n - 1), k = x - i;
        const a = r[i], b = r[i + 1];
        let j = i, hd = 0;
        /* rumo: procura o próximo trecho com deslocamento real (paradas têm pontos repetidos) */
        for (let s = i; s < n; s++) { const dx = r[s + 1][0] - r[s][0], dy = r[s + 1][1] - r[s][1]; if (Math.hypot(dx, dy) > 0.6) { j = s; hd = Math.atan2(dy, dx) * 180 / Math.PI; break; } }
        return {x: a[0] + (b[0] - a[0]) * k, y: a[1] + (b[1] - a[1]) * k, heading: hd, idx: j};
    };
    P.kmAt = (t, f) => {
        const r = t.cum, n = r.length - 1, x = Math.min(Math.max(f, 0), 1) * n, i = Math.min(Math.floor(x), n - 1);
        return (r[i] + (r[i + 1] - r[i]) * (x - i)) * t.kmPerUnit;
    };
    P.nearest = function (t, x, y) {
        let best = 0, d = Infinity;
        t.route.forEach((p, i) => { const q = (p[0] - x) ** 2 + (p[1] - y) ** 2; if (q < d) { d = q; best = i; } });
        return {f: best / (t.route.length - 1), dist: Math.sqrt(d)};
    };
    P.frameAt = function (t, f) {
        const seg = Math.floor(Math.min(f, 0.9999) * 40);
        return t.frames[seg % t.frames.length];
    };
    P.inGap = (t, cam, f) => (t.gaps[cam] || []).find((g) => f >= g.from && f <= g.to) || null;

    /* ---------- marcos (capítulos) derivados ---------- */
    function deriveMarks(t) {
        const out = [{type: 'start', f: 0, label: 'Partida'}];
        const alt = t.altitude, W = 60;
        let bestUp = {g: 0}, bestDown = {g: 0};
        for (let i = 0; i + W < alt.length; i++) {
            const g = alt[i + W] - alt[i];
            if (g > bestUp.g) bestUp = {g, i};
            if (-g > bestDown.g) bestDown = {g: -g, i};
        }
        function refine(b, up) {
            let i0 = b.i, i1 = b.i + W;
            for (let k = b.i; k <= b.i + W; k++) { if (up ? alt[k] < alt[i0] : alt[k] > alt[i0]) i0 = k; }
            i1 = i0; for (let k = i0; k <= b.i + W; k++) { if (up ? alt[k] > alt[i1] : alt[k] < alt[i1]) i1 = k; }
            return {f: i0 / (alt.length - 1), to: i1 / (alt.length - 1), m: Math.abs(alt[i1] - alt[i0])};
        }
        if (bestUp.g > 250) { const r = refine(bestUp, true); out.push({type: 'climb', f: r.f, to: r.to, meters: r.m, label: `Subida de ${P.num(Math.round(r.m / 10) * 10)} m`}); }
        if (bestDown.g > 250) { const r = refine(bestDown, false); out.push({type: 'descent', f: r.f, to: r.to, meters: r.m, label: `Descida de ${P.num(Math.round(r.m / 10) * 10)} m`}); }
        (t.stops || []).forEach((s) => out.push({type: 'stop', f: s.from, to: s.to, minutes: s.min, label: `Parada de ${P.num(Math.round(s.min))} min`}));
        out.push({type: 'max', f: t.max_speed_at, label: `Velocidade máxima ${P.num(Math.round(t.max_speed))} km/h`, short: `${P.num(Math.round(t.max_speed))} km/h`});
        ['front', 'rear'].forEach((cam) => (t.gaps[cam] || []).forEach((g) => out.push({type: 'gap', cam, f: g.from, to: g.to, example: !!g.example,
            label: `Sem vídeo ${cam === 'front' ? 'dianteiro' : 'traseiro'}${g.example ? ' (exemplo)' : ''}`})));
        out.push({type: 'end', f: 1, label: 'Chegada'});
        return out.sort((a, b) => a.f - b.f);
    }

    /* ---------- coordenada ilustrativa (as rotas do mock não têm lat/lon reais) ---------- */
    function dmsPart(v, pos, neg) {
        const s = v < 0 ? neg : pos; v = Math.abs(v);
        const d = Math.floor(v), mf = (v - d) * 60, m = Math.floor(mf), sec = (mf - m) * 60;
        return `${d}°${pad(m)}′${sec.toFixed(1).replace('.', ',').padStart(4, '0')}″ ${s}`;
    }
    P.coord = function (t, f) {
        const p = P.pos(t, f);
        const lat = -(27.38 + p.y * 0.00046 + t.index * 0.0007), lon = -(48.52 + (1000 - p.x) * 0.00088);
        return {lat, lon, text: `${dmsPart(lat, 'N', 'S')}  ${dmsPart(lon, 'L', 'O')}`};
    };

    /* ---------- caminhos SVG ---------- */
    const r1 = (v) => Math.round(v * 10) / 10;
    P.line = (pts) => pts.length ? 'M' + pts.map((p) => r1(p[0]) + ' ' + r1(p[1])).join('L') : '';
    P.routeSlice = function (t, a, b) {
        const n = t.route.length - 1, i0 = Math.max(0, Math.floor(a * n)), i1 = Math.min(n, Math.ceil(b * n));
        const pts = t.route.slice(i0, i1 + 1).map((p) => p.slice());
        const pa = P.pos(t, a), pb = P.pos(t, b);
        if (pts.length) { pts[0] = [pa.x, pa.y]; pts[pts.length - 1] = [pb.x, pb.y]; }
        return pts;
    };
    /* Série (0..n) → path em caixa w×h. Retorna linha e área. */
    P.seriesPath = function (series, w, h, lo, hi, padTop = 0) {
        const n = series.length - 1, span = (hi - lo) || 1;
        const pts = series.map((v, i) => [i / n * w, padTop + (h - padTop) * (1 - (v - lo) / span)]);
        const line = P.line(pts);
        return {line, area: line + `L${w} ${h}L0 ${h}Z`};
    };
    function blob(cx, cy, r, rnd, n = 9, squash = 1) {
        const pts = [];
        for (let i = 0; i < n; i++) { const a = i / n * Math.PI * 2, rr = r * (0.72 + rnd() * 0.5); pts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr * squash]); }
        let d = '';
        for (let i = 0; i < n; i++) {
            const p = pts[i], q = pts[(i + 1) % n], mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2;
            d += (i ? '' : `M${r1((pts[n - 1][0] + p[0]) / 2)} ${r1((pts[n - 1][1] + p[1]) / 2)}`) + `Q${r1(p[0])} ${r1(p[1])} ${r1(mx)} ${r1(my)}`;
        }
        return d + 'Z';
    }

    /* ---------- cenário de mapa gerado (ruas, água, parques, relevo) ----------
     * Não é geografia real: só sugere um mapa ao redor da rota. Determinístico por viagem. */
    P.scenery = function (t) {
        const rnd = rng(hash(t.id + 'map')), bb = t.bbox, R = t.route;
        const far = (x, y, min) => R.every((p, i) => i % 3 || (p[0] - x) ** 2 + (p[1] - y) ** 2 > min * min);
        const S = {water: [], waterLines: [], land: [], parks: [], minor: [], major: [], towns: [], contours: [], bridges: []};
        const loop = Math.hypot(R[0][0] - R[R.length - 1][0], R[0][1] - R[R.length - 1][1]) < 30;
        const W = {x0: bb.x0 - 900, y0: bb.y0 - 900, x1: bb.x1 + 900, y1: bb.y1 + 900};
        if (!loop) {
            /* litoral a leste da rota (ponta costeira das viagens 1 e 3) + uma ilha */
            const base = bb.x1 + 42, pts = [];
            for (let y = W.y0; y <= W.y1; y += 12) pts.push([base + 11 * Math.sin(y / 37) + 6 * Math.sin(y / 11 + 1.3) + (y > bb.cy + 60 ? (y - bb.cy - 60) * 0.25 : 0), y]);
            S.water.push(P.line(pts) + `L${W.x1} ${W.y1}L${W.x1} ${W.y0}Z`);
            S.land.push(blob(bb.x1 + 140, bb.cy - 10, 70, rnd, 11, 2.1));
            S.bridges.push(P.line([[bb.x1 + 8, bb.cy - 8], [bb.x1 + 82, bb.cy - 14]]));
        } else {
            for (let k = 0; k < 40 && S.water.length < 2; k++) {
                const x = bb.x0 + rnd() * bb.w, y = bb.y0 + rnd() * bb.h;
                if (far(x, y, 75)) S.water.push(blob(x, y, 30 + rnd() * 18, rnd, 10, 0.7));
            }
        }
        /* rio: atravessa a área inteira */
        { const pts = []; let x = bb.x0 + bb.w * (0.25 + rnd() * 0.5), y = W.y0, a = Math.PI / 2;
          while (y < W.y1) { a += (rnd() - 0.5) * 0.5; a = Math.min(Math.max(a, 0.9), 2.2); x += Math.cos(a) * 14; y += Math.sin(a) * 14; pts.push([x, y]); }
          S.waterLines.push(P.line(pts)); }
        for (let k = 0; k < 60 && S.parks.length < 7; k++) {
            const x = bb.x0 - 120 + rnd() * (bb.w + 240), y = bb.y0 - 140 + rnd() * (bb.h + 280);
            if (far(x, y, 30)) S.parks.push(blob(x, y, 18 + rnd() * 30, rnd, 9, 0.6 + rnd() * 0.6));
        }
        /* rodovias que cruzam a área */
        for (let k = 0; k < 2; k++) {
            const pts = []; let x = k ? W.x0 : bb.x0 + bb.w * rnd(), y = k ? bb.y0 + bb.h * rnd() : W.y0, a = k ? 0.1 : Math.PI / 2;
            for (let s = 0; s < 260; s++) { a += (rnd() - 0.5) * 0.18; x += Math.cos(a) * 12; y += Math.sin(a) * 12; pts.push([x, y]); if (x > W.x1 || y > W.y1) break; }
            S.major.push(P.line(pts));
        }
        /* estradas vicinais saindo da rota */
        for (let k = 0; k < 46; k++) {
            const i = Math.floor(rnd() * (R.length - 2)) + 1, p = R[i], q = R[i + 1];
            let a = Math.atan2(q[1] - p[1], q[0] - p[0]) + (rnd() < 0.5 ? 1 : -1) * (Math.PI / 2 + (rnd() - 0.5) * 0.9);
            const pts = [p.slice()]; let x = p[0], y = p[1];
            const steps = 3 + Math.floor(rnd() * 6);
            for (let s = 0; s < steps; s++) { a += (rnd() - 0.5) * 0.8; const L = 10 + rnd() * 18; x += Math.cos(a) * L; y += Math.sin(a) * L; pts.push([x, y]); }
            S.minor.push(P.line(pts));
        }
        /* bairros: grade de ruas recortada num círculo, onde a velocidade é baixa (cidade) */
        const towns = [0, R.length - 1];
        for (let k = 0; k < 2; k++) {
            let bestI = 0, best = Infinity;
            for (let s = 0; s < 30; s++) { const i = Math.floor(rnd() * R.length), v = P.val(t.speed, i / (R.length - 1)); if (v < best && towns.every((j) => Math.abs(j - i) > 50)) { best = v; bestI = i; } }
            towns.push(bestI);
        }
        towns.forEach((i, n) => {
            const c = R[i], Rr = n < 2 ? 42 : 28, step = 13, ang = rnd() * Math.PI;
            const ux = Math.cos(ang), uy = Math.sin(ang), vx = -uy, vy = ux;
            let d = '';
            for (let dir = 0; dir < 2; dir++) {
                const ax = dir ? vx : ux, ay = dir ? vy : uy, bx = dir ? ux : vx, by = dir ? uy : vy;
                for (let o = -Rr; o <= Rr; o += step) {
                    const half = Math.sqrt(Math.max(0, Rr * Rr - o * o));
                    const mx = c[0] + ax * o, my = c[1] + ay * o;
                    d += `M${r1(mx - bx * half)} ${r1(my - by * half)}L${r1(mx + bx * half)} ${r1(my + by * half)}`;
                }
            }
            S.towns.push({d, x: c[0], y: c[1], r: Rr});
        });
        /* relevo: curvas de nível em volta de picos próximos ao trecho mais alto */
        const hiIdx = t.altitude.indexOf(Math.max(...t.altitude)), hiF = hiIdx / (t.altitude.length - 1);
        if (Math.max(...t.altitude) > 500) {
            for (let k = 0; k < 3; k++) {
                const p = P.pos(t, Math.min(1, Math.max(0, hiF + (rnd() - 0.5) * 0.3)));
                const cx = p.x + (rnd() - 0.5) * 160, cy = p.y + (rnd() < 0.5 ? -1 : 1) * (50 + rnd() * 60);
                const seed = rnd() * 1000;
                for (let ring = 1; ring <= 6; ring++) {
                    const rr = ring * 17, pts = [];
                    for (let a = 0; a <= 64; a++) { const th = a / 64 * Math.PI * 2; const w = 1 + 0.22 * Math.sin(th * 3 + seed) + 0.12 * Math.sin(th * 5 + seed * 2); pts.push([cx + Math.cos(th) * rr * w * 1.4, cy + Math.sin(th) * rr * w]); }
                    S.contours.push(P.line(pts) + 'Z');
                }
            }
        }
        return S;
    };

    /* ---------- player simulado (um único relógio para tudo) ---------- */
    P.player = function (opts) {
        const s = {trip: P.trips[0], f: 0.35, playing: false, rate: 1, linked: true, sel: {a: 0.30, b: 0.42}, cams: 'both'};
        Object.assign(s, opts || {});
        const subs = [];
        let raf = 0, last = 0;
        const emit = (why) => subs.forEach((fn) => fn(s, why || 'tick'));
        function tick(ts) {
            if (!s.playing) return;
            const dt = Math.min(0.1, (ts - last) / 1000); last = ts;
            s.f += dt * s.rate * P.DEMO / s.trip.elapsed_s;
            if (s.f >= 1) { s.f = 1; s.playing = false; emit('state'); return; }
            emit('tick');
            raf = requestAnimationFrame(tick);
        }
        const api = {
            s, on(fn) { subs.push(fn); fn(s, 'init'); return api; },
            emit,
            play() { if (s.playing) return; if (s.f >= 1) s.f = 0; s.playing = true; last = performance.now(); raf = requestAnimationFrame(tick); emit('state'); },
            pause() { if (!s.playing) return; s.playing = false; cancelAnimationFrame(raf); emit('state'); },
            toggle() { s.playing ? api.pause() : api.play(); },
            seek(f) { s.f = Math.min(1, Math.max(0, f)); emit('seek'); },
            nudge(sec) { api.seek(s.f + sec / s.trip.elapsed_s); },
            setRate(r) { s.rate = r; emit('state'); },
            setLinked(v) { s.linked = v; emit('state'); },
            setSel(sel) { s.sel = sel ? {a: Math.min(sel.a, sel.b), b: Math.max(sel.a, sel.b)} : null; emit('sel'); },
            markIn() { const b = s.sel ? s.sel.b : Math.min(1, s.f + 0.05); api.setSel({a: s.f, b: Math.max(b, s.f + 0.002)}); },
            markOut() { const a = s.sel ? s.sel.a : Math.max(0, s.f - 0.05); api.setSel({a: Math.min(a, s.f - 0.002), b: s.f}); },
            setTrip(i, f = 0) { api.pause(); s.trip = P.trips[i]; s.f = f; s.sel = null; emit('trip'); },
        };
        return api;
    };

    /* ---------- atalhos de teclado ---------- */
    P.keys = function (player, extra) {
        document.addEventListener('keydown', function (e) {
            if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
            const el = e.target, tag = (el.tagName || '').toLowerCase(), role = el.getAttribute && el.getAttribute('role');
            if (tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable) return;
            if (role && /^(menu|menuitem|option|listbox|tab)$/.test(role) && /Arrow/.test(e.key)) return;
            const activatable = tag === 'button' || tag === 'a' || tag === 'summary' || role === 'button' || role === 'menuitem' || role === 'option';
            const k = e.key;
            if ((k === ' ' || k === 'k' || k === 'K') && !(k === ' ' && activatable)) { e.preventDefault(); player.toggle(); }
            else if (k === 'ArrowLeft' || k === 'j' || k === 'J') { e.preventDefault(); player.nudge(e.shiftKey ? -60 : -10); }
            else if (k === 'ArrowRight' || k === 'l' || k === 'L') { e.preventDefault(); player.nudge(e.shiftKey ? 60 : 10); }
            else if (k === 'i' || k === 'I') { player.markIn(); }
            else if (k === 'o' || k === 'O') { player.markOut(); }
            else if (extra) extra(e);
        });
    };

    /* ---------- interações de faixa (linha do tempo / gráfico) ---------- */
    P.fracFrom = (el, clientX) => { const r = el.getBoundingClientRect(); return Math.min(1, Math.max(0, (clientX - r.left) / (r.width || 1))); };
    /* Clique ou arraste na faixa = pular/escrubar. */
    P.scrub = function (el, player, ignoreSel) {
        el.addEventListener('pointerdown', function (e) {
            if (e.button !== 0 || (ignoreSel && e.target.closest(ignoreSel))) return;
            el.setPointerCapture(e.pointerId);
            player.seek(P.fracFrom(el, e.clientX));
            const move = (ev) => player.seek(P.fracFrom(el, ev.clientX));
            const up = () => { el.removeEventListener('pointermove', move); el.removeEventListener('pointerup', up); el.removeEventListener('pointercancel', up); };
            el.addEventListener('pointermove', move); el.addEventListener('pointerup', up); el.addEventListener('pointercancel', up);
        });
    };
    /* Alças da seleção. which: 'a' | 'b' | 'body' */
    P.dragSel = function (handle, track, player, which) {
        handle.addEventListener('pointerdown', function (e) {
            e.stopPropagation(); e.preventDefault();
            handle.setPointerCapture(e.pointerId);
            const f0 = P.fracFrom(track, e.clientX), s0 = Object.assign({}, player.s.sel);
            const move = (ev) => {
                const f = P.fracFrom(track, ev.clientX), sel = player.s.sel; if (!sel) return;
                if (which === 'a') player.setSel({a: Math.min(f, sel.b - 0.003), b: sel.b});
                else if (which === 'b') player.setSel({a: sel.a, b: Math.max(f, sel.a + 0.003)});
                else { const d = Math.min(Math.max(f - f0, -s0.a), 1 - s0.b); player.setSel({a: s0.a + d, b: s0.b + d}); }
            };
            const up = () => { handle.removeEventListener('pointermove', move); handle.removeEventListener('pointerup', up); };
            handle.addEventListener('pointermove', move); handle.addEventListener('pointerup', up);
        });
        handle.addEventListener('keydown', function (e) {
            const sel = player.s.sel; if (!sel || which === 'body') return;
            const step = (e.shiftKey ? 60 : 10) / player.s.trip.elapsed_s;
            if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                e.preventDefault(); e.stopPropagation();
                const d = e.key === 'ArrowLeft' ? -step : step;
                if (which === 'a') player.setSel({a: Math.min(Math.max(0, sel.a + d), sel.b - 0.003), b: sel.b});
                else player.setSel({a: sel.a, b: Math.max(Math.min(1, sel.b + d), sel.a + 0.003)});
            }
        });
    };
    /* Leitura ao passar o mouse: cb(f) ou cb(null). */
    P.hover = function (el, cb) {
        el.addEventListener('pointermove', (e) => cb(P.fracFrom(el, e.clientX), e));
        el.addEventListener('pointerleave', () => cb(null));
    };

    /* ---------- mapa: viewBox controlado (zoom, seguir, clique → ponto) ---------- */
    P.mapView = function (svg, trip, insetFn) {
        let vb = {x: 0, y: 0, w: 1000, h: 1000}, tr = trip, following = false;
        const size = () => { const r = svg.getBoundingClientRect(); return {w: r.width || 1, h: r.height || 1}; };
        const apply = () => { svg.setAttribute('viewBox', `${r1(vb.x)} ${r1(vb.y)} ${r1(vb.w)} ${r1(vb.h)}`); api.onchange && api.onchange(); };
        const api = {
            get vb() { return vb; }, get following() { return following; },
            setTrip(t) { tr = t; api.fit(); },
            fit() {
                const s = size(), ins = insetFn ? insetFn(s) : {l: 24, r: 24, t: 24, b: 24}, bb = tr.bbox;
                const fw = Math.max(60, s.w - ins.l - ins.r), fh = Math.max(60, s.h - ins.t - ins.b);
                const bw = Math.max(bb.w, 40), bh = Math.max(bb.h, 40), k = Math.min(fw / bw, fh / bh);
                vb = {w: s.w / k, h: s.h / k, x: bb.cx - (ins.l + fw / 2) / k, y: bb.cy - (ins.t + fh / 2) / k};
                apply();
            },
            zoom(f, cx, cy) {
                if (cx === undefined) { cx = vb.x + vb.w / 2; cy = vb.y + vb.h / 2; }
                vb = {x: cx - (cx - vb.x) / f, y: cy - (cy - vb.y) / f, w: vb.w / f, h: vb.h / f}; apply();
            },
            center(x, y) { vb.x = x - vb.w / 2; vb.y = y - vb.h / 2; apply(); },
            follow(v) { following = v; },
            unitsPerPx() { return vb.w / size().w; },
            toWorld(cx, cy) { const r = svg.getBoundingClientRect(); return {x: vb.x + (cx - r.left) / r.width * vb.w, y: vb.y + (cy - r.top) / r.height * vb.h}; },
            /* clique sem arrastar → onpick(x,y); arrastar → mover o mapa */
            interactive(onpick) {
                let start = null;
                svg.addEventListener('pointerdown', (e) => { if (e.button !== 0) return; start = {x: e.clientX, y: e.clientY, vb: Object.assign({}, vb), moved: false}; svg.setPointerCapture(e.pointerId); });
                svg.addEventListener('pointermove', (e) => {
                    if (!start) return;
                    const dx = e.clientX - start.x, dy = e.clientY - start.y;
                    if (!start.moved && Math.hypot(dx, dy) < 5) return;
                    start.moved = true; following = false; svg.classList.add('is-panning');
                    const u = api.unitsPerPx(); vb.x = start.vb.x - dx * u; vb.y = start.vb.y - dy * u; apply();
                });
                svg.addEventListener('pointerup', (e) => { if (start && !start.moved) { const w = api.toWorld(e.clientX, e.clientY); onpick && onpick(w.x, w.y, e); } start = null; svg.classList.remove('is-panning'); });
                svg.addEventListener('wheel', (e) => { e.preventDefault(); const w = api.toWorld(e.clientX, e.clientY); api.zoom(e.deltaY < 0 ? 1.2 : 1 / 1.2, w.x, w.y); }, {passive: false});
            },
        };
        if (window.ResizeObserver) { let first = true; new ResizeObserver(() => { if (first) { first = false; return; } api.fit(); }).observe(svg); }
        return api;
    };

    /* ---------- quadros de vídeo com crossfade ---------- */
    /* box contém duas <img class="fr">. Troca a de trás e faz o crossfade. */
    P.frameSwap = function (box, src) {
        const imgs = box.querySelectorAll('img.fr');
        if (imgs.length < 2) return;
        const cur = box.querySelector('img.fr.on') || imgs[0];
        if (cur.dataset.src === src) return;
        const nxt = cur === imgs[0] ? imgs[1] : imgs[0];
        nxt.onerror = () => { nxt.classList.remove('on'); nxt.dataset.src = ''; };
        nxt.onload = () => { nxt.classList.add('on'); cur.classList.remove('on'); };
        nxt.dataset.src = src; nxt.src = src;
        if (nxt.complete && nxt.naturalWidth) { nxt.classList.add('on'); cur.classList.remove('on'); }
    };

    /* ---------- popovers / menus ---------- */
    const openPops = new Set();
    P.popover = function (btn, panel, onopen) {
        const close = () => { panel.hidden = true; btn.setAttribute('aria-expanded', 'false'); openPops.delete(close); };
        const open = () => { openPops.forEach((c) => c()); panel.hidden = false; btn.setAttribute('aria-expanded', 'true'); openPops.add(close); onopen && onopen(); const first = panel.querySelector('[role=menuitem],button,input,[tabindex="0"]'); first && first.focus({preventScroll: true}); };
        btn.setAttribute('aria-expanded', 'false'); panel.hidden = true;
        btn.addEventListener('click', (e) => { e.stopPropagation(); panel.hidden ? open() : close(); });
        panel.addEventListener('click', (e) => { e.stopPropagation(); if (e.target.closest('[data-close]')) { close(); btn.focus({preventScroll: true}); } });
        panel.addEventListener('keydown', (e) => {
            const items = [...panel.querySelectorAll('[role=menuitem]:not([disabled])')];
            if (!items.length) return;
            const i = items.indexOf(document.activeElement);
            if (e.key === 'ArrowDown') { e.preventDefault(); items[(i + 1) % items.length].focus(); }
            if (e.key === 'ArrowUp') { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
        });
        return {open, close};
    };
    document.addEventListener('click', () => openPops.forEach((c) => c()));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && openPops.size) { openPops.forEach((c) => c()); } });

    /* ---------- toast + área de transferência ---------- */
    P.toast = function (el, msg) {
        el.textContent = msg; el.classList.add('show');
        clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove('show'), 3200);
    };
    P.copy = function (text) {
        if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text).then(() => true, () => fallback());
        return Promise.resolve(fallback());
        function fallback() {
            try { const ta = document.createElement('textarea'); ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta); ta.select(); const ok = document.execCommand('copy'); ta.remove(); return ok; } catch (e) { return false; }
        }
    };
    /* Marcos muito próximos na régua: recolhe os rótulos e deixa só o ícone. */
    P.declutter = function (box) {
        const pins = [...box.querySelectorAll('.pin, .st')];
        pins.forEach((p) => p.classList.remove('compact'));
        const sorted = pins.map((p) => ({p, r: p.getBoundingClientRect()})).sort((a, b) => a.r.left - b.r.left);
        for (let i = 1; i < sorted.length; i++) if (sorted[i].r.left < sorted[i - 1].r.right + 4) { sorted[i].p.classList.add('compact'); sorted[i - 1].p.classList.add('compact'); }
    };
    /* ---------- ícones (sprite SVG inline; traço herda currentColor) ---------- */
    const ICONS = {
        play: '<path d="M7 4.6v14.8L19 12z" fill="currentColor" stroke="none"/>',
        pause: '<path d="M6.5 4.5h4v15h-4zM13.5 4.5h4v15h-4z" fill="currentColor" stroke="none"/>',
        back10: '<path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3"/><path d="M4.5 3.8v4.5H9"/><text x="12.4" y="15.4" font-size="7.6" font-weight="700" text-anchor="middle" fill="currentColor" stroke="none" font-family="system-ui,sans-serif">10</text>',
        fwd10: '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 3.8v4.5H15"/><text x="11.6" y="15.4" font-size="7.6" font-weight="700" text-anchor="middle" fill="currentColor" stroke="none" font-family="system-ui,sans-serif">10</text>',
        link: '<path d="M10.2 13.8a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M13.8 10.2a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
        unlink: '<path d="M15.6 13.6l3-3a4 4 0 0 0-5.7-5.7l-1 1M8.4 10.4l-3 3a4 4 0 0 0 5.7 5.7l1-1"/><path d="M4 4l16 16"/>',
        lock: '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8.5 10.5V7.8a3.5 3.5 0 0 1 7 0v2.7"/>',
        unlock: '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8.5 10.5V7.8a3.5 3.5 0 0 1 6.8-1.2"/>',
        swap: '<path d="M7 7.5h12l-3.2-3.2M17 16.5H5l3.2 3.2"/>',
        pip: '<rect x="3" y="5" width="18" height="14" rx="1.6"/><rect x="12.2" y="11.4" width="6.6" height="5.4" rx=".8" fill="currentColor" stroke="none"/>',
        split: '<rect x="2.8" y="6.5" width="8.6" height="11" rx="1.3"/><rect x="12.6" y="6.5" width="8.6" height="11" rx="1.3"/>',
        single: '<rect x="3" y="5" width="18" height="14" rx="1.6"/>',
        expand: '<path d="M14 4h6v6M10 20H4v-6M20 4l-6.5 6.5M4 20l6.5-6.5"/>',
        collapse: '<path d="M19.5 10H14V4.5M4.5 14H10v5.5M14 10l6-6M10 14l-6 6"/>',
        more: '<circle cx="5.5" cy="12" r="1.7" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.7" fill="currentColor" stroke="none"/><circle cx="18.5" cy="12" r="1.7" fill="currentColor" stroke="none"/>',
        copy: '<rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2"/><path d="M15.5 8.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7.5a2 2 0 0 0 2 2h2.5"/>',
        download: '<path d="M12 4v11M7.2 10.4 12 15.2l4.8-4.8M5 20h14"/>',
        info: '<circle cx="12" cy="12" r="8.6"/><path d="M12 11v5.5M12 7.6v.4"/>',
        warn: '<path d="M10.3 4.3 2.9 17.5A2 2 0 0 0 4.6 20.5h14.8a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0z"/><path d="M12 9.5v4.3M12 16.8v.3"/>',
        check: '<circle cx="12" cy="12" r="8.6"/><path d="M8.3 12.4l2.5 2.5 5-5.2"/>',
        chev: '<path d="M6.5 9.5 12 15l5.5-5.5"/>',
        chevR: '<path d="M9.5 6.5 15 12l-5.5 5.5"/>',
        back: '<path d="M19 12H5.5M11 6l-6 6 6 6"/>',
        stop: '<rect x="4" y="4" width="16" height="16" rx="3.2"/><path d="M10 17V7h3a3 3 0 0 1 0 6h-3"/>',
        gauge: '<path d="M4 16.5a8 8 0 1 1 16 0"/><path d="M12 16.5l4.2-4.8"/><circle cx="12" cy="16.5" r="1" fill="currentColor"/>',
        climb: '<path d="M2.5 19.5 9 9.5l4 6 2.6-3.8 5.9 7.8z"/><path d="M15.5 4.5h4v4"/><path d="M19.5 4.5l-4.5 4.5"/>',
        descent: '<path d="M2.5 19.5 9 9.5l4 6 2.6-3.8 5.9 7.8z"/><path d="M19.5 8.5h-4v-4"/><path d="M15.5 8.5l4-4"/>',
        nofilm: '<rect x="3" y="6.5" width="12.5" height="11" rx="1.6"/><path d="M15.5 10.5l5.5-3v9l-5.5-3"/><path d="M3.5 3.5l17 17"/>',
        flag: '<path d="M5.5 21V4M5.5 4.5h11.5l-2.4 3.9 2.4 3.9H5.5"/>',
        finish: '<path d="M5.5 21V4"/><path d="M5.5 4.5h13v8.5h-13z"/><path d="M9.8 4.5v8.5M14.2 4.5v8.5M5.5 8.7h13"/>',
        target: '<circle cx="12" cy="12" r="6.8"/><circle cx="12" cy="12" r="2.1" fill="currentColor" stroke="none"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3"/>',
        plus: '<path d="M12 5v14M5 12h14"/>',
        minus: '<path d="M5 12h14"/>',
        cam: '<rect x="3" y="6.5" width="12.5" height="11" rx="1.6"/><path d="M15.5 10.5l5.5-3v9l-5.5-3"/>',
        markIn: '<path d="M9.5 5H6v14h3.5"/><path d="M12 12h7.5M16.5 9l3 3-3 3"/>',
        markOut: '<path d="M14.5 5H18v14h-3.5"/><path d="M4.5 12H12M9 9l3 3-3 3"/>',
        keyboard: '<rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6.5 10h.01M10 10h.01M13.5 10h.01M17 10h.01M7.5 14h9"/>',
        moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
        sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
        search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
        layers: '<path d="M12 4 3 8.5l9 4.5 9-4.5z"/><path d="M3 12.5 12 17l9-4.5M3 16.5 12 21l9-4.5"/>',
        route: '<circle cx="6" cy="18" r="2.2"/><circle cx="18" cy="6" r="2.2"/><path d="M8 18h6.5a3.5 3.5 0 0 0 0-7h-5a3.5 3.5 0 0 1 0-7H16"/>',
        clock: '<circle cx="12" cy="12" r="8.6"/><path d="M12 7.5V12l3 2"/>',
        pin: '<path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>',
        x: '<path d="M6 6l12 12M18 6 6 18"/>',
        calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/>',
        dock: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M14 4v16"/>',
    };
    P.injectIcons = function () {
        const s = '<svg xmlns="http://www.w3.org/2000/svg" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true">' +
            Object.entries(ICONS).map(([k, v]) => `<symbol id="i-${k}" viewBox="0 0 24 24">${v}</symbol>`).join('') + '</svg>';
        document.body.insertAdjacentHTML('afterbegin', s);
    };
    P.icon = (name, cls = '') => `<svg class="i ${cls}" aria-hidden="true" focusable="false"><use href="#i-${name}"/></svg>`;
    P.markIcon = {start: 'flag', end: 'finish', stop: 'stop', max: 'gauge', climb: 'climb', descent: 'descent', gap: 'nofilm'};
    P.compass = (heading) => ['N', 'NE', 'L', 'SE', 'S', 'SO', 'O', 'NO'][Math.round((((heading + 90) % 360) + 360) % 360 / 45) % 8];
    P.syncText = (t) => t.sync.status === 'partial'
        ? {state: 'warn', label: 'Sincronização parcial', tip: 'Parte do vídeo não pôde ser alinhada ao GPS. Nesses trechos, o ponto no mapa pode ficar alguns segundos à frente ou atrás da imagem.'}
        : t.sync.status === 'unavailable'
            ? {state: 'warn', label: 'Sem sincronização', tip: 'Não foi possível alinhar vídeo e GPS nesta viagem. O mapa e os vídeos funcionam, mas cada um com o próprio relógio.'}
            : {state: 'ok', label: 'Vídeo e GPS alinhados', tip: 'O relógio das câmeras foi alinhado ao GPS com alta confiança: o ponto no mapa corresponde à imagem.'};
    P.renderThumb = function (t, w, h, padPx) {
        const bb = t.bbox, k = Math.min((w - padPx * 2) / Math.max(bb.w, 1), (h - padPx * 2) / Math.max(bb.h, 1));
        const pts = t.route.filter((_, i) => i % 2 === 0).map((p) => [w / 2 + (p[0] - bb.cx) * k, h / 2 + (p[1] - bb.cy) * k]);
        return {d: P.line(pts), a: pts[0], b: pts[pts.length - 1]};
    };
    /* verificação de layout em captura headless: opcao-x.html#debug-sw */
    if (/debug-sw/.test(location.hash)) setTimeout(() => {
        const d = document.documentElement, wide = [...document.querySelectorAll('body *')].filter((e) => !e.closest('svg') && e.getBoundingClientRect().right > d.clientWidth + 1).slice(0, 8).map((e) => e.tagName + '.' + (e.className.baseVal !== undefined ? e.className.baseVal : e.className)).join(' | ');
        const b = document.createElement('div'); b.style.cssText = 'position:fixed;z-index:9999;left:0;right:0;top:0;background:#c00;color:#fff;font:12px monospace;padding:4px;word-break:break-all';
        b.textContent = `SW=${d.scrollWidth} CW=${d.clientWidth} IW=${innerWidth} WIDE=${wide}`; document.body.appendChild(b);
    }, 1500);
    P.exportName = (t, sel, fmt) => {
        const tag = sel ? `${P.clock(t, sel.a, false).replace(':', '')}-${P.clock(t, sel.b, false).replace(':', '')}` : 'completa';
        return `trecho-${t.id}-${tag}.${fmt}`;
    };
    P.selInfo = (t, sel) => sel ? {
        from: P.clock(t, sel.a, false), to: P.clock(t, sel.b, false),
        min: (sel.b - sel.a) * t.elapsed_s / 60, km: P.kmAt(t, sel.b) - P.kmAt(t, sel.a),
    } : null;
})();
