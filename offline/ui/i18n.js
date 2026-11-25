// Senada's own words in the language the user picked (Bahasa aplikasi in the header). The Indonesian text
// is the key, as Cicada keys on its Chinese text: a string missing here simply stays Indonesian.
// Runs before Sakuga's scripts, so tabs, radios and toggles read their labels already translated.
// The choice lives in localStorage so it is known before Python answers; app.js keeps it in step with
// the `uiLang` setting (WebView2's storage is cleared when ui/ changes).
'use strict';

const UI_LANGS = [['id', 'Bahasa Indonesia'], ['en', 'English'], ['ko', '한국어']];
const UI_LANG = (() => {
  const v = localStorage.getItem('senadaUiLang');
  return UI_LANGS.some(([id]) => id === v) ? v : 'id';
})();
const LOCALE = { id: 'id-ID', en: 'en-US', ko: 'ko-KR' }[UI_LANG];

const WORDS = {
  en: {
    // header and pages
    'Halaman': 'Pages', 'Teks': 'Text', 'Suara langsung': 'Live audio', 'Rekaman': 'Recordings', 'Model': 'Models',
    'Bahasa aplikasi': 'App language',
    // text page
    'Tukar bahasa': 'Swap languages', 'Teks asal': 'Source text', 'Ketik atau tempel teks di sini': 'Type or paste text here',
    'Hapus teks': 'Clear text', 'Salin': 'Copy', 'Terjemahkan': 'Translate',
    'Terjemahkan sambil mengetik': 'Translate as you type', 'Pikir lebih dalam': 'Think deeper',
    'Gaya bahasa': 'Wording', 'Sehari-hari': 'Everyday', 'Formal': 'Formal',
    'Konteks': 'Context', 'Konteks, misalnya: chat dengan teman kantor': 'Context, e.g. a chat with a coworker',
    'Baru saja': 'Recent', 'Kosongkan riwayat': 'Clear history',
    'Bahasa': 'Language', 'Bahasa lain': 'Other languages', 'Lainnya': 'More', 'Deteksi': 'Detect',
    'Terjemahan disalin': 'Translation copied', 'Hapus semua riwayat terjemahan teks?': 'Delete all text translation history?',
    'Riwayat dikosongkan': 'History cleared', 'Catatan: {text}': 'Note: {text}', 'Terdeteksi: {lang}': 'Detected: {lang}',
    'Bahasa tidak dikenali, dianggap {lang}': 'Language not recognized, treated as {lang}',
    'Bahasa asal dan tujuan sama': 'Source and target are the same language',
    // live page
    'Sumber suara': 'Sound source', 'Suara komputer': 'Computer audio', 'Mikrofon': 'Microphone',
    'Bahasa yang diucapkan': 'Spoken language', 'Bahasa yang mungkin terdengar': 'Languages you may hear',
    'Tambah bahasa yang mungkin terdengar': 'Add a language you may hear', 'Terjemahkan ke': 'Translate to',
    'Topik pembicaraan': 'Topic', 'Topik, misalnya: rapat riset kondensasi': 'Topic, e.g. condensation research meeting',
    'Mulai mendengarkan': 'Start listening', 'Subtitle melayang': 'Floating subtitles', 'Ukuran': 'Size',
    'Ukuran subtitle': 'Subtitle size', 'Terjemahkan berkas': 'Translate a file',
    'Audio atau video: mp3, m4a, wav, mp4, mkv. Hasilnya tersimpan di Rekaman.': 'Audio or video: mp3, m4a, wav, mp4, mkv. The result is saved in Recordings.',
    'Berkas apa saja': 'Which files', 'Transkrip': 'Transcript', 'Mendengarkan': 'Listening',
    'Pilih paling sedikit satu bahasa.': 'Choose at least one language.', 'Tambah bahasa…': 'Add a language…',
    'Deteksi otomatis': 'Detect automatically', 'Hentikan dulu yang sedang berjalan.': 'Stop the current session first.',
    'Menerjemahkan berkas': 'Translating file', 'Selesai ✓': 'Done ✓', 'Membaca berkas': 'Reading file',
    'Hentikan': 'Stop', 'Berhenti': 'Stop', '{n} kalimat tersimpan di Rekaman': '{n} sentences saved in Recordings',
    'Tidak ada ucapan yang terdengar': 'No speech was heard', 'Pindah ke {name}': 'Switched to {name}',
    'Berhenti: {message}': 'Stopped: {message}', 'Menerjemahkan…': 'Translating…',
    'Dibetulkan dari yang terdengar: {fixes}': 'Corrected from what was heard: {fixes}',
    // records
    'Cari rekaman': 'Search recordings', 'Cari di rekaman': 'Search recordings', '{n} kalimat': '{n} sentences',
    'Format berkas': 'File format', 'Teks dua bahasa (.txt)': 'Bilingual text (.txt)',
    'Subtitle terjemahan (.srt)': 'Translated subtitles (.srt)', 'Tabel Markdown (.md)': 'Markdown table (.md)',
    'Simpan': 'Save', 'Berkas disimpan': 'File saved', 'Hapus rekaman': 'Delete recording',
    'Hapus rekaman "{title}"? Transkripnya tidak bisa dikembalikan.': 'Delete recording "{title}"? The transcript can\'t be recovered.',
    'Rekaman dihapus': 'Recording deleted',
    // models
    'Penalar': 'Reasoner', 'Pakai Penalar': 'Use Reasoner', 'Istilah dan nama': 'Terms and names',
    'Satu per baris, misalnya:\nfluks massa\nKookmin University': 'One per line, e.g.:\nmass flux\nKookmin University',
    'Bahasa gaul': 'Slang',
    'Satu per baris, kata = artinya, misalnya:\ngabut = bosan, tidak ada kerjaan\n킹받네 = bikin kesal banget': 'One per line, word = meaning, e.g.:\nno cap = honestly\n킹받네 = really annoying',
    'Penerjemah': 'Translator', 'Pendengar': 'Listener', 'Kecepatan': 'Speed',
    'Simpan riwayat terjemahan teks': 'Keep text translation history', 'Folder data': 'Data folder',
    'Mengunduh…': 'Downloading…', 'Batalkan': 'Cancel', 'Unduh {size}': 'Download {size}', 'Sedang dipakai': 'In use',
    'Pakai ini': 'Use this', 'Hapus dari komputer': 'Remove from computer',
    'Hapus {title} ({size} MB) dari komputer ini? Bisa diunduh lagi nanti.': 'Remove {title} ({size} MB) from this computer? You can download it again later.',
    'Berjalan di CPU': 'Running on CPU', 'Aktifkan GPU ({size} MB)': 'Enable GPU ({size} MB)', 'Pakai GPU': 'Use GPU',
    'Pakai GPU NVIDIA': 'Use NVIDIA GPU', 'Mengunduh model': 'Downloading model', 'Terunduh ✓': 'Downloaded ✓',
    'Model siap dipakai': 'Model ready', 'Unduh model di tab Model untuk mulai.': 'Download a model in the Models tab to start.',
    'Penalar gagal dimuat: {message}': 'Reasoner failed to load: {message}', 'Mesin gagal dimuat: {message}': 'Engine failed to load: {message}',
    'Penerjemah · Kualitas': 'Translator · Quality', 'Penerjemah · Cepat': 'Translator · Fast',
    'Pendengar · Seimbang': 'Listener · Balanced', 'Pendengar · Ringan': 'Listener · Light', 'Pendengar · Akurat': 'Listener · Accurate',
    'Penalar · Kualitas': 'Reasoner · Quality', 'Penalar · Ringan': 'Reasoner · Light',
    // credits (three pieces around the two bold names)
    'Dibangun di atas': 'Built on', 'oleh wquguru (Apache-2.0) dan tombol': 'by wquguru (Apache-2.0) and',
    'oleh Justin Finkelman (MIT). Model terjemahan NLLB-200 dari Meta berlisensi CC-BY-NC 4.0, hanya untuk pemakaian non-komersial. Whisper dari OpenAI berlisensi MIT. Penalar memakai Gemma 4 dari Google (Apache-2.0) lewat llama.cpp (MIT).':
      'buttons by Justin Finkelman (MIT). The NLLB-200 translation models from Meta are licensed CC-BY-NC 4.0, for non-commercial use only. Whisper from OpenAI is MIT licensed. The Reasoner runs Google\'s Gemma 4 (Apache-2.0) through llama.cpp (MIT).',
    // floating subtitles
    'Tutup subtitle melayang': 'Close floating subtitles',
    // messages from Python (app.py)
    'Penerjemah belum siap. Unduh atau pilih modelnya di tab Model.': 'The translator isn\'t ready. Download or pick its model in the Models tab.',
    'Penalar tidak memberi terjemahan, dan NLLB belum siap.': 'The Reasoner gave no translation, and NLLB isn\'t ready.',
    'Sudah sedang mendengarkan.': 'Already listening.',
    'Pendengar atau penerjemah belum siap. Cek tab Model.': 'The listener or translator isn\'t ready. Check the Models tab.',
    'Rekaman tidak ditemukan.': 'Recording not found.', 'Satu unduhan sedang berjalan.': 'A download is already running.',
    'Unduhan dibatalkan.': 'Download cancelled.', 'Model ini sedang dipakai. Pilih model lain dulu.': 'This model is in use. Pick another model first.',
    'Terjemahan gagal: ': 'Translation failed: ', 'Berkas tidak bisa dibaca: ': 'The file can\'t be read: ', 'Unduhan gagal: ': 'Download failed: ',
  },
  ko: {
    'Halaman': '페이지', 'Teks': '텍스트', 'Suara langsung': '실시간 음성', 'Rekaman': '녹음', 'Model': '모델',
    'Bahasa aplikasi': '앱 언어',
    'Tukar bahasa': '언어 바꾸기', 'Teks asal': '원문', 'Ketik atau tempel teks di sini': '여기에 텍스트를 입력하거나 붙여넣으세요',
    'Hapus teks': '지우기', 'Salin': '복사', 'Terjemahkan': '번역',
    'Terjemahkan sambil mengetik': '입력하면서 번역', 'Pikir lebih dalam': '더 깊이 생각',
    'Gaya bahasa': '말투', 'Sehari-hari': '일상어', 'Formal': '격식체',
    'Konteks': '맥락', 'Konteks, misalnya: chat dengan teman kantor': '맥락 (예: 회사 동료와의 채팅)',
    'Baru saja': '최근', 'Kosongkan riwayat': '기록 지우기',
    'Bahasa': '언어', 'Bahasa lain': '다른 언어', 'Lainnya': '더 보기', 'Deteksi': '감지',
    'Terjemahan disalin': '번역을 복사했습니다', 'Hapus semua riwayat terjemahan teks?': '텍스트 번역 기록을 모두 지울까요?',
    'Riwayat dikosongkan': '기록을 지웠습니다', 'Catatan: {text}': '참고: {text}', 'Terdeteksi: {lang}': '감지됨: {lang}',
    'Bahasa tidak dikenali, dianggap {lang}': '언어를 알 수 없어 {lang}(으)로 처리했습니다',
    'Bahasa asal dan tujuan sama': '원문과 번역 언어가 같습니다',
    'Sumber suara': '소리 입력', 'Suara komputer': '컴퓨터 소리', 'Mikrofon': '마이크',
    'Bahasa yang diucapkan': '말하는 언어', 'Bahasa yang mungkin terdengar': '들릴 수 있는 언어',
    'Tambah bahasa yang mungkin terdengar': '들릴 수 있는 언어 추가', 'Terjemahkan ke': '번역할 언어',
    'Topik pembicaraan': '대화 주제', 'Topik, misalnya: rapat riset kondensasi': '주제 (예: 응축 연구 회의)',
    'Mulai mendengarkan': '듣기 시작', 'Subtitle melayang': '떠 있는 자막', 'Ukuran': '크기',
    'Ukuran subtitle': '자막 크기', 'Terjemahkan berkas': '파일 번역',
    'Audio atau video: mp3, m4a, wav, mp4, mkv. Hasilnya tersimpan di Rekaman.': '오디오 또는 비디오: mp3, m4a, wav, mp4, mkv. 결과는 녹음에 저장됩니다.',
    'Berkas apa saja': '지원 파일', 'Transkrip': '녹취록', 'Mendengarkan': '듣는 중',
    'Pilih paling sedikit satu bahasa.': '언어를 하나 이상 선택하세요.', 'Tambah bahasa…': '언어 추가…',
    'Deteksi otomatis': '자동 감지', 'Hentikan dulu yang sedang berjalan.': '진행 중인 작업을 먼저 멈추세요.',
    'Menerjemahkan berkas': '파일 번역 중', 'Selesai ✓': '완료 ✓', 'Membaca berkas': '파일 읽는 중',
    'Hentikan': '중지', 'Berhenti': '멈추기', '{n} kalimat tersimpan di Rekaman': '문장 {n}개를 녹음에 저장했습니다',
    'Tidak ada ucapan yang terdengar': '들린 말이 없습니다', 'Pindah ke {name}': '{name}(으)로 전환했습니다',
    'Berhenti: {message}': '중지됨: {message}', 'Menerjemahkan…': '번역 중…',
    'Dibetulkan dari yang terdengar: {fixes}': '들린 말에서 고침: {fixes}',
    'Cari rekaman': '녹음 검색', 'Cari di rekaman': '녹음에서 검색', '{n} kalimat': '문장 {n}개',
    'Format berkas': '파일 형식', 'Teks dua bahasa (.txt)': '두 언어 텍스트 (.txt)',
    'Subtitle terjemahan (.srt)': '번역 자막 (.srt)', 'Tabel Markdown (.md)': '마크다운 표 (.md)',
    'Simpan': '저장', 'Berkas disimpan': '파일을 저장했습니다', 'Hapus rekaman': '녹음 삭제',
    'Hapus rekaman "{title}"? Transkripnya tidak bisa dikembalikan.': '"{title}" 녹음을 삭제할까요? 녹취록은 되돌릴 수 없습니다.',
    'Rekaman dihapus': '녹음을 삭제했습니다',
    'Penalar': '추론 엔진', 'Pakai Penalar': '추론 엔진 사용', 'Istilah dan nama': '용어와 이름',
    'Satu per baris, misalnya:\nfluks massa\nKookmin University': '한 줄에 하나씩, 예:\n질량 유속\nKookmin University',
    'Bahasa gaul': '신조어·은어',
    'Satu per baris, kata = artinya, misalnya:\ngabut = bosan, tidak ada kerjaan\n킹받네 = bikin kesal banget': '한 줄에 하나씩, 단어 = 뜻, 예:\n킹받네 = 정말 짜증 난다\ngabut = 심심하다, 할 일이 없다',
    'Penerjemah': '번역기', 'Pendengar': '음성 인식', 'Kecepatan': '속도',
    'Simpan riwayat terjemahan teks': '텍스트 번역 기록 저장', 'Folder data': '데이터 폴더',
    'Mengunduh…': '다운로드 중…', 'Batalkan': '취소', 'Unduh {size}': '{size} 다운로드', 'Sedang dipakai': '사용 중',
    'Pakai ini': '이것 사용', 'Hapus dari komputer': '컴퓨터에서 삭제',
    'Hapus {title} ({size} MB) dari komputer ini? Bisa diunduh lagi nanti.': '이 컴퓨터에서 {title}({size} MB)을(를) 삭제할까요? 나중에 다시 다운로드할 수 있습니다.',
    'Berjalan di CPU': 'CPU에서 실행 중', 'Aktifkan GPU ({size} MB)': 'GPU 켜기 ({size} MB)', 'Pakai GPU': 'GPU 사용',
    'Pakai GPU NVIDIA': 'NVIDIA GPU 사용', 'Mengunduh model': '모델 다운로드 중', 'Terunduh ✓': '다운로드 완료 ✓',
    'Model siap dipakai': '모델 준비 완료', 'Unduh model di tab Model untuk mulai.': '시작하려면 모델 탭에서 모델을 다운로드하세요.',
    'Penalar gagal dimuat: {message}': '추론 엔진을 불러오지 못했습니다: {message}', 'Mesin gagal dimuat: {message}': '엔진을 불러오지 못했습니다: {message}',
    'Penerjemah · Kualitas': '번역기 · 품질', 'Penerjemah · Cepat': '번역기 · 빠름',
    'Pendengar · Seimbang': '음성 인식 · 균형', 'Pendengar · Ringan': '음성 인식 · 가벼움', 'Pendengar · Akurat': '음성 인식 · 정확',
    'Penalar · Kualitas': '추론 엔진 · 품질', 'Penalar · Ringan': '추론 엔진 · 가벼움',
    'Dibangun di atas': '기반:', 'oleh wquguru (Apache-2.0) dan tombol': '(wquguru, Apache-2.0), 버튼:',
    'oleh Justin Finkelman (MIT). Model terjemahan NLLB-200 dari Meta berlisensi CC-BY-NC 4.0, hanya untuk pemakaian non-komersial. Whisper dari OpenAI berlisensi MIT. Penalar memakai Gemma 4 dari Google (Apache-2.0) lewat llama.cpp (MIT).':
      '(Justin Finkelman, MIT). Meta의 NLLB-200 번역 모델은 CC-BY-NC 4.0 라이선스로 비상업적 용도로만 쓸 수 있습니다. OpenAI의 Whisper는 MIT 라이선스입니다. 추론 엔진은 Google의 Gemma 4(Apache-2.0)를 llama.cpp(MIT)로 실행합니다.',
    'Tutup subtitle melayang': '떠 있는 자막 닫기',
    'Penerjemah belum siap. Unduh atau pilih modelnya di tab Model.': '번역기가 준비되지 않았습니다. 모델 탭에서 모델을 다운로드하거나 선택하세요.',
    'Penalar tidak memberi terjemahan, dan NLLB belum siap.': '추론 엔진이 번역을 내놓지 않았고 NLLB도 준비되지 않았습니다.',
    'Sudah sedang mendengarkan.': '이미 듣고 있습니다.',
    'Pendengar atau penerjemah belum siap. Cek tab Model.': '음성 인식 또는 번역기가 준비되지 않았습니다. 모델 탭을 확인하세요.',
    'Rekaman tidak ditemukan.': '녹음을 찾을 수 없습니다.', 'Satu unduhan sedang berjalan.': '다른 다운로드가 진행 중입니다.',
    'Unduhan dibatalkan.': '다운로드를 취소했습니다.', 'Model ini sedang dipakai. Pilih model lain dulu.': '이 모델은 사용 중입니다. 먼저 다른 모델을 선택하세요.',
    'Terjemahan gagal: ': '번역 실패: ', 'Berkas tidak bisa dibaca: ': '파일을 읽을 수 없습니다: ', 'Unduhan gagal: ': '다운로드 실패: ',
  },
};

