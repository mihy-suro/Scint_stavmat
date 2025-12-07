# Kalibrace spekter - App3

Minimalistická aplikace pro manuální kalibraci scintilačních spekter.

## Funkce

- Načtení kalibračních spekter z Excel souboru (list "Kalibrace")
- Zobrazení spektra v závislosti na kanálech
- Manuální výběr píků klikáním do grafu
- Přiřazení známých energií (238, 295, 352, 609, 1461 keV)
- Automatický výpočet lineární kalibrace E = a₀ + a₁·CH
- Zobrazení reziduí pro kontrolu kvality

## Spuštění

```bash
cd app3
python app.py
```

Aplikace běží na http://localhost:8052

## Použití

1. Nahrajte Excel soubor s kalibračními spektry
2. Vyberte spektrum ze seznamu
3. Klikněte na pík v grafu
4. Stiskněte tlačítko "Set" u odpovídající energie
5. Opakujte pro další píky (min. 2)
6. Klikněte "Vypočítat kalibraci"
7. Zkopírujte hodnoty a₀ a a₁ do hlavní aplikace
