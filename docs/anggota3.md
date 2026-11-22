# Hasta Putra — Exercise 11.15 & 11.18

## Aturan analisis

Aktivitas target adalah `W_Assess Potential Fraud`. Kedua latihan hanya menghitung event dengan `lifecycle:transition` bernilai `complete` (pencocokan mengabaikan kapitalisasi dan spasi di awal/akhir nilai).

- **11.15:** satu case memenuhi syarat jika memiliki minimal dua event target berstatus complete. Case dihitung sekali, sedangkan jumlah dan posisi semua event complete ditampilkan sebagai bukti.
- **11.18:** event complete dikelompokkan menurut `org:resource` di dalam case. Case memenuhi syarat jika ada resource teridentifikasi yang melakukan minimal dua occurrence. `None`, nilai null pandas, string kosong, dan string whitespace diabaikan sebagai resource; event tersebut masih dapat dihitung di 11.15.
- Jika lebih dari satu resource memenuhi syarat pada case yang sama, hasil 11.18 menampilkan satu baris evidence per resource, tetapi jumlah case tetap satu.
- Evidence mencatat Case ID, posisi 0-based, urutan 1-based, activity, lifecycle, resource, dan timestamp. Tidak ada event pada log sumber yang diubah.

## Kontrak modul

```python
from modules.exercise_115_118 import analyze_115_118

results = analyze_115_118(active_log)
results["11.15"]["count"]
results["11.15"]["evidence"]
results["11.18"]["count"]
results["11.18"]["evidence"]
```

Fungsi menerima PM4Py `EventLog` atau DataFrame PM4Py. Untuk DataFrame non-kosong, kolom wajibnya `case:concept:name`, `concept:name`, dan `time:timestamp`; kolom lifecycle/resource boleh tidak tersedia. Jika lifecycle tidak tersedia, tidak ada event yang dapat dibuktikan sebagai complete dan hasil kedua latihan bernilai nol. Jika resource tidak tersedia, 11.15 tetap dihitung sedangkan 11.18 bernilai nol.

Output per latihan memuat `count` sebagai jumlah case unik, `total_cases`, `case_ids`, aturan, serta `evidence`. Untuk 11.18, `evidence_group_count` menunjukkan jumlah pasangan case-resource yang memenuhi syarat; angka ini dapat lebih besar daripada `count`.

## Halaman aplikasi

Menu **Exercise 11.15 & 11.18** memakai worker bersama `MainWindow`, menampilkan ringkasan dan tabel evidence masing-masing latihan, serta menyediakan Reset dan Jalankan ulang. Pilih atau klik dua kali baris evidence untuk membuka seluruh trace di Case Explorer; event pembukti ditandai sesuai posisi dalam trace.

## Skenario tes

Fixture mencakup dua complete oleh resource sama; dua complete oleh resource berbeda; dua event target non-complete; hanya satu complete; resource kosong/null; dan dua resource berbeda yang masing-masing memenuhi syarat dalam satu case. Tes juga membandingkan hasil EventLog dengan DataFrame, menjaga posisi event per case, serta menguji alur halaman dan highlight evidence di Case Explorer.

Verifikasi terakhir pada Python 3.13 dengan dependency dari `requirements.txt`: 7 tes khusus fitur dan seluruh 74 tes proyek lulus. Pemeriksaan XML `BPI Challenge 2017.xes` (31.509 trace, 1.202.267 event) menemukan nama aktivitas `W_Assess potential fraud` dan 282 event complete. Dengan pencocokan nama aktivitas yang tidak peka kapitalisasi: 13 case memenuhi 11.15 dan 3 case memenuhi 11.18 (3 pasangan case-resource).

Jalankan tes terarah dengan:

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_exercise_115_118.py" -v
```

## Naskah demo video (±1 menit 45 detik)

**0:00–0:20 — Aturan**  
“Pada Exercise 11.15 dan 11.18, aktivitas yang diperiksa adalah `W_Assess Potential Fraud`. Saya hanya menghitung event dengan lifecycle `complete`; event schedule atau start tidak masuk hitungan.”

**0:20–0:50 — Exercise 11.15**  
“Saya jalankan analisis dari dataset aktif. Hasil menampilkan jumlah case yang memiliki minimal dua penyelesaian, Case ID, jumlah pengulangan, dan posisi serta detail event buktinya.”

**0:50–1:20 — Exercise 11.18**  
“Exercise 11.18 menambahkan syarat bahwa dua atau lebih penyelesaian dilakukan oleh resource yang sama. Karena itu case dengan dua complete dari resource berbeda dapat lolos 11.15 tetapi tidak 11.18. Resource kosong juga tidak dianggap sebagai resource bersama.”

**1:20–1:45 — Bukti case**  
“Saya buka satu baris bukti di Case Explorer. Trace lengkap ditampilkan, dan event complete yang dipakai untuk hasil ditandai. Jumlah case dihitung unik, termasuk ketika beberapa resource dalam case yang sama memenuhi aturan 11.18.”
