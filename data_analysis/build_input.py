#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_input.py - Konstrukce vstupního souboru pro vizualizaci

Spojuje HPGe referenční data z labsys_vysledky.xlsx s NaI výsledky 
z accumulated_results aplikace. Vytváří long-format tabulku se třemi
metodami na vzorek:
- HPGe (referenční měření)
- NaI(Tl) (scintilační měření - dekonvoluce pro Ra/K/Th)
- NaI(Tl) – 186 keV (pouze Ra-226 z 186 keV píku)
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional


# ============================================================
# KONSTANTY
# ============================================================
EXPECTED_COLS_HPGE = [
    "Kniha analýz", "Popis vzorku", "ID měření", "Objem [l]",
    "Hmotnost [kg]", "Metoda", "Ref. Dat",
    "A_Ra", "U_Ra", "A_K", "U_K", "A_Th", "U_Th",
]

EXPECTED_COLS_ACC = [
    "sample_name",
    "Ra", "Ra_err",
    "Ra_186", "Ra_186_err",
    "K", "K_err",
    "Th", "Th_err",
]


def load_hpge_data(file_path: Path, sheet_name: str = "data") -> pd.DataFrame:
    """
    Načte HPGe referenční data z Excel souboru.
    
    Parameters:
    -----------
    file_path : Path
        Cesta k labsys_vysledky.xlsx
    sheet_name : str
        Název listu s daty
    
    Returns:
    --------
    DataFrame s HPGe daty
    """
    if not file_path.exists():
        raise FileNotFoundError(f"HPGe soubor nenalezen: {file_path}")
    
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    
    # Kontrola sloupců
    missing = [c for c in EXPECTED_COLS_HPGE if c not in df.columns]
    if missing:
        raise RuntimeError(f"V HPGe souboru chybí sloupce: {missing}")
    
    # Filtrovat pouze HPGe řádky (pokud soubor obsahuje více metod)
    if "Metoda" in df.columns:
        df_hpge = df[df["Metoda"] == "HPGe"].copy()
    else:
        df_hpge = df.copy()
        df_hpge["Metoda"] = "HPGe"
    
    print(f"  Načteno {len(df_hpge)} HPGe měření z {file_path.name}")
    return df_hpge


