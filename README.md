# BPIC17 Process Mining

Aplikasi desktop untuk proyek Data Mining Tahap 1. PM4Py membaca event log pengajuan pinjaman BPI Challenge 2017. PySide6 menampilkan validasi, statistik, delapan jawaban latihan, dan bukti event dari dataset aktif.

## Menjalankan di Windows

Dari root repositori, jalankan perintah berikut di PowerShell. Audit menggunakan Python 3.13, PySide6 6.11.3, PM4Py 2.7.23.13, dan pandas 2.3.3. Versi terpasang juga tersedia di **Bantuan → About**.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Gunakan XES yang ditetapkan dosen atau BPI Challenge 2017 versi 1 dari Boudewijn van Dongen (2017), DOI `10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b`. Jika mengunduh arsip, ekstrak `BPI Challenge 2017.xes.gz` ke file `.xes` dan simpan di `data/` atau di luar repo. [Rekaman dataset 4TU](https://data.4tu.nl/articles/_/12696884/1) · [Unduh arsip](https://data.4tu.nl/file/34c3f44b-3101-4ea9-8281-e38905c68b8d/f3aec4f7-d52c-4217-82f4-57d719a8298c)

## Alur penggunaan

1. **Import Dataset** → **Pilih file XES**. Periksa jumlah case/event dan atribut tersedia. Impor yang berhasil mengganti dataset aktif dan mengosongkan hasil lama. Jika impor gagal, status menyebut dataset yang masih aktif.
2. **Overview** menampilkan rentang waktu, jumlah dan frekuensi aktivitas, mean cycle time, serta tabel durasi yang dapat dicari berdasarkan Case ID.
3. Buka **Exercise 11.7**, **Exercise 11.15 & 11.18**, atau **Exercise 11.22**, lalu klik **Jalankan Analisis**. Gunakan Reset untuk menghapus hasil, lalu Jalankan ulang atau Jalankan Analisis untuk menghitung kembali dari dataset yang sama.
4. Pilih baris bukti dan buka **Case Explorer**. Urutan event, timestamp, activity, lifecycle, resource, dan sorotan bukti muncul di trace lengkap. Case ID juga bisa dicari langsung.
5. **Export Results** menyimpan ringkasan semua latihan yang sudah dihitung, atau daftar case dan bukti dari kategori yang dipilih. CSV menggunakan UTF-8 dengan BOM. Ringkasan lengkap berisi delapan baris jawaban setelah ketiga menu Exercise dijalankan.

Lihat [laporan audit, hasil, dan alur demo](docs/test_report.md) serta [matriks pengujian](docs/test_matrix.md).

## Struktur dan kontribusi

| Bagian | Penanggung jawab |
|---|---|
| `modules/data_loader.py`, `modules/overview.py`, `gui/import_overview_page.py` | Anggota 1 · impor, validasi, overview |
| `modules/exercise_117.py`, `modules/export_csv.py`, panel 11.7 dan Export | Anggota 2 · 11.7 A–E dan CSV |
| `modules/exercise_115_118.py`, panel 11.15/11.18 | Anggota 3 · lifecycle complete dan resource yang sama |
| `modules/exercise_1122.py`, `modules/case_explorer.py`, panel 11.22 dan Case Explorer | Anggota 4 · urutan event, trace, dan matriks pengujian |
| `main.py`, `gui/main_window.py`, `gui/app_state.py`, `gui/workers.py`, `gui/widgets/` | Anggota 5 · shell, worker, dataset aktif, integrasi, dan finalisasi |

Panel menerima objek log yang sama melalui `AppState`. Shell menjalankan analisis dan ekspor di worker. Impor dan indeks Case Explorer juga diproses di background. Tabel case berukuran besar menggunakan model Qt untuk menampilkan baris sesuai kebutuhan.

## Pengujian

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m tests.verify_bpic17 ".\data\BPI Challenge 2017.xes"
```

Perintah kedua menjalankan jalur GUI asli pada BPIC17, memeriksa delapan jawaban, membuka evidence, membaca kembali CSV yang diekspor, dan menjalankan analisis ulang. Untuk membuat ulang bukti visual di Qt native Windows, tambahkan `--screenshots docs/screenshots`.
