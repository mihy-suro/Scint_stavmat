#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
viz_scatter.py - Helper funkce pro scatter ploty

Obsahuje:
- add_scatter_trace: Přidání scatter trace s error bars
- add_identity_line: Přidání 1:1 referenční linie
- add_correction_annotation: Anotace s korekčními koeficienty
- prepare_customdata: Příprava dat pro hover tooltip
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from typing import Optional, Dict, Any, Tuple


def prepare_customdata(
    df: pd.DataFrame,
    weight_col: str,
    desc_col: str,
    hpge_unc_col: str,
    nai_unc_col: str,
    zscore: np.ndarray,
    density: np.ndarray
) -> np.ndarray:
    """
    Připraví customdata array pro hover tooltips.
    
    Parameters:
    -----------
    df : DataFrame
        Data pro zobrazení
    weight_col : str
        Název sloupce s hmotností
    desc_col : str
        Název sloupce s popisem vzorku
    hpge_unc_col : str
        Název sloupce s nejistotou HPGe
    nai_unc_col : str
        Název sloupce s nejistotou NaI
    zscore : array
        Z-score hodnoty
    density : array
        Hustota vzorků
        
    Returns:
    --------
    np.ndarray s customdata pro Plotly
    """
    n = len(df)
    return np.column_stack((
        df[weight_col].values if weight_col in df.columns else np.zeros(n),
        density,
        df[desc_col].values if desc_col in df.columns else np.array([''] * n),
        df[hpge_unc_col].values if hpge_unc_col in df.columns else np.zeros(n),
        df[nai_unc_col].values if nai_unc_col in df.columns else np.zeros(n),
        zscore
    ))


def add_scatter_trace(
    fig: go.Figure,
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    row: int,
    col: int,
    customdata: np.ndarray,
    weight_col: str,
    hpge_unc_col: Optional[str] = None,
    nai_unc_col: Optional[str] = None,
    is_outlier: bool = False,
    is_corrected: bool = False,
    show_colorbar: bool = False,
    show_legend: bool = True,
    legend_group: str = "original",
    name: str = "Měření"
) -> None:
    """
    Přidá scatter trace do figure s error bars a hover info.
    
    Parameters:
    -----------
    fig : Figure
        Plotly figure
    df : DataFrame
        Data pro zobrazení
    x_col : str
        Název sloupce pro osu X (HPGe)
    y_col : str
        Název sloupce pro osu Y (NaI)
    row, col : int
        Pozice v subplot gridu
    customdata : array
        Data pro hover tooltip
    weight_col : str
        Název sloupce s hmotností (pro barvu)
    hpge_unc_col : str, optional
        Název sloupce s nejistotou HPGe
    nai_unc_col : str, optional
        Název sloupce s nejistotou NaI
    is_outlier : bool
        Zda jde o outlier body
    is_corrected : bool
        Zda jde o korigovaná data
    show_colorbar : bool
        Zobrazit colorbar
    show_legend : bool
        Zobrazit v legendě
    legend_group : str
        Skupina pro legendu
    name : str
        Název trace
    """
    if len(df) == 0:
        return
    
    # Nastavení markeru podle typu bodu
    if is_outlier:
        marker_symbol = 'triangle-up'
        marker_size = 10
        line_color = 'red'
        error_color = 'rgba(255, 0, 0, 0.3)'
        outlier_text = ' ⚠️ OUTLIER'
    else:
        marker_symbol = 'circle'
        marker_size = 8
        line_color = 'white'
        error_color = 'rgba(128, 128, 128, 0.3)'
        outlier_text = ''
    
    # Hover template
    y_label = "NaI corr" if is_corrected else "NaI(Tl)"
    hovertemplate = (
        f'<b>%{{text}}</b>{outlier_text}<br>%{{customdata[2]}}<br>'
        f'HPGe: %{{x:.2f}} ± %{{customdata[3]:.2f}} Bq/kg<br>'
        f'{y_label}: %{{y:.2f}} ± %{{customdata[4]:.2f}} Bq/kg<br>'
        f'Hmotnost: %{{customdata[0]:.3f}} kg<br>'
        f'Hustota: %{{customdata[1]:.3f}} g/cm³<br>'
        f'z-score: %{{customdata[5]:.2f}}<extra></extra>'
    )
    
    # Colorbar nastavení
    colorbar = None
    if show_colorbar:
        colorbar = dict(
            title='Hmotnost [kg]',
            thickness=15,
            len=0.15,
            y=0.92,
            x=1.02
        )
    
    fig.add_trace(
        go.Scatter(
            x=df[x_col],
            y=df[y_col],
            mode='markers',
            marker=dict(
                size=marker_size,
                symbol=marker_symbol,
                color=df[weight_col] if weight_col in df.columns else None,
                colorscale='Viridis',
                showscale=show_colorbar,
                colorbar=colorbar,
                opacity=0.8 if not is_outlier else 0.9,
                line=dict(width=0.5 if not is_outlier else 1, color=line_color)
            ),
            error_x=dict(
                type='data',
                array=df[hpge_unc_col] if hpge_unc_col and hpge_unc_col in df.columns else None,
                color=error_color,
                thickness=1,
                width=2
            ) if hpge_unc_col else None,
            error_y=dict(
                type='data',
                array=df[nai_unc_col] if nai_unc_col and nai_unc_col in df.columns else None,
                color=error_color,
                thickness=1,
                width=2
            ) if nai_unc_col else None,
            text=df['Kniha analýz'] if 'Kniha analýz' in df.columns else None,
            customdata=customdata,
            hovertemplate=hovertemplate,
            showlegend=show_legend,
            name=name,
            legendgroup=legend_group
        ),
        row=row, col=col
    )


