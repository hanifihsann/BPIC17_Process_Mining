# BPIC17 Process Mining

Aplikasi desktop kelompok untuk proyek Data Mining Tahap 1. Python dan PM4Py membaca event log BPI Challenge 2017 dalam format XES. PySide6 menyediakan satu jendela untuk impor, overview, analisis, pemeriksaan bukti event, dan ekspor.

## Menjalankan di Windows

Jalankan perintah berikut dari root repositori menggunakan PowerShell. Lingkungan pengujian menggunakan Python 3.13.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

1. Buka **Import Dataset**, klik **Pilih file XES**, lalu pilih file `.xes`. Ekstrak arsip `.xes.gz` terlebih dahulu.
2. Periksa status validasi dan informasi dataset aktif. **Overview** membuka ringkasan, frekuensi aktivitas, dan daftar durasi case dari panel yang sama.
3. Untuk mengganti dataset, pilih file lagi dari **Import Dataset**. Impor yang berhasil mengganti log aktif dan membersihkan hasil lama. Jika impor gagal, nama dataset aktif dan pesan error menunjukkan bahwa dataset sebelumnya masih dipakai.
4. **Bantuan → About** menampilkan versi Python, PySide6, PM4Py, dan pandas yang sedang digunakan.

## Status fitur dan pembagian kerja

| Menu atau komponen | PIC | Status |
|---|---|---|
| Import Dataset dan Overview | Anggota 1 | Panel asli terhubung ke shell. |
| Exercise 11.7 dan Export Results | Anggota 2 | Placeholder sampai panel analisis dan ekspor CSV siap. |
| Exercise 11.15 & 11.18 | Anggota 3 | Placeholder sampai panel analisis siap. |
| Exercise 11.22 dan Case Explorer | Anggota 4 | Placeholder sampai panel analisis dan trace case siap. |
| Shell, worker, dataset aktif, About, dan komponen bersama | Anggota 5 | Tersedia. Run, Reset, dan Re-run diuji dengan panel fixture. |

Setelah panel PIC terpasang, alurnya adalah menjalankan exercise pada dataset aktif, membuka case ID dari hasil untuk memeriksa urutan event di Case Explorer, lalu memilih **Export Results** untuk menyimpan ringkasan dan daftar case ke CSV.

## Struktur repositori

```text
main.py                         Entry point aplikasi
gui/main_window.py              Navigasi, pemasangan panel, dan koordinasi operasi
gui/app_state.py                Referensi dataset aktif dan hasil per halaman
gui/workers.py                  Worker untuk operasi fitur
gui/styles.py                   Tema Qt untuk shell
gui/widgets/                    DatasetBar, FeedbackBar, DataTable, ResultArea, TaskControls
gui/import_overview_page.py     Panel Import dan Overview Anggota 1
modules/                        Loader, validasi, helper trace, dan overview Anggota 1
tests/                          Unit test Anggota 1 dan pengujian integrasi shell
```

## Memasang panel fitur

`MainWindow.install_page(page_key, panel, controls=None)` menerima `QWidget` milik PIC. Gunakan key `exercise_117`, `exercise_115_118`, `exercise_1122`, `case_explorer`, atau `export`. Panel yang memakai `TaskControls` meneruskan komponen tersebut saat pemasangan. Shell akan menghubungkan Reset dan Re-run serta mengaktifkan tombol sesuai status worker dan dataset.

- Hubungkan sinyal `controls.run_requested` ke handler panel yang memanggil `window.run_task(page_key, deskripsi, operasi)`. `operasi` adalah callable yang menerima `ActiveDataset`. Gunakan `dataset.log` sebagai input fungsi PIC. `dataset.metadata` dan `dataset.overview` juga tersedia. Ketiganya merujuk objek yang sudah dimuat oleh panel impor.
- Ambil pilihan pengguna, case ID, atau tujuan ekspor di thread GUI sebelum memulai worker. Callable worker boleh membaca dataset dan menjalankan modul PIC. Akses widget, dialog, dan `window.state` tetap di thread GUI. Perlakukan log dan metadata bersama sebagai data baca saja.
- Dengarkan `window.state.dataset_changed` untuk memperbarui tampilan saat dataset berganti. Dengarkan `window.state.result_changed` lalu baca `state.has_result(page_key)` dan `state.result(page_key)` untuk merender payload sesuai schema PIC. Sinyal yang sama dipancarkan saat hasil dibersihkan.
- Gunakan `DataTable(headers)` dan `set_rows(rows)` untuk tabel baca saja. Setiap baris berisi satu nilai per kolom. Berikan tabel atau widget lain ke `ResultArea(content)` lalu panggil `show_result()` atau `show_message(text)` untuk menampilkan kondisi yang sesuai.
- Reset menghapus hasil untuk halaman tersebut. Re-run mengulang operasi terakhir dengan parameter yang sama pada dataset aktif. Jika pengguna mengubah parameter, gunakan tombol Run untuk mengambil parameter terbaru. Penggantian dataset membersihkan hasil dan riwayat Re-run.
- `run_task` mengembalikan `True` jika operasi diterima. Saat satu operasi berjalan, shell menahan operasi lain dan menampilkan progress tanpa persentase. Error worker ditampilkan di status bar dan ditulis ke log terminal.

Import dan Overview memakai `dataset_loaded`, `load_started`, `status_changed`, `dataset_validation_failed`, dan `load_failed` dari panel Anggota 1. Shell baru mengizinkan impor berikutnya setelah panel selesai membersihkan thread impor. Menu Overview menggulir panel yang sama ke bagian ringkasan.

## Pengujian

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tes shell memakai Qt offscreen secara default. Fixture XES kecil menguji impor, overview, validasi, file rusak, dan penggantian dataset melalui loader asli. Panel fixture menguji perubahan hasil, worker, pencegahan klik ganda, penanganan error, dan penutupan saat proses berjalan. Hasil exercise dan CSV nyata akan diuji setelah modul PIC bersangkutan tersedia.

Uji native Windows dengan XES publik 4TU menampilkan 31.509 case dan 1.202.267 event. Pada ukuran jendela minimum 780 × 540, Overview dapat digulir. Pengisian tabel durasi pada panel Anggota 1 berjalan di thread GUI dan menimbulkan jeda sekitar 2,8 detik saat impor selesai pada mesin uji.

## Dataset

Gunakan BPI Challenge 2017 versi 1, Boudewijn van Dongen (2017), DOI `10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b`, atau XES yang ditetapkan dosen. Pilih arsip `BPI Challenge 2017.xes.gz` untuk event log pengajuan dan ekstrak file `.xes` sebelum impor. Simpan file dataset di `data/` atau di luar repositori. [Rekaman dataset 4TU](https://data.4tu.nl/articles/_/12696884/1) · [Unduh arsip XES](https://data.4tu.nl/file/34c3f44b-3101-4ea9-8281-e38905c68b8d/f3aec4f7-d52c-4217-82f4-57d719a8298c)
