// Cicada Offline page. Python is window.pywebview.api (app.py's Api); what it reports arrives
// through window.cicadaEvent. Built with DOM calls and textContent only: translated text is never HTML.
'use strict';

const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, ...kids) => {
  const n = Object.assign(document.createElement(tag), props);
  for (const k of kids) if (k != null) n.append(k);
  return n;
};
const state = { langs: [], byId: {}, settings: {}, models: [], gpu: {}, engines: {}, live: false, detected: null, record: null };
let api = null;

// ───────── events from Python ─────────
const handlers = {};
const on = (type, fn) => (handlers[type] ||= []).push(fn);
window.cicadaEvent = (e) => (handlers[e.type] || []).forEach((fn) => fn(e));

const toast = (msg) => $('toast').show(msg);
const langName = (id) => (id === 'auto' ? 'Deteksi' : state.byId[id]?.name || id);
const clock = (t) => {
  const s = Math.max(0, Math.round(t));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
};
const save = (patch) => api.save_settings(patch).then((v) => (state.settings = v));

// ───────── language bars: Sakuga tabs for the three favourites, a list for the rest ─────────
// Tabs read their options once, so a language picked from the list rebuilds the tabs with it in.
class LangBar {
  constructor(host, { auto = false, speechOnly = false, value, onChange }) {
    Object.assign(this, { host, auto, speechOnly, value, onChange });
    this.extra = null;
    this.render();
  }
  options() {
    const ids = [...(this.auto ? ['auto'] : []), ...state.langs.filter((l) => l.favorite).map((l) => l.id)];
    if (this.value && !ids.includes(this.value)) this.extra = this.value;
    if (this.extra && !ids.includes(this.extra)) ids.push(this.extra);
    return ids;
  }
  render() {
    const ids = this.options();
    const tabs = el('sakuga-tabs', { label: 'Bahasa' });
    for (const id of ids) tabs.append(el('option', { value: id, textContent: langName(id) }));
    tabs.setAttribute('selected', String(Math.max(0, ids.indexOf(this.value))));
    tabs.addEventListener('change', (e) => this.set(e.detail.value, false));
    const more = el('select', { title: 'Bahasa lain' });
    more.append(el('option', { value: '', textContent: 'Bahasa lain…' }));
    for (const l of state.langs) {
      if (this.speechOnly && !l.speech) continue;
      if (l.favorite) continue;
      more.append(el('option', { value: l.id, textContent: `${l.name} · ${l.native}` }));
    }
    more.addEventListener('change', () => more.value && this.set(more.value, true));
    this.host.replaceChildren(tabs, more);
    this.tabs = tabs;
  }
  set(id, rebuild = true) {
    if (!id) return;
    const changed = id !== this.value;
    this.value = id;
    if (rebuild) this.render();
    if (changed) this.onChange?.(id);
  }
}

// ───────── Text ─────────
let srcBar, tgtBar, typingTimer = null, lastAsked = '';

function setupText() {
  srcBar = new LangBar($('textSrcBar'), { auto: true, value: state.settings.textSrc, onChange: (v) => { save({ textSrc: v }); translateNow(); } });
  tgtBar = new LangBar($('textTgtBar'), { value: state.settings.textTgt, onChange: (v) => { save({ textTgt: v }); translateNow(); } });
  const src = $('srcText');
  src.addEventListener('input', () => {
    $('count').textContent = src.value.length.toLocaleString('id-ID');
    if (!$('asType').checked) return;
    clearTimeout(typingTimer);
    typingTimer = setTimeout(() => translateNow(), 550);
  });
  src.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $('go').impact?.(); translateNow(true); }
  });
  $('asType').checked = !!state.settings.translateAsYouType;
  $('asType').addEventListener('change', () => save({ translateAsYouType: $('asType').checked }));
  $('go').addEventListener('click', () => translateNow(true));
  $('swap').addEventListener('click', swap);
  $('clearSrc').addEventListener('click', () => { src.value = ''; $('dstText').textContent = ''; $('detected').textContent = ''; $('count').textContent = '0'; src.focus(); });
  $('copyDst').addEventListener('click', async () => {
    const text = $('dstText').textContent;
    if (!text) return;
    await navigator.clipboard.writeText(text);
    toast('Terjemahan disalin');
  });
  $('clearHistory').addEventListener('click', async () => {
    if (!confirm('Hapus semua riwayat terjemahan teks?')) return;
    await api.clear_history();
    renderHistory([]);
    toast('Riwayat dikosongkan');
  });
}

