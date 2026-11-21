# Panduan Operasional & Script Demo Video — Anggota 4 (Exercise 11.22 & Case Explorer)

**Durasi target:** 1,5 – 2 menit  
**Cakupan:** Menjalankan aplikasi lewat `python main.py`, impor dataset sekali, navigasi **Exercise 11.22**, double-click bukti ke **Case Explorer**, pencarian Case ID, `Reset hasil` & `Jalankan ulang`, serta verifikasi unit test.

---

## 1. Persiapan Operasional Sebelum Merekam
1. Pastikan berada di root repository `BPIC17_Process_Mining` dengan `pm4py`, `PySide6`, dan `pandas` terpasang.
2. Siapkan file `.xes`:
   - **Data BPIC17 asli (jika sudah diunduh):** gunakan file `.xes` hasil ekstrak dari arsip resmi `BPI Challenge 2017.xes.gz` (4TU.ResearchData, DOI `10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b`).
   - **Data sintetis (jika file asli belum ada):** siapkan file `.xes` contoh kecil (misal di folder `data/demo_synthetic.xes`, folder `data/` sudah masuk `.gitignore`) yang memiliki minimal 1 case dengan `O_Cancelled` diikuti `O_Accepted` dan 1 case kontrol (`O_Accepted` sebelum `O_Cancelled`).
3. Jalankan aplikasi desktop utama langsung dari entry point resmi:
   ```powershell
   python main.py
   ```

---

## 2. Langkah Klik Layar & Narasi (1,5 – 2 Menit)

### 0:00 – 0:25 | Pembukaan & Impor Dataset Sekali
- **Aksi Layar:**
  1. Aplikasi `BPIC17 Process Mining` terbuka di menu **Import Dataset**.
  2. Klik tombol **Pilih file XES** -> pilih file `.xes` -> tunggu progress di status bar bawah selesai (`... siap digunakan.`).
  3. Tunjukkan *DatasetBar* di bagian atas menampilkan nama file serta total case dan event.
- **Narasi:**  
  "Halo, saya Fazl sebagai Anggota 4 untuk proyek Process Mining BPIC17. Kita menjalankan aplikasi utama melalui `main.py`. Pertama, pada menu Import Dataset milik Anggota 1, kita memuat file XES satu kali ke memori. Dataset aktif ini langsung dibagikan oleh shell utama ke seluruh halaman tanpa membaca ulang file XES dari disk."

### 0:25 – 0:55 | Menjalankan Analisis Exercise 11.22
- **Aksi Layar:**
  1. Klik menu **Exercise 11.22** pada sidebar kiri (halaman asli Anggota 4 langsung tampil menggantikan placeholder).
  2. Tunjukkan aturan filter (*O_Cancelled pada posisi i diikuti O_Accepted pada posisi j dengan i < j*).
  3. Klik tombol **Jalankan Analisis** -> tunjukkan indikator *busy* berjalan non-blocking di status bar bawah -> tunjukkan **Jumlah case lolos**, **Total active cases (denominator)**, **Persentase**, dan tabel **Daftar Case Terpilih**.
- **Narasi:**  
  "Sekarang kita masuk ke halaman Exercise 11.22. Saat tombol Jalankan Analisis diklik, `analyze_1122` berjalan di background worker agar GUI tetap responsif. Setiap case diproses satu kali pada level case dengan mempertahankan urutan event asli, termasuk bila ada timestamp yang sama. Case yang hanya punya `O_Accepted` sebelum `O_Cancelled` tidak dihitung, dan beberapa pasangan dalam satu case tetap dihitung satu case."

### 0:55 – 1:30 | Buka Evidence Lintas Halaman ke Case Explorer & Pencarian
- **Aksi Layar:**
  1. **Klik dua kali** baris case pada tabel hasil Exercise 11.22 (atau pilih baris lalu klik tombol **Buka di Case Explorer**).
  2. Layar otomatis berpindah ke menu **Case Explorer**.
  3. Tunjukkan pada tabel **Detail Event Trace**: **seluruh event asli** tampil berurutan (`No.`, `Timestamp`, `Activity`, `Lifecycle`, `Resource`, `Evidence`), nilai opsional kosong tampil jujur sebagai `-`, dan pasangan `O_Cancelled` serta `O_Accepted` tersorot warna kuning sebagai *evidence*.
  4. Ketik Case ID lain di kotak **Cari Case ID**, klik **Cari**, lalu klik **Reset** di Case Explorer.
- **Narasi:**  
  "Dengan klik dua kali pada hasil 11.22, aplikasi otomatis membuka Case Explorer pada Case ID yang tepat. Berbeda dari ringkasan filter, Case Explorer menampilkan seluruh event asli dalam case tersebut secara berurutan, menampilkan atribut `lifecycle` dan `resource` secara jujur, serta menyorot pasangan evidence `O_Cancelled` dan `O_Accepted`. Kolom pencarian juga memanfaatkan index cache untuk menemukan case lain secara cepat, dan tombol Reset mengembalikan daftar case tanpa membaca ulang file XES."

### 1:30 – 1:55 | Reset, Re-run, dan Verifikasi Pengujian
- **Aksi Layar:**
  1. Klik menu **Exercise 11.22** di sidebar kiri.
  2. Klik tombol **Reset hasil** -> tabel dan ringkasan bersih, tombol **Jalankan ulang** aktif.
  3. Klik tombol **Jalankan ulang** -> hasil langsung terhitung kembali dari dataset aktif yang sama.
  4. Akhiri dengan menunjukkan terminal yang menjalankan `$env:QT_QPA_PLATFORM="offscreen"; python -m unittest discover -s tests -v` dengan seluruh test `OK`.
- **Narasi:**  
  "Tombol Reset hasil membersihkan output analisis dan tombol Jalankan ulang mengeksekusi ulang perhitungan dari dataset aktif di memori. Seluruh modul, integrasi `MainWindow`, serta smoke test offscreen telah lulus pengujian otomatis. Sekian demo bagian Anggota 4, terima kasih."
