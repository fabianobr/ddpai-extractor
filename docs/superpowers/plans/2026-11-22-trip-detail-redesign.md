# Tela de viagem (opção C, fase 1) — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir `web/index.html` pela tela de detalhe da opção C: vídeo, mapa, capítulos e linha do tempo
juntos, um controle único com horário real, temas claro e escuro.

**Architecture:** A lógica pura vai para um módulo novo, `web/trip-model.js` (UMD; global `TripModel` no
navegador, `module.exports` no Node), testado em Node. `web/index.html` é reescrito com a marcação e o CSS
portados de `docs/ux/redesign-2026-11/opcao-c.html` e com o script inline reduzido a cola de DOM.
`web/video-sync.js` não muda.

**Tech Stack:** HTML/CSS/JS sem build; Leaflet 1.9.4 (cdnjs); tiles CARTO; Google Fonts; testes `unittest` do
Python, que chamam Node 22 para o JS.

**Spec:** `docs/superpowers/specs/2026-11-22-trip-detail-redesign-design.md` (base:
`docs/superpowers/specs/2026-11-22-dashboard-use-cases-journey.md`; referência visual
`docs/ux/redesign-2026-11/opcao-c.html#detalhe` + `proto-core.js`).

## Global Constraints

- Página estática servida por `src.processing.http_server`, sem build; bibliotecas só via CDN com versão exata (Leaflet `1.9.4` do cdnjs). Chart.js sai.
- Fontes: Google Fonts `Familjen Grotesk` (500/600/700) e `Atkinson Hyperlegible` (400/700), sempre com pilha de fallback do sistema.
- Tiles CARTO `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png` e `…/dark_all/…`, atribuição `© OpenStreetMap © CARTO`, trocados conforme o tema.
- `web/video-sync.js` intacto; `linkVideos` é chamado **uma única vez**, na inicialização, com `getGroup = () => currentTrip`.
- Lazy loading: caminho em `dataset.lazySrc`; limpar com `removeAttribute('src')` + `.load()`; nunca `src = ''`; condição de carga `hasAttribute('src')`.
- Toda a interface em pt-BR, sem jargão de build. Nada de `alert/confirm/prompt`.
- Git Flow + TDD: branch `feature/trip-detail-redesign`; teste falhando antes do código; Conventional Commits; rodapé de commit com as linhas de atribuição da sessão.
- **Repositório público:** nunca versionar `docs/ux/redesign-2026-11/frames/`, `docs/ux/redesign-2026-11/mock-data.js`, `data/` ou `merged_videos/`.
- Suíte completa: `python3 -m unittest discover -s tests -v`.

## Review Focus

1. **Viagem com uma só câmera, ou sem vídeo:** a câmera ausente mostra "Sem vídeo desta câmera"; sem nenhuma, o play fica desativado com "Viagem sem vídeo", e linha do tempo, mapa e capítulos continuam navegáveis (teste na Tarefa 5).
2. **`trips.json` antigo** (pontos com 5 campos, sem `video_sync`, sem `start_timestamp`): o relógio interpola, o título cai para o `label` e os capítulos mostram ao menos Partida/Chegada (testes nas Tarefas 1 e 3).
3. **Navegador sem suporte ao codec (HEVC):** em vez de "Carregando vídeo…" eterno, aparece "Este navegador não conseguiu reproduzir o vídeo." (teste na Tarefa 5).
4. **Atalhos com foco em botão ou campo:** espaço num botão focado não pode disparar duas vezes, e digitação em campo é ignorada (teste na Tarefa 6).
5. **Viagem longa** (~9 mil pontos, 3 h) **e viagem que cruza a meia-noite:** as faixas usam `downsample`, a atualização da rota percorrida é limitada, e o horário e o título usam o fuso local (testes nas Tarefas 1 e 6).

---

### Task 0: Branch e documentação de design

**Executor:** orquestrador (comandos triviais).

**Files:**
- Modify: `docs/ux/redesign-2026-11/.gitignore` (acrescentar `mock-data.js`)
- Modify: `docs/ux/redesign-2026-11/PROPOSTA.md` (nota: `mock-data.js` é gerado localmente a partir de `data/trips.json` e não é versionado; sem ele os protótipos abrem vazios)

