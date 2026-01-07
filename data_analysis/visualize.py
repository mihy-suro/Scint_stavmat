#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visualize.py - Vizualizace porovnání HPGe vs NaI(Tl) měření

Vytváří interaktivní grafy:
- Řádek 1: Původní data (Ra-226, K-40, Th-232 z dekonvoluce)
- Řádek 2: Korigovaná data (s korekcí na samoabsorpci)
- Řádek 3: Ra-226 (186 keV) vs HPGe - jeden široký graf

Vstup: comparison_input.xlsx (vytvořený pomocí build_input.py)
Výstup: comparison_results_*.html

Konfigurace: config.yaml
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from scipy import stats
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from density_correction_utils import optimize_all_elements, apply_correction
from config_loader import (
    get_config, get_elements_dict, get_correction_model, 
    get_reference_density, get_relative_uncertainty_nai, get_outlier_threshold
)


# ============================================================
# KONFIGURACE - načteno z config.yaml
# ============================================================
CORRECTION_MODEL = get_correction_model()
REFERENCE_DENSITY = get_reference_density()
RELATIVE_UNCERTAINTY_NAI = get_relative_uncertainty_nai()
OUTLIER_THRESHOLD = get_outlier_threshold()

# Prvky pro dekonvoluční analýzu (Ra, K, Th)
ELEMENTS_DECONV = get_elements_dict(get_config(), 'deconvolution')

# Ra-226 z 186 keV (pouze Ra)
ELEMENT_186 = get_elements_dict(get_config(), '186_keV')
# ============================================================


def calculate_zscore(A_hpge: np.ndarray, A_nai: np.ndarray, 
                     U_hpge: np.ndarray, U_nai: np.ndarray) -> np.ndarray:
    """
    Vypočítá z-score (normalizované residuum) pro identifikaci outlierů.
    
    z = |A_HPGe - A_NaI| / sqrt(U_HPGe² + U_NaI²)
    
    Parameters:
    -----------
    A_hpge, A_nai : array
        Aktivity HPGe a NaI
    U_hpge, U_nai : array
        Nejistoty HPGe a NaI
    
    Returns:
    --------
    array : z-score pro každý vzorek
    """
    combined_uncertainty = np.sqrt(U_hpge**2 + U_nai**2)
    # Ochrana proti dělení nulou
    combined_uncertainty = np.maximum(combined_uncertainty, 1e-10)
    return np.abs(A_hpge - A_nai) / combined_uncertainty


def load_comparison_data(file_path: Path) -> pd.DataFrame:
    """Načte comparison_input soubor."""
    if not file_path.exists():
        raise FileNotFoundError(f"Vstupní soubor nenalezen: {file_path}")
    
    df = pd.read_excel(file_path, sheet_name="comparison")
    print(f"Načteno {len(df)} řádků z {file_path.name}")
    print(f"Metody: {df['Metoda'].unique()}")
    return df


def prepare_comparison_df(df: pd.DataFrame, method_nai: str = "NaI(Tl)") -> pd.DataFrame:
    """
    Připraví DataFrame pro porovnání - merge HPGe a NaI metod.
    
    Parameters:
    -----------
    df : DataFrame
        Long-format data
    method_nai : str
        Metoda NaI pro porovnání ('NaI(Tl)' nebo 'NaI(Tl) – 186 keV')
    
    Returns:
    --------
    DataFrame se sloupci _HPGe a _NaI sufixy
    """
    df_hpge = df[df["Metoda"] == "HPGe"].copy()
    df_nai = df[df["Metoda"] == method_nai].copy()
    
    # Merge
    df_compare = df_hpge.merge(
        df_nai,
        on="Kniha analýz",
        suffixes=("_HPGe", "_NaI"),
        how="inner"
    )
    
    print(f"Porovnání {method_nai}: {len(df_compare)} vzorků")
    return df_compare


def apply_uncertainty_expansion(df: pd.DataFrame, elements: dict, rel_unc: float = 0.10):
    """Aplikuje rozšířenou nejistotu na NaI měření."""
    for element_name, (activity_col, uncertainty_col) in elements.items():
        nai_act = f"{activity_col}_NaI"
        nai_unc = f"{uncertainty_col}_NaI"
        
        if nai_act in df.columns and nai_unc in df.columns:
            # Minimální nejistota = rel_unc * aktivita
            min_unc = df[nai_act] * rel_unc
            df[nai_unc] = df[[nai_unc, nai_act]].apply(
                lambda row: max(row[nai_unc], row[nai_act] * rel_unc) 
                if pd.notna(row[nai_act]) else row[nai_unc], 
                axis=1
            )
    return df


def calculate_density(df: pd.DataFrame) -> pd.Series:
    """Vypočítá hustotu vzorků."""
    weight_col = 'Hmotnost [kg]_HPGe' if 'Hmotnost [kg]_HPGe' in df.columns else 'Hmotnost [kg]'
    volume_col = 'Objem [l]_HPGe' if 'Objem [l]_HPGe' in df.columns else 'Objem [l]'
    return df[weight_col] / df[volume_col]


def calculate_statistics(x: np.ndarray, y: np.ndarray) -> dict:
    """Vypočítá statistiky pro porovnání."""
    mask = ~(np.isnan(x) | np.isnan(y))
    x_clean = x[mask]
    y_clean = y[mask]
    
    if len(x_clean) < 3:
        return {'n': 0, 'R2': 0, 'RMSE': 0, 'slope': 1, 'intercept': 0}
    
    slope, intercept, r_value, p_value, std_err = stats.linregress(x_clean, y_clean)
    rmse = np.sqrt(np.mean((x_clean - y_clean)**2))
    rel_dev = (y_clean - x_clean) / x_clean * 100
    
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


