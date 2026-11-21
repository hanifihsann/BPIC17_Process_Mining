# Dokumentasi Anggota 4 — Exercise 11.22, Case Explorer, Pengujian & Integrasi

## 1. Struktur dan Fungsi File Anggota 4

| File | Peran | Komponen Utama |
| --- | --- | --- |
| `modules/exercise_1122.py` | Logika analisis Exercise 11.22 pada level case | `analyze_1122`, `RULE_DESCRIPTION` |
| `modules/case_explorer.py` | Inspeksi trace case lengkap, pencarian, indexing cache, dan penanda evidence | `get_case_trace`, `get_case_detail`, `list_cases`, `search_cases`, `build_case_index`, `CaseIndex`, `clear_case_index_cache` |
| `gui/pages/__init__.py` | Paket halaman reusable GUI desktop | Ekspor `Exercise1122Page`, `CaseExplorerPage` |
| `gui/pages/exercise_1122_page.py` | Widget `QWidget` halaman Exercise 11.22 (non-blocking `QThread`) | `Exercise1122Page`, `Exercise1122Worker` |
| `gui/pages/case_explorer_page.py` | Widget `QWidget` halaman Case Explorer (non-blocking indexing `QThread`) | `CaseExplorerPage`, `CaseIndexWorker` |
| `tests/test_exercise_1122.py` | Unit test Exercise 11.22 untuk `EventLog` & `DataFrame` | `Exercise1122Tests` |
| `tests/test_case_explorer.py` | Unit test Case Explorer + smoke test widget GUI offscreen | `CaseExplorerTests`, `GuiWidgetsOffscreenSmokeTests` |
| `docs/test_matrix.md` | Matriks uji gabungan lintas fitur (11.7, 11.15, 11.18, 11.22, integrasi) | Tabel skenario, expected/actual, status |
| `docs/anggota4.md` | Dokumentasi teknis, kontrak API, panduan integrasi & demo | Dokumen ini |
| `docs/script_demo_anggota4.md` | Naskah narasi dan langkah layar video demo (1,5–2 menit) | Panduan demo |

---

## 2. Kontrak Input–Output Modul Inti

### 2.1 `analyze_1122(log_or_df, *, cancelled_activity="O_Cancelled", accepted_activity="O_Accepted")`
- **Input:** Objek aktif di memori berupa `pm4py.objects.log.obj.EventLog` atau `pandas.DataFrame` berformat PM4Py (kolom wajib: `case:concept:name`, `concept:name`, `time:timestamp`). Tidak membaca ulang file XES dan tidak memutasi objek sumber.
- **Validasi:**
  - `log_or_df is None` -> `ValueError`
  - Tipe bukan `EventLog`/`DataFrame` -> `TypeError`
  - Atribut/kolom wajib kosong atau hilang pada dataset non-kosong -> `ValueError`
  - Dataset kosong (`EventLog([])` atau `DataFrame` 0 baris) -> aman, mengembalikan `count=0`, `total_cases=0`, `percentage=0.0`.
- **Output (`dict[str, Any]`):**
  ```python
  {
      "exercise": "11.22",
      "rule": "O_Cancelled pada posisi i diikuti O_Accepted pada posisi j dengan i < j (analisis level case, urutan event asli dipertahankan)",
      "cancelled_activity": "O_Cancelled",
      "accepted_activity": "O_Accepted",
      "count": int,          # jumlah case unik yang lolos
      "total_cases": int,    # total active cases (denominator)
      "percentage": float,   # (count / total_cases * 100.0) atau 0.0 jika total_cases == 0
      "case_ids": list[Any], # daftar Case ID yang lolos
      "evidence": [          # satu entri per case lolos
          {
              "case_id": Any,
              "cancelled_index": int,       # posisi 0-based i
              "accepted_index": int,        # posisi 0-based j (i < j)
              "cancelled_seq": int,         # urutan 1-based (i + 1)
              "accepted_seq": int,          # urutan 1-based (j + 1)
              "cancelled_activity": str,
              "accepted_activity": str,
              "cancelled_timestamp": Any,
              "accepted_timestamp": Any,
              "cancelled_event": dict,
              "accepted_event": dict,
              "evidence_positions": [int, int],
              "trace_length": int,
          }
      ],
  }
  ```