def add_identity_line(
    fig: go.Figure,
    x_data: np.ndarray,
    y_data: np.ndarray,
    row: int,
    col: int
) -> None:
    """
    Přidá 1:1 referenční linii do grafu.
    
    Parameters:
    -----------
    fig : Figure
        Plotly figure
    x_data, y_data : array
        Data pro určení rozsahu
    row, col : int
        Pozice v subplot gridu
    """
    min_val = min(np.nanmin(x_data), np.nanmin(y_data))
    max_val = max(np.nanmax(x_data), np.nanmax(y_data))
    
    fig.add_trace(
        go.Scatter(
            x=[min_val, max_val],
            y=[min_val, max_val],
            mode='lines',
            line=dict(color='red', dash='dash', width=1),
            showlegend=False,
            hoverinfo='skip'
        ),
        row=row, col=col
    )


def add_correction_annotation(
    fig: go.Figure,
    correction_params: Dict[str, float],
    model: str,
    row: int,
    col: int
) -> None:
    """
    Přidá anotaci s korekčními koeficienty.
    
    Parameters:
    -----------
    fig : Figure
        Plotly figure
    correction_params : dict
        Slovník s korekčními parametry (a, b, c)
    model : str
        Typ korekčního modelu
    row, col : int
        Pozice v subplot gridu (pro určení subplot indexu)
    """
    if not correction_params:
        return
    
    # Sestavení textu anotace podle modelu
    if model == 'scaled_exponential':
        ann_text = f"a={correction_params.get('a', 1.0):.3f}<br>b={correction_params.get('b', 0):.3f}"
    elif model == 'scaled_exponential_quadratic':
        ann_text = (
            f"a={correction_params.get('a', 1.0):.3f}<br>"
            f"b={correction_params.get('b', 0):.3f}<br>"
            f"c={correction_params.get('c', 0):.3f}"
        )
    elif model == 'quadratic_centered':
        ann_text = f"b={correction_params.get('b', 0):.3f}<br>c={correction_params.get('c', 0):.3f}"
    else:
        ann_text = f"b={correction_params.get('b', 0):.3f}"
    
    # Výpočet subplot indexu (pro 2-sloupcový grid)
    subplot_idx = (row - 1) * 2 + col
    
    fig.add_annotation(
        text=ann_text,
        x=0.05, y=0.95,
        xref=f"x{subplot_idx} domain" if subplot_idx > 1 else "x domain",
        yref=f"y{subplot_idx} domain" if subplot_idx > 1 else "y domain",
        xanchor='left', yanchor='top',
        showarrow=False,
        bgcolor='rgba(255,255,255,0.8)',
        bordercolor='gray',
        borderwidth=1,
        font=dict(size=9)
    )


