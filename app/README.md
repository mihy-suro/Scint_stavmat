# Gamma Spektroskopie - Dash Aplikace

Interaktivní webová aplikace pro kvantitativní analýzu scintilačních spekter pomocí dekonvoluce s kalibračními etalony.

---

## 🎯 Účel aplikace

Tato aplikace slouží k **určení aktivit přirozených radionuklidů** (Ra-226, K-40, Th-232) ve stavebních materiálech měřených scintilačními detektory (CeBr₃, NaI(Tl)). Hlavní výhodou oproti HPGe spektrometrii je **rychlost měření** díky vyšší účinnosti detektorů, což umožňuje screeningovou analýzu velkého počtu vzorků.

### Matematický princip

Aplikace využívá **spektrální dekonvoluci** - rozklad změřeného spektra na příspěvky jednotlivých radionuklidů pomocí jejich referenčních spekter:

```
y_measured = c₁·S_Ra + c₂·S_K + c₃·S_Th + c₄·S_BG + ε
```

kde:
- **y_measured**: Naměřené spektrum vzorku [counts/s v každém kanálu]
- **S_Ra, S_K, S_Th**: Normalizovaná kalibrační spektra etalonů Ra-226, K-40, Th-232
- **S_BG**: Spektrum pozadí detektoru
- **c₁, c₂, c₃, c₄**: Hledané koeficienty (úměrné aktivitám)
- **ε**: Reziduální chyba (statistický šum)

Soustava se řeší pomocí **NNLS** (Non-Negative Least Squares) nebo **OLS** (Ordinary Least Squares) regrese. Pro zlepšení přesnosti se spektrum rozděluje do energetických oblastí (ROI - Regions of Interest) a každá oblast se analyzuje samostatně.

Klíčovou technikou je **rebinning** - mapování spekter z různých detektorů/nastavení do společné kanálové mřížky pomocí lineární transformace `ch_ref = a₀ + a₁·ch_sample`, což umožňuje dekonvoluci i při mírných rozdílech v energetické kalibraci.

---

## 📋 Obsah

- [Účel aplikace](#účel-aplikace)
- [Vstupy a výstupy](#vstupy-a-výstupy)
- [Architektura](#architektura)
- [Matematické metody](#matematické-metody)
- [Závislosti](#závislosti)
- [Instalace a spuštění](#instalace-a-spuštění)
- [Workflow aplikace](#workflow-aplikace)
- [Debugging tipy](#debugging-tipy)

---

## 📥 Vstupy a výstupy

### Požadované vstupy

#### 1. **Kalibrační spektra** (etalony)
Umístění: `app/data/calibration/`

Formát: **SPE soubory** (Maestro formát)
- `Ra_CeBr.SPE` / `Ra_NaI.SPE` - Spektrum Ra-226 etalonu (známá aktivita)
- `K_CeBr.SPE` / `K_NaI.SPE` - Spektrum K-40 etalonu (známá aktivita)
- `Th_CeBr.SPE` / `Th_NaI.SPE` - Spektrum Th-232 etalonu (známá aktivita)
- `BG_CeBr.SPE` / `BG_NaI.SPE` - Spektrum pozadí detektoru

Tyto soubory se načítají automaticky při výběru detektoru.

> **Poznámka**: Pro konverzi z CNF (Genie 2000) do SPE použijte nástroj `Converter/` ve workspace.

#### 2. **Spektra vzorků**
Formát: **SPE soubory** (Maestro formát)

Vzorky se nahrávají přes Upload komponentu v aplikaci. Aplikace automaticky detekuje:
- Live time (doba měření)
- Počet kanálů
- Název vzorku (z `$SPEC_ID` sekce)

#### 3. **Konfigurace detektoru**
Soubor: `config/detectors.yaml` - obsahuje ROI rozsahy, aktivity etalonů, energetickou kalibraci a parametry analýzy.

### Výstupy aplikace

#### 1. **Interaktivní grafy** (Plotly)
- Celé spektrum s ROI oblastmi a kalibračními značkami
- Zoom ROI #1 (Ra/Th) a ROI #2 (K-40) s fitem a komponentami
- Residuální grafy pro kontrolu kvality fitu
- Graf píku Ra-226 @ 186 keV s net area

#### 2. **Tabulka výsledků**
- Aktivity Ra-226, K-40, Th-232 s nejistotami [Bq]
- Ra-226 z analýzy píku 186 keV
- Aktivitní index

#### 3. **Excel export**
Soubor: `accumulated_results_YYYYMMDD_HHMMSS.xlsx` - tabulka výsledků pro všechny analyzované vzorky.

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
│   ├── data_loading.py      # Načítání SPE souborů a YAML konfigurace
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

- **Windows 10/11** (primární platforma)
- Python 3.9+
- 4 GB RAM (pro velké spektra)
- Moderní webový prohlížeč (Chrome, Firefox, Edge)

---

## 🚀 Instalace a spuštění

### 1. Vytvoření virtuálního prostředí

```powershell
cd app/
python -m venv .venv
.venv\Scripts\activate
```

> **Poznámka**: Na Linux/Mac použijte `source .venv/bin/activate`

### 2. Instalace závislostí

```powershell
pip install -r requirements.txt
```

### 3. Příprava dat

Umístit kalibrační spektra do `app/data/calibration/`:
- `Ra_CeBr.SPE` (nebo `Ra_NaI.SPE`)
- `K_CeBr.SPE`
- `Th_CeBr.SPE`
- `BG_CeBr.SPE`

### 4. Spuštění aplikace

```powershell
python app.py
```

Aplikace běží na `http://localhost:8051`

---

## 🔄 Workflow aplikace

### Krok 1: Načtení dat

1. Vybrat detektor (CeBr3 / NaI(Tl))
   - Automaticky se načtou kalibrační SPE soubory (Ra, K, Th, BG)
   - Nastaví se defaultní ROI rozsahy a parametry z YAML
2. Upload SPE souboru vzorku přes drag&drop oblast
3. Aplikace načte spektrum + metadata (live time, název vzorku)

### Krok 2: Kalibrace

**Energetická kalibrace**:
- Zadat známé energie píků [keV]
- Kliknout na odpovídající píky ve spektru
- Fit polynomu: `E = a0 + a1*CH + a2*CH²`
- Koeficienty se použijí **pouze pro display** (osy grafu)

**Channel mapping**:
- Defaultně: identity mapping `(0.0, 1.0)`
- Manuálně upravit `a0`, `a1`
- Nebo zapnout automatickou optimalizaci (switch "Optimalizovat")

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

##  Debugging tipy

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

**Autor**: Miroslav Hýža  
**Email**: miroslav.hyza@suro.cz  
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
- ✅ SPE file loading
- ✅ NNLS/OLS deconvolution
- ✅ Interactive Plotly graphs
