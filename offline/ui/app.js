// Senada page. Python is window.pywebview.api (app.py's Api); what it reports arrives
// through window.senadaEvent. Built with DOM calls and textContent only: translated text is never HTML.
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
window.senadaEvent = (e) => (handlers[e.type] || []).forEach((fn) => fn(e));

const toast = (msg) => $('toast').show(msg);
// Over 200 languages: the list is alphabetical by Indonesian name, so typing a letter jumps to it.
const byName = () => [...state.langs].sort((a, b) => a.name.localeCompare(b.name, 'id'));
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
    more.append(el('option', { value: '', textContent: 'Lainnya' }));
    for (const l of byName()) {
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
  $('deep').checked = !!state.settings.thinkDeep;
  $('deep').addEventListener('change', () => save({ thinkDeep: $('deep').checked }));
  keepTyped($('textContext'), 'textContext', () => { lastAsked = ''; });
  $('clearSrc').addEventListener('click', () => { src.value = ''; $('dstText').textContent = ''; showNote(''); $('detected').textContent = ''; $('count').textContent = '0'; src.focus(); });
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

// A text field whose value is a setting: saved a moment after typing stops.
function keepTyped(field, key, after) {
  field.value = state.settings[key] || '';
  let timer = null;
  const store = () => { clearTimeout(timer); if (field.value !== state.settings[key]) save({ [key]: field.value }).then(() => after?.()); };
  field.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(store, 700); });
  field.addEventListener('change', store);
}

function showNote(text) {
  $('dstNote').hidden = !text;
  $('dstNote').textContent = text ? `Catatan: ${text}` : '';
}

const penalarOn = () => !!state.engines.llm;

