# Dokumentasi Anggota 4 — Exercise 11.22, Case Explorer, Pengujian & Integrasi

## 1. Struktur dan Fungsi File Anggota 4

| File | Peran | Komponen Utama |
| --- | --- | --- |
| `modules/exercise_1122.py` | Logika analisis Exercise 11.22 pada level case | `analyze_1122`, `RULE_DESCRIPTION` |
| `modules/case_explorer.py` | Inspeksi trace case lengkap, pencarian, indexing cache, dan penanda evidence | `get_case_trace`, `get_case_detail`, `list_cases`, `search_cases`, `build_case_index`, `CaseIndex`, `clear_case_index_cache` |
| `gui/pages/__init__.py` | Paket halaman reusable GUI desktop & helper pemasangan `MainWindow` | `Exercise1122Page`, `CaseExplorerPage`, `install_anggota4_pages` |
| `gui/pages/exercise_1122_page.py` | Widget `QWidget` halaman Exercise 11.22 (mendukung `MainWindow` `TaskControls`/`TaskThread` & standalone `QThread`) | `Exercise1122Page`, `Exercise1122Worker` |
| `gui/pages/case_explorer_page.py` | Widget `QWidget` halaman Case Explorer (mendukung `AppState.dataset_changed` & background indexing `QThread`) | `CaseExplorerPage`, `CaseIndexWorker` |
| `tests/test_exercise_1122.py` | Unit test Exercise 11.22 untuk `EventLog` & `DataFrame` | `Exercise1122Tests` |
| `tests/test_case_explorer.py` | Unit test Case Explorer, smoke test standalone, & uji integrasi `MainWindow` end-to-end | `CaseExplorerTests`, `GuiWidgetsOffscreenSmokeTests`, `MainWindowAnggota4IntegrationTests` |
| `docs/test_matrix.md` | Matriks uji gabungan lintas fitur (11.7, 11.15, 11.18, 11.22, integrasi) | Tabel skenario, expected/actual, status |
| `docs/anggota4.md` | Dokumentasi teknis, kontrak API, panduan integrasi & demo | Dokumen ini |
| `docs/script_demo_anggota4.md` | Naskah narasi dan langkah operasional perekaman video demo (1,5–2 menit) | Panduan demo |

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
  - `exercise`: `"11.22"`
  - `rule`: deskripsi aturan `i < j`
  - `count`: jumlah case unik yang lolos
  - `total_cases`: total active cases (denominator)
  - `percentage`: `(count / total_cases * 100.0)` atau `0.0` jika `total_cases == 0`
  - `case_ids`: daftar `Case ID` yang lolos
  - `evidence`: daftar dict (1 entri per case lolos) berisi `case_id`, `cancelled_index`, `accepted_index`, `cancelled_seq`, `accepted_seq`, `cancelled_activity`, `accepted_activity`, `cancelled_timestamp`, `accepted_timestamp`, `cancelled_event`, `accepted_event`, `evidence_positions`, `trace_length`.

### 2.2 `get_case_trace(log_or_df, case_id, *, evidence=None, highlight_positions=None, index=None)`
- **Input:** `log_or_df` (`EventLog` / `DataFrame` PM4Py), `case_id`, dan penanda evidence opsional (`evidence` dict hasil 11.22, dict `{posisi: label}` untuk latihan 11.7/11.15/11.18, atau iterable posisi `highlight_positions`).
- **Output (`list[dict[str, Any]]`):** Seluruh event asli dari case secara berurutan (mengembalikan `[]` jika `case_id` tidak ditemukan), berisi `seq`, `position`, `case_id`, `timestamp`, `activity`, `lifecycle` (`None` jika kosong), `resource` (`None` jika kosong), `is_evidence`, dan `evidence_role`.
- **Fungsi Pendukung Case Explorer:** `build_case_index`, `get_or_build_case_index`, `list_cases`, `search_cases`, `get_case_detail`, `clear_case_index_cache`.

---

## 3. Aturan Filter `i < j` dan Perhitungan Persentase

1. **Level Case (bukan Offer ID):** Setiap trace/case dievaluasi satu kali berdasarkan urutan event aslinya.
2. **Urutan Event Asli & Stabil:** Event tidak diurutkan ulang berdasarkan timestamp; jika terdapat timestamp identik, urutan asli trace tetap dipertahankan.
3. **Kondisi `i < j`:** Mencari kemunculan pertama `O_Cancelled` pada indeks `i` yang diikuti `O_Accepted` pada indeks `j` dengan `i < j` (aktivitas perantara diperbolehkan). `O_Accepted` yang hanya muncul sebelum `O_Cancelled` tidak lolos. Beberapa pasangan valid dalam 1 case tetap dihitung 1 case.
4. **Persentase:** `count / total_cases * 100.0` saat `total_cases > 0`, dan `0.0` saat `total_cases == 0`.

---

## 4. Cara Menjalankan Unit Test

```powershell
$env:QT_QPA_PLATFORM="offscreen"; python -m unittest discover -s tests -v
```

Untuk modul Anggota 4 saja:
```powershell
$env:QT_QPA_PLATFORM="offscreen"; python -m unittest discover -s tests -p "test_exercise_1122.py" -v
$env:QT_QPA_PLATFORM="offscreen"; python -m unittest discover -s tests -p "test_case_explorer.py" -v
```