// One string in the user's language; {name} parts are filled from `vars`.
function t(text, vars) {
  const out = (WORDS[UI_LANG] && WORDS[UI_LANG][text]) || text;
  return vars ? out.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m)) : out;
}

// A message from Python: known whole, or a known start ("Unduhan gagal: ") with the details kept.
function tMsg(text) {
  if (!text || UI_LANG === 'id') return text;
  const dict = WORDS[UI_LANG];
  if (dict[text]) return dict[text];
  const start = Object.keys(dict).find((k) => k.endsWith(': ') && text.startsWith(k));
  return start ? dict[start] + text.slice(start.length) : text;
}

// A language's name in the interface language (Chromium knows most); Senada's Indonesian name otherwise.
const LANG_NAMES = UI_LANG === 'id' ? null : new Intl.DisplayNames([UI_LANG], { type: 'language', fallback: 'none' });
function uiLangName(id, fallback) {
  if (!LANG_NAMES) return fallback;
  try { return LANG_NAMES.of(id) || fallback; } catch { return fallback; }
}

// The page's own text and the attributes people read, translated in place (whitespace around kept).
function translatePage(root) {
  if (UI_LANG === 'id') return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const key = n.nodeValue.trim();
    if (key && WORDS[UI_LANG][key]) n.nodeValue = n.nodeValue.replace(key, WORDS[UI_LANG][key]);
  }
  for (const attr of ['placeholder', 'label', 'title', 'aria-label', 'text']) {
    for (const node of root.querySelectorAll(`[${attr}]`)) {
      const v = node.getAttribute(attr);
      if (WORDS[UI_LANG][v]) node.setAttribute(attr, WORDS[UI_LANG][v]);
    }
  }
  document.documentElement.lang = UI_LANG;
}

translatePage(document.body);