async function translateNow(pressed = false) {
  const text = $('srcText').value;
  const deep = pressed && $('deep').checked && penalarOn();
  const key = `${srcBar.value}|${tgtBar.value}|${deep}|${text}`;
  if (!text.trim()) { $('dstText').textContent = ''; showNote(''); $('detected').textContent = ''; return; }
  if (!pressed && key === lastAsked) return;
  lastAsked = key;
  $('dstText').classList.add('busy');
  $('timing').textContent = '';
  const r = await api.translate(text, srcBar.value, tgtBar.value, true, deep);
  if (key !== lastAsked) return; // a newer request is on its way
  $('dstText').classList.remove('busy');
  if (r.error) { $('dstText').textContent = ''; showNote(''); $('timing').textContent = r.error; return; }
  $('dstText').textContent = r.text;
  showNote(r.note);
  state.detected = r.src;
  $('detected').textContent = srcBar.value === 'auto' ? (r.guessed ? `Terdeteksi: ${langName(r.guessed)}` : `Bahasa tidak dikenali, dianggap ${langName(r.src)}`) : '';
  $('timing').textContent = r.src === tgtBar.value ? 'Bahasa asal dan tujuan sama' : '';
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

// "Detect" picks only among these: asked to choose from all 99, Whisper heard Indonesian as Javanese,
// Vietnamese and once Khmer. The favourites are always offered; others can be added.
function renderHear() {
  $('hearRow').hidden = $('liveSrc').value !== 'auto';
  const chosen = state.settings.liveLangs || [];
  const speech = state.langs.filter((l) => l.speech);
  const shown = [...new Set([...speech.filter((l) => l.favorite).map((l) => l.id), ...chosen])];
  const box = $('hearLangs');
  box.replaceChildren();
  for (const id of shown) {
    const c = el('sakuga-checkbox', { textContent: langName(id) });
    if (chosen.includes(id)) c.setAttribute('checked', '');
    c.addEventListener('change', () => {
      const now = c.checked ? [...chosen, id] : chosen.filter((x) => x !== id);
      if (!now.length) { c.checked = true; toast('Pilih paling sedikit satu bahasa.'); return; }
      save({ liveLangs: now }).then(renderHear);
    });
    box.append(c);
  }
  const more = $('hearMore');
  more.replaceChildren(el('option', { value: '', textContent: 'Tambah bahasa…' }));
  for (const l of byName().filter((l) => l.speech && !shown.includes(l.id))) {
    more.append(el('option', { value: l.id, textContent: `${l.name} · ${l.native}` }));
  }
  more.onchange = () => more.value && save({ liveLangs: [...chosen, more.value] }).then(renderHear);
}

function setupLive() {
  const radio = $('liveSource');
  radio.value = state.settings.liveSource;
  radio.addEventListener('change', () => save({ liveSource: radio.value }));
  const src = $('liveSrc');
  src.append(el('option', { value: 'auto', textContent: 'Deteksi otomatis' }));
  for (const l of byName().filter((l) => l.speech)) src.append(el('option', { value: l.id, textContent: `${l.name} · ${l.native}` }));
  src.value = state.settings.liveSrc;
  src.addEventListener('change', () => { save({ liveSrc: src.value }); renderHear(); });
  renderHear();
  liveTgtBar = new LangBar($('liveTgtBar'), { value: state.settings.liveTgt, onChange: (v) => { save({ liveTgt: v }); api.set_live_target(v); } });
  keepTyped($('liveTopic'), 'liveTopic');

  $('liveGo').addEventListener('click', async () => {
    if (state.live) { await api.stop_live(); return; }
    const r = await api.start_live(radio.value, src.value, liveTgtBar.value, null);
    if (r.error) { $('liveState').textContent = r.error; }
  });
  // The size only matters while the subtitle is up, so it is shown only then.
  const sizeRow = () => { $('sizeRow').hidden = !$('overlayToggle').checked; };
  $('overlayToggle').checked = !!state.settings.overlay;
  sizeRow();
  $('overlayToggle').addEventListener('change', () => { api.overlay($('overlayToggle').checked); sizeRow(); });
  on('overlay-state', (e) => { if ($('overlayToggle').checked !== e.on) $('overlayToggle').checked = e.on; sizeRow(); });
  $('overlaySize').value = state.settings.overlaySize;
  $('overlaySize').addEventListener('change', () => save({ overlaySize: Number($('overlaySize').value) }));
  $('fileGo').addEventListener('click', async () => {
    if (state.live) { $('liveState').textContent = 'Hentikan dulu yang sedang berjalan.'; return; }
    const r = await api.translate_file(src.value, liveTgtBar.value);
    if (r.error) { $('liveState').textContent = r.error; return; }
    if (r.cancelled) return;
    $('fileBox').hidden = false;
    $('fileName').textContent = r.name;
    // Made only now: a progress bar draws on the page-wide effects layer every frame, and a hidden one draws at the top-left corner.
    if (!$('fileProgress')) {
      const bar = el('sakuga-progress', { id: 'fileProgress', label: 'Menerjemahkan berkas' });
      bar.setAttribute('done-label', 'Selesai ✓');
      $('fileBox').append(bar);
    }
    $('fileProgress').reset();
  });

  on('started', (e) => {
    state.live = true;
    $('liveLines').replaceChildren();
    document.body.classList.add('live-on');
    $('liveBadge').hidden = false;
    $('liveBadge').textContent = e.source === 'file' ? 'Membaca berkas' : 'Mendengarkan';
    $('liveGo').textContent = e.source === 'file' ? 'Hentikan' : 'Berhenti';
    $('liveState').textContent = '';
  });
  on('stopped', (e) => {
    dropPartial();
    state.live = false;
    document.body.classList.remove('live-on');
    $('liveBadge').hidden = true;
    $('liveGo').textContent = 'Mulai mendengarkan';
    $('meter').style.width = '0';
    $('liveState').textContent = e.lines ? `${e.lines} kalimat tersimpan di Rekaman` : 'Tidak ada ucapan yang terdengar';
    if (e.lines) $('liveGo').done();
  });
  on('device', (e) => {
    $('liveState').textContent = e.name;
    if (e.switched) toast(`Pindah ke ${e.name}`);
  });
  on('level', (e) => { $('meter').style.width = `${Math.min(100, Math.sqrt(e.rms) * 260)}%`; });
  on('partial', showPartial);
  on('partial-gone', dropPartial);
  on('line', (e) => { dropPartial(); addLine($('liveLines'), e, true); });
  on('error', (e) => { $('liveState').textContent = `Berhenti: ${e.message}`; });
  on('file-progress', (e) => $('fileProgress')?.set(e.value));
}

// The sentence still being spoken: one grey line at the bottom, replaced as more is heard.
function showPartial(e) {
  const list = $('liveLines');
  let li = list.querySelector('li.partial');
  if (!li) { li = el('li', { className: 'partial' }); list.append(li); }
  li.replaceChildren(el('span', { className: 't', textContent: clock(e.t) }), el('div', { className: 'dst', textContent: e.src }));
  li.scrollIntoView({ block: 'nearest' });
}
function dropPartial() { $('liveLines').querySelector('li.partial')?.remove(); }

// A heard line, or the same line again once Penalar has translated it (same id: replaced in place).
function addLine(list, line, fresh) {
  const pending = !!line.translating;
  const kids = [
    el('span', { className: 't', textContent: clock(line.t) }),
    el('div', { className: 'src' }, el('span', { className: 'lang', textContent: langName(line.srcLang) }), line.src),
    el('div', { className: pending ? 'dst pending' : 'dst', textContent: pending ? 'Menerjemahkan…' : line.dst || line.src }),
  ];
  if (line.fixes?.length) kids.push(el('p', { className: 'fixed', textContent: `Dibetulkan dari yang terdengar: ${line.fixes.map(([a, b]) => `${a} → ${b}`).join(', ')}` }));
  if (line.note) kids.push(el('p', { className: 'note', textContent: `Catatan: ${line.note}` }));
  const old = line.id && list.querySelector(`li[data-id="${CSS.escape(line.id)}"]`);
  if (old) { old.replaceChildren(...kids); return; }
  list.querySelector('.fresh')?.classList.remove('fresh');
  const li = el('li', { className: fresh ? 'fresh' : '' }, ...kids);
  if (line.id) li.dataset.id = line.id;
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
  $('recordsGrid').hidden = !records.length;
  $('recordsBlank').hidden = !!records.length;
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
  if (s.error) { box.replaceChildren(el('p', { className: 'error', textContent: s.error })); return; }
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
    box.replaceChildren();
    toast('Rekaman dihapus');
    loadRecords();
  });
  box.replaceChildren(el('div', { className: 'detail-head' }, el('h2', { textContent: s.title }), del), exp, list);
}

