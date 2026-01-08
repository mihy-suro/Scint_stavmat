# Scint_stavmat

**Analýza scintilačních spekter pro NaI(Tl) a CeBr₃ detektory**

Projekt obsahuje:
1. **Dash aplikaci** pro dekonvoluční analýzu γ-spekter
2. **Pipeline** pro porovnání výsledků s HPGe referenčními měřeními

---

## 📁 Struktura

```
├── app/                    # Interaktivní Dash aplikace
│   ├── app.py              # Entry point
│   ├── layout.py           # UI komponenty
│   ├── processing.py       # Zpracování spekter
│   ├── callbacks/          # Dash callbacky
│   ├── utils/              # Pomocné moduly
│   ├── config/             # Konfigurace detektorů (YAML)
│   ├── data/calibration/   # Kalibrační spektra (SPE)
│   └── README.md           # Dokumentace aplikace
├── data_analysis/          # HPGe vs NaI(Tl) porovnání
│   ├── main.py             # Pipeline orchestrace
│   ├── config.yaml         # Nastavení analýzy
│   ├── input/              # Vstupní xlsx soubory
│   ├── output/             # Výstupní grafy a data
│   ├── src/                # Python moduly
│   │   ├── visualize.py    # Hlavní vizualizace
│   │   ├── viz_*.py        # Pomocné moduly (config, data, stats, scatter, rmse)
│   │   ├── build_input.py  # Spojení HPGe + NaI dat
│   │   └── density_correction_utils.py  # Korekce samoabsorpce
│   └── README.md           # Dokumentace pipeline
├── Spektra/                # Spektra vzorků (SPE, CNF)
│   ├── naitl/              # NaI(Tl) spektra
│   └── cebr/               # CeBr₃ spektra
└── pyproject.toml          # Závislosti a metadata
```

---

## 🚀 Rychlý start

### Instalace

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

### Spuštění aplikace

```powershell
cd app
python app.py
```
→ http://localhost:8051

### Porovnání s HPGe

Uživatel poskytne:
- HPGe referenční hodnoty (`labsys_vysledky.xlsx`)
- NaI výsledky z aplikace (`accumulated_results_*.xlsx`)

```powershell
cd data_analysis
python main.py
```
→ Otevřete `comparison_results_plot.html`

---

## 📖 Dokumentace

- **[app/README.md](app/README.md)** - Dokumentace Dash aplikace (workflow, konfigurace)
- **[data_analysis/README.md](data_analysis/README.md)** - Dokumentace porovnávací pipeline
- **[data_analysis/config.yaml](data_analysis/config.yaml)** - Nastavení korekčních modelů

---

## 📐 Metodika (přehled)

| Metoda | Popis |
|--------|-------|
| **Dekonvoluce** | Rozklad spektra na Ra-226, K-40, Th-232 pomocí NNLS/OLS regrese |
| **Rebinning** | Kanálové zarovnání spekter pomocí energetické kalibrace |
| **186 keV analýza** | Alternativní určení Ra-226 z net area nízkoenergetického píku |
| **Korekce samoabsorpce** | Hustotně závislá transformace: $A_{corr} = a \cdot A \cdot e^{b \cdot \Delta\rho + c \cdot \Delta\rho^2}$ |

---

## 🔧 Požadavky

- Python ≥ 3.9
- Windows 10/11 (primární platforma)
- Závislosti: `dash`, `plotly`, `pandas`, `numpy`, `scipy`, `openpyxl`, `pyyaml`