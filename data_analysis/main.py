#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - Hlavní orchestrační skript pro analýzu porovnání HPGe vs NaI(Tl)

Workflow:
1. Načte HPGe referenční data z labsys_vysledky.xlsx
2. Načte NaI výsledky z accumulated_results_*.xlsx (z aplikace)
3. Vytvoří kombinovaný vstupní soubor comparison_input.xlsx
4. Spustí vizualizaci a vytvoří comparison_results_*.html

Konfigurace:
    Veškerá konfigurace je v souboru config.yaml

Použití:
    python main.py
"""

from pathlib import Path
from datetime import datetime

from src.build_input import build_comparison_input
from src.visualize import run_visualization
from src.config_loader import get_config, get_input_files, get_output_dir, get_outlier_threshold


def find_latest_accumulated_results(directory: Path) -> Path:
    """Najde nejnovější accumulated_results soubor v adresáři."""
    pattern = "accumulated_results_*.xlsx"
    files = list(directory.glob(pattern))
    
    if not files:
        raise FileNotFoundError(
            f"Žádný soubor odpovídající vzoru '{pattern}' nenalezen v {directory}.\n"
            f"Zkontrolujte, že jste exportovali výsledky z aplikace."
        )
    
    # Seřadit podle názvu (obsahuje timestamp)
    latest = sorted(files, key=lambda x: x.name)[-1]
    return latest


def main():
    """Hlavní funkce - spustí celou pipeline."""
    # Načtení konfigurace
    config = get_config()
    input_config = get_input_files()
    
    script_dir = Path(__file__).parent.resolve()
    output_dir = (script_dir / get_output_dir()).resolve()
    
    print("\n" + "="*70)
    print("  ANALÝZA POROVNÁNÍ: HPGe vs NaI(Tl)")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*70)
    print(f"\n  Konfigurace: config.yaml")
    print(f"  Model: {config['correction']['model']}")
    print(f"  Outlier práh: {config['outliers']['threshold']}σ")
    
    # ------------------------
    # 1) Určení vstupních souborů
    # ------------------------
    input_dir = (script_dir / input_config.get('directory', 'input')).resolve()
    
    hpge_file = input_dir / input_config['hpge_file']
    hpge_sheet = input_config['hpge_sheet']
    
    if input_config['accumulated_results_file']:
        acc_file = input_dir / input_config['accumulated_results_file']
    else:
        print("\nHledám nejnovější accumulated_results soubor...")
        acc_file = find_latest_accumulated_results(input_dir)
        print(f"Nalezen: {acc_file.name}")
    
    # Kontrola existence
    if not hpge_file.exists():
        raise FileNotFoundError(
            f"HPGe soubor nenalezen: {hpge_file}\n"
            f"Umístěte soubor '{input_config['hpge_file']}' do adresáře {input_dir}"
        )
    
    if not acc_file.exists():
        raise FileNotFoundError(
            f"Accumulated results soubor nenalezen: {acc_file}\n"
            f"Exportujte výsledky z aplikace nebo upravte accumulated_results_file v config.yaml."
        )
    
    print(f"\nVstupní soubory:")
    print(f"  Vstup:    {input_dir}")
    print(f"  HPGe:     {hpge_file.name}")
    print(f"  NaI(Tl):  {acc_file.name}")
    print(f"  Výstup:   {output_dir}")
    
    # ------------------------
    # 2) Konstrukce vstupního souboru
    # ------------------------
    comparison_file = build_comparison_input(
        hpge_file=hpge_file,
        acc_file=acc_file,
        output_dir=output_dir,
        hpge_sheet=hpge_sheet
    )
    
    # ------------------------
    # 3) Vizualizace
    # ------------------------
    output_html = run_visualization(
        input_file=comparison_file,
        output_dir=output_dir,
        outlier_threshold=get_outlier_threshold()
    )
    
    # ------------------------
    # 4) Shrnutí
    # ------------------------
    print("\n" + "="*70)
    print("  PIPELINE DOKONČENA")
    print("="*70)
    print(f"\nVytvořené soubory:")
    print(f"  1. Vstupní data:  {comparison_file.name}")
    print(f"  2. Vizualizace:   {output_html.name}")
    print(f"\nPro zobrazení grafů otevřete HTML soubor v prohlížeči.")
    print("="*70 + "\n")
    
    return comparison_file, output_html


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as e:
        print(f"\n❌ CHYBA: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ NEOČEKÁVANÁ CHYBA: {e}")
        raise
