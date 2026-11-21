# Dokumentasi Anggota 2 — Exercise 11.7 (A–E), Cycle Time, Ekspor CSV & GUI

## 1. Struktur dan Luaran File Anggota 2

| File | Peran | Komponen Utama |
| --- | --- | --- |
| `modules/exercise_117.py` | Logika analisis Exercise 11.7 (A–E) level case secara dinamis | `analyze_117`, definisi aturan `RULE_117_A` s.d. `RULE_117_E` |
| `modules/export_csv.py` | Utilitas ekspor CSV ringkasan metrik dan daftar case evidence | `export_summary_to_csv`, `export_cases_to_csv` |
| `gui/pages/exercise_117_page.py` | Widget GUI desktop PySide6 untuk analisis Exercise 11.7 | `Exercise117Page`, `Exercise117Worker` |
| `gui/pages/export_page.py` | Widget GUI desktop PySide6 untuk halaman menu "Export Results" | `ExportPage` |
| `gui/pages/__init__.py` | Paket ekspor halaman GUI modular | Mengekspor `Exercise117Page`, `ExportPage` bersama halaman lainnya |
| `tests/test_exercise_117.py` | Unit test komprehensif 11.7 (A–E), ekspor CSV, dan integrasi GUI offscreen | `Exercise117Tests`, `CsvExportTests`, `Exercise117GuiTests` (13 test cases) |
| `docs/examples/contoh_ringkasan_117.csv` | Contoh file CSV hasil ekspor ringkasan jawaban metrik | CSV UTF-8 BOM dengan kolom pertanyaan, aturan, denominator, dsb. |
| `docs/examples/contoh_cases_117.csv` | Contoh file CSV hasil ekspor detail case terpilih dan evidence | CSV detail case ID, durasi hari, timestamp, dan posisi event bukti |
| `docs/test_matrix.md` | Matriks pengujian gabungan (diperbarui) | Mencatat status `PASS` untuk TM-03, TM-04, dan TM-04B |
| `docs/anggota2.md` | Dokumentasi teknis, kontrak API, definisi operasional, dan panduan demo | Dokumen ini |

---

## 2. Kontrak Input–Output Modul Inti

### 2.1 `analyze_117(log_or_df, *, accepted_activity="O_Accepted", refused_activity="O_Refused", cancelled_activity="O_Cancelled")`
- **Input:** Objek aktif di memori berupa `pm4py.objects.log.obj.EventLog` atau `pandas.DataFrame` berformat PM4Py (kolom wajib: `case:concept:name`, `concept:name`, `time:timestamp`). Menggunakan data aktif dari loader Anggota 1 tanpa membaca ulang file XES dan tanpa memutasi objek sumber.
- **Validasi:**
  - `log_or_df is None` $\rightarrow$ `ValueError`
  - Tipe bukan `EventLog` / `DataFrame` $\rightarrow$ `TypeError`
  - Kolom wajib DataFrame hilang $\rightarrow$ `ValueError`
  - Dataset kosong (`EventLog([])` atau DataFrame 0 baris) $\rightarrow$ aman dari `ZeroDivisionError`, mengembalikan `total_cases=0`, `mean_cycle_time_days=0.0`, `count=0`.
- **Output (`dict[str, Any]`):**
  ```python
  {
      "exercise": "11.7",
      "total_cases": int,
      "11.7_a": {
          "subsoal": "11.7 A",
          "question": "Berapa jumlah keseluruhan case?",
          "rule": "Hitung unique case/trace dari keseluruhan log aktif",
          "count": int,
      },
      "11.7_b": {
          "subsoal": "11.7 B",
          "question": "Berapa rata-rata cycle time seluruh case?",
          "rule": "Durasi tiap case = waktu event terakhir − event pertama pada trace asli",
          "count": int,
          "valid_duration_cases": int,
          "mean_cycle_time_days": float,  # dalam satuan hari
      },
      "11.7_c": {
          "subsoal": "11.7 C",
          "question": "Berapa successful cases dan rata-rata cycle time-nya?",
          "rule": "Case memuat setidaknya satu event O_Accepted (contains rule)",
          "target_activity": "O_Accepted",
          "count": int,
          "total_cases": int,
          "percentage": float,
          "mean_cycle_time_days": float,
          "case_ids": list[Any],
          "evidence": list[dict],
      },
      "11.7_d": {
          "subsoal": "11.7 D",
          "question": "Berapa unsuccessful cases dan rata-rata cycle time-nya?",
          "rule": "Case memuat setidaknya satu event O_Refused (contains rule)",
          "target_activity": "O_Refused",
          "count": int,
          "total_cases": int,
          "percentage": float,
          "mean_cycle_time_days": float,
          "case_ids": list[Any],
          "evidence": list[dict],
      },
      "11.7_e": {
          "subsoal": "11.7 E",
          "question": "Berapa canceled cases dan rata-rata cycle time-nya?",
          "rule": "Event TERAKHIR pada trace adalah O_Cancelled (endpoint rule)",
          "target_activity": "O_Cancelled",
          "count": int,
          "total_cases": int,
          "percentage": float,
          "mean_cycle_time_days": float,
          "case_ids": list[Any],
          "evidence": list[dict],
      },
      "cases_summary": list[dict],
  }
  ```