- [ ] **Step 1:** `git checkout -b feature/trip-detail-redesign` (a partir do estado atual, que é igual a `develop` mais os docs não versionados), depois `git branch -d docs/ux-redesign-options`.
- [ ] **Step 2:** Aplicar as duas modificações acima e conferir com `git status --short`: não podem aparecer `frames/` nem `mock-data.js`.
- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-11-22-*.md docs/superpowers/plans/2026-11-22-trip-detail-redesign.md docs/ux/redesign-2026-11
git commit -m "docs(ux): use cases, redesign options and trip detail design"
```

---

### Task 1: `trip-model.js` — tempo e formatação

**Executor:** qwen3-coder:30b (Ollama). Se falhar 2×, o Sonnet assume.

**Files:**
- Create: `web/trip-model.js`
- Create: `tests/trip_model_cases.js` (casos Node, um grupo por tarefa)
- Create: `tests/test_trip_model.py`

**Interfaces:**
- Produces (todas em `TripModel`):
  - `parseUtc(ts: string|null) -> number|null`: ms desde epoch; sem fuso, assume UTC; inválida → `null`.
  - `elapsedAt(trip, i: number) -> number`: segundos desde o início (offset `points[i][5]`; sem offsets, proporcional à duração)
  - `wallClockAt(trip, i: number) -> number|null`: `parseUtc(start_timestamp) + elapsedAt*1000`
  - `formatClock(ms: number|null, timeZone?: string) -> string` (`'HH:MM:SS'`, ciclo 24 h; `null` → `'--:--:--'`)
  - `formatDuration(seconds: number) -> string`
  - `tripTitle(trip, timeZone?: string) -> string`
  - `indexAtElapsed(trip, seconds: number) -> number`
- Convenção: `trip.points[i] = [lat, lon, speed_kmh, altitude_m, heading, time_offset_s?]`; a duração do fallback é `trip.duration_min * 60`.

- [ ] **Step 1: Escrever `tests/test_trip_model.py`**

```python
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_group(group):
    return subprocess.run(['node', 'tests/trip_model_cases.js', group], cwd=ROOT, capture_output=True, text=True)


@unittest.skipUnless(shutil.which('node'), 'Node.js necessário para testar web/trip-model.js')
class TestTripModel(unittest.TestCase):
    def test_time(self):
        r = run_group('time'); self.assertEqual(r.returncode, 0, r.stderr)

    def test_geometry(self):
        r = run_group('geometry'); self.assertEqual(r.returncode, 0, r.stderr)

    def test_chapters(self):
        r = run_group('chapters'); self.assertEqual(r.returncode, 0, r.stderr)
```

- [ ] **Step 2: Escrever `tests/trip_model_cases.js` com o grupo `time`** (as Tarefas 2 e 3 acrescentam `geometry` e `chapters` ao mesmo objeto `cases`)

```js
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
};

