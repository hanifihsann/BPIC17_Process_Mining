# Script Demo Video — Anggota 4 (Exercise 11.22 & Case Explorer)

**Durasi target:** 1,5 – 2 menit  
**Cakupan:** Alur analisis Exercise 11.22 (`O_Cancelled` diikuti `O_Accepted` dengan `i < j`), inspeksi Case Explorer lintas halaman, reset/re-run tanpa membaca ulang XES, dan ringkasan hasil unit test.

---

## Persiapan Sebelum Rekaman
1. Pastikan branch aktif adalah `feature/fazl-exercise1122`.
2. Pastikan `pm4py` dan `PySide6` terpasang pada environment Python aktif.
3. Siapkan main window Anggota 5 (saat sudah terintegrasi) **atau** jalankan harness demo sementara dengan fixture sintetis sesuai panduan di `docs/anggota4.md` (tanpa membuat main window produksi terpisah).

---

## Naskah Narasi & Langkah Layar

### 0:00 – 0:20 | Pembukaan & Konteks Data Aktif
- **Layar:** Tampilkan halaman Import/Overview (Anggota 1) dengan dataset sudah dimuat ke memori (`active_log`), lalu pindah ke tab/halaman **Exercise 11.22**.
- **Narasi:**  
  "Halo, saya Fazl sebagai Anggota 4 yang bertanggung jawab atas Exercise 11.22, Case Explorer, pengujian terpadu, dan dokumentasi. Pada tahap ini, dataset BPIC17/fixture sudah dimuat satu kali oleh modul Anggota 1, dan halaman Exercise 11.22 langsung menggunakan objek `EventLog` aktif di memori tanpa membaca ulang file XES."

### 0:20 – 0:50 | Menjalankan Analisis Exercise 11.22
- **Layar:** Tunjukkan panel aturan filter (`O_Cancelled` di posisi `i` diikuti `O_Accepted` di posisi `j` dengan `i < j`), klik tombol **Jalankan Analisis**. Tunjukkan indikator status `loading` singkat (non-blocking `QThread`) lalu hasil ringkasan: *Jumlah case lolos*, *Total active cases (denominator)*, *Persentase*, dan tabel daftar case terpilih.
- **Narasi:**  
  "Saat tombol Jalankan Analisis ditekan, fungsi `analyze_1122` berjalan di background thread agar GUI tetap responsif. Setiap case diproses satu kali pada level case dengan mempertahankan urutan event asli, termasuk bila terdapat timestamp yang sama. Case yang hanya memiliki `O_Accepted` sebelum `O_Cancelled` tidak dihitung, dan case dengan beberapa pasangan valid tetap dihitung sebagai satu case."

### 0:50 – 1:25 | Lintas Halaman ke Case Explorer & Highlight Evidence
- **Layar:** Klik dua kali salah satu baris hasil pada tabel Exercise 11.22 (atau klik **Buka di Case Explorer**). Layar berpindah ke halaman **Case Explorer** dan langsung menampilkan case tersebut. Tunjukkan daftar event berurutan lengkap (termasuk event di antara/sebelum/sesudah), kolom `Lifecycle` dan `Resource` (nilai kosong tampil jujur sebagai `-`), serta baris `O_Cancelled` dan `O_Accepted` yang tersorot sebagai *evidence*. Coba juga mengetik Case ID lain pada kotak pencarian lalu klik **Cari**.
- **Narasi:**  
  "Dengan mengklik dua kali baris hasil, sinyal integrasi langsung membuka case terkait di Case Explorer. Berbeda dari ringkasan filter, Case Explorer menampilkan seluruh event asli dalam case tersebut secara berurutan, lengkap dengan atribut opsional `lifecycle` dan `resource` secara jujur, serta menyorot pasangan evidence `O_Cancelled` dan `O_Accepted`. Fitur pencarian dan indeks case juga tersedia agar modul latihan anggota lain seperti 11.7, 11.15, dan 11.18 dapat memanggil komponen yang sama."

### 1:25 – 1:50 | Reset, Re-run, dan Verifikasi Unit Test
- **Layar:** Klik **Reset** di Case Explorer dan **Reset Hasil** di Exercise 11.22, lalu klik **Jalankan Analisis** kembali untuk menunjukkan re-run instan tanpa memuat ulang XES. Akhiri dengan menampilkan terminal yang menjalankan `python -m unittest discover -s tests -v`.
- **Narasi:**  
  "Tombol Reset membersihkan tampilan dan memungkinkan analisis dijalankan ulang tanpa memuat ulang dataset dari disk. Seluruh logika 11.22, Case Explorer, kesetaraan EventLog dan DataFrame, serta smoke test widget PySide6 telah diverifikasi menggunakan `unittest`. Sekian demo bagian Anggota 4, terima kasih."
