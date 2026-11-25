# Cicada Offline

Penerjemah teks dan suara langsung yang berjalan sepenuhnya di komputer Windows. Dibangun di atas
[Cicada](https://github.com/wquguru/cicada) (Apache-2.0). Tombol dan kontrolnya memakai
[Sakuga VFX](https://github.com/finktheartist/sakuga-vfx) (MIT).

Cicada versi Windows mengirim suara ke layanan AI di internet dan butuh key. Cicada Offline
mengganti mesin itu dengan model yang jalan di komputer ini. Internet hanya dipakai sekali untuk
mengunduh model.

## Yang bisa dilakukan

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

Model, pengaturan, riwayat dan rekaman tersimpan di folder ini: `models/` dan `data/`.

## Model

| Peran | Model | Ukuran | Lisensi |
|---|---|---|---|
| Penerjemah · Kualitas (bawaan) | NLLB-200 distilled 1.3B, CTranslate2 int8 | 1,4 GB | CC-BY-NC-4.0 |
| Penerjemah · Cepat | NLLB-200 distilled 600M | 630 MB | CC-BY-NC-4.0 |
| Pendengar · Seimbang (bawaan) | Whisper small | 490 MB | MIT |
| Pendengar · Ringan | Whisper base | 150 MB | MIT |
| Pendengar · Akurat | Whisper large-v3 turbo | 1,6 GB | MIT |

NLLB-200 dari Meta berlisensi **non-komersial** (CC-BY-NC-4.0). Aplikasi ini boleh dipakai sendiri,
tapi tidak untuk dijual.

## Bagaimana ia memakai Cicada

Dari `linux/cicada/core` (mesin Cicada versi Linux yang hanya memakai pustaka standar Python),
bagian-bagian ini dipakai apa adanya:

- `segmenter.py`: memotong suara menjadi kalimat. Angkanya sama di semua platform Cicada.
- `roommic.VoiceGate`: mempelajari tingkat bising ruangan untuk mikrofon.
- `models.py` dan `session_store.py`: format rekaman. Rekaman Cicada Offline bisa dibaca Cicada.
- `audio.Wav`: membaca berkas WAV.

Yang baru ada di `cicada_offline/`:

- `asr.py`: Whisper lewat faster-whisper.
- `translate.py`: NLLB lewat CTranslate2.
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
  ("koevisien"); untuk istilah teknis, pakai Pendengar · Akurat.