const group = process.argv[2];
if (!cases[group]) { console.error(`grupo desconhecido: ${group}`); process.exit(2); }
cases[group]();
```

- [ ] **Step 3:** `python3 -m unittest tests.test_trip_model -v`. Esperado: `test_time` FAIL (`Cannot find module '../web/trip-model.js'`).
- [ ] **Step 4: Implementar em `web/trip-model.js`** (casca UMD igual à de `web/video-sync.js`: `module.exports = api` no Node e `root.TripModel = api` no navegador).
  - `formatDuration`: abaixo de 60 s → `` `${Math.floor(s)} s` ``. Senão, total = `Math.round(s/60)` min, h = `floor(total/60)`, m = `total%60`, e as saídas são `'N min'`, `'N h'` ou `'N h M min'`.
  - `tripTitle`: dia da semana via `Intl.DateTimeFormat('pt-BR', {weekday:'long', timeZone})` com a inicial maiúscula. O período sai da hora local: [0,5) `de madrugada`, [5,12) `de manhã`, [12,18) `à tarde`, [18,24) `à noite`. Sem `start_timestamp` válido → `trip.label`.
  - `wallClockAt` e `indexAtElapsed`: com offsets (`points[i].length >= 6`), usam o offset (busca binária pelo último offset ≤ s). Sem offsets, usam proporção `i/(n-1) * duration_min*60` (inverso: `Math.round`, limitado a `[0, n-1]`).
- [ ] **Step 5:** `python3 -m unittest tests.test_trip_model.TestTripModel.test_time -v`. Esperado: PASS.
- [ ] **Step 6: Commit** `feat(web): trip-model time and formatting helpers`

---

### Task 2: `trip-model.js` — geometria, séries e exportação

**Executor:** qwen3-coder:30b.

**Files:** Modify `web/trip-model.js`, `tests/trip_model_cases.js` (grupo `geometry`).

**Interfaces:**
- Produces:
  - `cumulativeKm(points) -> number[]` (haversine, R = 6371 km; `[0]` = 0)
  - `downsample(values: number[], n: number, mode: 'max'|'mean') -> number[]`: balde `b` cobre `[floor(b*L/n), max(início+1, floor((b+1)*L/n)))`; se `n >= L`, devolve uma cópia.
  - `routeThumbPath(points, w, h, n) -> string`: path SVG `M x y L x y …` com no máximo `n` pontos (amostragem uniforme, sempre incluindo o último). Projeção equiretangular (`x = lon·cos(lat médio)`, `y = −lat`), escala uniforme, centrada, margem de 4 px, 1 casa decimal.
  - `decimalToDms(value, axis: 'lat'|'lon') -> string`: copiar a implementação atual de `web/index.html` (`function decimalToDms`) sem mudar a saída.
  - `buildGpx(points) -> string`, `buildKml(points) -> string`: copiar as strings atuais de `exportRoute` em `web/index.html`, sem mudança.

- [ ] **Step 1: Acrescentar o grupo `geometry`**

```js
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

        assert.strictEqual(M.decimalToDms(-27.565393, 'lat'), `27° 33' 55.41" S`);
        assert.strictEqual(M.decimalToDms(-48.51551, 'lon'), `48° 30' 55.84" W`);

        const pts = [[-27.5, -48.5, 0, 0, 0, 0], [-27.6, -48.6, 0, 0, 0, 1]];
        assert.strictEqual(M.buildGpx(pts), '<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="DDpai" xmlns="http://www.topografix.com/GPX/1/1"><trk><name>Trecho DDpai</name><trkseg><trkpt lat="-27.5" lon="-48.5"></trkpt><trkpt lat="-27.6" lon="-48.6"></trkpt></trkseg></trk></gpx>');
        assert.strictEqual(M.buildKml(pts), '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>Trecho DDpai</name><LineString><coordinates>-48.5,-27.5 -48.6,-27.6</coordinates></LineString></Placemark></Document></kml>');
    },
