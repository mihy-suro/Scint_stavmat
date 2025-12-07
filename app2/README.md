# Dash aplikace pro sekvenční analýzu scintilačních spekter (v2)

## 🎯 Popis

Zjednodušená webová aplikace pro sekvenční analýzu jednotlivých gamma spekter z CeBr₃ a NaI(Tl) scintilačních detektorů. Umožňuje dekonvoluci spekter na základě kalibračních vzorků (Ra-226, K-40, Th-232) a výpočet aktivit radionuklidů.

## 🚀 Spuštění

```bash
cd app2
python app.py
```

Aplikace se spustí na `http://localhost:8051`

## 📁 Struktura Excel souboru

### **Povinné sheety:**

#### 1. **"Kalibrace"**
- Sloupce: `Channel | Ra | K | Th`
- Řádek 12+: Data (první 11 řádků = metadata)
- Kalibrační spektra normalizovaná na pravděpodobnostní hustotu

#### 2. **"Vzorky"**
- Řádek 1: Názvy vzorků (např. `COUNTS_5019-2024`)
- Řádek 3: Live times [s]
- Řádek 12+: Data `Channel | Vzorek1 | Vzorek2 | ...`

#### 3. **"Pozadí"**
- Řádek 3: Live time [s]
- Řádek 12+: Data `Channel | BG`

#### 4. **"Parametry"** (nový!)
- 2 sloupce: `Parametr | Hodnota`

```
Parametr       Hodnota
Ra_faktor      13.9
K_faktor       212
Th_faktor      7.4
ref_a0         9.6229
ref_a1         1.3793
ref_a2         0
manual_a0      9.62228359
manual_a1      1.37495787
skip_rows      11
cut_channel    150
```

## 🎯 Workflow

1. **Nahrát Excel soubor** - automatická validace struktury
2. **Vybrat vzorek** z dropdownu (naplněno ze sloupců Excelu)
3. **Nastavit parametry** (předvyplněno z sheetu "Parametry"):
   - Energetická kalibrace (a₀, a₁, a₂)
   - Cut channel (vynulování prvních N kanálů)
   - Optimalizace ON/OFF
4. **Spustit analýzu** tlačítkem
5. **Zobrazení výsledků**:
   - Graf: naměřené spektrum + OLS fit + NNLS fit + pozadí
   - Tabulka: Ra, K, Th aktivity [Bq], R², stderr
   - Export CSV

## 📊 Výstupy

### Graf
- X-osa: Energie [keV]
- Y-osa: Intenzita [CPS] (po odečtení pozadí)
- Čáry: Naměřené (černá), Pozadí (šedá), Fit OLS (zelená), Fit NNLS (oranžová)

### Tabulka výsledků
| Method | Ra (Bq) | K (Bq) | Th (Bq) | Ra_stderr | K_stderr | Th_stderr | R² | Adj R² |
|--------|---------|---------|---------|-----------|-----------|-----------|-----|--------|
| OLS    | 0.2451  | 0.5321  | 0.1893  | 0.015     | 0.022     | 0.018     | 0.956 | 0.954 |
| NNLS   | 0.2487  | 0.5298  | 0.1901  | 0.016     | 0.023     | 0.019     | 0.955 | 0.953 |

## 🔧 Technické detaily

### Zpracování dat:
1. Načtení parametrů z Excelu
2. Normalizace kalibračních spekter → pravděpodobnostní hustota
3. Normalizace vzorků a pozadí → CPS (dělení live time)
4. Odečtení pozadí
5. Vynulování prvních `cut_channel` kanálů
6. Rebinning (korekce energetické kalibrace)
7. Regrese OLS a NNLS (s Poissonovou korekcí šumu)
8. Konverze na aktivity [Bq] pomocí faktorů z Excelu

### Energetická kalibrace:
$$E = a_0 + a_1 \cdot CH + a_2 \cdot CH^2$$

- **Referenční** (a₀, a₁, a₂) - pro kalibrační spektra
- **Vzorků** - optimalizovaná nebo manuální

## 🆚 Rozdíly oproti app/

| Funkce | app/ (v1) | app2/ (v2) |
|--------|-----------|------------|
| **Režim** | Dávkový (všechny vzorky najednou) | Sekvenční (po jednom) |
| **Sheety** | Konfigurovatelné názvy | Fixní názvy |
| **Parametry** | UI inputy | Z Excelu + editovatelné v UI |
| **Výstupy** | 4 záložky (kalibrace, vzorky, souhrn, diagnostika) | 1 stránka (graf + tabulka) |
| **Složitost** | Vysoká (520 řádků callbacks) | Nízká (380 řádků callbacks) |

## 💡 Tipy

- **Optimalizace kalibrace**: Použij pro první vzorek, pak zkopíruj hodnoty do manuální kalibrace pro rychlejší zpracování dalších
- **Cut channel**: Zvyš, pokud vidíš hodně šumu v nízkých energiích
- **NNLS vs OLS**: NNLS garantuje nezáporné aktivity (fyzikálně správnější)
- **Export**: Tlačítko "Export CSV" uloží výsledky pro aktuální vzorek

## 📝 Poznámky

- Port: **8051** (původní app běží na 8050)
- Konverzní faktory nyní v Excelu (flexibilnější pro různé detektory)
- Validace: kontroluje existenci všech povinných sheetů
- Error handling: alert komponenty pro chyby