async function translateNow(pressed = false) {
  const text = $('srcText').value;
  const key = `${srcBar.value}|${tgtBar.value}|${text}`;
  if (!text.trim()) { $('dstText').textContent = ''; $('detected').textContent = ''; return; }
  if (!pressed && key === lastAsked) return;
  lastAsked = key;
  $('dstText').classList.add('busy');
  const r = await api.translate(text, srcBar.value, tgtBar.value, true);
  if (key !== lastAsked) return; // a newer request is on its way
  $('dstText').classList.remove('busy');
  if (r.error) { $('dstText').textContent = ''; $('timing').textContent = r.error; return; }
  $('dstText').textContent = r.text;
  state.detected = r.src;
  $('detected').textContent = srcBar.value === 'auto' ? (r.guessed ? `Terdeteksi: ${langName(r.guessed)}` : `Bahasa tidak dikenali, dianggap ${langName(r.src)}`) : '';
  const took = r.ms < 100 ? 'kurang dari 0,1 detik' : `${(r.ms / 1000).toLocaleString('id-ID', { maximumFractionDigits: 1 })} detik`;
  $('timing').textContent = r.src === tgtBar.value ? 'Bahasa asal dan tujuan sama' : `${took} · ${r.device === 'cuda' ? 'GPU' : 'CPU'}`;
  if (pressed) $('go').done();
  refreshHistory();
}

function swap() {
  const from = srcBar.value === 'auto' ? (state.detected || 'id') : srcBar.value;
  const to = tgtBar.value;
  const out = $('dstText').textContent;
  srcBar.set(to);
  tgtBar.set(from);
  if (out) { $('srcText').value = out; $('dstText').textContent = ''; $('count').textContent = out.length.toLocaleString('id-ID'); }
  save({ textSrc: to, textTgt: from });
  translateNow(true);
}

async function refreshHistory() { renderHistory((await api.history_items()).slice(0, 12)); }
function renderHistory(items) {
  const list = $('historyList');
  list.replaceChildren(...items.map((h) => {
    const li = el('li', { tabIndex: 0 },
      el('span', { className: 'pair-tag', textContent: `${langName(h.src)} → ${langName(h.tgt)}` }),
      el('p', { className: 'from', textContent: h.text }),
      el('p', { textContent: h.out }));
    const load = () => {
      $('srcText').value = h.text; $('dstText').textContent = h.out;
      srcBar.set(h.src); tgtBar.set(h.tgt);
      $('count').textContent = h.text.length.toLocaleString('id-ID');
      lastAsked = `${h.src}|${h.tgt}|${h.text}`;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    };
    li.addEventListener('click', load);
    li.addEventListener('keydown', (e) => e.key === 'Enter' && load());
    return li;
  }));
  $('clearHistory').hidden = !items.length;
  document.querySelector('.history').hidden = !items.length;
}

// ───────── Live ─────────
let liveTgtBar;

