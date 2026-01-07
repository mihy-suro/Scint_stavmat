# Data Analysis Pipeline

Porovnání výsledků NaI(Tl) scintilační spektrometrie s HPGe referenčními měřeními.

---

## 📁 Struktura

```
data_analysis/
├── main.py              # Entry point
├── config.yaml          # Konfigurace pipeline
├── input/               # Vstupní xlsx soubory
│   ├── labsys_vysledky.xlsx         # HPGe referenční data (Bq/kg)
│   └── accumulated_results_*.xlsx   # NaI výsledky z app/ (Bq)
├── output/              # Výstupy
│   ├── comparison_input.xlsx        # Spojená data (vše v Bq/kg)
│   └── comparison_results_plot.html # Interaktivní vizualizace
└── src/                 # Python moduly
    ├── build_input.py               # Spojení dat + konverze Bq → Bq/kg
    ├── config_loader.py             # Načítání konfigurace
    ├── density_correction_utils.py  # Optimalizace korekčních faktorů
    ├── visualize.py                 # Hlavní vizualizační modul
    ├── viz_config.py                # VizConfig dataclass, konstanty
    ├── viz_data.py                  # Načítání a příprava dat
    ├── viz_stats.py                 # Statistické funkce (z-score, RMSE)
    ├── viz_scatter.py               # Helper funkce pro scatter ploty
    └── viz_rmse_chart.py            # Dumbbell chart pro RMSE
```

> **Poznámka k jednotkám**: Aplikace exportuje aktivity v **Bq** (celková aktivita). Pipeline automaticky dělí hmotností vzorku pro převod na **Bq/kg** (specifická aktivita) kompatibilní s HPGe daty.

---

## 🚀 Použití

### 1. Příprava vstupních dat

Umístěte do `input/`:
- **HPGe data**: `labsys_vysledky.xlsx` (export z LabSys)
- **NaI data**: `accumulated_results_*.xlsx` (export z Dash aplikace)

### 2. Spuštění pipeline

```powershell
cd data_analysis
python main.py
```

### 3. Výsledky

Otevřete `output/comparison_results_plot.html` v prohlížeči.

---

## ⚙️ Konfigurace

Veškerá nastavení v `config.yaml`:

```yaml
input:
  directory: "input"
  hpge_file: "labsys_vysledky.xlsx"
  accumulated_results_file: ""  # prázdné = auto-detect nejnovější

output:
  directory: "output"

correction:
  model: "scaled_exponential_quadratic"  # korekce samoabsorpce
  reference_density: 1.0                 # g/cm³

outliers:
  threshold: 2.5  # z-score práh
```

### Dostupné korekční modely

| Model | Vzorec |
|-------|--------|
| `exponential` | $A_{corr} = A \cdot e^{b \cdot \rho}$ |
| `linear` | $A_{corr} = A \cdot (1 + b \cdot \rho)$ |
| `quadratic_centered` | $A_{corr} = A \cdot [1 + b \cdot \Delta\rho + c \cdot \Delta\rho^2]$ |
| `scaled_exponential_quadratic` | $A_{corr} = a \cdot A \cdot e^{b \cdot \Delta\rho + c \cdot \Delta\rho^2}$ |

---

## 📊 Výstupy

### Interaktivní graf (`comparison_results_plot.html`)

5-řádkový layout (2 sloupce: před | po korekci):

| Řádek | Obsah |
|-------|-------|
| 1 | K-40 (před \| po korekci) |
| 2 | Th-232 (před \| po korekci) |
| 3 | Ra-226 z dekonvoluce (před \| po korekci) |
| 4 | Ra-226 z 186 keV píku (před \| po korekci) |
| 5 | RMSE dumbbell chart (zlepšení po korekci) |

Každý scatter plot obsahuje:
- Body s error bary (nejistoty měření)
- Barva podle hmotnosti vzorku (colorbar)
- Identifikované outliers (trojúhelníky, z-score > threshold)
- 1:1 referenční linie
- Anotace s korekčními koeficienty (a, b, c)

### Statistické shrnutí (konzole)

```
Ra-226:
  Původní:    R²=0.94, RMSE=11.1 Bq/kg
  Korigované: R²=0.97, RMSE=5.8 Bq/kg
  Zlepšení:   ΔR²=+0.03, RMSE redukce=48.0%

Ra-226 (186 keV):
  Původní:    R²=0.83, RMSE=30.2 Bq/kg
  Korigované: R²=0.91, RMSE=10.0 Bq/kg
  Zlepšení:   ΔR²=+0.08, RMSE redukce=66.8%
```

---

## 🧩 Moduly

| Modul | Popis |
|-------|-------|
| `viz_config.py` | `VizConfig` dataclass, načítání konstant z config.yaml |
| `viz_data.py` | `load_comparison_data()`, `prepare_comparison_df()`, `apply_uncertainty_expansion()` |
| `viz_stats.py` | `calculate_zscore()`, `calculate_statistics()`, `identify_outliers()` |
| `viz_scatter.py` | `add_scatter_trace()`, `add_identity_line()`, `plot_element_comparison()` |
| `viz_rmse_chart.py` | `collect_rmse_data()`, `add_rmse_dumbbell()` |
| `visualize.py` | `create_visualization()`, `run_visualization()` - orchestrace |

---

## 🔧 Závislosti

- `pandas`, `numpy`, `scipy`
- `plotly`
- `openpyxl`
- `pyyaml`

Instalace: `pip install -e .` z kořenového adresáře projektu.