### 2.2 Struktur Evidence Record untuk Case Explorer
Setiap entri pada daftar `evidence` memuat:
```python
{
    "case_id": Any,
    "subsoal": str,                     # Contoh: "11.7 C"
    "activity": str,                    # Contoh: "O_Accepted"
    "evidence_positions": list[int],    # Indeks 0-based kemunculan event bukti
    "label": str,                       # Label penanda pada Case Explorer
    "occurrence_count": int,
    "duration_days": float,
    "trace_length": int,
    "first_timestamp": Timestamp,
    "last_timestamp": Timestamp,
    "evidence_events": list[dict],
}
```
Ketika pengguna menekan tombol **"Buka di Case Explorer"** pada tabel hasil 11.7, sinyal `open_case_requested(case_id, evidence)` dikirim langsung ke `CaseExplorerPage.open_case(case_id, evidence)`. Case Explorer akan membuka case terkait dan menandai/menyorot event pembukti pada trace secara otomatis.

---

## 3. Definisi Operasional & Aturan Analisis

1. **Level Case (bukan Event):**
   - Agregasi dihitung pada level case unik. Satu case hanya dihitung **1 kali** pada kelompok hasil meskipun aktivitas pemicunya (`O_Accepted` / `O_Refused`) muncul berkali-kali dalam satu trace.
2. **Perhitungan Cycle Time pada Trace Asli:**
   - Durasi case dihitung sebagai selisih waktu antara event terakhir dan event pertama pada trace asli:
     $$\text{duration\_days} = \frac{\text{timestamp}_{\text{terakhir}} - \text{timestamp}_{\text{pertama}}}{86400 \text{ detik}}$$
   - Event tidak difilter/dihapus sebelum menghitung durasi, sehingga cycle time merepresentasikan durasi proses nyata dari awal hingga akhir case.
3. **Contains vs Endpoint Rule:**
   - **11.7 C & 11.7 D (Contains):** Memeriksa apakah case memuat setidaknya satu kemunculan aktivitas target di posisi manapun dalam trace.
   - **Bukan Kelompok Saling Eksklusif:** Case yang memiliki `O_Accepted` dan `O_Refused` lolos di kedua kategori (11.7 C dan 11.7 D).
   - **11.7 E (Endpoint):** Memeriksa apakah event **terakhir** (`events[-1]`) adalah `O_Cancelled`. Jika `O_Cancelled` muncul di awal atau di tengah dan diikuti oleh event lain sesudahnya, case **tidak lolos** 11.7 E.

---

## 4. Verifikasi dan Pengujian Unit

Seluruh skenario pengujian telah diuji dan lulus 100%:

```powershell
.\.venv\Scripts\python.exe -m unittest tests/test_exercise_117.py -v
```

Hasil eksekusi:
- `test_117_a_total_cases`: Menghitung total case unik secara presisi.
- `test_117_b_cycle_time_calculation`: Rata-rata cycle time seluruh case dalam satuan hari.
- `test_117_c_successful_cases_and_duplicate_accepted`: Case dengan multiple `O_Accepted` dihitung tepat 1 kali.
- `test_117_d_unsuccessful_cases`: Case dengan multiple `O_Refused` dihitung tepat 1 kali.
- `test_overlap_c_and_d_not_mutually_exclusive`: Memastikan case dengan Accepted dan Refused masuk ke kedua subsoal.
- `test_117_e_endpoint_rule`: Memastikan hanya case dengan `O_Cancelled` di akhir yang lolos; yang di tengah ditolak.
- `test_empty_dataframe` & `test_empty_event_log`: Kebal dari `ZeroDivisionError` pada dataset kosong.
- `test_eventlog_and_dataframe_equivalence`: Hasil identik antara input `EventLog` dan `DataFrame`.
- `test_validation_errors`: Validasi input `None`, string, atau kolom hilang.
- `test_export_summary_and_cases_csv`: Memverifikasi integritas file CSV hasil ekspor.
- `test_exercise_117_page_and_case_explorer_flow`: Uji alur antarmuka GUI PySide6 offscreen dan navigasi bukti event ke Case Explorer.
- `test_export_page_integration`: Uji widget ekspor hasil CSV saat hasil analisis tersedia.
