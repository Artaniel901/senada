# Senada

<img src="ui/senada.svg" width="72" alt="Logo Senada: dua garis suara yang bersilang lalu menyatu">

**Terjemahan yang paham maksud.** Penerjemah teks dan suara langsung yang berjalan sepenuhnya di
komputer Windows. Namanya dari *se-nada*: terjemahannya tetap senada dengan maksud dan nada
pembicara. Dibangun di atas [Cicada](https://github.com/wquguru/cicada) (Apache-2.0). Tombol dan
kontrolnya memakai [Sakuga VFX](https://github.com/finktheartist/sakuga-vfx) (MIT).

Cicada versi Windows mengirim suara ke layanan AI di internet dan butuh key. Senada mengganti mesin
itu dengan model yang jalan di komputer ini. Internet hanya dipakai sekali untuk mengunduh model.
(Sampai 0.2.0 namanya Cicada Offline.)

## Yang bisa dilakukan

- **Penalar** (baru di 0.2.0): model bahasa lokal (Gemma 4 lewat llama.cpp) yang menerjemahkan
  *maksud*, bukan kata per kata. Idiom, bahasa gaul dan kalimat yang belum selesai jadi kalimat yang
  wajar dan benar tata bahasanya. Ia membaca kalimat-kalimat sebelumnya, topik dan daftar istilah Anda,
  jadi kata yang salah dengar ("Coevisien", "fluk semasa") dibetulkan jadi "Koefisien" dan "fluks massa".
  Kalau maknanya tidak sama dengan kata-katanya (idiom, sindiran, basa-basi), ada catatan pendek.
  Untuk kalimat yang sangat aneh, nyalakan **Pikir lebih dalam** di tab Teks (sekitar 10–30 detik).
- **Kamus bahasa gaul** (baru di 0.3.0): sekitar 370 kata gaul Indonesia, Korea dan Inggris
  (`senada/slang/*.tsv`), misalnya gabut, julid, zonk, 어쩔티비, 점메추, "ate and left no crumbs". Kata
  yang ditemukan di kalimat diberikan ke Penalar beserta artinya. NLLB tidak bisa membaca catatan, jadi
  kata yang aman diganti ditukar dulu dengan kata bakunya ("mager" jadi "malas bergerak"). Kata yang
  juga punya arti biasa (cabut, garing, bet) hanya diberi catatan. Kata gaul Anda sendiri bisa
  ditambahkan di tab Model, **Bahasa gaul**, satu per baris: `kata = artinya`.

- **Teks**: ketik atau tempel teks, lalu terjemahkan antar **202 bahasa**, yaitu semua bahasa yang
  dikenal NLLB-200. Indonesia, Korea dan Inggris ada di depan; sisanya urut abjad di "Bahasa lain".
  Bahasa sumber dideteksi otomatis. Bisa menerjemahkan sambil mengetik, dan terjemahan terbaru
  disimpan di riwayat. Ada bahasa daerah (Jawa, Sunda, Minang, Bali, Banjar, Bugis, Aceh), bahasa
  Arab sehari-hari (Mesir, Maroko, Irak, Syam, …), dan banyak bahasa Asia, Afrika dan Eropa.
  Suara langsung bisa mendengar 98 di antaranya; sisanya untuk teks.
- **Suara langsung**: mendengarkan suara komputer (rapat, video, siaran) atau mikrofon. Setiap
  kalimat ditulis beserta terjemahannya, dan bahasanya dideteksi per kalimat, jadi rapat
  campuran Korea–Indonesia–Inggris tetap terbaca benar.
  - Kalimat dipotong di jeda ucapan (Silero VAD), bukan di jeda bunyi, jadi musik latar tidak
    menggabungkan atau memotong kalimat, dan musik tanpa suara orang tidak ditulis.
  - Deteksi otomatis hanya memilih dari **Bahasa yang mungkin terdengar** (bawaannya Indonesia,
    Korea, Inggris). Memilih dari 99 bahasa membuat bahasa Indonesia terbaca sebagai Jawa atau Vietnam.
  - Teks yang tidak mungkin ucapan (huruf berulang, aksara yang salah) dibuang. Kalimat yang
    pendengarnya ragu ditandai, dan Penalar tidak mengarang makna untuknya; kalau sama sekali tidak
    jelas, terjemahannya "…" dengan catatan.
  - Dengan GPU NVIDIA, pakai **Pendengar · Akurat** (Whisper large-v3 turbo). Di GPU 6 GB ia muat
    bersama Penalar · Kualitas (puncak sekitar 5,5 GB).
- **Subtitle melayang**: bilah subtitle yang selalu di atas jendela lain. Bisa diseret dan
  ukuran hurufnya bisa diatur.
- **Berkas rekaman**: menerjemahkan audio atau video (mp3, m4a, wav, mp4, mkv, …).
- **Rekaman**: setiap sesi tersimpan dalam format rekaman Cicada. Bisa disimpan sebagai teks
  dua bahasa, subtitle `.srt`, atau tabel Markdown.

## Pasang dan buka

1. Butuh Windows 10/11 x64 dan Python 3.12.
2. Jalankan `setup.cmd` sekali. Lingkungan Python dibuat di `.venv` di folder ini, tidak di C:.
3. Buka shortcut **Senada** yang dibuat setup (di folder ini, Desktop dan Start). Shortcut itu
   membawa ikon Senada, juga di taskbar kalau disematkan. `Senada.cmd` adalah cadangannya;
   `tools\shortcut.ps1` membuat ulang shortcut-nya.
4. Di tab **Model**, unduh penerjemah dan pendengar. Bawaannya NLLB-200 1.3B (1,4 GB) dan
   Whisper small (490 MB).
5. Kalau ada kartu NVIDIA, tekan **Aktifkan GPU** (cuBLAS, unduhan 553 MB). Dengan GPU satu
   kalimat selesai di bawah 1 detik. Tanpa GPU sekitar 4–6 detik.
6. Untuk terjemahan yang paham maksud, unduh **Penalar · Kualitas** (4,7 GB). Mesinnya (llama.cpp,
   39 MB) ikut terunduh. Penalar memakai GPU lewat Vulkan, jadi kartu AMD dan Intel juga bisa.

Model, pengaturan, riwayat dan rekaman tersimpan di folder ini: `models/` dan `data/`.

## Model

| Peran | Model | Ukuran | Lisensi |
|---|---|---|---|
| Penerjemah · Kualitas (bawaan) | NLLB-200 distilled 1.3B, CTranslate2 int8 | 1,4 GB | CC-BY-NC-4.0 |
| Penerjemah · Cepat | NLLB-200 distilled 600M | 630 MB | CC-BY-NC-4.0 |
| Pendengar · Seimbang (bawaan) | Whisper small | 490 MB | MIT |
| Pendengar · Ringan | Whisper base | 150 MB | MIT |
| Pendengar · Akurat | Whisper large-v3 turbo | 1,6 GB | MIT |
| Penalar · Kualitas (bawaan) | Gemma 4 E4B, GGUF Q4_K_M | 4,7 GB | Apache-2.0 |
| Penalar · Ringan | Gemma 4 E2B, GGUF Q4_K_M | 3,0 GB | Apache-2.0 |

Mesin Penalar adalah `llama-server` dari llama.cpp (MIT), build b12721 versi Vulkan, dicek dengan
SHA-256. Ia hanya mendengarkan di 127.0.0.1 dengan kunci acak, dan ikut mati kalau aplikasi ditutup.

Dengan Penalar menyala, NLLB pindah ke CPU. Ia tetap menerjemahkan bahasa yang kurang dikuasai Gemma
(bahasa daerah, bahasa Arab sehari-hari, banyak bahasa Afrika; daftarnya `PENALAR` di `reason.py`,
98 bahasa) dan menjadi cadangan kalau Penalar gagal. Di GPU 6 GB, Whisper dan Gemma 4 E4B bersama
memakai sekitar 5,4 GB.

GPU tidak wajib. Tanpa kartu grafis semuanya jalan di prosesor: teks dengan NLLB tetap cepat, suara
langsung tertinggal beberapa detik, dan Penalar sebaiknya memakai **Ringan** (E2B) dengan RAM minimal
16 GB, sekitar beberapa detik per kalimat. Kartu dengan memori 4 GB cukup untuk Whisper dan E2B.

NLLB-200 dari Meta berlisensi **non-komersial** (CC-BY-NC-4.0). Aplikasi ini boleh dipakai sendiri,
tapi tidak untuk dijual.

## Bagaimana ia memakai Cicada

Dari `linux/cicada/core` (mesin Cicada versi Linux yang hanya memakai pustaka standar Python),
bagian-bagian ini dipakai apa adanya:

- `segmenter.py`: memotong suara menjadi kalimat. Angkanya sama di semua platform Cicada.
- `roommic.VoiceGate`: mempelajari tingkat bising ruangan untuk mikrofon.
- `models.py` dan `session_store.py`: format rekaman. Rekaman Senada bisa dibaca Cicada.
  Kata yang dibetulkan Penalar disimpan di kolom `fixes` milik Cicada; teks yang terdengar tetap utuh.
- `audio.Wav`: membaca berkas WAV.

Yang baru ada di `senada/`:

- `asr.py`: Whisper lewat faster-whisper.
- `translate.py`: NLLB lewat CTranslate2.
- `reason.py`: Penalar, Gemma 4 lewat `llama-server`.
- `capture.py`: suara komputer lewat WASAPI loopback, plus mikrofon.
- `live.py`: alur langsung.
- `app.py`: jendela pywebview.
- `catalog.py`: pengunduh model dengan cek SHA-256.

## Untuk pengembang

```bat
.venv\Scripts\python -m unittest discover -s tests
.venv\Scripts\python -X utf8 tools\try_live.py id rekaman.wav
```

- `tools/try_live.py` menjalankan alur langsung pada berkas WAV tanpa jendela.
- `tools/try_slang.py <hasil.tsv>` mencoba kalimat gaul di `tests/slang_cases.tsv` lewat Penalar dan
  NLLB; `--no-slang` membandingkan tanpa kamus.
- `tools/get_fleurs.py <folder> id_id:25 ko_kr:25 en_us:25` mengambil potongan rekaman orang dari
  Google FLEURS (CC-BY 4.0) tanpa mengunduh arsip penuhnya; `tools/try_hearing.py --hear id,ko,en <folder>`
  menghitung bahasa yang terdengar benar, kata yang salah dan waktu Whisper per klip.
- `tools/make_icon.py` menggambar ulang `senada.ico` dari `ui/senada.svg` (butuh Chrome atau Edge).
- `SENADA_HOME` memindahkan folder `data/`, misalnya untuk uji.
- `SENADA_MODELS` memindahkan folder `models/`.
- `SENADA_DEBUG=1` membuka DevTools.
- `tools/try_live.py --penalar --topic "..." --words "..." id rekaman.wav` mencoba Penalar tanpa jendela.
- `SENADA_DRIVE=<berkas.js>` menjalankan skrip di halaman setelah dimulai. Ini hanya untuk
  uji antarmuka.

Komponen Sakuga ada di `ui/vendor/sakuga/` dan tidak diubah. Gayanya hanya diatur lewat variabel
`--sk-*` (lihat `SOURCE.txt`).

## Batasan

- Hanya untuk Windows. Penangkap suara memakai WASAPI. Belum ada versi HP.
- Bahasa Jawa yang diucapkan terdengar sebagai bahasa Indonesia, dan tulisannya banyak yang salah
  (uji FLEURS: 15 dari 15 klip). Whisper hampir tidak dilatih bahasa Jawa. Bahasa Melayu baru
  terdengar benar kalau dicentang di **Bahasa yang mungkin terdengar** (9 dari 15 klip).
- Mutu terjemahan bahasa kecil bervariasi. Bahasa besar (Islandia, Zulu, Marathi, Cebuano) bagus;
  bahasa dengan sedikit data, misalnya Banjar dalam huruf Jawi atau Kashmir dalam Dewanagari, bisa
  memotong atau mencampur kalimat.
- Catatan rapat otomatis dan juru bahasa suara dari Cicada tidak ada di sini, karena keduanya butuh
  model bahasa besar atau suara sintetis.
- Mikrofon laptop yang punya peredam gema bisa membuang suara dari speaker laptop sendiri. Ucapan
  orang di ruangan tetap tertangkap.
- Ketepatan istilah teknis tergantung model pendengar. Whisper small kadang salah mendengar
  ("koevisien"). Penalar membetulkan sebagian besar, apalagi kalau istilahnya ada di daftar
  **Istilah dan nama**; untuk rapat yang sangat teknis, pakai juga Pendengar · Akurat.
- Penalar menambah 1–2,5 detik per kalimat di suara langsung: kalimat yang terdengar muncul dulu,
  terjemahannya menyusul. Tanpa GPU, Penalar jauh lebih lambat; matikan saja di tab Model.
