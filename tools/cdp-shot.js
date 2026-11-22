#!/usr/bin/env node
// Captures a PNG of URL at an exact viewport using headless Chrome over the DevTools protocol.
// Usage: node tools/cdp-shot.js URL OUT.png WIDTH HEIGHT [--dark]
// Requires Node 22+ (global WebSocket) and google-chrome on PATH; no npm dependencies.
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const [, , url, out, w, h, ...flags] = process.argv;
if (!url || !out || !w || !h) {
  console.error('usage: node tools/cdp-shot.js URL OUT.png WIDTH HEIGHT [--dark]');
  process.exit(1);
}
const width = Number(w);
const height = Number(h);
const dark = flags.includes('--dark');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitForPort(profileDir, timeoutMs = 10000) {
  const file = path.join(profileDir, 'DevToolsActivePort');
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (fs.existsSync(file)) {
      const port = fs.readFileSync(file, 'utf8').split('\n')[0].trim();
      if (port) return port;
    }
    await sleep(100);
  }
  throw new Error('Chrome did not expose DevToolsActivePort within 10 s');
}

async function main() {
  const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ddpai-cdp-'));
  const chrome = spawn('google-chrome', [
    '--headless=new',
    '--remote-debugging-port=0',
    `--user-data-dir=${profileDir}`,
    `--window-size=${width},${height}`,
    '--no-first-run',
    '--no-default-browser-check',
    'about:blank',
  ], { stdio: 'ignore', detached: true });
  let chromeError = null;
  chrome.on('error', (err) => { chromeError = err; });
  const chromeExited = new Promise((resolve) => chrome.on('exit', resolve));

  try {
    const port = await waitForPort(profileDir);
    if (chromeError) throw new Error(`cannot start google-chrome: ${chromeError.message}`);

    const resp = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' });
    if (!resp.ok) throw new Error(`/json/new failed with HTTP ${resp.status}`);
    const target = await resp.json();

    const ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = () => reject(new Error('cannot open DevTools WebSocket'));
    });

    let nextId = 1;
    const pending = new Map();
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && pending.has(msg.id)) {
        const { resolve, reject } = pending.get(msg.id);
        pending.delete(msg.id);
        if (msg.error) reject(new Error(`${msg.error.message} (${msg.error.code})`));
        else resolve(msg.result);
      }
    };
    const send = (method, params = {}) => new Promise((resolve, reject) => {
      const id = nextId++;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });

    await send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: width < 700,
    });
    await send('Emulation.setEmulatedMedia', {
      features: [{ name: 'prefers-color-scheme', value: dark ? 'dark' : 'light' }],
    });
    await send('Page.enable');
    await send('Page.navigate', { url });
    await sleep(4000);
    const shot = await send('Page.captureScreenshot', { format: 'png' });

    fs.writeFileSync(out, Buffer.from(shot.data, 'base64'));
    ws.close();
  } finally {
    // Chrome is detached, so it leads its own process group: signal the whole group so that
    // renderer/GPU/crashpad children stop writing to the profile too.
    try { process.kill(-chrome.pid, 'SIGTERM'); } catch {}
    await Promise.race([chromeExited, sleep(5000)]);
    if (chrome.exitCode === null && chrome.signalCode === null) {
      try { process.kill(-chrome.pid, 'SIGKILL'); } catch {}
      await Promise.race([chromeExited, sleep(2000)]);
    }
    // Best-effort: the screenshot already succeeded, so a leftover profile must not change the exit code.
    try {
      fs.rmSync(profileDir, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
    } catch {
      console.error(`cdp-shot: aviso: não consegui apagar ${profileDir}`);
    }
  }
}

main()
  .then(() => console.log(`wrote ${out} (${width}x${height}${dark ? ', dark' : ''})`))
  .catch((err) => {
    console.error(`cdp-shot: ${err.message}`);
    process.exitCode = 1;
  });
