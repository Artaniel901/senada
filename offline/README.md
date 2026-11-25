# Cicada Offline

Penerjemah teks dan suara langsung yang berjalan sepenuhnya di komputer Windows. Dibangun di atas
[Cicada](https://github.com/wquguru/cicada) (Apache-2.0). Tombol dan kontrolnya memakai
[Sakuga VFX](https://github.com/finktheartist/sakuga-vfx) (MIT).

Cicada versi Windows mengirim suara ke layanan AI di internet dan butuh key. Cicada Offline
mengganti mesin itu dengan model yang jalan di komputer ini. Internet hanya dipakai sekali untuk
mengunduh model.

## Yang bisa dilakukan

- **Penalar** (baru di 0.2.0): model bahasa lokal (Gemma 4 lewat llama.cpp) yang menerjemahkan
  *maksud*, bukan kata per kata. Idiom, bahasa gaul dan kalimat yang belum selesai jadi kalimat yang
  wajar dan benar tata bahasanya. Ia membaca kalimat-kalimat sebelumnya, topik dan daftar istilah Anda,
  jadi kata yang salah dengar ("Coevisien", "fluk semasa") dibetulkan jadi "Koefisien" dan "fluks massa".
  Kalau maknanya tidak sama dengan kata-katanya (idiom, sindiran, basa-basi), ada catatan pendek.
  Untuk kalimat yang sangat aneh, nyalakan **Pikir lebih dalam** di tab Teks (sekitar 10–30 detik).

- **Teks**: ketik atau tempel teks, lalu terjemahkan antar 73 bahasa. Indonesia, Korea dan Inggris
  ada di depan. Bahasa sumber dideteksi otomatis. Bisa menerjemahkan sambil mengetik, dan
  terjemahan terbaru disimpan di riwayat. Ada juga bahasa daerah: Jawa, Sunda, Minang, Bali,
  Banjar, Bugis dan Aceh (khusus teks).
- **Suara langsung**: mendengarkan suara komputer (rapat, video, siaran) atau mikrofon. Setiap
  kalimat ditulis beserta terjemahannya, dan bahasanya dideteksi per kalimat, jadi rapat
  campuran Korea–Indonesia–Inggris tetap terbaca benar.
- **Subtitle melayang**: bilah subtitle yang selalu di atas jendela lain. Bisa diseret dan
  ukuran hurufnya bisa diatur.
- **Berkas rekaman**: menerjemahkan audio atau video (mp3, m4a, wav, mp4, mkv, …).
- **Rekaman**: setiap sesi tersimpan dalam format rekaman Cicada. Bisa disimpan sebagai teks
  dua bahasa, subtitle `.srt`, atau tabel Markdown.

## Pasang dan buka

1. Butuh Windows 10/11 x64 dan Python 3.12.
2. Jalankan `setup.cmd` sekali. Lingkungan Python dibuat di `.venv` di folder ini, tidak di C:.
3. Buka `Cicada Offline.cmd`.
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

Dengan Penalar menyala, NLLB pindah ke CPU dan hanya dipakai untuk bahasa daerah (Minang, Bali,
Banjar, Bugis, Aceh) dan sebagai cadangan kalau Penalar gagal. Di GPU 6 GB, Whisper dan Gemma 4 E4B
bersama memakai sekitar 5,4 GB.

NLLB-200 dari Meta berlisensi **non-komersial** (CC-BY-NC-4.0). Aplikasi ini boleh dipakai sendiri,
tapi tidak untuk dijual.

## Bagaimana ia memakai Cicada

Dari `linux/cicada/core` (mesin Cicada versi Linux yang hanya memakai pustaka standar Python),
bagian-bagian ini dipakai apa adanya:

- `segmenter.py`: memotong suara menjadi kalimat. Angkanya sama di semua platform Cicada.
- `roommic.VoiceGate`: mempelajari tingkat bising ruangan untuk mikrofon.
- `models.py` dan `session_store.py`: format rekaman. Rekaman Cicada Offline bisa dibaca Cicada.
  Kata yang dibetulkan Penalar disimpan di kolom `fixes` milik Cicada; teks yang terdengar tetap utuh.
- `audio.Wav`: membaca berkas WAV.

Yang baru ada di `cicada_offline/`:

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
- `CICADA_OFFLINE_HOME` memindahkan folder `data/`, misalnya untuk uji.
- `CICADA_OFFLINE_MODELS` memindahkan folder `models/`.
- `CICADA_OFFLINE_DEBUG=1` membuka DevTools.
- `tools/try_live.py --penalar --topic "..." --words "..." id rekaman.wav` mencoba Penalar tanpa jendela.
- `CICADA_OFFLINE_DRIVE=<berkas.js>` menjalankan skrip di halaman setelah dimulai. Ini hanya untuk
  uji antarmuka.

Komponen Sakuga ada di `ui/vendor/sakuga/` dan tidak diubah. Gayanya hanya diatur lewat variabel
`--sk-*` (lihat `SOURCE.txt`).

## Batasan

- Hanya untuk Windows. Penangkap suara memakai WASAPI dan peluncurnya berupa `.cmd`.
- Catatan rapat otomatis dan juru bahasa suara dari Cicada tidak ada di sini, karena keduanya butuh
  model bahasa besar atau suara sintetis.
- Mikrofon laptop yang punya peredam gema bisa membuang suara dari speaker laptop sendiri. Ucapan
  orang di ruangan tetap tertangkap.
- Ketepatan istilah teknis tergantung model pendengar. Whisper small kadang salah mendengar
  ("koevisien"). Penalar membetulkan sebagian besar, apalagi kalau istilahnya ada di daftar
  **Istilah dan nama**; untuk rapat yang sangat teknis, pakai juga Pendengar · Akurat.
- Penalar menambah 1–2,5 detik per kalimat di suara langsung: kalimat yang terdengar muncul dulu,
  terjemahannya menyusul. Tanpa GPU, Penalar jauh lebih lambat; matikan saja di tab Model.
