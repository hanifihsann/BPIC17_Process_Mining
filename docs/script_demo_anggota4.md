# Panduan Operasional & Script Demo Video — Anggota 4 (Exercise 11.22 & Case Explorer)

**Durasi target:** 1,5 – 2 menit  
**Cakupan:** Menjalankan aplikasi lewat `python main.py`, impor dataset sekali, navigasi **Exercise 11.22**, double-click bukti ke **Case Explorer**, pencarian Case ID, `Reset hasil` & `Jalankan ulang`, serta verifikasi unit test.

---

## 1. Persiapan Operasional Sebelum Merekam
1. Pastikan berada di root repository `BPIC17_Process_Mining` dengan `pm4py`, `PySide6`, dan `pandas` terpasang.
2. Pastikan dataset asli `data/BPI Challenge 2017.xes` sudah tersedia di folder `data/`.
3. Jalankan aplikasi desktop utama langsung dari entry point resmi:
   ```powershell
   python main.py
   ```

---

## 2. Langkah Klik Layar & Narasi (1,5 – 2 Menit)

### 0:00 – 0:25 | Pembukaan & Impor Dataset BPIC17 Asli Sekali
- **Aksi Layar:**
  1. Aplikasi `BPIC17 Process Mining` terbuka di menu **Import Dataset**.
  2. Klik tombol **Pilih file XES** -> pilih `data/BPI Challenge 2017.xes` -> tunggu bar status bawah selesai (`BPI Challenge 2017.xes siap digunakan.`).
  3. Tunjukkan *DatasetBar* di bagian atas menampilkan `BPI Challenge 2017.xes` dan `31,509 case / 1,202,267 event`.
- **Narasi:**  
  "Halo, saya Fazl sebagai Anggota 4 untuk proyek Process Mining BPIC17. Kita menjalankan aplikasi utama melalui `main.py`. Pertama, pada menu Import Dataset milik Anggota 1, kita memuat dataset asli BPI Challenge 2017 satu kali ke memori sebanyak 31.509 case dan 1,2 juta lebih event. Dataset aktif ini dibagikan ke seluruh halaman tanpa membaca ulang file XES."

### 0:25 – 0:55 | Menjalankan Analisis Exercise 11.22
- **Aksi Layar:**
  1. Klik menu **Exercise 11.22** pada sidebar kiri.
  2. Tunjukkan aturan filter (*O_Cancelled pada posisi i diikuti O_Accepted pada posisi j dengan i < j*).
  3. Klik tombol **Jalankan Analisis** -> tunjukkan indikator *busy* berjalan non-blocking di status bar bawah -> tunjukkan hasil: **Jumlah case lolos `902`**, **Total active cases `31509`**, **Persentase `2.86%`**, dan tabel **Daftar Case Terpilih**.
- **Narasi:**  
  "Di halaman Exercise 11.22, saat tombol Jalankan Analisis diklik, `analyze_1122` berjalan di background worker sehingga antarmuka tetap responsif. Setiap case diproses satu kali pada level case dengan mempertahankan urutan event asli, termasuk saat ada timestamp yang sama. Dari 31.509 case aktif, ditemukan 902 case atau 2,86 persen yang memiliki `O_Cancelled` kemudian diikuti `O_Accepted`."

### 0:55 – 1:30 | Buka Evidence Lintas Halaman ke Case Explorer & Pencarian
- **Aksi Layar:**
  1. **Klik dua kali** baris pertama (`Application_428409768`) pada tabel hasil Exercise 11.22 (atau pilih baris lalu klik tombol **Buka di Case Explorer**).
  2. Layar otomatis berpindah ke menu **Case Explorer** dan langsung menggulir ke baris evidence kuning (`#19 O_Cancelled`, `#43 O_Accepted`).
  3. Tunjukkan pada tabel **Detail Event Trace**: seluruh **45 event asli** case tersebut tampil berurutan lengkap dengan `Lifecycle` dan `Resource`, serta baris evidence tersorot.
  4. Ketik `Application_1059184025` pada kotak **Cari Case ID**, klik **Cari**, lalu klik **Reset** di Case Explorer.
- **Narasi:**  
  "Dengan klik dua kali pada hasil 11.22, aplikasi otomatis membuka Case Explorer pada `Application_428409768`. Case Explorer menampilkan seluruh 45 event asli dalam case tersebut secara berurutan, bukan hanya event filter, lengkap dengan atribut opsional secara jujur serta sorotan kuning pada pasangan `O_Cancelled` urutan 19 dan `O_Accepted` urutan 43. Kolom pencarian juga memakai index cache untuk membuka case lain secara instan, dan tombol Reset membersihkan pencarian tanpa membaca ulang XES."

### 1:30 – 1:55 | Reset, Re-run, dan Verifikasi Pengujian
- **Aksi Layar:**
  1. Klik menu **Exercise 11.22** di sidebar kiri.
  2. Klik tombol **Reset hasil** -> tabel dan ringkasan bersih, tombol **Jalankan ulang** aktif.
  3. Klik tombol **Jalankan ulang** -> hasil `902` case (`2.86%`) terhitung kembali dari log aktif.
  4. Akhiri dengan menunjukkan terminal yang menjalankan `$env:QT_QPA_PLATFORM="offscreen"; python -m unittest discover -s tests -v` dengan seluruh **67 test lulus (`OK`)**.
- **Narasi:**  
  "Tombol Reset hasil membersihkan tampilan analisis dan tombol Jalankan ulang mengeksekusi ulang perhitungan dari dataset aktif yang sama di memori. Seluruh modul, integrasi `MainWindow`, serta pengujian pada dataset BPIC17 asli telah diverifikasi dan 67 test otomatis lulus. Sekian demo bagian Anggota 4, terima kasih."
