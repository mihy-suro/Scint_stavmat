# Scint_stavmat

**Analýza scintilačních spekter - dekonvoluce a kalibrace pro NaI(Tl) a CeBr₃ detektory**

Projekt obsahuje interaktivní Dash aplikaci pro analýzu γ-spekter a pipeline pro porovnání výsledků NaI(Tl) spektroskopie s referenčními HPGe měřeními.

---

## 📁 Struktura projektu

### `app/` - Interaktivní Dash aplikace

Webová aplikace pro analýzu jednotlivých vzorků pomocí scintilačních detektorů (NaI(Tl), CeBr₃).

**Funkce:**
- Načítání spekter ze souborů SPE (formát Ortec Maestro)
- Ruční kalibrace peaků (Ra-226, Th-232, K-40)
- Dekonvoluční analýza s ROI fittingem (Ra/Th a K-40 oblasti)
- Alternativní analýza Ra-226 z 186 keV píku
- Export výsledků do XLSX

**Spuštění:**
```bash
cd app
python app.py
```
Aplikace běží na http://localhost:8051

**Konfigurace:**
- `app/config/detectors.yaml` - parametry detektorů, efektivnosti, kalibrace

---

### `data_analysis/` - HPGe vs NaI(Tl) komparace

Pipeline pro porovnání výsledků NaI(Tl) měření s HPGe referenčními hodnotami.

**Workflow:**
1. Načte HPGe data (`labsys_vysledky.xlsx`)
2. Načte NaI výsledky z aplikace (`accumulated_results_*.xlsx`)
3. Vytvoří kombinovaný vstup (`comparison_input.xlsx`)
4. Aplikuje korekce na samoabsorpci (hustotně závislé)
5. Vygeneruje interaktivní vizualizaci (`comparison_results_plot.html`)

**Spuštění:**
```bash
cd data_analysis
python main.py
```

**Konfigurace:**
- `data_analysis/config.yaml` - vstupní soubory, korekční model, outlier threshold

**Korekční modely:**
- `scaled_exponential_quadratic`: $A_{corr} = a \times A \times \exp(b \times \Delta\rho + c \times \Delta\rho^2)$
- Outlier detekce: z-score = $|A_{HPGe} - A_{NaI}| / \sqrt{U_{HPGe}^2 + U_{NaI}^2}$

---

## 🚀 Instalace

### Požadavky
- Python ≥ 3.9
- Doporučeno: [uv](https://github.com/astral-sh/uv) pro správu závislostí

### Instalace závislostí

**S uv (doporučeno):**
```bash
uv sync
```

**S pip:**
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e .
```

---

## 📊 Použití

### 1. Analýza vzorků (Dash aplikace)

1. Spusťte aplikaci: `python app/app.py`
2. Nahrajte YAML konfiguraci vzorků
3. Proveďte manuální kalibraci (Ra, Th, K)
4. Spusťte dekonvoluční analýzu nebo 186 keV analýzu
5. Exportujte výsledky do Excel

### 2. Porovnání s HPGe

1. Exportujte výsledky z aplikace (`accumulated_results_*.xlsx`)
2. Upravte `data_analysis/config.yaml` (volitelně)
3. Spusťte: `python data_analysis/main.py`
4. Otevřete `comparison_results_plot.html` v prohlížeči

---

## 📐 Metodika

### Dekonvoluční analýza
- **ROI #1 (Ra/Th)**: Multiplet fitting Ra-226 (609, 352, 295, 242 keV) + Th-232 (583, 338, 911 keV)
- **ROI #2 (K-40)**: Singlet 1461 keV
- **Regrese**: Weighted least squares s Poisson nejistotami
- **Calibration**: Polynomická E(ch) = a₀ + a₁·ch + a₂·ch²

### Ra-226 186 keV analýza
- Jednoduchá net-area metoda pro nízkoenergetický pík
- Linear background odhad
- Nezávislá alternativa k dekonvoluci

### Korekce na samoabsorpci
- Empirická transformace: $f(\rho) = a \times \exp(b \times \Delta\rho + c \times \Delta\rho^2)$
- Referenční hustota: $\rho_{ref} = 1.0 \, \mathrm{g/cm^3}$
- Optimalizace parametrů pomocí scipy minimize

---

## 📝 Závislosti

Hlavní balíčky:
- `dash` + `dash-bootstrap-components` - webová aplikace
- `plotly` - interaktivní grafy
- `pandas`, `numpy`, `scipy` - analýza dat
- `scikit-learn`, `statsmodels` - regrese
- `openpyxl` - Excel I/O
- `pyyaml` - konfigurace

---

## 📄 Licence

Tento projekt je určen pro výzkumné účely.

---

## 👤 Autor

Projekt vytvořen v rámci výzkumu scintilační spektroskopie stavebních materiálů.
