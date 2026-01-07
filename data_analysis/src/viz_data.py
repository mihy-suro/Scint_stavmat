#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
viz_data.py - Načítání a příprava dat pro vizualizaci

Obsahuje:
- load_comparison_data: Načtení Excel souboru
- prepare_comparison_df: Merge HPGe a NaI dat
- apply_uncertainty_expansion: Rozšíření nejistot
- calculate_density: Výpočet hustoty vzorků
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Tuple


def load_comparison_data(file_path: Path) -> pd.DataFrame:
    """
    Načte comparison_input Excel soubor.
    
    Parameters:
    -----------
    file_path : Path
        Cesta k Excel souboru
        
    Returns:
    --------
    DataFrame s daty
    
    Raises:
    -------
    FileNotFoundError: Pokud soubor neexistuje
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Vstupní soubor nenalezen: {file_path}")
    
    df = pd.read_excel(file_path, sheet_name="comparison")
    print(f"Načteno {len(df)} řádků z {file_path.name}")
    print(f"Metody: {df['Metoda'].unique()}")
    return df


def prepare_comparison_df(df: pd.DataFrame, method_nai: str = "NaI(Tl)") -> pd.DataFrame:
    """
    Připraví DataFrame pro porovnání - merge HPGe a NaI metod.
    
    Spojí data z HPGe a zvolené NaI metody podle sloupce 'Kniha analýz'.
    
    Parameters:
    -----------
    df : DataFrame
        Long-format data s metodami v sloupci 'Metoda'
    method_nai : str
        Metoda NaI pro porovnání:
        - 'NaI(Tl)' pro dekonvoluční analýzu
        - 'NaI(Tl) – 186 keV' pro analýzu 186 keV píku
    
    Returns:
    --------
    DataFrame se sloupci _HPGe a _NaI sufixy
    """
    df_hpge = df[df["Metoda"] == "HPGe"].copy()
    df_nai = df[df["Metoda"] == method_nai].copy()
    
    # Merge na základě knihy analýz
    df_compare = df_hpge.merge(
        df_nai,
        on="Kniha analýz",
        suffixes=("_HPGe", "_NaI"),
        how="inner"
    )
    
    print(f"Porovnání {method_nai}: {len(df_compare)} vzorků")
    return df_compare


def apply_uncertainty_expansion(
    df: pd.DataFrame, 
    elements: Dict[str, Tuple[str, str]], 
    rel_unc: float = 0.10
) -> pd.DataFrame:
    """
    Aplikuje rozšířenou nejistotu na NaI měření.
    
    Pro každý prvek zajistí, že nejistota NaI měření je minimálně
    rel_unc * aktivita. Toto řeší případy, kdy jsou nejistoty
    podhodnocené.
    
    Parameters:
    -----------
    df : DataFrame
        Data s _NaI sloupci
    elements : dict
        Slovník {název_prvku: (sloupec_aktivity, sloupec_nejistoty)}
    rel_unc : float
        Minimální relativní nejistota (default 0.10 = 10%)
        
    Returns:
    --------
    DataFrame s upravenými nejistotami
    """
    df = df.copy()
    
    for element_name, (activity_col, uncertainty_col) in elements.items():
        nai_act = f"{activity_col}_NaI"
        nai_unc = f"{uncertainty_col}_NaI"
        
        if nai_act in df.columns and nai_unc in df.columns:
            # Vektorizovaná verze - výpočet minimální nejistoty
            min_unc = df[nai_act].abs() * rel_unc
            
            # Aktualizace nejistot - použij maximum ze stávající a minimální
            mask = pd.notna(df[nai_act])
            df.loc[mask, nai_unc] = np.maximum(
                df.loc[mask, nai_unc], 
                min_unc[mask]
            )
    
    return df


def calculate_density(df: pd.DataFrame) -> pd.Series:
    """
    Vypočítá hustotu vzorků z hmotnosti a objemu.
    
    Automaticky detekuje správné názvy sloupců (s/bez suffixu).
    
    Parameters:
    -----------
    df : DataFrame
        Data s hmotností a objemem
        
    Returns:
    --------
    Series s hustotou [g/cm³]
    """
    # Detekce sloupců
    weight_col = 'Hmotnost [kg]_HPGe' if 'Hmotnost [kg]_HPGe' in df.columns else 'Hmotnost [kg]'
    volume_col = 'Objem [l]_HPGe' if 'Objem [l]_HPGe' in df.columns else 'Objem [l]'
    
    # Hustota = hmotnost [kg] / objem [l] = [kg/l] = [g/cm³]
    return df[weight_col] / df[volume_col]


def get_column_names(df: pd.DataFrame) -> dict:
    """
    Vrátí slovník se správnými názvy sloupců.
    
    Automaticky detekuje, zda jsou sloupce s _HPGe suffixem nebo bez.
    
    Parameters:
    -----------
    df : DataFrame
        Data k analýze
        
    Returns:
    --------
    dict s klíči 'weight', 'volume', 'description'
    """
    return {
        'weight': 'Hmotnost [kg]_HPGe' if 'Hmotnost [kg]_HPGe' in df.columns else 'Hmotnost [kg]',
        'volume': 'Objem [l]_HPGe' if 'Objem [l]_HPGe' in df.columns else 'Objem [l]',
        'description': 'Popis vzorku_HPGe' if 'Popis vzorku_HPGe' in df.columns else 'Popis vzorku'
    }