function setupLive() {
  const radio = $('liveSource');
  radio.value = state.settings.liveSource;
  radio.addEventListener('change', () => save({ liveSource: radio.value }));
  const src = $('liveSrc');
  src.append(el('option', { value: 'auto', textContent: 'Deteksi otomatis' }));
  for (const l of state.langs.filter((l) => l.speech)) src.append(el('option', { value: l.id, textContent: `${l.name} · ${l.native}` }));
  src.value = state.settings.liveSrc;
  src.addEventListener('change', () => save({ liveSrc: src.value }));
  liveTgtBar = new LangBar($('liveTgtBar'), { value: state.settings.liveTgt, onChange: (v) => { save({ liveTgt: v }); api.set_live_target(v); } });

  $('liveGo').addEventListener('click', async () => {
    if (state.live) { await api.stop_live(); return; }
    const r = await api.start_live(radio.value, src.value, liveTgtBar.value, null);
    if (r.error) { $('liveState').textContent = r.error; }
  });
  $('overlayToggle').checked = !!state.settings.overlay;
  $('overlayToggle').addEventListener('change', () => api.overlay($('overlayToggle').checked));
  on('overlay-state', (e) => { if ($('overlayToggle').checked !== e.on) $('overlayToggle').checked = e.on; });
  $('overlaySize').value = state.settings.overlaySize;
  $('overlaySize').addEventListener('change', () => save({ overlaySize: Number($('overlaySize').value) }));
  $('fileGo').addEventListener('click', async () => {
    if (state.live) { $('liveState').textContent = 'Hentikan dulu yang sedang berjalan.'; return; }
    const r = await api.translate_file(src.value, liveTgtBar.value);
    if (r.error) { $('liveState').textContent = r.error; return; }
    if (r.cancelled) return;
    $('fileBox').hidden = false;
    $('fileName').textContent = r.name;
    $('fileProgress').reset();
  });

  on('started', (e) => {
    state.live = true;
    $('liveLines').replaceChildren();
    document.body.classList.add('live-on');
    $('liveBadge').hidden = false;
    $('liveBadge').textContent = e.source === 'file' ? 'Membaca berkas' : 'Mendengarkan';
    $('liveGo').textContent = e.source === 'file' ? 'Hentikan' : 'Berhenti';
    $('liveState').textContent = e.source === 'mic' ? 'Mendengarkan mikrofon…' : e.source === 'file' ? `Menerjemahkan ${e.name || 'berkas'}…` : 'Mendengarkan suara komputer…';
  });
  on('stopped', (e) => {
    state.live = false;
    document.body.classList.remove('live-on');
    $('liveBadge').hidden = true;
    $('liveGo').textContent = 'Mulai mendengarkan';
    $('meter').style.width = '0';
    $('liveState').textContent = e.lines ? `Selesai. ${e.lines} kalimat tersimpan di Rekaman.` : 'Selesai. Tidak ada ucapan yang terdengar, jadi tidak ada yang disimpan.';
    if (e.lines) $('liveGo').done();
  });
  on('level', (e) => { $('meter').style.width = `${Math.min(100, Math.sqrt(e.rms) * 260)}%`; });
  on('pending', (e) => {
    if (state.live && e.count > 0) $('liveState').textContent = `Memproses ${e.count} potongan suara…`;
  });
  on('line', (e) => {
    addLine($('liveLines'), e, true);
    $('liveState').textContent = 'Mendengarkan…';
  });
  on('error', (e) => { $('liveState').textContent = `Berhenti: ${e.message}`; });
  on('file-progress', (e) => $('fileProgress').set(e.value));
}