def plot_element_comparison(
    fig: go.Figure,
    df: pd.DataFrame,
    element_name: str,
    activity_col: str,
    uncertainty_col: str,
    row: int,
    correction_params: Optional[Dict[str, float]] = None,
    correction_model: str = 'scaled_exponential_quadratic',
    outlier_threshold: float = 3.0,
    show_colorbar: bool = False,
    show_legend: bool = True
) -> None:
    """
    Vykreslí porovnání pro jeden prvek (před a po korekci).
    
    Parameters:
    -----------
    fig : Figure
        Plotly figure
    df : DataFrame
        Data s _HPGe a _NaI sloupci
    element_name : str
        Název prvku (pro legendu)
    activity_col : str
        Základní název sloupce aktivity (bez suffixu)
    uncertainty_col : str
        Základní název sloupce nejistoty (bez suffixu)
    row : int
        Řádek v subplot gridu
    correction_params : dict, optional
        Korekční parametry (a, b, c)
    correction_model : str
        Typ korekčního modelu
    outlier_threshold : float
        Práh z-score pro outliers
    show_colorbar : bool
        Zobrazit colorbar (typicky jen pro první prvek)
    show_legend : bool
        Zobrazit v legendě
    """
    from .viz_stats import calculate_zscore
    from .viz_data import calculate_density, get_column_names
    
    # Názvy sloupců
    hpge_act = f"{activity_col}_HPGe"
    nai_act = f"{activity_col}_NaI"
    nai_act_corr = f"{activity_col}_NaI_corrected"
    hpge_unc = f"{uncertainty_col}_HPGe"
    nai_unc = f"{uncertainty_col}_NaI"
    
    # Filtrace platných dat
    df_plot = df.dropna(subset=[hpge_act, nai_act]).copy()
    if len(df_plot) == 0:
        return
    
    # Pomocné sloupce
    cols = get_column_names(df_plot)
    density = calculate_density(df_plot)
    
    # Z-score pro původní data
    U_hpge = df_plot[hpge_unc].values if hpge_unc in df_plot.columns else np.ones(len(df_plot))
    U_nai = df_plot[nai_unc].values if nai_unc in df_plot.columns else np.ones(len(df_plot))
    zscore_orig = calculate_zscore(df_plot[hpge_act].values, df_plot[nai_act].values, U_hpge, U_nai)
    is_outlier = zscore_orig >= outlier_threshold
    
    # Customdata pro hover
    customdata = prepare_customdata(
        df_plot, cols['weight'], cols['description'],
        hpge_unc, nai_unc, zscore_orig, density
    )
    
    # ---- Sloupec 1: Původní data ----
    # Normální body
    df_normal = df_plot[~is_outlier]
    if len(df_normal) > 0:
        add_scatter_trace(
            fig, df_normal, hpge_act, nai_act, row, 1,
            customdata[~is_outlier], cols['weight'],
            hpge_unc, nai_unc,
            is_outlier=False, is_corrected=False,
            show_colorbar=show_colorbar, show_legend=show_legend,
            legend_group='original', name='Měření'
        )
    
    # Outliers
    df_outlier = df_plot[is_outlier]
    if len(df_outlier) > 0:
        add_scatter_trace(
            fig, df_outlier, hpge_act, nai_act, row, 1,
            customdata[is_outlier], cols['weight'],
            hpge_unc, nai_unc,
            is_outlier=True, is_corrected=False,
            show_colorbar=False, show_legend=show_legend,
            legend_group='outlier', name='Outlier'
        )
    
    # 1:1 linie
    add_identity_line(fig, df_plot[hpge_act].values, df_plot[nai_act].values, row, 1)
    
    # ---- Sloupec 2: Korigovaná data ----
    if nai_act_corr in df_plot.columns:
        # Z-score pro korigovaná data
        zscore_corr = calculate_zscore(df_plot[hpge_act].values, df_plot[nai_act_corr].values, U_hpge, U_nai)
        is_outlier_corr = zscore_corr >= outlier_threshold
        
        customdata_corr = prepare_customdata(
            df_plot, cols['weight'], cols['description'],
            hpge_unc, nai_unc, zscore_corr, density
        )
        
        # Normální body
        df_normal_corr = df_plot[~is_outlier_corr]
        if len(df_normal_corr) > 0:
            add_scatter_trace(
                fig, df_normal_corr, hpge_act, nai_act_corr, row, 2,
                customdata_corr[~is_outlier_corr], cols['weight'],
                hpge_unc, nai_unc,
                is_outlier=False, is_corrected=True,
                show_colorbar=False, show_legend=show_legend,
                legend_group='corrected', name='Korigováno'
            )
        
        # Outliers
        df_outlier_corr = df_plot[is_outlier_corr]
        if len(df_outlier_corr) > 0:
            add_scatter_trace(
                fig, df_outlier_corr, hpge_act, nai_act_corr, row, 2,
                customdata_corr[is_outlier_corr], cols['weight'],
                hpge_unc, nai_unc,
                is_outlier=True, is_corrected=True,
                show_colorbar=False, show_legend=False,
                legend_group='outlier', name='Outlier corr'
            )
        
        # 1:1 linie
        add_identity_line(fig, df_plot[hpge_act].values, df_plot[nai_act_corr].values, row, 2)
        
        # Anotace s korekčními koeficienty
        if correction_params:
            add_correction_annotation(fig, correction_params, correction_model, row, 2)
