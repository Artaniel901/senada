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
// Over 200 languages: the list is alphabetical in the interface language, so typing a letter jumps to it.
const byName = () => [...state.langs].sort((a, b) => a.name.localeCompare(b.name, LOCALE));
const langName = (id) => (id === 'auto' ? t('Deteksi') : state.byId[id]?.name || id);
const num = (n, opts) => n.toLocaleString(LOCALE, opts);
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
    const tabs = el('sakuga-tabs', { label: t('Bahasa') });
    for (const id of ids) tabs.append(el('option', { value: id, textContent: langName(id) }));
    tabs.setAttribute('selected', String(Math.max(0, ids.indexOf(this.value))));
    tabs.addEventListener('change', (e) => this.set(e.detail.value, false));
    const more = el('select', { title: t('Bahasa lain') });
    more.append(el('option', { value: '', textContent: t('Lainnya') }));
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
    $('count').textContent = num(src.value.length);
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
  setupStyle();
  $('clearSrc').addEventListener('click', () => { src.value = ''; $('dstText').textContent = ''; showNote(''); $('detected').textContent = ''; $('count').textContent = '0'; src.focus(); });
  $('copyDst').addEventListener('click', async () => {
    const text = $('dstText').textContent;
    if (!text) return;
    await navigator.clipboard.writeText(text);
    toast(t('Terjemahan disalin'));
  });
  $('clearHistory').addEventListener('click', async () => {
    if (!confirm(t('Hapus semua riwayat terjemahan teks?'))) return;
    await api.clear_history();
    renderHistory([]);
    toast(t('Riwayat dikosongkan'));
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
  $('dstNote').textContent = text ? t('Catatan: {text}', { text }) : '';
}

const penalarOn = () => !!state.engines.llm;

// Sehari-hari / Formal: one setting, a switch on both pages; live picks it up from the next line.
function setupStyle() {
  const show = () => {
    for (const b of document.querySelectorAll('.style-switch button')) {
      b.setAttribute('aria-pressed', String(b.dataset.style === (state.settings.style || 'casual')));
    }
  };
  for (const b of document.querySelectorAll('.style-switch button')) {
    b.addEventListener('click', async () => {
      if (b.dataset.style === state.settings.style) return;
      await save({ style: b.dataset.style });
      show();
      lastAsked = '';
      translateNow();  // the text already on the page, in the new style
    });
  }
  show();
}

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
  if (r.error) { $('dstText').textContent = ''; showNote(''); $('timing').textContent = tMsg(r.error); return; }
  $('dstText').textContent = r.text;
  showNote(r.note);
  state.detected = r.src;
  $('detected').textContent = srcBar.value === 'auto' ? (r.guessed ? t('Terdeteksi: {lang}', { lang: langName(r.guessed) }) : t('Bahasa tidak dikenali, dianggap {lang}', { lang: langName(r.src) })) : '';
  $('timing').textContent = r.src === tgtBar.value ? t('Bahasa asal dan tujuan sama') : '';
  if (pressed) $('go').done();
  refreshHistory();
}

