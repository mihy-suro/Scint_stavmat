#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
viz_stats.py - Statistické funkce pro vizualizaci

Obsahuje:
- calculate_zscore: Výpočet z-score pro identifikaci outlierů
- calculate_statistics: Komplexní statistiky porovnání
"""

import numpy as np
from scipy import stats
from typing import Dict, Any


def calculate_zscore(
    A_hpge: np.ndarray, 
    A_nai: np.ndarray, 
    U_hpge: np.ndarray, 
    U_nai: np.ndarray
) -> np.ndarray:
    """
    Vypočítá z-score (normalizované residuum) pro identifikaci outlierů.
    
    z = |A_HPGe - A_NaI| / √(U_HPGe² + U_NaI²)
    
    Vzorky s vysokým z-score (typicky > 3) jsou považovány za outliers,
    což může indikovat:
    - Nehomogenitu vzorku
    - Chybu měření
    - Problém s geometrií detektoru
    
    Parameters:
    -----------
    A_hpge : array
        Aktivity měřené HPGe [Bq/kg]
    A_nai : array
        Aktivity měřené NaI(Tl) [Bq/kg]
    U_hpge : array
        Nejistoty HPGe měření [Bq/kg]
    U_nai : array
        Nejistoty NaI měření [Bq/kg]
    
    Returns:
    --------
    array : z-score pro každý vzorek
    """
    combined_uncertainty = np.sqrt(U_hpge**2 + U_nai**2)
    # Ochrana proti dělení nulou
    combined_uncertainty = np.maximum(combined_uncertainty, 1e-10)
    return np.abs(A_hpge - A_nai) / combined_uncertainty


def calculate_statistics(x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    """
    Vypočítá kompletní statistiky pro porovnání dvou měření.
    
    Parameters:
    -----------
    x : array
        Referenční hodnoty (HPGe) [Bq/kg]
    y : array
        Porovnávané hodnoty (NaI) [Bq/kg]
    
    Returns:
    --------
    dict obsahující:
        - n: počet datových bodů
        - R2: koeficient determinace
        - RMSE: Root Mean Square Error [Bq/kg]
        - slope: sklon regresní přímky
        - intercept: úsek regresní přímky
        - p_value: p-hodnota regrese
        - mean_rel_dev: průměrná relativní odchylka [%]
        - median_rel_dev: medián relativní odchylky [%]
        - std_rel_dev: směrodatná odchylka relativní odchylky [%]
    """
    # Odstranění NaN hodnot
    mask = ~(np.isnan(x) | np.isnan(y))
    x_clean = x[mask]
    y_clean = y[mask]
    
    # Minimální požadavek pro statistiky
    if len(x_clean) < 3:
        return {
            'n': len(x_clean),
            'R2': 0.0,
            'RMSE': 0.0,
            'slope': 1.0,
            'intercept': 0.0,
            'p_value': 1.0,
            'mean_rel_dev': 0.0,
            'median_rel_dev': 0.0,
            'std_rel_dev': 0.0,
        }
    
    # Lineární regrese
    slope, intercept, r_value, p_value, std_err = stats.linregress(x_clean, y_clean)
    
    # RMSE
    rmse = np.sqrt(np.mean((x_clean - y_clean)**2))
    
    # Relativní odchylky (ochrana proti dělení nulou)
    with np.errstate(divide='ignore', invalid='ignore'):
        rel_dev = np.where(
            np.abs(x_clean) > 1e-10,
            (y_clean - x_clean) / x_clean * 100,
            0.0
        )
    
    return {
        'n': len(x_clean),
        'R2': r_value**2,
        'RMSE': rmse,
        'slope': slope,
        'intercept': intercept,
        'p_value': p_value,
        'mean_rel_dev': np.mean(rel_dev),
        'median_rel_dev': np.median(rel_dev),
        'std_rel_dev': np.std(rel_dev),
    }


def identify_outliers(
    A_hpge: np.ndarray,
    A_nai: np.ndarray,
    U_hpge: np.ndarray,
    U_nai: np.ndarray,
    threshold: float = 3.0
) -> np.ndarray:
    """
    Identifikuje outliers na základě z-score.
    
    Parameters:
    -----------
    A_hpge, A_nai : array
        Aktivity HPGe a NaI
    U_hpge, U_nai : array
        Nejistoty měření
    threshold : float
        Práh z-score pro označení outlierů (default 3.0 = 99.7% CI)
        
    Returns:
    --------
    boolean array : True pro outliers
    """
    zscore = calculate_zscore(A_hpge, A_nai, U_hpge, U_nai)
    return zscore >= threshold
