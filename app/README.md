# Gamma Spektroskopie - Dash Aplikace

Interaktivní webová aplikace pro analýzu scintilačních spekter pomocí kanálově-centrického přístupu s rebinningem a dekonvolucí.

---

## 📋 Obsah

- [Přehled](#přehled)
- [Architektura](#architektura)
- [Matematické metody](#matematické-metody)
- [Vstupy a výstupy](#vstupy-a-výstupy)
- [Závislosti](#závislosti)
- [Instalace a spuštění](#instalace-a-spuštění)
- [Workflow aplikace](#workflow-aplikace)
- [Struktura souborů](#struktura-souborů)

---

## 🎯 Přehled

Tato Dash aplikace umožňuje:
- **Načítání spekter** z Excel souborů nebo SPE formátu
- **Energetickou kalibraci** pomocí známých píků
- **Dekonvoluci spekter** pomocí NNLS/OLS regrese s kalibračními etalonými spektry
- **Výpočet aktivit** Ra-226, K-40 a Th-232 ve vzorcích
- **Analýzu píku Ra-226 @ 186 keV** s korekcí interference U-235
- **Interaktivní vizualizaci** celých spekter, ROI oblastí a residuí
- **Export výsledků** do Excel formátu

### Hlavní vlastnosti
- **Channel-centric design**: Všechny ROI a mapování jsou v kanálech, energie pouze pro display
- **Rebinning**: Mapování spekter vzorků do referenční kanálové mřížky pomocí lineární transformace
- **Multi-ROI analýza**: Samostatné regrese pro Ra/Th a K-40 oblasti s odlišnými channel mappingy
- **Optimalizace kalibrace**: Automatické hledání optimálního channel mappingu minimalizací MSE

---

## 🏗️ Architektura

### Modularita

Aplikace je rozdělena do logických modulů:

```
app/
├── app.py                    # Entry point, inicializace Dash
├── layout.py                 # UI layout definice
├── processing.py             # Wrapper pro zpracovací funkce
├── assets/
│   └── style.css            # Vlastní CSS styly
├── callbacks/               # Reaktivní logika (Dash callbacks)
│   ├── __init__.py          # Registrace všech callbacks
│   ├── analysis.py          # Hlavní regresní analýza
│   ├── calibration.py       # Energetická kalibrace
│   ├── data_loading.py      # Načítání dat z Excel/SPE
│   ├── results.py           # Export a zobrazení výsledků
│   ├── utils.py             # Sdílené importy pro callbacks
│   ├── visualization.py     # Wrapper pro vizualizace
│   ├── visualization_full_spectrum.py  # Celé spektrum + ROI overlay
│   ├── visualization_roi.py             # ROI #1/#2 + residua
│   └── visualization_186peak.py         # Ra-226 @ 186 keV peak
├── config/
│   └── detectors.yaml       # Konfigurace detektorů (ROI, kalibrace, atd.)
├── data/
│   └── calibration/         # Kalibrační spektra (Ra, K, Th, BG)
├── scripts/
│   ├── deconv.py            # Standalone dekonvoluce
│   └── utils.py             # Rebinning, NNLS, OLS, kompilace výsledků
└── utils/                   # Pomocné moduly
    ├── analysis_core.py     # Těžká regresní logika (testovatelná)
    ├── channel_processing.py # Optimalizace channel mappingu
    ├── config_loader.py     # YAML parser pro detectors.yaml
    ├── data_helpers.py      # Extrakce dat z Excel
    ├── peak_analysis.py     # Analýza Ra-226 @ 186 keV
    ├── plot_builders.py     # Plotly figure buildery
    ├── plot_components.py   # Opakovaně použitelné trace komponenty
    ├── results_calculations.py # Kompilace výsledků
    ├── spe_handler.py       # SPE formát parser
    └── ui_builders.py       # Dash komponenty (cards, tables, atd.)
```

### Separace zodpovědností

| Modul | Zodpovědnost |
|-------|-------------|
| `app.py` | Inicializace Dash, registrace callbacks, server start |
| `layout.py` | Definice UI layoutu (cards, sliders, tabs) |
| `callbacks/` | Reaktivní logika - propojení UI a výpočtů |
| `scripts/` | Matematické algoritmy (NNLS, OLS, rebinning) |
| `utils/` | Reusable utility funkce bez Dash závislostí |
| `config/` | Statická konfigurace detektorů |

---

## 🧮 Matematické metody

### 1. **Rebinning spekter**

Lineární transformace kanálů z měřeného spektra do referenční mřížky:

```
ch_ref = a0 + a1 * ch_sample
```

- **Zachování počtů**: Částečné počty se redistribuují mezi sousední kanály pomocí lineární interpolace
- **Implementace**: `scripts/utils.py::rebin_channels()`
- **Účel**: Umožňuje dekonvoluci s kalibračními spektry v jednotné kanálové mřížce

### 2. **Dekonvoluce spektra**

Řešení soustavy lineárních rovnic:

```
y = X · β + ε
```

kde:
- `y`: Vektor měřeného spektra (CPS v každém kanálu)
- `X`: Matice kalibrací [Ra | K | Th | BG], každý sloupec = normalizované spektrum
- `β`: Vektor aktivit [A_Ra, A_K, A_Th, A_BG] - **hledané koeficienty**
- `ε`: Residuální chyba

#### Metody řešení:

**A) NNLS (Non-Negative Least Squares)**
```python
β_NNLS = argmin ||y - X·β||²  s.t. β ≥ 0
```
- Vynucuje fyzikálně smysluplné nezáporné aktivity
- Implementace: `scipy.optimize.nnls`
- Výstup: Koeficienty + MSE (mean squared error)

**B) OLS (Ordinary Least Squares)**
```python
β_OLS = (X^T · X)^(-1) · X^T · y
```
- Analytické řešení metodou nejmenších čtverců
- Může dát záporné koeficienty (fyzikálně nesmyslné)
- Implementace: `scripts/utils.py::ols()`

### 3. **Multi-ROI regrese**

Pro zlepšení přesnosti se spektrum rozdělí do oblastí:

- **ROI #1 (Ra/Th)**: ~200-800 keV - dominují Ra-226 a Th-232
- **ROI #2 (K-40)**: ~700-1640 keV - dominuje K-40 @ 1460 keV

Každá ROI může mít **samostatný channel mapping**:
```
ROI1: ch_ref = a0_roi1 + a1_roi1 * ch_sample
ROI2: ch_ref = a0_roi2 + a1_roi2 * ch_sample
```

**Kombinace výsledků**:
```python
A_Ra  = A_Ra_roi1          # Ra pouze z ROI #1
A_K   = A_K_roi2           # K pouze z ROI #2
A_Th  = A_Th_roi1          # Th pouze z ROI #1
```

### 4. **Optimalizace channel mappingu**

Automatické hledání optimálních parametrů `(a0, a1)` minimalizací MSE:

```python
(a0*, a1*) = argmin MSE(rebin(a0, a1))
```

**Metody**:
- `L-BFGS-B`: Limited-memory BFGS s bounds (default) - efektivní gradient-based optimalizace
- `Powell`: Powell's conjugate direction method
- `Nelder-Mead`: Nelder-Mead simplex (gradient-free, pomalejší)

**Bounds**:
- `a0`: ±50 kanálů od initial guess
- `a1`: 0.9 - 1.1 (±10% gain variace)

**Implementace**: `scripts/utils.py::find_optimal_channel_mapping()` + wrapper v `utils/channel_processing.py`

### 5. **Analýza Ra-226 @ 186 keV**

Samostatná analýza jediného píku pro zvýšení přesnosti Ra-226:

**Kroky**:
1. **Peak search**: Hledání maxima ve spektru v okolí očekávané pozice
2. **ROI integrace**: Definice peak ROI (např. ±15 kanálů)
3. **Pozadí**: Lineární fit z okrajových kanálů
4. **Net area**: `Net = Gross - Background`
5. **Aktivita**: `A_Ra = Net_sample / (Net_calib / A_calib) / Live_time`

**Korekce U-235 interference**:
```python
A_Ra_corrected = A_Ra_raw * 0.575  # 57.5% contribution from Ra-226
```

**Implementace**: `utils/peak_analysis.py::calculate_ra226_from_186kev_peak()`

### 6. **Konverze aktivita → hustota**

```python
ρ_material = A_nuclide / (m_sample * A_specific)
```

kde:
- `A_nuclide`: Aktivita radionuklidu [Bq]
- `m_sample`: Hmotnost vzorku [g]
- `A_specific`: Specifická aktivita [Bq/g]

**Specifické aktivity** (datované k 1.1.2026):
- K-40: 265114 Bq/g
- Th-232: 4065 Bq/g (rovnováha s dceřinými)
- Ra-226: 36590 Bq/g (rovnováha s dceřinými)

---

## 📊 Vstupy a výstupy

### Vstupy

#### 1. **Excel soubor** (primární)

Struktura:
```
Sheet "Detektor vzorky":
  Row 1: Sample names [-, SAMP1, SAMP2, ...]
  Row 3: Live times [-, 1000, 1000, ...]  # [s]
  Row 12+: [CHNL | Counts_1 | Counts_2 | ...]

Sheet "Detektor kalibrace":
  Row 1: [-, Ra, K, Th, BG]
  Row 12+: [CHNL | Ra_counts | K_counts | Th_counts | BG_counts]
```

#### 2. **SPE soubory** (alternativní)

Maestro formát:
```
$SPEC_ID:
Sample description
$MEAS_TIM:
1000 1000    # Live time, Real time [s]
$DATA:
0 2047       # Start channel, End channel
123          # Counts in ch 0
456          # Counts in ch 1
...
$ROI:        # Optional
3
200 300      # ROI 1: channels 200-300
...
```

#### 3. **Konfigurace detektoru** (`config/detectors.yaml`)

```yaml
CeBr3:
  channel_mapping:
    ref_a0: 0.0
    ref_a1: 1.0
  display_calibration:
    a0: 9.6229      # [keV]
    a1: 1.3793      # [keV/channel]
    a2: 0.0         # [keV/channel²]
  standard_activities:
    Ra: 1001.4      # [Bq]
    K: 11505        # [Bq]
    Th: 1020.0      # [Bq]
  roi_ranges:
    roi1: [138, 573]   # Ra/Th ROI [channels]
    roi2: [504, 1182]  # K-40 ROI [channels]
  peak_analysis:
    ra_186_energy: 186.0
    roi_half_width: 15
    bg_margin: 5
    ra_186_correction: 0.575
  calibration_spectra:
    Ra: "app/data/calibration/Ra_CeBr.SPE"
    K: "app/data/calibration/K_CeBr.SPE"
    Th: "app/data/calibration/Th_CeBr.SPE"
    BG: "app/data/calibration/BG_CeBr.SPE"
```

### Výstupy

#### 1. **Interaktivní grafy** (Plotly)

- **Celé spektrum**: Resampled spectrum + ROI overlays + calibration markers
- **ROI #1 zoom**: Ra/Th region with fit + components (Ra, Th, BG)
- **ROI #2 zoom**: K-40 region with fit + components (K, BG)
- **Residua**: Relative residuals `(Data - Fit) / Data`
- **Ra-226 @ 186 keV**: Peak with linear background + net area

#### 2. **Results table**

| Parameter | Value | Unit |
|-----------|-------|------|
| Ra-226 activity | 1234.5 ± 12.3 | Bq |
| K-40 activity | 5678.9 ± 56.7 | Bq |
| Th-232 activity | 987.6 ± 9.8 | Bq |
| MSE (ROI #1) | 0.0123 | - |
| MSE (ROI #2) | 0.0456 | - |

#### 3. **Excel export**

Soubor: `results_YYYYMMDD_HHMMSS.xlsx`

Sheets:
- **Summary**: Aktivita [Bq], Hustota [g/g], Nejistoty
- **Calibration**: Channel mapping koeficienty
- **Metadata**: Live time, sample name, detector, timestamp

---

## 🔗 Závislosti

### Python balíčky (requirements.txt)

```
dash>=2.14.0              # Webový framework
dash-bootstrap-components # UI komponenty
plotly>=5.18.0            # Interaktivní grafy
pandas>=2.1.0             # Data manipulace
numpy>=1.24.0             # Numerické výpočty
scipy>=1.11.0             # NNLS solver
pyyaml>=6.0               # YAML parser
openpyxl>=3.1.0           # Excel I/O
```

### Systémové požadavky

- Python 3.9+
- 4 GB RAM (pro velké spektra)
- Moderní webový prohlížeč (Chrome, Firefox, Edge)

---

## 🚀 Instalace a spuštění

### 1. Vytvoření virtuálního prostředí

```bash
cd app/
python -m venv .venv
.venv\Scripts\activate     # Windows
source .venv/bin/activate  # Linux/Mac
```

### 2. Instalace závislostí

```bash
pip install -r requirements.txt
```

### 3. Příprava dat

Umístit kalibrační spektra do `app/data/calibration/`:
- `Ra_CeBr.SPE` (nebo `Ra_NaI.SPE`)
- `K_CeBr.SPE`
- `Th_CeBr.SPE`
- `BG_CeBr.SPE`

### 4. Spuštění aplikace

```bash
python app.py
```

Aplikace běží na `http://localhost:8051`

---

## 🔄 Workflow aplikace

### Krok 1: Načtení dat

1. Vybrat detektor (CeBr3 / NaI(Tl))
2. Upload Excel souboru nebo SPE souborů
3. Aplikace načte spektra + metadata (live times, sample names)

### Krok 2: Kalibrace

**Energetická kalibrace**:
- Zadat známé energie píků [keV]
- Kliknout na odpovídající píky ve spektru
- Fit polynomu: `E = a0 + a1*CH + a2*CH²`
- Koeficienty se použijí **pouze pro display** (osy grafu)

**Channel mapping**:
- Defaultně: identity mapping `(0.0, 1.0)`
- Manuálně upravit `a0`, `a1`
- Nebo optimalizovat automaticky (tlačítko "Optimize")

### Krok 3: Nastavení ROI

- Posunout slidery pro ROI #1 (Ra/Th) a ROI #2 (K-40)
- ROI jsou v **kanálech**, ne energiích
- Defaultní hodnoty z `detectors.yaml`

### Krok 4: Analýza

1. Vybrat vzorek z dropdownu
2. Nastavit parametry:
   - Regression method: NNLS / OLS
   - Use background: ON / OFF
   - Optimize calibration: ON / OFF (pro každou ROI zvlášť)
3. Kliknout **"Run Analysis"**

### Krok 5: Výsledky

- Zobrazí se grafy + tabulka aktivit
- Zkontrolovat residua (měla by být kolem 0)
- Ra-226 @ 186 keV se analyzuje automaticky (pokud je pík detekován)

### Krok 6: Export

- Kliknout **"Export to Excel"**
- Stáhne se soubor s kompletními výsledky

---

## 📁 Struktura souborů (detaily)

### `app.py`
Inicializace Dash aplikace, registrace callbacks, server start.

```python
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.layout = create_layout()
register_all_callbacks(app)
app.run(debug=True, port=8051)
```

### `layout.py`
Definice UI layoutu pomocí Dash Bootstrap Components:
- Header s výběrem detektoru
- Upload area
- Sample selector
- Parameter cards (calibration, ROI, regression)
- Tabs: Spectrum | Results | Export
- Plotly graphs placeholders

### `callbacks/`

#### `__init__.py`
Registruje všechny callback moduly:
```python
def register_all_callbacks(app):
    register_data_loading_callbacks(app)
    register_calibration_callbacks(app)
    register_analysis_callbacks(app)
    register_visualization_callbacks(app)
    register_results_callbacks(app)
```

#### `data_loading.py`
- Upload Excel → parse → store v `dcc.Store`
- Upload SPE → parse → konverze do unified formátu
- Load detector config z YAML
- Inicializace calibration stores

#### `calibration.py`
- Click na graf → capture channel position
- Fit polynomu energií k channel positions
- Update energetických koeficientů (`a0`, `a1`, `a2`)
- Display fitted calibration curve

#### `analysis.py`
**Hlavní modul** s regresní analýzou:

1. `prepare_sample_data()`: Extrakce + normalizace + rebinning
2. `build_calibration_matrix()`: Sestavení `X` matice
3. `perform_single_regression()` nebo `perform_dual_roi_regression()`:
   - Single: Jedna regrese přes celé spektrum
   - Dual: Samostatné regrese pro ROI #1 a #2 s různými mappingy
4. `optimize_channel_mapping_wrapper()`: Iterativní optimalizace MSE
5. `calculate_ra226_from_186kev_peak()`: 186 keV peak analýza
6. `compile_results_dynamic()`: Package všech výsledků
7. Store → accumulated results (pro vícenásobné vzorky)

#### `visualization.py`
Wrapper registrující sub-moduly:
- `register_full_spectrum_callbacks()`
- `register_roi_callbacks()`
- `register_186peak_callbacks()`
- ROI slider sync callback

#### `visualization_full_spectrum.py`
Callback: `update_plot_full()`
- X-axis: Channels (CHNL)
- Y-axis: Counts (CPS)
- Traces: Sample spectrum + fit (if available)
- Overlays: ROI #1, ROI #2 (colored rectangles)
- Markers: Calibration peaks (green X)
- Zoom: Synced s ROI display slider

#### `visualization_roi.py`
4 callbacks:
- `update_plot_roi1()`: Ra/Th region zoom + fit components
- `update_plot_roi2()`: K-40 region zoom + fit components
- `update_residuals_roi1()`: Relative residuals ROI #1
- `update_residuals_roi2()`: Relative residuals ROI #2

#### `visualization_186peak.py`
Callback: `update_plot_186()`
- Zoomed view kolem 186 keV píku
- Linear background fit
- Net area calculation (yellow fill)
- RangeSlider: Outer = zoom, Inner = peak ROI boundaries
- Live text update: Net area + activity

#### `results.py`
- Generate results table (HTML)
- Export to Excel callback
- Clear results callback

### `scripts/`

#### `deconv.py`
Standalone script pro batch analýzu (bez GUI):
```python
# Load calibration spectra
calib_df = load_calibrations()

# Process sample
sample_df = load_sample()
sample_rebinned = rebin_spectrum(sample_df)

# Deconvolve
coeffs, mse = nnls_detailed(X=calib_df, y=sample_rebinned)

# Compile results
results = compile_results(coeffs, standard_activities)
```

#### `utils.py`
Core matematické funkce:
- `rebin_channels()`: Lineární interpolace pro rebinning
- `ols()`: Ordinary Least Squares solver
- `nnls_detailed()`: NNLS wrapper s MSE
- `compile_results()`: Aktivita → hustota konverze
- `normalize_by_live_time()`: Counts → CPS
- `subtract_background()`: Sample - BG
- `calculate_energy()`: Channel → Energy (polynomial)

### `utils/`

#### `analysis_core.py`
Extrahované těžké výpočty z `analysis.py`:
- `prepare_sample_data()`: Rebin + normalizace
- `build_calibration_matrix()`: X matrix construction
- `perform_single_regression()`: Full spectrum NNLS/OLS
- `perform_dual_roi_regression()`: Multi-ROI s oddělnými mappingy
- `package_analysis_results()`: Kompilace do dictionary

#### `channel_processing.py`
- `optimize_channel_mapping()`: Grid search nebo Nelder-Mead
- `find_optimal_calibration()`: Wrapper s MSE tracking
- `validate_roi_ranges()`: Check ROI validity

#### `config_loader.py`
- `load_detector_config()`: Parse YAML → Python dict
- `get_detector_params()`: Extract specifických parametrů
- Validation checks (missing keys, invalid ranges)

#### `data_helpers.py`
- `unpack_excel_data()`: Extract calib_df, sample_df, bg_df
- `get_sample_data()`: Retrieve specific sample spectrum
- `has_background_data()`: Check if BG is available

#### `peak_analysis.py`
- `calculate_ra226_from_186kev_peak()`: Complete 186 keV workflow
- `find_peak_position()`: Smooth + search maximum
- `integrate_peak_area()`: Gross - linear background
- `estimate_background()`: Edge channels → linear fit

#### `plot_builders.py`
High-level Plotly figure buildery:
- `create_full_spectrum_plot()`: Complete spectrum viz
- `create_roi_plot()`: Zoomed ROI with fit
- `create_residuals_plot()`: Residuals with stats
- `create_186peak_plot()`: 186 keV peak viz

#### `plot_components.py`
Reusable trace factories:
- `add_spectrum_trace()`: Step histogram
- `add_fit_trace()`: Fitted curve
- `add_component_traces()`: Stacked components (Ra, K, Th, BG)
- `add_roi_overlay()`: Colored rectangle
- `add_calibration_markers()`: Green X markers

#### `results_calculations.py`
- `compile_results_dynamic()`: Unified result packaging
- `calculate_activity_uncertainties()`: Poisson statistics
- `convert_to_density()`: Bq → g/g
- `format_results_table()`: HTML rendering

#### `spe_handler.py`
- `parse_spe_file()`: Maestro format parser
- `extract_live_time()`: From `$MEAS_TIM` section
- `extract_roi_info()`: From `$ROI` section (optional)
- `spe_to_dataframe()`: SPE → pandas DataFrame

#### `ui_builders.py`
Dash component factories:
- `create_parameter_card()`: Bootstrap card with inputs
- `create_slider_card()`: RangeSlider with labels
- `create_button_group()`: Action buttons
- `create_alert()`: Status messages

---

## 🔍 Debugging tipy

### 1. **Print diagnostics**

Většina funkcí má `print_diagnostics=True` parameter:
```python
prepare_sample_data(sample_name, excel_data, channel_mapping, print_diagnostics=True)
```
Vypíše:
- Sample pairing check
- Rebinning conservation ratio
- Channel mapping coefficients

### 2. **Kontrola MSE**

Nízké MSE = dobrý fit:
- MSE < 0.01: Výborný fit
- MSE 0.01-0.1: Přijatelný
- MSE > 0.1: Problém (špatná kalibrace, kontaminace)

### 3. **Residua**

Residuals by měla být **náhodná kolem 0**:
- Systematický bias → špatný channel mapping
- Velké outliers → pík chybí v kalibraci

### 4. **Browser Console**

Otevřít Developer Tools (F12) → Console tab
- Zobrazí Dash callback errors
- Network tab → API requests timing

---

## 📝 Licence

Tento projekt je vyvíjen pro výzkumné účely na oddělení radiometrie SÚRO.

---

## 👥 Kontakt

**Autor**: Michal Hybler  
**Email**: michal.hybler@suro.cz  
**GitHub**: https://github.com/mihy-suro/Scint_stavmat

---

## 🔄 Changelog

### v2.0 (2026-01-07)
- ✅ Refactoring visualization.py → 4 moduly
- ✅ Channel-centric ROI design
- ✅ Multi-ROI regression s oddělenými mappingy
- ✅ Ra-226 @ 186 keV peak analysis
- ✅ README dokumentace

### v1.0 (2024-12-15)
- ✅ Initial Dash aplikace
- ✅ Excel/SPE loading
- ✅ NNLS/OLS deconvolution
- ✅ Interactive Plotly graphs