function swap() {
  const from = srcBar.value === 'auto' ? (state.detected || 'id') : srcBar.value;
  const to = tgtBar.value;
  const out = $('dstText').textContent;
  srcBar.set(to);
  tgtBar.set(from);
  if (out) { $('srcText').value = out; $('dstText').textContent = ''; $('count').textContent = num(out.length); }
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
      $('count').textContent = num(h.text.length);
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
      if (!now.length) { c.checked = true; toast(t('Pilih paling sedikit satu bahasa.')); return; }
      save({ liveLangs: now }).then(renderHear);
    });
    box.append(c);
  }
  const more = $('hearMore');
  more.replaceChildren(el('option', { value: '', textContent: t('Tambah bahasa…') }));
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
  src.append(el('option', { value: 'auto', textContent: t('Deteksi otomatis') }));
  for (const l of byName().filter((l) => l.speech)) src.append(el('option', { value: l.id, textContent: `${l.name} · ${l.native}` }));
  src.value = state.settings.liveSrc;
  src.addEventListener('change', () => { save({ liveSrc: src.value }); renderHear(); });
  renderHear();
  liveTgtBar = new LangBar($('liveTgtBar'), { value: state.settings.liveTgt, onChange: (v) => { save({ liveTgt: v }); api.set_live_target(v); } });
  keepTyped($('liveTopic'), 'liveTopic');

  $('liveGo').addEventListener('click', async () => {
    if (state.live) { await api.stop_live(); return; }
    const r = await api.start_live(radio.value, src.value, liveTgtBar.value, null);
    if (r.error) { $('liveState').textContent = tMsg(r.error); }
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
    if (state.live) { $('liveState').textContent = t('Hentikan dulu yang sedang berjalan.'); return; }
    const r = await api.translate_file(src.value, liveTgtBar.value);
    if (r.error) { $('liveState').textContent = tMsg(r.error); return; }
    if (r.cancelled) return;
    $('fileBox').hidden = false;
    $('fileName').textContent = r.name;
    // Made only now: a progress bar draws on the page-wide effects layer every frame, and a hidden one draws at the top-left corner.
    if (!$('fileProgress')) {
      const bar = el('sakuga-progress', { id: 'fileProgress', label: t('Menerjemahkan berkas') });
      bar.setAttribute('done-label', t('Selesai ✓'));
      $('fileBox').append(bar);
    }
    $('fileProgress').reset();
  });

  on('started', (e) => {
    state.live = true;
    $('liveLines').replaceChildren();
    document.body.classList.add('live-on');
    $('liveBadge').hidden = false;
    $('liveBadge').textContent = t(e.source === 'file' ? 'Membaca berkas' : 'Mendengarkan');
    $('liveGo').textContent = t(e.source === 'file' ? 'Hentikan' : 'Berhenti');
    $('liveState').textContent = '';
  });
  on('stopped', (e) => {
    dropPartial();
    state.live = false;
    document.body.classList.remove('live-on');
    $('liveBadge').hidden = true;
    $('liveGo').textContent = t('Mulai mendengarkan');
    $('meter').style.width = '0';
    $('liveState').textContent = e.lines ? t('{n} kalimat tersimpan di Rekaman', { n: e.lines }) : t('Tidak ada ucapan yang terdengar');
    if (e.lines) $('liveGo').done();
  });
  on('device', (e) => {
    $('liveState').textContent = e.name;
    if (e.switched) toast(t('Pindah ke {name}', { name: e.name }));
  });
  on('level', (e) => { $('meter').style.width = `${Math.min(100, Math.sqrt(e.rms) * 260)}%`; });
  on('partial', showPartial);
  on('partial-gone', dropPartial);
  on('line', (e) => { dropPartial(); addLine($('liveLines'), e, true); });
  on('error', (e) => { $('liveState').textContent = t('Berhenti: {message}', { message: tMsg(e.message) }); });
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
    el('div', { className: pending ? 'dst pending' : 'dst', textContent: pending ? t('Menerjemahkan…') : line.dst || line.src }),
  ];
  if (line.fixes?.length) kids.push(el('p', { className: 'fixed', textContent: t('Dibetulkan dari yang terdengar: {fixes}', { fixes: line.fixes.map(([a, b]) => `${a} → ${b}`).join(', ') }) }));
  if (line.note) kids.push(el('p', { className: 'note', textContent: t('Catatan: {text}', { text: line.note }) }));
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
      el('span', { textContent: `${when.toLocaleDateString(LOCALE, { day: 'numeric', month: 'short' })} ${when.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit' })} · ${t('{n} kalimat', { n: r.lines })} · ${clock(r.seconds)}` }),
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
  if (s.error) { box.replaceChildren(el('p', { className: 'error', textContent: tMsg(s.error) })); return; }
  const list = el('ol', { className: 'lines' });
  for (const l of s.lines) addLine(list, l, false);
  const fmt = el('select', { title: t('Format berkas') });
  for (const [v, label] of [['txt', 'Teks dua bahasa (.txt)'], ['srt', 'Subtitle terjemahan (.srt)'], ['md', 'Tabel Markdown (.md)']]) fmt.append(el('option', { value: v, textContent: t(label) }));
  const saveBtn = el('sakuga-button', { textContent: t('Simpan') });
  saveBtn.setAttribute('variant', 'secondary');
  saveBtn.addEventListener('click', async () => {
    const r = await api.export_session(id, fmt.value);
    if (r.path) { saveBtn.done(); toast(t('Berkas disimpan')); }
    else if (r.error) toast(tMsg(r.error));
  });
  const exp = el('div', { className: 'export langbar-like' }, fmt, saveBtn);
  const del = el('button', { className: 'plain danger', type: 'button', textContent: t('Hapus rekaman') });
  del.addEventListener('click', async () => {
    if (!confirm(t('Hapus rekaman "{title}"? Transkripnya tidak bisa dikembalikan.', { title: s.title }))) return;
    await api.delete_session(id);
    state.record = null;
    box.replaceChildren();
    toast(t('Rekaman dihapus'));
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
    actions.append(el('span', { className: 'state', textContent: t('Mengunduh…') }));
    const cancel = el('button', { className: 'plain', type: 'button', textContent: t('Batalkan') });
    cancel.addEventListener('click', () => api.cancel_download());
    actions.append(cancel);
  } else if (!m.installed) {
    const size = m.sizeMb >= 1000 ? num(m.sizeMb / 1000, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' GB' : m.sizeMb + ' MB';
    const b = el('sakuga-button', { textContent: t('Unduh {size}', { size }) });
    b.addEventListener('click', () => startDownload(m.id));
    actions.append(b);
  } else if (active) {
    actions.append(el('span', { className: 'state', textContent: t('Sedang dipakai') }));
  } else {
    const use = el('sakuga-button', { textContent: t('Pakai ini') });
    use.setAttribute('variant', 'secondary');
    use.addEventListener('click', async () => {
      await save({ [MODEL_KEY[kind]]: m.id });
      use.done(); renderModels();
    });
    const rm = el('button', { className: 'plain danger', type: 'button', textContent: t('Hapus dari komputer') });
    rm.addEventListener('click', async () => {
      if (!confirm(t('Hapus {title} ({size} MB) dari komputer ini? Bisa diunduh lagi nanti.', { title: t(m.title), size: m.sizeMb }))) return;
      const r = await api.remove_model(m.id);
      if (r.error) return toast(tMsg(r.error));
      state.models = r.models; renderModels();
    });
    actions.append(use, rm);
  }
  const card = el('div', { className: `model${active && m.installed ? ' active' : ''}` },
    el('div', { className: 'model-head' }, el('b', { textContent: t(m.title) }), el('span', { className: 'size', textContent: `${m.sizeMb} MB` })),
    actions);
  if (downloads[m.id]) card.append(downloads[m.id].room);
  return card;
}
function renderGpu() {
  const g = state.gpu;
  const box = $('gpuBox');
  const parts = [];
  if (!g.nvidia) {
    parts.push(el('span', { className: 'state', textContent: t('Berjalan di CPU') }));
  } else if (!g.installed) {
    if (downloads['gpu-cuda']) {
      parts.push(el('span', { className: 'state', textContent: t('Mengunduh…') }), downloads['gpu-cuda'].room);
    } else {
      const b = el('sakuga-button', { textContent: t('Aktifkan GPU ({size} MB)', { size: g.sizeMb }) });
      b.addEventListener('click', () => startDownload('gpu-cuda'));
      parts.push(b);
    }
  } else {
    const gpu = el('sakuga-toggle', { label: t('Pakai GPU') });
    gpu.checked = state.settings.device !== 'cpu';
    gpu.addEventListener('change', async () => { await save({ device: gpu.checked ? 'auto' : 'cpu' }); });
    parts.push(el('label', { className: 'inline gpu-toggle' }, gpu, el('span', { textContent: t('Pakai GPU NVIDIA') })));
  }
  box.replaceChildren(...parts);
}
async function startDownload(id) {
  const r = await api.download(id);
  if (r.error) return toast(tMsg(r.error));
  const bar = el('sakuga-progress', { label: t('Mengunduh model') });
  bar.setAttribute('done-label', t('Terunduh ✓'));
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
      toast(t('Model siap dipakai'));
    }, 1600);
  });
  on('download-failed', (e) => { delete downloads[e.id]; renderModels(); toast(tMsg(e.message).slice(0, 40)); });
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
    const problem = state.engineError || (state.missing ? t('Unduh model di tab Model untuk mulai.') : '');
    $('engineText').textContent = problem;
    box.hidden = !problem;
  };
  on('engine', (e) => {
    state.engineError = e.state === 'error' ? t(e.kind === 'llm' ? 'Penalar gagal dimuat: {message}' : 'Mesin gagal dimuat: {message}', { message: e.message }) : null;
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
  // The interface language is read from storage before Python answers (i18n.js); the setting wins. One
  // reload at most (#lang), in case the storage can't keep it.
  const wanted = init.settings.uiLang || 'id';
  if (wanted !== UI_LANG && location.hash !== '#lang') {
    localStorage.setItem('senadaUiLang', wanted);
    location.hash = 'lang';
    location.reload();
    return;
  }
  if (LANG_NAMES) for (const l of state.langs) l.name = uiLangName(l.id, l.name);
  setupUiLang();
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
// The header's language menu: each language named in itself; the page reloads in the one picked.
function setupUiLang() {
  const pick = $('uiLang');
  for (const [id, name] of UI_LANGS) pick.append(el('option', { value: id, textContent: name }));
  pick.value = UI_LANG;
  pick.addEventListener('change', async () => {
    if (state.live) { pick.value = UI_LANG; toast(t('Hentikan dulu yang sedang berjalan.')); return; }
    await save({ uiLang: pick.value });
    localStorage.setItem('senadaUiLang', pick.value);
    location.reload();
  });
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