// ───────── Models ─────────
const downloads = {};
const MODEL_KEY = { mt: 'mtModel', asr: 'asrModel', llm: 'llmModel' };
const HOST = { mt: 'mtModels', asr: 'asrModels', llm: 'llmModels' };
function renderModels() {
  for (const kind of ['llm', 'mt', 'asr']) {
    const active = state.settings[MODEL_KEY[kind]];
    $(HOST[kind]).replaceChildren(...state.models.filter((m) => m.kind === kind).map((m) => modelCard(m, m.id === active, kind)));
  }
  renderGpu();
  renderPenalar();
}
// The Penalar-only controls (deep thinking, topic) show only while Penalar is loaded.
function renderPenalar() {
  document.body.classList.toggle('penalar-on', penalarOn());
}
function modelCard(m, active, kind) {
  const actions = el('div', { className: 'model-actions' });
  if (downloads[m.id]) {
    actions.append(el('span', { className: 'state', textContent: 'Mengunduh…' }));
    const cancel = el('button', { className: 'plain', type: 'button', textContent: 'Batalkan' });
    cancel.addEventListener('click', () => api.cancel_download());
    actions.append(cancel);
  } else if (!m.installed) {
    const b = el('sakuga-button', { textContent: `Unduh ${m.sizeMb >= 1000 ? (m.sizeMb / 1000).toLocaleString('id-ID', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' GB' : m.sizeMb + ' MB'}` });
    b.addEventListener('click', () => startDownload(m.id));
    actions.append(b);
  } else if (active) {
    actions.append(el('span', { className: 'state', textContent: 'Sedang dipakai' }));
  } else {
    const use = el('sakuga-button', { textContent: 'Pakai ini' });
    use.setAttribute('variant', 'secondary');
    use.addEventListener('click', async () => {
      await save({ [MODEL_KEY[kind]]: m.id });
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
    actions);
  if (downloads[m.id]) card.append(downloads[m.id].room);
  return card;
}
function renderGpu() {
  const g = state.gpu;
  const box = $('gpuBox');
  const parts = [];
  if (!g.nvidia) {
    parts.push(el('span', { className: 'state', textContent: 'Berjalan di CPU' }));
  } else if (!g.installed) {
    if (downloads['gpu-cuda']) {
      parts.push(el('span', { className: 'state', textContent: 'Mengunduh…' }), downloads['gpu-cuda'].room);
    } else {
      const b = el('sakuga-button', { textContent: `Aktifkan GPU (${g.sizeMb} MB)` });
      b.addEventListener('click', () => startDownload('gpu-cuda'));
      parts.push(b);
    }
  } else {
    const t = el('sakuga-toggle', { label: 'Pakai GPU' });
    t.checked = state.settings.device !== 'cpu';
    t.addEventListener('change', async () => { await save({ device: t.checked ? 'auto' : 'cpu' }); });
    parts.push(el('label', { className: 'inline gpu-toggle' }, t, el('span', { textContent: 'Pakai GPU NVIDIA' })));
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
  $('reasoning').checked = !!state.settings.reasoning;
  $('reasoning').addEventListener('change', () => save({ reasoning: $('reasoning').checked }));
  keepTyped($('words'), 'words');
  keepTyped($('slang'), 'slang');
  $('keepHistory').checked = !!state.settings.keepHistory;
  $('keepHistory').addEventListener('change', () => save({ keepHistory: $('keepHistory').checked }));
  $('openData').textContent = state.dataFolder;
  $('openData').addEventListener('click', () => api.open_data_folder());
}

// ───────── Engine status ─────────
function setupEngines() {
  const show = () => {
    const box = $('engine');
    // Only something the user must act on is shown here: a failed engine or a missing model.
    box.className = 'engine error';
    const problem = state.engineError || (state.missing ? 'Unduh model di tab Model untuk mulai.' : '');
    $('engineText').textContent = problem;
    box.hidden = !problem;
  };
  on('engine', (e) => {
    state.engineError = e.state === 'error' ? `${e.kind === 'llm' ? 'Penalar' : 'Mesin'} gagal dimuat: ${e.message}` : null;
    if (e.state === 'missing' && e.kind !== 'llm') state.missing = true;  // no Penalar model is fine: NLLB translates
    if (e.state === 'ready') { state.engines[e.kind] = { model: e.model, device: e.device }; state.missing = false; }
    if (['loading', 'off', 'missing', 'error'].includes(e.state)) state.engines[e.kind] = null;
    show();
    renderGpu();
    renderPenalar();
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
  $('nav').addEventListener('change', (e) => showPage(e.detail.value));
  if (!init.models.some((m) => m.installed)) showPage('models');
  $('srcText').focus();
  if (init.drive) new Function('api', '$', 'on', 'showPage', init.drive)(api, $, on, showPage);
}
// One way to change page, for the tabs and for code: the tabs follow, and the page's data is fetched fresh.
const PAGES = ['text', 'live', 'records', 'models'];
function showPage(name) {
  for (const p of document.querySelectorAll('.page')) p.hidden = p.id !== `page-${name}`;
  if ($('nav').selected !== PAGES.indexOf(name)) $('nav').selected = PAGES.indexOf(name);
  if (name === 'records') loadRecords();
  if (name === 'models') api.models().then((r) => { state.models = r.models; state.gpu.installed = r.gpuInstalled; state.engines = { ...state.engines, ...r.engines }; renderModels(); });
}

if (window.pywebview?.api?.init) start();
else window.addEventListener('pywebviewready', start, { once: true });