function addLine(list, line, fresh) {
  list.querySelector('.fresh')?.classList.remove('fresh');
  const li = el('li', { className: fresh ? 'fresh' : '' },
    el('span', { className: 't', textContent: clock(line.t) }),
    el('div', { className: 'src' }, el('span', { className: 'lang', textContent: langName(line.srcLang) }), line.src),
    el('div', { className: 'dst', textContent: line.dst || line.src }));
  list.append(li);
  if (fresh) li.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

// ───────── Records ─────────
let records = [];
async function loadRecords() {
  records = await api.sessions();
  renderRecords();
}
function renderRecords() {
  const q = ($('recordSearch').value || '').toLowerCase();
  const shown = records.filter((r) => !q || `${r.title} ${r.preview}`.toLowerCase().includes(q));
  $('recordList').replaceChildren(...shown.map((r) => {
    const when = new Date(r.startedAt);
    const b = el('button', { className: 'record', type: 'button' },
      el('b', { textContent: r.title }),
      el('span', { textContent: `${when.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' })} ${when.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })} · ${r.lines} kalimat · ${clock(r.seconds)}` }),
      el('p', { textContent: r.preview }));
    b.setAttribute('aria-current', String(state.record === r.id));
    b.addEventListener('click', () => openRecord(r.id));
    return el('li', {}, b);
  }));
}
async function openRecord(id) {
  state.record = id;
  renderRecords();
  const s = await api.session(id);
  const box = $('recordDetail');
  if (s.error) { box.replaceChildren(el('p', { className: 'empty-note', textContent: s.error })); return; }
  const list = el('ol', { className: 'lines' });
  for (const l of s.lines) addLine(list, l, false);
  const fmt = el('select', { title: 'Format berkas' });
  for (const [v, label] of [['txt', 'Teks dua bahasa (.txt)'], ['srt', 'Subtitle terjemahan (.srt)'], ['md', 'Tabel Markdown (.md)']]) fmt.append(el('option', { value: v, textContent: label }));
  const saveBtn = el('sakuga-button', { textContent: 'Simpan' });
  saveBtn.setAttribute('variant', 'secondary');
  saveBtn.addEventListener('click', async () => {
    const r = await api.export_session(id, fmt.value);
    if (r.path) { saveBtn.done(); toast('Berkas disimpan'); }
    else if (r.error) toast(r.error);
  });
  const exp = el('div', { className: 'export langbar-like' }, fmt, saveBtn);
  const del = el('button', { className: 'plain danger', type: 'button', textContent: 'Hapus rekaman' });
  del.addEventListener('click', async () => {
    if (!confirm(`Hapus rekaman "${s.title}"? Transkripnya tidak bisa dikembalikan.`)) return;
    await api.delete_session(id);
    state.record = null;
    box.replaceChildren(el('p', { className: 'empty-note', textContent: 'Rekaman dihapus.' }));
    loadRecords();
  });
  box.replaceChildren(el('div', { className: 'detail-head' }, el('h2', { textContent: s.title }), del), exp, list);
}

// ───────── Models ─────────
const downloads = {};
function renderModels() {
  for (const kind of ['mt', 'asr']) {
    const host = $(kind === 'mt' ? 'mtModels' : 'asrModels');
    const active = state.settings[kind === 'mt' ? 'mtModel' : 'asrModel'];
    host.replaceChildren(...state.models.filter((m) => m.kind === kind).map((m) => modelCard(m, m.id === active, kind)));
  }
  renderGpu();
}
function modelCard(m, active, kind) {
  const actions = el('div', { className: 'model-actions' });
  if (downloads[m.id]) {
    actions.append(el('span', { className: 'state', textContent: 'Mengunduh…' }));
    const cancel = el('button', { className: 'plain', type: 'button', textContent: 'Batalkan' });
    cancel.addEventListener('click', () => api.cancel_download());
    actions.append(cancel);
  } else if (!m.installed) {
    const b = el('sakuga-button', { textContent: `Unduh ${m.sizeMb >= 1000 ? (m.sizeMb / 1000).toFixed(1) + ' GB' : m.sizeMb + ' MB'}` });
    b.addEventListener('click', () => startDownload(m.id));
    actions.append(b);
  } else if (active) {
    actions.append(el('span', { className: 'state', textContent: 'Sedang dipakai' }));
  } else {
    const use = el('sakuga-button', { textContent: 'Pakai ini' });
    use.setAttribute('variant', 'secondary');
    use.addEventListener('click', async () => {
      await save({ [kind === 'mt' ? 'mtModel' : 'asrModel']: m.id });
      use.done(); renderModels();
    });
    const rm = el('button', { className: 'plain danger', type: 'button', textContent: 'Hapus dari komputer' });
    rm.addEventListener('click', async () => {
      if (!confirm(`Hapus ${m.title} (${m.sizeMb} MB) dari komputer ini? Bisa diunduh lagi nanti.`)) return;
      const r = await api.remove_model(m.id);
      if (r.error) return toast(r.error);
      state.models = r.models; renderModels();
    });
    actions.append(use, rm);
  }
  const card = el('div', { className: `model${active && m.installed ? ' active' : ''}` },
    el('div', { className: 'model-head' }, el('b', { textContent: m.title }), el('span', { className: 'size', textContent: `${m.sizeMb} MB` })),
    el('p', { textContent: `${m.blurb} · lisensi ${m.license}` }), actions);
  if (downloads[m.id]) card.append(downloads[m.id].room);
  return card;
}
function renderGpu() {
  const g = state.gpu;
  const box = $('gpuBox');
  const parts = [];
  if (!g.nvidia) {
    parts.push(el('p', { className: 'hint', textContent: 'Kartu grafis NVIDIA tidak ditemukan. Semua berjalan di prosesor (CPU): teks tetap cepat, suara langsung sedikit tertinggal.' }));
  } else if (!g.installed) {
    parts.push(el('p', { className: 'hint', textContent: `Komputer ini punya GPU NVIDIA. Unduh pustaka cuBLAS (${g.sizeMb} MB) agar suara langsung diproses di bawah satu detik per kalimat.` }));
    if (downloads['gpu-cuda']) {
      parts.push(el('span', { className: 'state', textContent: 'Mengunduh…' }), downloads['gpu-cuda'].room);
    } else {
      const b = el('sakuga-button', { textContent: 'Aktifkan GPU' });
      b.addEventListener('click', () => startDownload('gpu-cuda'));
      parts.push(b);
    }
  } else {
    const t = el('sakuga-toggle', { label: 'Pakai GPU' });
    t.checked = state.settings.device !== 'cpu';
    t.addEventListener('change', async () => { await save({ device: t.checked ? 'auto' : 'cpu' }); });
    parts.push(el('label', { className: 'inline gpu-toggle' }, t, el('span', { textContent: 'Pakai GPU NVIDIA' })));
    const where = [state.engines.mt && `penerjemah di ${state.engines.mt.device === 'cuda' ? 'GPU' : 'CPU'}`, state.engines.asr && `pendengar di ${state.engines.asr.device === 'cuda' ? 'GPU' : 'CPU'}`].filter(Boolean).join(', ');
    parts.push(el('p', { className: 'hint', textContent: where ? `Sekarang: ${where}.` : 'Mesin sedang dimuat.' }));
  }
  box.replaceChildren(...parts);
}
async function startDownload(id) {
  const r = await api.download(id);
  if (r.error) return toast(r.error);
  const bar = el('sakuga-progress', { label: 'Mengunduh model' });
  bar.setAttribute('done-label', 'Terunduh ✓');
  const room = el('div', { className: 'progress-room' }, bar);
  downloads[id] = { bar, room };
  renderModels();
}

function setupModels() {
  on('download', (e) => downloads[e.id]?.bar.set(e.total ? e.done / e.total : 0));
  on('download-done', async (e) => {
    downloads[e.id]?.bar.set(1);
    setTimeout(async () => {
      delete downloads[e.id];
      const r = await api.models();
      state.models = r.models; state.gpu.installed = r.gpuInstalled; renderModels();
      toast('Model siap dipakai');
    }, 1600);
  });
  on('download-failed', (e) => { delete downloads[e.id]; renderModels(); toast(e.message.slice(0, 40)); });
  $('keepHistory').checked = !!state.settings.keepHistory;
  $('keepHistory').addEventListener('change', () => save({ keepHistory: $('keepHistory').checked }));
  $('openData').textContent = state.dataFolder;
  $('openData').addEventListener('click', () => api.open_data_folder());
}

// ───────── Engine status ─────────
function setupEngines() {
  const show = () => {
    const box = $('engine');
    const { mt, asr } = state.engines;
    box.className = 'engine';
    if (state.engineError) { box.classList.add('error'); $('engineText').textContent = state.engineError; return; }
    if (state.missing) { box.classList.add('error'); $('engineText').textContent = 'Unduh model di tab Model untuk mulai.'; return; }
    if (mt && asr) {
      box.classList.add('ready');
      const gpu = mt.device === 'cuda' || asr.device === 'cuda';
      $('engineText').textContent = `Siap, tanpa internet · ${gpu ? 'GPU' : 'CPU'}`;
    } else $('engineText').textContent = 'Memuat mesin…';
  };
  on('engine', (e) => {
    state.engineError = e.state === 'error' ? `Mesin gagal dimuat: ${e.message}` : null;
    if (e.state === 'missing') state.missing = true;
    if (e.state === 'ready') { state.engines[e.kind] = { model: e.model, device: e.device }; state.missing = false; }
    if (e.state === 'loading') state.engines[e.kind] = null;
    show();
    renderGpu();
  });
  show();
}

// ───────── Start ─────────
async function start() {
  api = window.pywebview.api;
  const init = await api.init();
  state.langs = init.languages;
  state.byId = Object.fromEntries(init.languages.map((l) => [l.id, l]));
  state.settings = init.settings;
  state.models = init.models;
  state.gpu = init.gpu;
  state.engines = init.engines;
  state.dataFolder = init.dataFolder;
  setupText();
  setupLive();
  setupModels();
  setupEngines();
  renderModels();
  renderHistory(init.history.slice(0, 12));
  $('recordSearch').addEventListener('input', renderRecords);
  $('nav').addEventListener('change', (e) => {
    for (const p of document.querySelectorAll('.page')) p.hidden = p.id !== `page-${e.detail.value}`;
    if (e.detail.value === 'records') loadRecords();
    if (e.detail.value === 'models') api.models().then((r) => { state.models = r.models; state.gpu.installed = r.gpuInstalled; state.engines = { ...state.engines, ...r.engines }; renderModels(); });
  });
  if (!init.models.some((m) => m.installed)) { $('nav').selected = 3; showPage('models'); }
  $('srcText').focus();
  if (init.drive) new Function('api', '$', 'on', 'showPage', init.drive)(api, $, on, showPage);
}
function showPage(name) { for (const p of document.querySelectorAll('.page')) p.hidden = p.id !== `page-${name}`; }

if (window.pywebview?.api?.init) start();
else window.addEventListener('pywebviewready', start, { once: true });