---

## 5. Cara Integrasi ke GUI Utama Anggota 5 (`MainWindow`)

Shell `gui/main_window.py` menyediakan `MainWindow.install_page(page_key, panel, controls=None)` untuk key `"exercise_1122"` dan `"case_explorer"`. Paket Anggota 4 sudah menyediakan fungsi `install_anggota4_pages(window)` pada `gui/pages/__init__.py`:

```python
from gui.pages import install_anggota4_pages

window = MainWindow()
install_anggota4_pages(window)
```

Di dalam `install_anggota4_pages(window)`:
1. `Exercise1122Page.bind_main_window(window)` mengaktifkan `TaskControls` (`Jalankan Analisis`, `Reset hasil`, `Jalankan ulang`), menghubungkan `controls.run_requested` ke `window.run_task("exercise_1122", ..., lambda ds: analyze_1122(ds.log))`, serta berlangganan `window.state.dataset_changed` dan `window.state.result_changed`.
2. `CaseExplorerPage.bind_main_window(window)` berlangganan `window.state.dataset_changed` untuk membangun `CaseIndex` dari `dataset.log` yang sama tanpa membaca ulang XES.
3. Sinyal `ex1122_page.open_case_requested` dihubungkan ke `case_explorer_page.open_case(case_id, evidence)` diikuti `window.navigate("case_explorer")`.

---

## 6. Status Entry Point `main.py` & Cara Menjalankan Aplikasi / Demo

- **Status `main.py`:** `main.py` sekarang memanggil `install_anggota4_pages(window)` tepat setelah `window = MainWindow()`, sehingga menjalankan `python main.py` langsung menampilkan halaman **Exercise 11.22** dan **Case Explorer** menggantikan placeholder.
- **Menjalankan aplikasi desktop utama:**
  ```powershell
  python main.py
  ```
- **Dataset BPIC17 Asli (Cara Memperoleh):**
  File BPIC17 `.xes` asli belum tersedia di workspace/mesin uji. Sumber resmi: **BPI Challenge 2017** (Boudewijn van Dongen, 2017, 4TU.ResearchData, DOI `10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b`). Unduh arsip `BPI Challenge 2017.xes.gz`, ekstrak file `.xes` ke folder `data/` (atau lokasi lokal di luar repo), lalu pilih melalui **Import Dataset -> Pilih file XES**.

---

## 7. Hasil Pengujian yang Benar-Benar Dijalankan

Pengujian dijalankan pada Python 3.11.0 dengan `pm4py==2.7.23.13`, `PySide6==6.12.0`, dan `pandas==3.0.5` menggunakan mode Qt offscreen:

- **Perintah:** `$env:QT_QPA_PLATFORM="offscreen"; python -m unittest discover -s tests -v`
- **Hasil:** **54 test dijalankan — 54 PASS, 0 FAIL, 0 ERROR**:
  - `tests/test_exercise_1122.py`: **12 PASS**
  - `tests/test_case_explorer.py`: **8 PASS** (6 `CaseExplorerTests`, 1 `GuiWidgetsOffscreenSmokeTests`, 1 `MainWindowAnggota4IntegrationTests` termasuk uji error `TaskThread` & `ImportOverviewPage` dengan fixture `.xes`)
  - `tests/test_data_loader.py` & `tests/test_overview.py` (Anggota 1): **23 PASS** (14 + 9)
  - `tests/test_integration.py` (Anggota 5): **11 PASS** (termasuk `test_main_entry_point` setelah integrasi `main.py`)
- **Verifikasi `python main.py` terintegrasi:** Diverifikasi membuka `MainWindow` dengan `Exercise1122Page` dan `CaseExplorerPage` terpasang (`EX_MOUNTED: True`, `CE_MOUNTED: True`), mengimpor fixture XES sintetis, menjalankan 11.22 (`1/2 = 50.00%`), dan membuka `App_1001` di Case Explorer.

---

## 8. Keterbatasan Integrasi & Kebutuhan Tes XES BPIC17 Asli

1. **Review Perubahan `main.py`:** `main.py` mendapat penambahan minimal 2 baris (`from gui.pages import install_anggota4_pages` dan `install_anggota4_pages(window)`) untuk memasang halaman Anggota 4; perlu ditinjau Anggota 5 saat PR/merge.
2. **Modul Anggota 2 & 3:** Halaman `exercise_117`, `exercise_115_118`, dan `export` masih berstatus placeholder di `MainWindow`.
3. **Dataset XES BPIC17 Asli:** File XES BPIC17 asli belum tersedia di workspace sehingga hasil hitung pada data asli dan performa skala penuh (~31.509 cases / >1,2 juta events) belum diverifikasi (`NOT TESTED`).
4. **Catatan Lingkungan:** `requirements.txt` mencantumkan `PySide6==6.11.3` dan `pandas==2.3.3` serta `README.md` mengacu Python 3.13, sedangkan lingkungan uji memakai Python 3.11.0 dengan `PySide6==6.12.0`, `pm4py==2.7.23.13`, dan `pandas==3.0.5`.