### 2.2 `get_case_trace(log_or_df, case_id, *, evidence=None, highlight_positions=None, index=None)`
- **Input:** `log_or_df` (`EventLog` / `DataFrame` PM4Py), `case_id`, dan penanda evidence opsional (`evidence` dict hasil 11.22, dict `{posisi: label}` untuk latihan 11.7/11.15/11.18, atau iterable posisi `highlight_positions`).
- **Output (`list[dict[str, Any]]`):** Seluruh event asli dari case secara berurutan (mengembalikan `[]` jika `case_id` tidak ditemukan). Setiap elemen berisi:
  ```python
  {
      "seq": int,                 # nomor urut 1-based
      "position": int,            # indeks 0-based
      "case_id": Any,
      "timestamp": Any,
      "activity": Any,
      "lifecycle": Any | None,    # None jika tidak tersedia (tidak dibuat-buat)
      "resource": Any | None,     # None jika tidak tersedia (tidak dibuat-buat)
      "is_evidence": bool,
      "evidence_role": str | None,
  }
  ```
- **Fungsi Pendukung Case Explorer:**
  - `build_case_index(log_or_df)` / `get_or_build_case_index(log_or_df)`: membangun indeks lookup cepat `O(1)` per case dengan weakref-managed cache dan pengecekan signature agar tidak melakukan full scan berulang kali.
  - `list_cases(log_or_df, *, index=None)` & `search_cases(log_or_df, query="", *, index=None)`: daftar dan pencarian Case ID substring (case-insensitive).
  - `get_case_detail(log_or_df, case_id, *, evidence=None, highlight_positions=None, index=None)`: ringkasan case + trace lengkap dalam satu dictionary.

---

## 3. Aturan Filter `i < j` dan Perhitungan Persentase

1. **Level Case (bukan Offer ID):** Setiap trace/case dievaluasi satu kali berdasarkan urutan event aslinya. Atribut Offer ID tidak memecah case.
2. **Urutan Event Asli & Stabil:** Event tidak diurutkan ulang berdasarkan timestamp; jika terdapat timestamp identik, urutan asli trace tetap dipertahankan.
3. **Kondisi `i < j`:**
   - Dicari kemunculan pertama `O_Cancelled` pada indeks `i`.
   - Kemudian dicari `O_Accepted` pada indeks `j` dengan `i < j`. Aktivitas lain di antara `i` dan `j` diperbolehkan (tidak harus bersebelahan).
   - Jika `O_Accepted` hanya muncul sebelum `O_Cancelled` tanpa ada `O_Accepted` setelahnya, case **tidak lolos**.
   - Jika terdapat beberapa pasangan `(i, j)` valid dalam satu case, case tetap dihitung **1 kali** (`count` menghitung case, bukan jumlah pasangan event).
4. **Persentase:**
   - `percentage = (count / total_cases) * 100.0` saat `total_cases > 0`.
   - `percentage = 0.0` saat `total_cases == 0` (aman dari `ZeroDivisionError`).

---

## 4. Cara Menjalankan Unit Test

```bash
python -m unittest discover -s tests -v
```

Untuk menjalankan modul Anggota 4 saja:
```bash
python -m unittest tests.test_exercise_1122 tests.test_case_explorer -v
```

---

## 5. Cara Integrasi ke GUI Anggota 5 & Log Anggota 1

Kedua halaman (`Exercise1122Page` dan `CaseExplorerPage`) adalah `QWidget` reusable dan **tidak** membuat `QMainWindow` atau `QApplication` sendiri. Contoh wiring pada main window Anggota 5:

```python
from gui.import_overview_page import ImportOverviewPage
from gui.pages.exercise_1122_page import Exercise1122Page
from gui.pages.case_explorer_page import CaseExplorerPage

import_page = ImportOverviewPage()
ex1122_page = Exercise1122Page()
case_explorer_page = CaseExplorerPage()

# 1. Sambungkan dataset aktif dari Anggota 1 (tanpa membaca XES ulang)
import_page.dataset_loaded.connect(ex1122_page.set_dataset)
import_page.dataset_loaded.connect(case_explorer_page.set_dataset)

# 2. Sambungkan klik dua kali / buka evidence dari 11.22 ke Case Explorer
def on_open_case_from_1122(case_id, evidence):
    case_explorer_page.open_case(case_id, evidence)
    main_stack_or_tabs.setCurrentWidget(case_explorer_page)

ex1122_page.open_case_requested.connect(on_open_case_from_1122)

# 3. Halaman anggota lain (11.7, 11.15, 11.18) dapat memanggil pola yang sama:
# case_explorer_page.open_case(case_id, {"evidence_positions": [pos1, pos2], "label": "11.15"})
```

---

## 6. Cara Menjalankan Demo dengan Fixture Sintetis (Tanpa Aplikasi Final Terpisah)

Sambil menunggu main window Anggota 5, halaman widget dapat dipreview secara langsung menggunakan skrip sekali jalan (`python -c ...`) dengan `QTabWidget` sementara dan fixture sintetis:

```bash
python -c "
from datetime import datetime, timezone
from pm4py.objects.log.obj import Event, EventLog, Trace
from PySide6.QtWidgets import QApplication, QTabWidget
from gui.pages.exercise_1122_page import Exercise1122Page
from gui.pages.case_explorer_page import CaseExplorerPage

t0 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
t1 = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
t2 = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
log = EventLog([
    Trace([
        Event({'concept:name': 'A_Create Application', 'time:timestamp': t0, 'lifecycle:transition': 'complete', 'org:resource': 'User_1'}),
        Event({'concept:name': 'O_Cancelled', 'time:timestamp': t1, 'lifecycle:transition': 'complete', 'org:resource': 'User_2'}),
        Event({'concept:name': 'O_Accepted', 'time:timestamp': t2, 'lifecycle:transition': 'complete', 'org:resource': 'User_3'}),
    ], attributes={'concept:name': 'Demo_Case_1'}),
    Trace([
        Event({'concept:name': 'O_Accepted', 'time:timestamp': t0}),
        Event({'concept:name': 'O_Cancelled', 'time:timestamp': t1}),
    ], attributes={'concept:name': 'Demo_Case_2'}),
])

app = QApplication([])
tabs = QTabWidget()
ex_page = Exercise1122Page()
ce_page = CaseExplorerPage()
tabs.addTab(ex_page, 'Exercise 11.22')
tabs.addTab(ce_page, 'Case Explorer')

ex_page.open_case_requested.connect(lambda cid, ev: (ce_page.open_case(cid, ev), tabs.setCurrentWidget(ce_page)))
ex_page.set_dataset(log, {'file_name': 'synthetic_demo.xes', 'case_count': len(log)})
ce_page.set_dataset(log, {'file_name': 'synthetic_demo.xes', 'case_count': len(log)})

tabs.resize(960, 600)
tabs.show()
app.exec()
"
```

---

## 7. Hasil Pengujian yang Benar-Benar Dijalankan

Pengujian dijalankan pada lingkungan Python 3.11.0 dengan `pm4py==2.7.23.13` dan `PySide6==6.12.0` menggunakan mode GUI offscreen:

- **Perintah:** `QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v`
- **Hasil:** **42 test dijalankan — 42 PASS, 0 FAIL, 0 ERROR** (`0.286s`):
  - `tests/test_exercise_1122.py`: **12 PASS** (mencakup seluruh skenario `i < j`, multi-pasangan dalam satu case, dataset kosong, timestamp identik, kesetaraan `EventLog` & `DataFrame`, serta validasi atribut wajib).
  - `tests/test_case_explorer.py`: **7 PASS** (6 unit test `CaseExplorerTests` untuk pencarian, trace lengkap + atribut opsional jujur, evidence generik, cache index, kesetaraan `EventLog` & `DataFrame`, validasi atribut wajib; serta 1 smoke test GUI offscreen `GuiWidgetsOffscreenSmokeTests` yang menguji alur lengkap `no_dataset -> ready -> loading -> loaded -> double-click buka evidence ke Case Explorer -> reset -> re-run -> empty search -> ganti dataset -> error state`).
  - `tests/test_data_loader.py` & `tests/test_overview.py` (milik Anggota 1): **23 PASS** (14 + 9).
- **Pengecekan Sintaks:** `python -m py_compile` pada seluruh file Python Anggota 4 lulus tanpa error.

---

## 8. Keterbatasan Integrasi & Kebutuhan Tes XES BPIC17 Asli

1. **Integrasi Main Window Anggota 5:** Pada branch `feature/fazl-exercise1122`, file main window Anggota 5 serta modul/halaman Anggota 2 (`11.7`, `11.15`) dan Anggota 3 (`11.18`) belum tersedia/tergabung, sehingga integrasi end-to-end antar halaman di dalam main window produksi belum dapat diuji.
2. **Dataset XES BPIC17 Asli:** File XES BPIC17 asli tidak tersedia di workspace ini. Pengujian pada data skala penuh (~31.509 cases / >1 juta events) diperlukan saat integrasi final untuk memastikan performa waktu komputasi, penggunaan memori indexing Case Explorer, dan kesesuaian atribut BPIC17 nyata.
3. **Asumsi Integrasi yang Perlu Dikonfirmasi dengan Anggota 1 & 5:**
   - Anggota 1 mempertahankan tipe output `EventLog` (atau `DataFrame` PM4Py) dan signature sinyal `dataset_loaded(log, metadata, overview)`.
   - Anggota 5 menghubungkan sinyal `open_case_requested(case_id, evidence)` dari halaman analisis ke slot `CaseExplorerPage.open_case(case_id, evidence)` sekaligus memindahkan navigasi aktif ke tab/halaman Case Explorer.
   - Halaman 11.7, 11.15, dan 11.18 mengikuti pola `set_dataset(log, metadata, overview)` agar tidak terjadi pembacaan ulang file XES.