def create_visualization(
    df_deconv: pd.DataFrame,
    df_186: pd.DataFrame,
    correction_results: dict,
    output_path: Path,
    correction_186: dict = None,
    outlier_threshold: float = 3.0
):
    """
    Vytvoří 3-řádkovou vizualizaci.
    
    Řádek 1: Původní data (Ra, K, Th)
    Řádek 2: Korigovaná data (Ra, K, Th)
    Řádek 3: Ra-226 (186 keV) - původní a korigovaný
    """
    n_elements = len(ELEMENTS_DECONV)
    
    # Názvy subplotů
    element_names = list(ELEMENTS_DECONV.keys())
    subplot_titles = (
        element_names +                                    # Řádek 1
        [f"{name} (korigováno)" for name in element_names] +  # Řádek 2
        ["Ra-226 (186 keV)", "Ra-226 (186 keV) korigováno"]   # Řádek 3
    )
    
    # Vytvoření 3x3 gridu - řádek 3 má 2 grafy (col 1-2 a col 3 prázdný)
    fig = make_subplots(
        rows=3, cols=n_elements,
        subplot_titles=subplot_titles,
        horizontal_spacing=0.08,
        vertical_spacing=0.10,
        specs=[
            [{}, {}, {}],                           # Řádek 1
            [{}, {}, {}],                           # Řádek 2
            [{"colspan": 1}, {"colspan": 1}, None]  # Řádek 3 - dva grafy
        ]
    )
    
    # Získání sloupců pro hover
    weight_col = 'Hmotnost [kg]_HPGe' if 'Hmotnost [kg]_HPGe' in df_deconv.columns else 'Hmotnost [kg]'
    desc_col = 'Popis vzorku_HPGe' if 'Popis vzorku_HPGe' in df_deconv.columns else 'Popis vzorku'
    density = calculate_density(df_deconv)
    
    # ========================================
    # ŘÁDEK 1 & 2: Dekonvoluční data
    # ========================================
    for idx, (element_name, (activity_col, uncertainty_col)) in enumerate(ELEMENTS_DECONV.items()):
        col = idx + 1
        
        hpge_act = f"{activity_col}_HPGe"
        nai_act = f"{activity_col}_NaI"
        nai_act_corr = f"{activity_col}_NaI_corrected"
        hpge_unc = f"{uncertainty_col}_HPGe"
        nai_unc = f"{uncertainty_col}_NaI"
        
        df_plot = df_deconv.dropna(subset=[hpge_act, nai_act])
        
        if len(df_plot) == 0:
            continue
        
        # Příprava customdata pro hover
        density_plot = calculate_density(df_plot)
        
        # Výpočet z-score pro identifikaci outlierů (pro původní data)
        U_hpge_arr = df_plot[hpge_unc].values if hpge_unc in df_plot.columns else np.ones(len(df_plot))
        U_nai_arr = df_plot[nai_unc].values if nai_unc in df_plot.columns else np.ones(len(df_plot))
        zscore_orig = calculate_zscore(df_plot[hpge_act].values, df_plot[nai_act].values, U_hpge_arr, U_nai_arr)
        is_outlier_orig = zscore_orig >= outlier_threshold
        
        customdata = np.column_stack((
            df_plot[weight_col], 
            density_plot, 
            df_plot[desc_col],
            df_plot[hpge_unc] if hpge_unc in df_plot.columns else np.zeros(len(df_plot)),
            df_plot[nai_unc] if nai_unc in df_plot.columns else np.zeros(len(df_plot)),
            zscore_orig
        ))
        
        # ---------- Řádek 1: Původní data ----------
        # Normální body (kolečka)
        df_normal = df_plot[~is_outlier_orig]
        customdata_normal = customdata[~is_outlier_orig]
        
        if len(df_normal) > 0:
            fig.add_trace(
                go.Scatter(
                    x=df_normal[hpge_act],
                    y=df_normal[nai_act],
                    mode='markers',
                    marker=dict(
                        size=8,
                        symbol='circle',
                        color=df_normal[weight_col],
                        colorscale='Viridis',
                        showscale=(idx == 0),
                        colorbar=dict(
                            title='Hmotnost [kg]',
                            thickness=15,
                            len=0.25,
                            y=0.87,
                            x=1.02
                        ) if idx == 0 else None,
                        opacity=0.8,
                        line=dict(width=0.5, color='white')
                    ),
                    error_x=dict(
                        type='data',
                        array=df_normal[hpge_unc] if hpge_unc in df_normal.columns else None,
                        color='rgba(128, 128, 128, 0.3)',
                        thickness=1, width=2
                    ),
                    error_y=dict(
                        type='data',
                        array=df_normal[nai_unc] if nai_unc in df_normal.columns else None,
                        color='rgba(128, 128, 128, 0.3)',
                        thickness=1, width=2
                    ),
                    text=df_normal['Kniha analýz'],
                    customdata=customdata_normal,
                    hovertemplate=(
                        '<b>%{text}</b><br>%{customdata[2]}<br>'
                        'HPGe: %{x:.2f} ± %{customdata[3]:.2f} Bq/kg<br>'
                        'NaI(Tl): %{y:.2f} ± %{customdata[4]:.2f} Bq/kg<br>'
                        'Hmotnost: %{customdata[0]:.3f} kg<br>'
                        'Hustota: %{customdata[1]:.3f} g/cm³<br>'
                        'z-score: %{customdata[5]:.2f}<extra></extra>'
                    ),
                    showlegend=(idx == 0),
                    name='Měření',
                    legendgroup='original'
                ),
                row=1, col=col
            )
        
        # Outliery (trojúhelníky s červeným okrajem)
        df_outlier = df_plot[is_outlier_orig]
        customdata_outlier = customdata[is_outlier_orig]
        
        if len(df_outlier) > 0:
            fig.add_trace(
                go.Scatter(
                    x=df_outlier[hpge_act],
                    y=df_outlier[nai_act],
                    mode='markers',
                    marker=dict(
                        size=10,
                        symbol='triangle-up',
                        color=df_outlier[weight_col],
                        colorscale='Viridis',
                        showscale=False,
                        opacity=0.9,
                        line=dict(width=1, color='red')
                    ),
                    error_x=dict(
                        type='data',
                        array=df_outlier[hpge_unc] if hpge_unc in df_outlier.columns else None,
                        color='rgba(255, 0, 0, 0.3)',
                        thickness=1, width=2
                    ),
                    error_y=dict(
                        type='data',
                        array=df_outlier[nai_unc] if nai_unc in df_outlier.columns else None,
                        color='rgba(255, 0, 0, 0.3)',
                        thickness=1, width=2
                    ),
                    text=df_outlier['Kniha analýz'],
                    customdata=customdata_outlier,
                    hovertemplate=(
                        '<b>%{text}</b> ⚠️ OUTLIER<br>%{customdata[2]}<br>'
                        'HPGe: %{x:.2f} ± %{customdata[3]:.2f} Bq/kg<br>'
                        'NaI(Tl): %{y:.2f} ± %{customdata[4]:.2f} Bq/kg<br>'
                        'Hmotnost: %{customdata[0]:.3f} kg<br>'
                        'Hustota: %{customdata[1]:.3f} g/cm³<br>'
                        'z-score: %{customdata[5]:.2f}<extra></extra>'
                    ),
                    showlegend=(idx == 0),
                    name='Outlier',
                    legendgroup='outlier'
                ),
                row=1, col=col
            )
        
        # 1:1 linie
        max_val = max(df_plot[hpge_act].max(), df_plot[nai_act].max())
        min_val = min(df_plot[hpge_act].min(), df_plot[nai_act].min())
        fig.add_trace(
            go.Scatter(
                x=[min_val, max_val], y=[min_val, max_val],
                mode='lines',
                line=dict(color='red', dash='dash', width=1),
                showlegend=False, hoverinfo='skip'
            ),
            row=1, col=col
        )
        
        # ---------- Řádek 2: Korigovaná data ----------
        if nai_act_corr in df_plot.columns:
            # Výpočet z-score pro korigovaná data
            zscore_corr = calculate_zscore(df_plot[hpge_act].values, df_plot[nai_act_corr].values, U_hpge_arr, U_nai_arr)
            is_outlier_corr = zscore_corr >= outlier_threshold
            
            customdata_corr = np.column_stack((
                df_plot[weight_col], 
                density_plot, 
                df_plot[desc_col],
                df_plot[hpge_unc] if hpge_unc in df_plot.columns else np.zeros(len(df_plot)),
                df_plot[nai_unc] if nai_unc in df_plot.columns else np.zeros(len(df_plot)),
                zscore_corr
            ))
            
            # Normální body
            df_normal_corr = df_plot[~is_outlier_corr]
            customdata_normal_corr = customdata_corr[~is_outlier_corr]
            
            if len(df_normal_corr) > 0:
                fig.add_trace(
                    go.Scatter(
                        x=df_normal_corr[hpge_act],
                        y=df_normal_corr[nai_act_corr],
                        mode='markers',
                        marker=dict(
                            size=8,
                            symbol='circle',
                            color=df_normal_corr[weight_col],
                            colorscale='Viridis',
                            showscale=False,
                            opacity=0.8,
                            line=dict(width=0.5, color='white')
                        ),
                        error_x=dict(
                            type='data',
                            array=df_normal_corr[hpge_unc] if hpge_unc in df_normal_corr.columns else None,
                            color='rgba(128, 128, 128, 0.3)',
                            thickness=1, width=2
                        ),
                        error_y=dict(
                            type='data',
                            array=df_normal_corr[nai_unc] if nai_unc in df_normal_corr.columns else None,
                            color='rgba(128, 128, 128, 0.3)',
                            thickness=1, width=2
                        ),
                        text=df_normal_corr['Kniha analýz'],
                        customdata=customdata_normal_corr,
                        hovertemplate=(
                            '<b>%{text}</b><br>%{customdata[2]}<br>'
                            'HPGe: %{x:.2f} ± %{customdata[3]:.2f} Bq/kg<br>'
                            'NaI corr: %{y:.2f} ± %{customdata[4]:.2f} Bq/kg<br>'
                            'Hmotnost: %{customdata[0]:.3f} kg<br>'
                            'Hustota: %{customdata[1]:.3f} g/cm³<br>'
                            'z-score: %{customdata[5]:.2f}<extra></extra>'
                        ),
                        showlegend=(idx == 0),
                        name='Korigováno',
                        legendgroup='corrected'
                    ),
                    row=2, col=col
                )
            
            # Outliery (trojúhelníky)
            df_outlier_corr = df_plot[is_outlier_corr]
            customdata_outlier_corr = customdata_corr[is_outlier_corr]
            
            if len(df_outlier_corr) > 0:
                fig.add_trace(
                    go.Scatter(
                        x=df_outlier_corr[hpge_act],
                        y=df_outlier_corr[nai_act_corr],
                        mode='markers',
                        marker=dict(
                            size=10,
                            symbol='triangle-up',
                            color=df_outlier_corr[weight_col],
                            colorscale='Viridis',
                            showscale=False,
                            opacity=0.9,
                            line=dict(width=1, color='red')
                        ),
                        error_x=dict(
                            type='data',
                            array=df_outlier_corr[hpge_unc] if hpge_unc in df_outlier_corr.columns else None,
                            color='rgba(255, 0, 0, 0.3)',
                            thickness=1, width=2
                        ),
                        error_y=dict(
                            type='data',
                            array=df_outlier_corr[nai_unc] if nai_unc in df_outlier_corr.columns else None,
                            color='rgba(255, 0, 0, 0.3)',
                            thickness=1, width=2
                        ),
                        text=df_outlier_corr['Kniha analýz'],
                        customdata=customdata_outlier_corr,
                        hovertemplate=(
                            '<b>%{text}</b> ⚠️ OUTLIER<br>%{customdata[2]}<br>'
                            'HPGe: %{x:.2f} ± %{customdata[3]:.2f} Bq/kg<br>'
                            'NaI corr: %{y:.2f} ± %{customdata[4]:.2f} Bq/kg<br>'
                            'Hmotnost: %{customdata[0]:.3f} kg<br>'
                            'Hustota: %{customdata[1]:.3f} g/cm³<br>'
                            'z-score: %{customdata[5]:.2f}<extra></extra>'
                        ),
                        showlegend=False,
                        name='Outlier corr',
                        legendgroup='outlier'
                    ),
                    row=2, col=col
                )
            
            # 1:1 linie
            max_val_corr = max(df_plot[hpge_act].max(), df_plot[nai_act_corr].max())
            min_val_corr = min(df_plot[hpge_act].min(), df_plot[nai_act_corr].min())
            fig.add_trace(
                go.Scatter(
                    x=[min_val_corr, max_val_corr], y=[min_val_corr, max_val_corr],
                    mode='lines',
                    line=dict(color='red', dash='dash', width=1),
                    showlegend=False, hoverinfo='skip'
                ),
                row=2, col=col
            )
            
            # Anotace s korekčními faktory
            if element_name in correction_results:
                if CORRECTION_MODEL == 'scaled_exponential':
                    a_val = correction_results[element_name].get('a', 1.0)
                    b_val = correction_results[element_name]['b']
                    ann_text = f"a={a_val:.3f}<br>b={b_val:.3f}"
                elif CORRECTION_MODEL == 'scaled_exponential_quadratic':
                    a_val = correction_results[element_name].get('a', 1.0)
                    b_val = correction_results[element_name]['b']
                    c_val = correction_results[element_name].get('c', 0)
                    ann_text = f"a={a_val:.3f}<br>b={b_val:.3f}<br>c={c_val:.3f}"
                elif CORRECTION_MODEL == 'quadratic_centered':
                    b_val = correction_results[element_name]['b']
                    c_val = correction_results[element_name].get('c', 0)
                    ann_text = f"b={b_val:.3f}<br>c={c_val:.3f}"
                else:
                    b_val = correction_results[element_name]['b']
                    ann_text = f"b={b_val:.3f}"
                
                # Pozice anotace
                fig.add_annotation(
                    text=ann_text,
                    x=0.05, y=0.95,
                    xref=f"x{col + n_elements} domain", yref=f"y{col + n_elements} domain",
                    xanchor='left', yanchor='top',
                    showarrow=False,
                    bgcolor='rgba(255,255,255,0.8)',
                    bordercolor='gray', borderwidth=1,
                    font=dict(size=9)
                )
        
        # Popisky os
        fig.update_xaxes(title_text="HPGe [Bq/kg]", row=1, col=col)
        fig.update_yaxes(title_text="NaI(Tl) [Bq/kg]", row=1, col=col)
        fig.update_xaxes(title_text="HPGe [Bq/kg]", row=2, col=col)
        fig.update_yaxes(title_text="NaI corr [Bq/kg]", row=2, col=col)
    
    # ========================================
    # ŘÁDEK 3: Ra-226 (186 keV) - 2 grafy
    # ========================================
    hpge_act_186 = "A_Ra_HPGe"
    nai_act_186 = "A_Ra_NaI"
    nai_act_186_corr = "A_Ra_NaI_corrected"
    hpge_unc_186 = "U_Ra_HPGe"
    nai_unc_186 = "U_Ra_NaI"
    
    weight_col_186 = 'Hmotnost [kg]_HPGe' if 'Hmotnost [kg]_HPGe' in df_186.columns else 'Hmotnost [kg]'
    desc_col_186 = 'Popis vzorku_HPGe' if 'Popis vzorku_HPGe' in df_186.columns else 'Popis vzorku'
    
    df_plot_186 = df_186.dropna(subset=[hpge_act_186, nai_act_186])
    
    if len(df_plot_186) > 0:
        density_186 = calculate_density(df_plot_186)
        
        # Výpočet z-score pro detekci outlierů - původní data
        U_hpge_186 = df_plot_186[hpge_unc_186].values if hpge_unc_186 in df_plot_186.columns else np.ones(len(df_plot_186))
        U_nai_186 = df_plot_186[nai_unc_186].values if nai_unc_186 in df_plot_186.columns else np.ones(len(df_plot_186))
        zscore_186_orig = calculate_zscore(
            df_plot_186[hpge_act_186].values,
            df_plot_186[nai_act_186].values,
            U_hpge_186, U_nai_186
        )
        is_outlier_186_orig = zscore_186_orig >= outlier_threshold
        
        # Rozdělit data na normální a outliery
        df_normal_186 = df_plot_186[~is_outlier_186_orig].copy()
        df_outlier_186 = df_plot_186[is_outlier_186_orig].copy()
        density_normal_186 = density_186[~is_outlier_186_orig]
        density_outlier_186 = density_186[is_outlier_186_orig]
        zscore_normal_186 = zscore_186_orig[~is_outlier_186_orig]
        zscore_outlier_186 = zscore_186_orig[is_outlier_186_orig]
        
        # customdata pro normální body
        if len(df_normal_186) > 0:
            customdata_normal_186 = np.column_stack((
                df_normal_186[weight_col_186],
                density_normal_186,
                df_normal_186[desc_col_186],
                df_normal_186[hpge_unc_186] if hpge_unc_186 in df_normal_186.columns else np.zeros(len(df_normal_186)),
                df_normal_186[nai_unc_186] if nai_unc_186 in df_normal_186.columns else np.zeros(len(df_normal_186)),
                zscore_normal_186
            ))
        
        # customdata pro outliery
        if len(df_outlier_186) > 0:
            customdata_outlier_186 = np.column_stack((
                df_outlier_186[weight_col_186],
                density_outlier_186,
                df_outlier_186[desc_col_186],
                df_outlier_186[hpge_unc_186] if hpge_unc_186 in df_outlier_186.columns else np.zeros(len(df_outlier_186)),
                df_outlier_186[nai_unc_186] if nai_unc_186 in df_outlier_186.columns else np.zeros(len(df_outlier_186)),
                zscore_outlier_186
            ))
        
        # ---------- Řádek 3, Col 1: Původní 186 keV data ----------
        # Normální body
        if len(df_normal_186) > 0:
            fig.add_trace(
                go.Scatter(
                    x=df_normal_186[hpge_act_186],
                    y=df_normal_186[nai_act_186],
                    mode='markers',
                    marker=dict(
                        size=8,
                        color=df_normal_186[weight_col_186],
                        colorscale='Viridis',
                        showscale=False,
                        opacity=0.8,
                        line=dict(width=0.5, color='white')
                    ),
                    error_x=dict(
                        type='data',
                        array=df_normal_186[hpge_unc_186] if hpge_unc_186 in df_normal_186.columns else None,
                        color='rgba(128, 128, 128, 0.3)',
                        thickness=1, width=2
                    ),
                    error_y=dict(
                        type='data',
                        array=df_normal_186[nai_unc_186] if nai_unc_186 in df_normal_186.columns else None,
                        color='rgba(128, 128, 128, 0.3)',
                        thickness=1, width=2
                    ),
                    text=df_normal_186['Kniha analýz'],
                    customdata=customdata_normal_186,
                    hovertemplate=(
                        '<b>%{text}</b><br>%{customdata[2]}<br>'
                        'HPGe: %{x:.2f} ± %{customdata[3]:.2f} Bq/kg<br>'
                        'NaI 186keV: %{y:.2f} ± %{customdata[4]:.2f} Bq/kg<br>'
                        'Hmotnost: %{customdata[0]:.3f} kg<br>'
                        'Hustota: %{customdata[1]:.3f} g/cm³<br>'
                        'z-score: %{customdata[5]:.2f}<extra></extra>'
                    ),
                    showlegend=False,
                    name='Měření',
                    legendgroup='original'
                ),
                row=3, col=1
            )
        
        # Outliery - trojúhelníky s červeným okrajem
        if len(df_outlier_186) > 0:
            fig.add_trace(
                go.Scatter(
                    x=df_outlier_186[hpge_act_186],
                    y=df_outlier_186[nai_act_186],
                    mode='markers',
                    marker=dict(
                        symbol='triangle-up',
                        size=10,
                        color=df_outlier_186[weight_col_186],
                        colorscale='Viridis',
                        showscale=False,
                        opacity=0.8,
                        line=dict(width=1, color='red')
                    ),
                    error_x=dict(
                        type='data',
                        array=df_outlier_186[hpge_unc_186] if hpge_unc_186 in df_outlier_186.columns else None,
                        color='rgba(255, 0, 0, 0.3)',
                        thickness=1, width=2
                    ),
                    error_y=dict(
                        type='data',
                        array=df_outlier_186[nai_unc_186] if nai_unc_186 in df_outlier_186.columns else None,
                        color='rgba(255, 0, 0, 0.3)',
                        thickness=1, width=2
                    ),
                    text=df_outlier_186['Kniha analýz'],
                    customdata=customdata_outlier_186,
                    hovertemplate=(
                        '<b>%{text}</b> ⚠️ OUTLIER<br>%{customdata[2]}<br>'
                        'HPGe: %{x:.2f} ± %{customdata[3]:.2f} Bq/kg<br>'
                        'NaI 186keV: %{y:.2f} ± %{customdata[4]:.2f} Bq/kg<br>'
                        'Hmotnost: %{customdata[0]:.3f} kg<br>'
                        'Hustota: %{customdata[1]:.3f} g/cm³<br>'
                        'z-score: %{customdata[5]:.2f}<extra></extra>'
                    ),
                    showlegend=False,
                    name='Outlier',
                    legendgroup='outlier'
                ),
                row=3, col=1
            )
        
        # 1:1 linie
        max_val_186 = max(df_plot_186[hpge_act_186].max(), df_plot_186[nai_act_186].max())
        min_val_186 = min(df_plot_186[hpge_act_186].min(), df_plot_186[nai_act_186].min())
        fig.add_trace(
            go.Scatter(
                x=[min_val_186, max_val_186], y=[min_val_186, max_val_186],
                mode='lines',
                line=dict(color='red', dash='dash', width=1),
                showlegend=False, hoverinfo='skip'
            ),
            row=3, col=1
        )
        
        # Statistiky pro 186 keV - původní (pro pozdější výpis)
        stats_186 = calculate_statistics(
            df_plot_186[hpge_act_186].values,
            df_plot_186[nai_act_186].values
        )
        
        # ---------- Řádek 3, Col 2: Korigované 186 keV data ----------
        if nai_act_186_corr in df_plot_186.columns:
            # Výpočet z-score pro korigovaná data
            zscore_186_corr = calculate_zscore(
                df_plot_186[hpge_act_186].values,
                df_plot_186[nai_act_186_corr].values,
                U_hpge_186, U_nai_186
            )
            is_outlier_186_corr = zscore_186_corr >= outlier_threshold
            
            df_normal_186_corr = df_plot_186[~is_outlier_186_corr].copy()
            df_outlier_186_corr = df_plot_186[is_outlier_186_corr].copy()
            density_normal_186_corr = density_186[~is_outlier_186_corr]
            density_outlier_186_corr = density_186[is_outlier_186_corr]
            zscore_normal_186_corr = zscore_186_corr[~is_outlier_186_corr]
            zscore_outlier_186_corr = zscore_186_corr[is_outlier_186_corr]
            
            # customdata pro normální body - korigované
            if len(df_normal_186_corr) > 0:
                customdata_normal_186_corr = np.column_stack((
                    df_normal_186_corr[weight_col_186],
                    density_normal_186_corr,
                    df_normal_186_corr[desc_col_186],
                    df_normal_186_corr[hpge_unc_186] if hpge_unc_186 in df_normal_186_corr.columns else np.zeros(len(df_normal_186_corr)),
                    df_normal_186_corr[nai_unc_186] if nai_unc_186 in df_normal_186_corr.columns else np.zeros(len(df_normal_186_corr)),
                    zscore_normal_186_corr
                ))
                
                fig.add_trace(
                    go.Scatter(
                        x=df_normal_186_corr[hpge_act_186],
                        y=df_normal_186_corr[nai_act_186_corr],
                        mode='markers',
                        marker=dict(
                            size=8,
                            color=df_normal_186_corr[weight_col_186],
                            colorscale='Viridis',
                            showscale=False,
                            opacity=0.8,
                            line=dict(width=0.5, color='white')
                        ),
                        error_x=dict(
                            type='data',
                            array=df_normal_186_corr[hpge_unc_186] if hpge_unc_186 in df_normal_186_corr.columns else None,
                            color='rgba(128, 128, 128, 0.3)',
                            thickness=1, width=2
                        ),
                        error_y=dict(
                            type='data',
                            array=df_normal_186_corr[nai_unc_186] if nai_unc_186 in df_normal_186_corr.columns else None,
                            color='rgba(128, 128, 128, 0.3)',
                            thickness=1, width=2
                        ),
                        text=df_normal_186_corr['Kniha analýz'],
                        customdata=customdata_normal_186_corr,
                        hovertemplate=(
                            '<b>%{text}</b><br>%{customdata[2]}<br>'
                            'HPGe: %{x:.2f} ± %{customdata[3]:.2f} Bq/kg<br>'
                            'NaI 186keV corr: %{y:.2f} ± %{customdata[4]:.2f} Bq/kg<br>'
                            'Hmotnost: %{customdata[0]:.3f} kg<br>'
                            'Hustota: %{customdata[1]:.3f} g/cm³<br>'
                            'z-score: %{customdata[5]:.2f}<extra></extra>'
                        ),
                        showlegend=False,
                        name='Korigováno',
                        legendgroup='corrected'
                    ),
                    row=3, col=2
                )
            
            # Outliery - korigované
            if len(df_outlier_186_corr) > 0:
                customdata_outlier_186_corr = np.column_stack((
                    df_outlier_186_corr[weight_col_186],
                    density_outlier_186_corr,
                    df_outlier_186_corr[desc_col_186],
                    df_outlier_186_corr[hpge_unc_186] if hpge_unc_186 in df_outlier_186_corr.columns else np.zeros(len(df_outlier_186_corr)),
                    df_outlier_186_corr[nai_unc_186] if nai_unc_186 in df_outlier_186_corr.columns else np.zeros(len(df_outlier_186_corr)),
                    zscore_outlier_186_corr
                ))
                
                fig.add_trace(
                    go.Scatter(
                        x=df_outlier_186_corr[hpge_act_186],
                        y=df_outlier_186_corr[nai_act_186_corr],
                        mode='markers',
                        marker=dict(
                            symbol='triangle-up',
                            size=10,
                            color=df_outlier_186_corr[weight_col_186],
                            colorscale='Viridis',
                            showscale=False,
                            opacity=0.8,
                            line=dict(width=1, color='red')
                        ),
                        error_x=dict(
                            type='data',
                            array=df_outlier_186_corr[hpge_unc_186] if hpge_unc_186 in df_outlier_186_corr.columns else None,
                            color='rgba(255, 0, 0, 0.3)',
                            thickness=1, width=2
                        ),
                        error_y=dict(
                            type='data',
                            array=df_outlier_186_corr[nai_unc_186] if nai_unc_186 in df_outlier_186_corr.columns else None,
                            color='rgba(255, 0, 0, 0.3)',
                            thickness=1, width=2
                        ),
                        text=df_outlier_186_corr['Kniha analýz'],
                        customdata=customdata_outlier_186_corr,
                        hovertemplate=(
                            '<b>%{text}</b> ⚠️ OUTLIER<br>%{customdata[2]}<br>'
                            'HPGe: %{x:.2f} ± %{customdata[3]:.2f} Bq/kg<br>'
                            'NaI 186keV corr: %{y:.2f} ± %{customdata[4]:.2f} Bq/kg<br>'
                            'Hmotnost: %{customdata[0]:.3f} kg<br>'
                            'Hustota: %{customdata[1]:.3f} g/cm³<br>'
                            'z-score: %{customdata[5]:.2f}<extra></extra>'
                        ),
                        showlegend=False,
                        name='Outlier corr',
                        legendgroup='outlier'
                    ),
                    row=3, col=2
                )
            
            # 1:1 linie
            max_val_186_corr = max(df_plot_186[hpge_act_186].max(), df_plot_186[nai_act_186_corr].max())
            min_val_186_corr = min(df_plot_186[hpge_act_186].min(), df_plot_186[nai_act_186_corr].min())
            fig.add_trace(
                go.Scatter(
                    x=[min_val_186_corr, max_val_186_corr], y=[min_val_186_corr, max_val_186_corr],
                    mode='lines',
                    line=dict(color='red', dash='dash', width=1),
                    showlegend=False, hoverinfo='skip'
                ),
                row=3, col=2
            )
            
            # Statistiky pro 186 keV - korigované (pro pozdější výpis)
            stats_186_corr = calculate_statistics(
                df_plot_186[hpge_act_186].values,
                df_plot_186[nai_act_186_corr].values
            )
            
            # Anotace pouze s koeficienty transformační funkce
            if correction_186:
                if CORRECTION_MODEL == 'scaled_exponential':
                    ann_text_186 = f"a={correction_186.get('a', 1.0):.3f}<br>b={correction_186.get('b', 0):.3f}"
                elif CORRECTION_MODEL == 'scaled_exponential_quadratic':
                    ann_text_186 = f"a={correction_186.get('a', 1.0):.3f}<br>b={correction_186.get('b', 0):.3f}<br>c={correction_186.get('c', 0):.3f}"
                elif CORRECTION_MODEL == 'quadratic_centered':
                    ann_text_186 = f"b={correction_186.get('b', 0):.3f}<br>c={correction_186.get('c', 0):.3f}"
                else:
                    ann_text_186 = f"b={correction_186.get('b', 0):.3f}"
                
                fig.add_annotation(
                    text=ann_text_186,
                    x=0.05, y=0.95,
                    xref="x8 domain", yref="y8 domain",
                    xanchor='left', yanchor='top',
                    showarrow=False,
                    bgcolor='rgba(255,255,255,0.8)',
                    bordercolor='gray', borderwidth=1,
                    font=dict(size=9)
                )
    
    fig.update_xaxes(title_text="HPGe Ra-226 [Bq/kg]", row=3, col=1)
    fig.update_yaxes(title_text="NaI(Tl) Ra-226 (186 keV) [Bq/kg]", row=3, col=1)
    fig.update_xaxes(title_text="HPGe Ra-226 [Bq/kg]", row=3, col=2)
    fig.update_yaxes(title_text="NaI corr Ra-226 (186 keV) [Bq/kg]", row=3, col=2)
    
    # ========================================
    # Layout
    # ========================================
    fig.update_layout(
        title_text="Porovnání metod: HPGe vs NaI(Tl)",
        height=1200,
        width=1600,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Uložení
    fig.write_html(output_path)
    print(f"Graf uložen: {output_path}")
    
    return fig


def run_visualization(input_file: Path, output_dir: Path, outlier_threshold: float = 3.0) -> Path:
    """
    Hlavní funkce pro vizualizaci.
    
    Parameters:
    -----------
    input_file : Path
        Cesta k comparison_input.xlsx
    output_dir : Path
        Adresář pro výstup
    outlier_threshold : float
        Z-score práh pro identifikaci outlierů (default 3.0 = 99.7% CI)
    
    Returns:
    --------
    Path : Cesta k vygenerovanému HTML
    """
    print("\n" + "="*60)
    print("VIZUALIZACE POROVNÁNÍ HPGe vs NaI(Tl)")
    print("="*60)
    
    # 1) Načtení dat
    print("\n1) Načítání dat...")
    df = load_comparison_data(input_file)
    
    # 2) Příprava DataFrame pro dekonvoluci (HPGe vs NaI(Tl))
    print("\n2) Příprava dat pro dekonvoluční analýzu...")
    df_deconv = prepare_comparison_df(df, "NaI(Tl)")
    df_deconv = apply_uncertainty_expansion(df_deconv, ELEMENTS_DECONV, RELATIVE_UNCERTAINTY_NAI)
    df_deconv['density'] = calculate_density(df_deconv)
    
    # 3) Příprava DataFrame pro 186 keV (HPGe vs NaI(Tl) – 186 keV)
    print("\n3) Příprava dat pro 186 keV analýzu...")
    df_186 = prepare_comparison_df(df, "NaI(Tl) – 186 keV")
    df_186 = apply_uncertainty_expansion(df_186, ELEMENT_186, RELATIVE_UNCERTAINTY_NAI)
    df_186['density'] = calculate_density(df_186)
    
    # 4) Optimalizace korekčních faktorů (pro dekonvoluci)
    print("\n4) Optimalizace korekčních faktorů pro dekonvoluci...")
    correction_results = optimize_all_elements(
        df_deconv,
        ELEMENTS_DECONV,
        model=CORRECTION_MODEL,
        rho_ref=REFERENCE_DENSITY,
        verbose=True
    )
    
    # 4b) Optimalizace korekčních faktorů pro 186 keV
    print("\n4b) Optimalizace korekčních faktorů pro 186 keV...")
    correction_186_results = optimize_all_elements(
        df_186,
        ELEMENT_186,
        model=CORRECTION_MODEL,
        rho_ref=REFERENCE_DENSITY,
        verbose=True
    )
    correction_186 = correction_186_results.get('Ra-226 (186 keV)', None)
    
    # 5) Aplikace korekcí
    print("\n5) Aplikace korekcí na dekonvoluční data...")
    for element_name, (activity_col, uncertainty_col) in ELEMENTS_DECONV.items():
        nai_act = f"{activity_col}_NaI"
        nai_act_corr = f"{activity_col}_NaI_corrected"
        
        if CORRECTION_MODEL == 'scaled_exponential':
            a_val = correction_results[element_name].get('a', 1.0)
            b_val = correction_results[element_name]['b']
            c_val = 0.0
        elif CORRECTION_MODEL == 'scaled_exponential_quadratic':
            a_val = correction_results[element_name].get('a', 1.0)
            b_val = correction_results[element_name]['b']
            c_val = correction_results[element_name].get('c', 0.0)
        else:
            a_val = 1.0
            b_val = correction_results[element_name]['b']
            c_val = correction_results[element_name].get('c', 0.0)
        
        df_deconv[nai_act_corr] = apply_correction(
            df_deconv[nai_act].values,
            df_deconv['density'].values,
            b=b_val,
            c=c_val,
            a=a_val,
            model=CORRECTION_MODEL,
            rho_ref=REFERENCE_DENSITY
        )
    
    # 5b) Aplikace korekcí na 186 keV data
    print("    Aplikace korekcí na 186 keV data...")
    if correction_186:
        nai_act = "A_Ra_NaI"
        nai_act_corr = "A_Ra_NaI_corrected"
        
        if CORRECTION_MODEL == 'scaled_exponential':
            a_val = correction_186.get('a', 1.0)
            b_val = correction_186['b']
            c_val = 0.0
        elif CORRECTION_MODEL == 'scaled_exponential_quadratic':
            a_val = correction_186.get('a', 1.0)
            b_val = correction_186['b']
            c_val = correction_186.get('c', 0.0)
        else:
            a_val = 1.0
            b_val = correction_186['b']
            c_val = correction_186.get('c', 0.0)
        
        df_186[nai_act_corr] = apply_correction(
            df_186[nai_act].values,
            df_186['density'].values,
            b=b_val,
            c=c_val,
            a=a_val,
            model=CORRECTION_MODEL,
            rho_ref=REFERENCE_DENSITY
        )
    
    # 6) Vytvoření vizualizace
    print("\n6) Vytváření vizualizace...")
    output_file = output_dir / "comparison_results_plot.html"
    
    create_visualization(df_deconv, df_186, correction_results, output_file, correction_186, outlier_threshold)
    
    # 7) Statistické shrnutí
    print("\n" + "="*60)
    print("STATISTICKÉ SHRNUTÍ")
    print("="*60)
    
    # Dekonvoluční data
    print("\n--- Dekonvoluční analýza (Ra, K, Th) ---")
    for element_name, (activity_col, _) in ELEMENTS_DECONV.items():
        hpge = df_deconv[f"{activity_col}_HPGe"].values
        nai = df_deconv[f"{activity_col}_NaI"].values
        nai_corr = df_deconv[f"{activity_col}_NaI_corrected"].values
        
        stats_orig = calculate_statistics(hpge, nai)
        stats_corr = calculate_statistics(hpge, nai_corr)
        
        print(f"\n{element_name}:")
        print(f"  Původní:    R²={stats_orig['R2']:.4f}, RMSE={stats_orig['RMSE']:.2f} Bq/kg")
        print(f"  Korigované: R²={stats_corr['R2']:.4f}, RMSE={stats_corr['RMSE']:.2f} Bq/kg")
        print(f"  Zlepšení:   ΔR²={stats_corr['R2']-stats_orig['R2']:+.4f}, "
              f"RMSE redukce={(1-stats_corr['RMSE']/stats_orig['RMSE'])*100:.1f}%")
    
    # 186 keV
    print("\n--- Ra-226 (186 keV) ---")
    hpge_186 = df_186["A_Ra_HPGe"].values
    nai_186 = df_186["A_Ra_NaI"].values
    stats_186 = calculate_statistics(hpge_186, nai_186)
    
    print(f"  Původní:")
    print(f"    n = {stats_186['n']}")
    print(f"    R² = {stats_186['R2']:.4f}")
    print(f"    RMSE = {stats_186['RMSE']:.2f} Bq/kg")
    print(f"    slope = {stats_186['slope']:.3f}")
    print(f"    Průměrná rel. odchylka = {stats_186['mean_rel_dev']:.2f}%")
    
    if "A_Ra_NaI_corrected" in df_186.columns:
        nai_186_corr = df_186["A_Ra_NaI_corrected"].values
        stats_186_corr = calculate_statistics(hpge_186, nai_186_corr)
        print(f"\n  Korigované:")
        print(f"    R² = {stats_186_corr['R2']:.4f}")
        print(f"    RMSE = {stats_186_corr['RMSE']:.2f} Bq/kg")
        print(f"    slope = {stats_186_corr['slope']:.3f}")
        print(f"    Průměrná rel. odchylka = {stats_186_corr['mean_rel_dev']:.2f}%")
        print(f"\n  Zlepšení:")
        print(f"    ΔR² = {stats_186_corr['R2']-stats_186['R2']:+.4f}")
        print(f"    RMSE redukce = {(1-stats_186_corr['RMSE']/stats_186['RMSE'])*100:.1f}%")
    
    print("\n" + "="*60)
    print(f"Hotovo! Výstup: {output_file.name}")
    print("="*60 + "\n")
    
    return output_file


if __name__ == "__main__":
    # Pro samostatné testování
    script_dir = Path(__file__).parent
    
    # Najít nejnovější comparison_input
    input_file = script_dir / "comparison_input.xlsx"
    if input_file.exists():
        run_visualization(input_file, script_dir)
    else:
        print("Soubor comparison_input.xlsx nenalezen. Spusťte nejprve build_input.py")