def load_accumulated_results(file_path: Path, sheet_name: str = "Results") -> pd.DataFrame:
    """
    Načte NaI výsledky z accumulated_results souboru.
    
    Parameters:
    -----------
    file_path : Path
        Cesta k accumulated_results_*.xlsx
    sheet_name : str
        Název listu s výsledky
    
    Returns:
    --------
    DataFrame s NaI výsledky
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Accumulated results soubor nenalezen: {file_path}")
    
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    
    # Kontrola sloupců
    missing = [c for c in EXPECTED_COLS_ACC if c not in df.columns]
    if missing:
        raise RuntimeError(f"V accumulated results chybí sloupce: {missing}")
    
    print(f"  Načteno {len(df)} NaI měření z {file_path.name}")
    return df


def merge_data(df_hpge: pd.DataFrame, df_acc: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """
    Spojí HPGe a NaI data přes ID měření.
    
    Returns:
    --------
    Tuple[DataFrame, int] : Sloučená data a počet chybějících párů
    """
    # Oříznutí mezer
    df_hpge = df_hpge.copy()
    df_acc = df_acc.copy()
    df_hpge["ID měření"] = df_hpge["ID měření"].astype(str).str.strip()
    df_acc["sample_name"] = df_acc["sample_name"].astype(str).str.strip()
    
    # Sloučení
    df_merge = df_hpge.merge(
        df_acc,
        left_on="ID měření",
        right_on="sample_name",
        how="left",
        validate="one_to_one"
    )
    
    n_missing = df_merge["Ra"].isna().sum()
    n_matched = len(df_merge) - n_missing
    
    print(f"  Spárováno: {n_matched} vzorků")
    if n_missing > 0:
        missing_ids = df_merge[df_merge["Ra"].isna()]["ID měření"].tolist()
        print(f"  ⚠️ Bez NaI dat: {n_missing} vzorků")
        for mid in missing_ids[:5]:
            print(f"     - {mid}")
        if len(missing_ids) > 5:
            print(f"     ... a dalších {len(missing_ids) - 5}")
    
    return df_merge, n_missing


def create_long_format(df_merge: pd.DataFrame) -> pd.DataFrame:
    """
    Vytvoří long-format tabulku se třemi metodami na vzorek.
    
    Metody:
    - HPGe: původní referenční hodnoty
    - NaI(Tl): Ra/K/Th z dekonvoluce
    - NaI(Tl) – 186 keV: pouze Ra z 186 keV píku
    
    Returns:
    --------
    DataFrame v long formátu
    """
    base_cols = EXPECTED_COLS_HPGE
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1) HPGe řádky - původní hodnoty
    df_hpge_out = df_merge[base_cols].copy()
    
    # 2) NaI(Tl) řádky - dekonvoluce
    df_nai = df_merge.copy()
    df_nai["Metoda"] = "NaI(Tl)"
    df_nai["Ref. Dat"] = today
    df_nai["A_Ra"] = df_nai["Ra"]
    df_nai["U_Ra"] = df_nai["Ra_err"]
    df_nai["A_K"] = df_nai["K"]
    df_nai["U_K"] = df_nai["K_err"]
    df_nai["A_Th"] = df_nai["Th"]
    df_nai["U_Th"] = df_nai["Th_err"]
    df_nai_out = df_nai[base_cols].copy()
    
    # 3) NaI(Tl) – 186 keV řádky - pouze Ra
    df_186 = df_merge.copy()
    df_186["Metoda"] = "NaI(Tl) – 186 keV"
    df_186["Ref. Dat"] = today
    df_186["A_Ra"] = df_186["Ra_186"]
    df_186["U_Ra"] = df_186["Ra_186_err"]
    df_186["A_K"] = pd.NA
    df_186["U_K"] = pd.NA
    df_186["A_Th"] = pd.NA
    df_186["U_Th"] = pd.NA
    df_186_out = df_186[base_cols].copy()
    
    # Spojení
    df_out = pd.concat([df_hpge_out, df_nai_out, df_186_out], ignore_index=True)
    df_out = df_out.sort_values(["Kniha analýz", "Metoda"]).reset_index(drop=True)
    
    return df_out


def build_comparison_input(
    hpge_file: Path,
    acc_file: Path,
    output_dir: Path,
    hpge_sheet: str = "data",
    acc_sheet: str = "Results"
) -> Path:
    """
    Hlavní funkce pro vytvoření vstupního souboru pro vizualizaci.
    
    Parameters:
    -----------
    hpge_file : Path
        Cesta k labsys_vysledky.xlsx
    acc_file : Path
        Cesta k accumulated_results_*.xlsx
    output_dir : Path
        Adresář pro výstupní soubor
    
    Returns:
    --------
    Path : Cesta k vytvořenému souboru
    """
    print("\n" + "="*60)
    print("KONSTRUKCE VSTUPNÍHO SOUBORU PRO VIZUALIZACI")
    print("="*60)
    
    # 1) Načtení dat
    print("\n1) Načítání HPGe dat...")
    df_hpge = load_hpge_data(hpge_file, hpge_sheet)
    
    print("\n2) Načítání NaI dat...")
    df_acc = load_accumulated_results(acc_file, acc_sheet)
    
    # 2) Sloučení
    print("\n3) Spojování dat...")
    df_merge, n_missing = merge_data(df_hpge, df_acc)
    
    # 3) Long format
    print("\n4) Vytváření long-format tabulky...")
    df_out = create_long_format(df_merge)
    
    # 4) Uložení
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = output_dir / "comparison_input.xlsx"
    
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        df_out.to_excel(writer, sheet_name="comparison", index=False)
    
    print(f"\n5) Uloženo: {out_file.name}")
    print(f"   Počet řádků: {len(df_out)}")
    print(f"   - HPGe: {len(df_out[df_out['Metoda'] == 'HPGe'])}")
    print(f"   - NaI(Tl): {len(df_out[df_out['Metoda'] == 'NaI(Tl)'])}")
    print(f"   - NaI(Tl) – 186 keV: {len(df_out[df_out['Metoda'] == 'NaI(Tl) – 186 keV'])}")
    print("="*60 + "\n")
    
    return out_file


if __name__ == "__main__":
    # Pro samostatné testování
    script_dir = Path(__file__).parent
    
    hpge = script_dir / "labsys_vysledky.xlsx"
    acc = script_dir / "accumulated_results_test.xlsx"
    
    if hpge.exists() and acc.exists():
        build_comparison_input(hpge, acc, script_dir)
    else:
        print("Pro testování spusťte přes main.py")
