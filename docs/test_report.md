# Laporan Tahap 1 dan Audit Akhir BPIC17

Audit dimulai dari `main` pada `a07ab35`. Pengujian menggunakan BPI Challenge 2017 versi 1 dari 4TU, Python 3.13, PySide6 6.11.3, PM4Py 2.7.23.13, dan pandas 2.3.3. PM4Py memuat **31.509 case** dan **1.202.267 event**. Pembacaan XML streaming langsung dari arsip mengonfirmasi hasil secara independen. [Sumber dataset](https://data.4tu.nl/articles/_/12696884/1)

## Hasil berdasarkan log aktif

| Soal | Fungsi | Aturan | Hasil BPIC17 | Referensi materi |
|---|---|---|---|---|
| 11.7 A | `analyze_117` | Hitung case unik pada log aktif | 31.509 case | 31.509 case |
| 11.7 B | `analyze_117` | Rata-rata durasi dari event terakhir dikurangi event pertama pada trace asli | 21,899606 hari | 21,9 hari |
| 11.7 C | `analyze_117` | Trace memuat `O_Accepted` | 17.228 case · 18,134257 hari | 17.228 case · 18,1 hari |
| 11.7 D | `analyze_117` | Trace memuat `O_Refused` | 3.720 case · 16,877526 hari | 3.720 case · 16,8 hari |
| 11.7 E | `analyze_117` | Event terakhir pada trace adalah `O_Cancelled` | 4.436 case · 23,510446 hari | 4.436 case · 23 hari |
| 11.15 | `analyze_115_118` | Minimal dua event fraud dengan lifecycle `complete` pada satu case | 13 case | 13 di Celonis · 20 di Disco |
| 11.18 | `analyze_115_118` | Minimal dua event fraud `complete` oleh resource teridentifikasi yang sama | 3 case · 3 pasangan case-resource | 3 di Celonis · 8 di Disco |
| 11.22 | `analyze_1122` | `O_Cancelled` muncul sebelum `O_Accepted` dalam trace yang sama | 902 / 31.509 case · 2,862674% | Materi tidak mencantumkan angka |

Urutan event mengikuti trace asli, termasuk saat timestamp sama. Durasi memakai selisih timestamp lengkap dalam hari. Case C dan D dapat beririsan. Persentase 11.22 dibagi semua case log aktif, termasuk case yang tidak memiliki event target.

Mean 11.7 D dan E masing-masing sekitar 0,0775 dan 0,5104 hari di atas angka pada slide. Hitung ulang langsung dari timestamp pertama/terakhir XES menghasilkan angka yang sama dengan GUI dan jumlah case yang sama dengan slide. Materi ringkas tidak menjelaskan pengaturan perhitungan durasi yang menghasilkan selisih tersebut.

Untuk Exercise 11.15 dan 11.18, file memuat label `W_Assess potential fraud`. Pencocokan activity dan lifecycle mengabaikan kapitalisasi. Menghitung hanya `complete` menghindari pengulangan schedule, start, atau abort yang menjelaskan hasil 11.15 pada eksperimen Disco. Pada 11.18, resource kosong tidak memenuhi syarat, dan beberapa pasangan case-resource tetap dihitung sebagai satu case pada agregat.

## Bukti trace

Posisi berikut menggunakan nomor urut 1-based seperti di Case Explorer. CSV menyimpan posisi 0-based dan memberi label pada kolomnya.

| Soal | Case ID | Event yang diperiksa | Bukti visual |
|---|---|---|---|
| 11.7 C | `Application_652823628` | `O_Accepted` pada #38 dari 40 event | [Trace](screenshots/evidence_117c.png) |
| 11.15 | `Application_612471425` | Dua event fraud `complete` pada #29 dan #47 dari 47 event | [#29](screenshots/evidence_115.png) · [#47](screenshots/evidence_115_lanjutan.png) |
| 11.18 | `Application_1221917431` | Dua event fraud `complete` oleh `User_144` pada #60 dan #74 dari 110 event | [#60](screenshots/evidence_118.png) · [#74](screenshots/evidence_118_lanjutan.png) |
| 11.22 | `Application_428409768` | `O_Cancelled` pada #19 dan `O_Accepted` pada #43 dari 45 event | [#19](screenshots/evidence_1122.png) · [#43](screenshots/evidence_1122_lanjutan.png) |

## Verifikasi akhir

| Area | Hasil pemeriksaan |
|---|---|
| F01–F02 · Impor dan overview | File BPIC17 asli dimuat di GUI. Jumlah case/event sesuai XML. Fixture berisi file rusak, atribut hilang, serta Case ID kosong dan duplikat ditolak. |
| F03–F06 · Exercise | Delapan jawaban cocok dengan perhitungan independen XML. Reset dan jalankan ulang menghasilkan payload yang sama tanpa impor ulang. |
| F07 · Case Explorer dan ekspor | Trace lengkap dan posisi evidence diverifikasi lewat panel. CSV ringkasan berisi delapan baris beserta aturan dan denominator. CSV evidence memuat 25.384 baris kategori 11.7 C/D/E, 13 baris 11.15, 3 baris 11.18, dan 902 baris 11.22. |
| Operasi dan state GUI | Klik ganda run tidak memulai operasi duplikat. Impor baru yang valid menghapus hasil dan menonaktifkan ekspor sampai analisis berikutnya. Error impor dan kegagalan worker dapat ditangani. |
| Pengujian otomatis | 76 tes lulus. `pip check` memastikan dependensi terpasang konsisten. PM4Py masih dapat mengeluarkan peringatan parser ketika menerima XML rusak; GUI melaporkan kegagalan impor. |

Perbaikan final mencakup pemakaian worker bersama untuk 11.7 dan ekspor, pemindahan hasil impor dan indeks ke thread GUI setelah worker selesai, dan tabel berbasis model untuk Overview serta daftar Case Explorer. Analisis 11.7 dan 11.22 memproses satu trace EventLog per giliran agar tidak menggandakan seluruh kumpulan event. Ekspor mengganti file tujuan setelah CSV selesai ditulis.

## Screenshot menu

[Import](screenshots/01_import.png) · [Overview](screenshots/02_overview.png) · [11.7 A–E](screenshots/03_exercise_117.png) · [11.15](screenshots/04_exercise_115.png) · [11.18](screenshots/05_exercise_118.png) · [11.22](screenshots/06_exercise_1122.png) · [Case Explorer](screenshots/07_case_explorer.png) · [Export Results](screenshots/08_export.png) · [About](screenshots/09_about.png)

## Alur demo langsung

1. Jalankan `main.py`, pilih BPIC17 di **Import Dataset**, dan buka **Overview** untuk menunjukkan validasi serta jumlah case/event.
2. Jalankan 11.7 dan jelaskan perbedaan *contains* pada C/D dengan *endpoint* pada E. Jalankan 11.15/11.18 dan 11.22.
3. Buka case dari tabel hasil. Pada 11.18, tunjukkan dua event complete oleh resource yang sama. Pada 11.22, tunjukkan posisi cancelled dan accepted yang terpisah.
4. Buka **Export Results**, simpan ringkasan, lalu pilih satu kategori evidence dan simpan CSV daftar case. Buka kedua CSV untuk memperlihatkan aturan, denominator, case ID, dan posisi bukti.
5. Reset satu hasil, jalankan ulang, dan cocokkan hitungannya dengan ringkasan sebelumnya.

Pembagian kontribusi kelima anggota dan perintah untuk mengulang pengujian tersedia di [README](../README.md).