```

- [ ] **Step 2:** `python3 -m unittest tests.test_trip_model.TestTripModel.test_geometry -v`. Esperado: FAIL (`M.cumulativeKm is not a function`).
- [ ] **Step 3:** Implementar as funções da lista Interfaces.
- [ ] **Step 4:** Rodar `python3 -m unittest tests.test_trip_model -v`. Esperado: `test_time` e `test_geometry` PASS.
- [ ] **Step 5: Commit** `feat(web): trip-model geometry, series and GPX/KML builders`

---

### Task 3: `trip-model.js` — lacunas de câmera e capítulos

**Executor:** qwen3-coder:30b.

**Files:** Modify `web/trip-model.js`, `tests/trip_model_cases.js` (grupo `chapters`).

**Interfaces:**
- Consumes: `downsample` (Tarefa 2), `formatDuration` (Tarefa 1).
- Produces:
  - `cameraGaps(trip, camera: 'front'|'rear', minSeconds = 30) -> {startIndex, endIndex}[]`: sequências de `null` em `trip.video_sync[camera]`. A duração é `points[end][5] − points[start][5]` (sem offsets: `(end − start) · duration_min·60/(n−1)`) e entra se for ≥ `minSeconds`. Devolve `[]` sem `video_sync` ou se `trip['video_' + camera]` for falso.
  - `deriveChapters(trip) -> {type, index, endIndex?, title, detail}[]`, ordenada por `index` (ordenação estável).
- Constantes no topo do módulo: `CHAPTER_SAMPLES = 300`, `CLIMB_WINDOW_FRACTION = 0.2`, `CLIMB_MIN_M = 250`, `GAP_MIN_SECONDS = 30`.

- [ ] **Step 1: Acrescentar o grupo `chapters`**

```js
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
```

- [ ] **Step 2:** Rodar o teste. Esperado: FAIL (`M.cameraGaps is not a function`).
- [ ] **Step 3: Implementar.** Subida e descida **portam exatamente** `deriveMarks`/`refine` de `docs/ux/redesign-2026-11/proto-core.js` (linhas 112–137), com estas adaptações:
  - a série é `downsample(altitudes, CHAPTER_SAMPLES, 'mean')` (tamanho `L`), com `W = Math.round(L * CLIMB_WINDOW_FRACTION)`;
  - o limiar é `> CLIMB_MIN_M`;
  - a amostra `k` vira o índice `Math.round(k*(n-1)/(L-1))`;
  - o título é `Subida de N m` / `Descida de N m`, com `N = Math.round(m/10)*10` formatado com `toLocaleString('pt-BR')`;
  - o detalhe é `` `De ${Math.round(altInicio)} m a ${Math.round(altFim)} m` ``.

  As demais regras:
  - `stop`: vem de `idle_segments`, com título `Parada de ${Math.round(duration_s/60)} min` e `endIndex = end_index`.
  - `max`: primeiro argmax de `points[i][2]`, com título `Velocidade máxima ${Math.round(v)} km/h`.
  - `gap`: sai de `cameraGaps` (dianteira e depois traseira), com título `Sem vídeo dianteiro|traseiro`.
  - `start` e `end`: ficam nos índices 0 e n−1.
  - `detail`: livre (frase curta em pt-BR) para os tipos que não são subida nem descida.
- [ ] **Step 4:** `python3 -m unittest tests.test_trip_model -v`. Esperado: 3 PASS.
- [ ] **Step 5: Commit** `feat(web): derive trip chapters and camera gaps`

---

### Task 4: Contrato estático da nova página (testes antes da reescrita)

**Executor:** Haiku (transcreve os testes abaixo). Os testes **devem falhar** contra o `index.html` atual.

**Files:**
- Rewrite: `tests/test_frontend_accessibility.py`
- Rewrite: `tests/test_lazy_video_loading.py` (passa de pytest para `unittest`, para entrar no `discover`)

**Interfaces (nomes que as Tarefas 5–7 têm de usar):** o helper `function_body` corta o corpo na próxima
declaração `function`, então dentro dessas funções use arrow functions em vez de `function` aninhada; e não cite
`linkVideos(` em comentários (o teste conta ocorrências). Funções: `renderTripPicker(trips)`, `initialTripIndex(trips)`, `cameraVideo(camera)`, `ensureVideoLoaded(video)`, `attachLazyLoadListener(video)`, `hideLoading(camera)`, `loadTripVideos(trip)`, `updateLayoutButtons()`, `updateSyncLock()`, `renderChapters(chapters)`, `onVideoTimeUpdate(event)`, `seekToPoint(index)`, `updatePlayhead(index)`, `handleShortcut(event)`, `exportRoute(format)`, `qualityFor(trip)`, `renderTechDetails(trip)`. Os IDs estão nos testes.

- [ ] **Step 1: Escrever `tests/test_frontend_accessibility.py`**

```python
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
        self.assertIn('basemaps.cartocdn.com', HTML)
        self.assertIn('light_all', HTML)
        self.assertIn('dark_all', HTML)
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
        for token in ('isContentEditable', "'INPUT'", "'BUTTON'", 'preventDefault',
                      "' '", "'k'", "'j'", "'l'", "'i'", "'o'", "'m'", "'c'",
                      "'ArrowLeft'", "'ArrowRight'", "'Escape'"):
            self.assertIn(token, body)


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
```

- [ ] **Step 2: Escrever `tests/test_lazy_video_loading.py`**

```python
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
```

- [ ] **Step 3:** `python3 -m unittest tests.test_frontend_accessibility tests.test_lazy_video_loading -v`. Esperado: FAIL na maioria (página antiga), sem erro de sintaxe ou importação.
- [ ] **Step 4: Commit** `test(web): static contract for trip detail redesign`

---

### Tarefas 5–7: Reescrita de `web/index.html`

**Executor:** um único agente Sonnet, que faz as três tarefas em sequência no mesmo contexto e faz commit ao fim
de cada uma. Antes de começar, ele lê o spec (seção 5), `docs/ux/redesign-2026-11/opcao-c.html` (só a tela de
detalhe e o `:root`) e as funções de `web/index.html` atual que serão portadas: `seekToPoint`,
`attachVideoSyncListeners`, `onVideoTimeUpdate`, `updateRouteSelection`, `exportRoute`,
`setMapCoordinate`, `copyMapCoordinate` e `updateMap`.

**Interfaces consumidas:** `TripModel.*` (Tarefas 1–3); `linkVideos`, `pointAtVideoTime`, `timeForPoint` e
`syncConfidenceWarning` de `video-sync.js`; os nomes de função e os IDs da Tarefa 4.

### Task 5: Casca, vídeo e mapa

**Files:** Rewrite `web/index.html`.

- [ ] **Step 1:** `python3 -m unittest tests.test_frontend_accessibility.TestDocument tests.test_frontend_accessibility.TestShell tests.test_lazy_video_loading -v`. Esperado: FAIL.
- [ ] **Step 2: Implementar.**
  - **Tokens e componentes:** do `:root` claro/escuro de `opcao-c.html` (linhas 16–45), com o padrão de tema do spec e `localStorage.theme` para o botão de tema.
  - **Cabeçalho:**
    - `#trip-picker` mostra o título (`TripModel.tripTitle`) e a data/hora. O popover é montado por `renderTripPicker`, agrupado pelo dia local, com miniatura (`TripModel.routeThumbPath(points, 72, 48, 60)`), km, duração e pill.
    - Os KPIs de cabeçalho vêm logo em seguida.
    - `initialTripIndex` devolve a viagem de `#viagem-<id>`; se não houver, a de maior `start_timestamp`. A troca de viagem grava `location.hash = 'viagem-' + id`.
  - **Estado vazio e erro de leitura:** conforme o spec, seção 5.3.1.
  - **Palco:**
    - `#video-front` e `#video-rear` ficam sem `controls`. O layout muda por classe (`pip`, `pip swapped`, `side`); `#camera-swap` troca `syncState.activeVideo`.
    - O overlay `#front-loading`/`#rear-loading` tem o texto "Carregando vídeo…". O erro da câmera mostra "Este navegador não conseguiu reproduzir o vídeo." e a câmera sem arquivo mostra "Sem vídeo desta câmera".
    - `attachLazyLoadListener(cameraVideo(c))` e `linkVideos(...)` são chamados **uma vez** em `init`.
    - `loadTripVideos(trip)` faz `removeAttribute('src')` + `.load()`, grava `dataset.lazySrc` e aplica o `playbackRate` atual.
  - **Mapa:**
    - Leaflet com tiles CARTO pelo tema. A rota é desenhada em duas polylines (percorrida e restante), as paradas tracejadas e o veículo em `L.circleMarker` amarelo.
    - `#map-follow` (aria-pressed), `#map-fit` e `#map-expand`. Ampliar alterna uma classe no layout e chama `invalidateSize` em seguida; a tecla M faz o mesmo.
    - Clique no mapa leva ao ponto mais próximo (lógica atual) via `seekToPoint`.
  - **Cadeado `#sync-lock`:** `updateSyncLock` reflete `syncState.mode` e grava `localStorage.syncMode`.
  - **Capítulos:** `renderChapters(TripModel.deriveChapters(trip))` gera botões que chamam `seekToPoint(c.index)`.
  - **`seekToPoint(index)`:** porta a lógica atual, com `ensureVideoLoaded` no lugar do `video.src = …`. No modo independente, mexe só em `cameraVideo(syncState.activeVideo)`.
- [ ] **Step 3:** Rodar o comando do Step 1. Esperado: PASS. Rodar também `python3 -m unittest tests.test_frontend_timeline tests.test_player_sync -v`. Esperado: PASS.
- [ ] **Step 4: Commit** `feat(web): trip detail shell with camera stage, map and chapters`

### Task 6: Barra da história (tempo único)

**Files:** Modify `web/index.html`.

- [ ] **Step 1:** `python3 -m unittest tests.test_frontend_accessibility.TestStoryBar -v`. Esperado: FAIL.
- [ ] **Step 2: Implementar.**
  - **Transporte:**
    - `#play` alterna play/pause na câmera principal (`ensureVideoLoaded` antes do play). O `aria-label` alterna entre "Reproduzir" e "Pausar"; sem vídeo, o botão fica desativado com "Viagem sem vídeo".
    - `#back10`/`#fwd10` chamam `seekToPoint(TripModel.indexAtElapsed(trip, TripModel.elapsedAt(trip, i) ± 10))`.
    - Os botões `data-rate` aplicam `playbackRate` às duas câmeras.
  - **Leituras:**
    - `#clock` = `TripModel.formatClock(TripModel.wallClockAt(trip, i))`;
    - `#elapsed` = `formatElapsed(TripModel.elapsedAt(trip, i))` "de" total;
    - também km/h, m e km percorridos (`cumulativeKm` calculado uma vez por viagem).
  - **`#timeline`** (`role="slider"`, `tabindex="0"`, `aria-valuemin/max/now`, ←/→ quando focado), um SVG desenhado de uma vez por viagem:
    - estações dos capítulos;
    - linha de metrô com os trechos de subida, descida, parada e lacuna hachurada;
    - faixas `role="img"` de velocidade (`downsample(…, 600, 'max')`) e altitude (`'mean'`);
    - eixo com horário real a cada 10 min (ajustar o passo para viagens curtas).
    - Clique e arrasto chamam `seekToPoint`. O SVG não é redesenhado por frame: só `updatePlayhead(index)` move o playhead, o veículo e a polyline percorrida (no máximo a cada 250 ms) e marca o capítulo "agora".
  - **`onVideoTimeUpdate`:** só considera o `timeupdate` da câmera principal e mapeia com `pointAtVideoTime` (fallbacks atuais para JSON antigo).
  - **`handleShortcut`** (em `keydown` no `document`):
    - ignora `INPUT`, `TEXTAREA`, `SELECT` e `isContentEditable`; com espaço em `BUTTON` focado, deixa o botão agir;
    - teclas: `' '`/`'k'` reproduzir/pausar, `'j'`/`'ArrowLeft'` −10 s, `'l'`/`'ArrowRight'` +10 s (Shift = ±60 s), `'i'`/`'o'` início e fim do trecho (a Tarefa 7 liga o trecho), `'m'` ampliar mapa, `'c'` trocar câmera, `'Escape'` fechar popovers;
    - normalização: `const key = event.key.length === 1 ? event.key.toLowerCase() : event.key`.
- [ ] **Step 3:** Rodar o comando do Step 1. Esperado: PASS. Rodar também a suíte completa; as falhas restantes devem ser só de `TestSelectionAndQuality`.
- [ ] **Step 4: Commit** `feat(web): single transport, real-time clock and chapter timeline`

### Task 7: Trecho, coordenada e qualidade dos dados

**Files:** Modify `web/index.html`.

- [ ] **Step 1:** `python3 -m unittest tests.test_frontend_accessibility.TestSelectionAndQuality -v`. Esperado: FAIL.
- [ ] **Step 2: Implementar.**
  - **Trecho:**
    - `routeStart`/`routeEnd` funcionam como hoje.
    - As alças `#sel-start`/`#sel-end` (`role="slider"`) aceitam arrasto, toque e ←/→ quando focadas; as teclas I/O também marcam o trecho.
    - O chip `#route-chip` mostra "Trecho HH:MM–HH:MM" e abre um popover com duração, km, `#route-gpx`, `#route-kml`, `#route-clear`, a nota da geometria e `#route-message` (`role="status"`).
    - `exportRoute(format)` usa `TripModel.buildGpx`/`buildKml`. A mensagem de seleção inválida é a atual.
    - A seleção aparece em azul no mapa e na linha.
  - **Coordenada:** clique no mapa mostra uma barra com `TripModel.decimalToDms` e `#copy-map-coordinate` (lógica atual de cópia). O menu ⋯ tem "Copiar coordenada do ponto atual".
  - **Qualidade:** `qualityFor(trip)` devolve rótulo, tom e tooltip pela tabela 5.5 do spec, usando `syncConfidenceWarning(trip.video_sync)` nos casos de confiança média/baixa. O pill `#quality-pill` fica no cabeçalho, e no popover de viagens fica uma versão compacta.
  - **Menu ⋯** (`#more-button`, `aria-expanded`): contém "Detalhes técnicos". `renderTechDetails(trip)` preenche `#tech-details` com os arquivos de vídeo, `video_status`, `video_notes`, a contagem de pontos GPS e a calibração (`video_sync.confidence`, `offset_typical_spread_s`).
- [ ] **Step 3:** `python3 -m unittest discover -s tests -v`. Esperado: tudo PASS.
- [ ] **Step 4: Commit** `feat(web): route selection, coordinate copy and data quality pill`

---

### Task 8: Verificação visual e documentação

**Executor:** Haiku (mecânico). A revisão do branch inteiro fica com o orquestrador (Opus).

**Files:**
- Create: `tools/cdp-shot.js`
- Modify: `docs/CHANGELOG.md` (seção `[Unreleased]`), `README.md` (linhas que citam Chart.js: 11, 22, 107, 281), `CLAUDE.md` (linhas 108, 126, 181, 286–287, 314), `tests/test_video_sync_frontend_manual.md` (passos que citam botões e players antigos)

- [ ] **Step 1: `tools/cdp-shot.js`**
  - Uso: `node tools/cdp-shot.js URL OUT.png WIDTH HEIGHT [--dark]`.
  - Abre `google-chrome --headless=new --remote-debugging-port=0 --user-data-dir=<tmp>` e lê a porta em `DevToolsActivePort`.
  - Cria um alvo via `/json/new` e usa o `WebSocket` global do Node 22, sem dependências.
  - Comandos CDP: `Emulation.setDeviceMetricsOverride {width, height, deviceScaleFactor:1, mobile: width<700}`, `Emulation.setEmulatedMedia {features:[{name:'prefers-color-scheme', value: dark?'dark':'light'}]}`, `Page.navigate`, espera de 4 s, `Page.captureScreenshot`.
  - Grava o PNG e encerra o Chrome.
- [ ] **Step 2:** Com `./run.sh` no ar, capturar `http://localhost:8765/web/` em 1440×900 (claro e `--dark`) e 390×844 (claro), salvando em `/tmp/ddpai-shots/`. Critério: em 1440×900, vídeo, mapa, capítulos, transporte e linha aparecem sem rolar; em 390×844 não há rolagem horizontal.
- [ ] **Step 3:** Atualizar a documentação listada em Files, trocando Chart.js por "linha do tempo SVG" e descrevendo a nova tela e os atalhos. Acrescentar uma entrada `### Changed` no CHANGELOG.
- [ ] **Step 4:** `python3 -m unittest discover -s tests -v`. Esperado: tudo PASS.
- [ ] **Step 5: Commit** `docs: describe trip detail redesign; add screenshot tool`
- [ ] **Step 6 (orquestrador):** revisar o branch inteiro (`git diff develop...`) contra o spec e a Review Focus; testar no navegador uma viagem com vídeo (play, ±10 s, clique no mapa e num capítulo, modo independente, exportar GPX); depois push e PR para `develop`.
