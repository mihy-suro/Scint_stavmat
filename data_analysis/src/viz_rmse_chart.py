#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
viz_rmse_chart.py - Dumbbell chart pro zobrazení zlepšení RMSE

Obsahuje:
- add_rmse_dumbbell: Vytvoření dumbbell chartu
- collect_rmse_data: Sběr RMSE dat pro všechny prvky
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from typing import List, Dict, Any, Tuple

from .viz_stats import calculate_statistics


def collect_rmse_data(
    df_deconv: pd.DataFrame,
    df_186: pd.DataFrame,
    elements_deconv: Dict[str, Tuple[str, str]]
) -> List[Dict[str, Any]]:
    """
    Sbírá RMSE data pro všechny prvky.
    
    Parameters:
    -----------
    df_deconv : DataFrame
        Data z dekonvoluční analýzy
    df_186 : DataFrame
        Data z 186 keV analýzy
    elements_deconv : dict
        Slovník prvků pro dekonvoluci
        
    Returns:
    --------
    List[dict] s klíči: name, rmse_before, rmse_after, reduction
    """
    rmse_data = []
    
    # Dekonvoluční data (K, Th, Ra)
    for element_name, (activity_col, _) in elements_deconv.items():
        hpge_act = f"{activity_col}_HPGe"
        nai_act = f"{activity_col}_NaI"
        nai_act_corr = f"{activity_col}_NaI_corrected"
        
        if nai_act_corr not in df_deconv.columns:
            continue
            
        hpge = df_deconv[hpge_act].dropna().values
        nai = df_deconv[nai_act].dropna().values
        nai_corr = df_deconv[nai_act_corr].dropna().values
        
        # Potřebujeme shodné délky
        mask = ~(np.isnan(df_deconv[hpge_act]) | np.isnan(df_deconv[nai_act]) | np.isnan(df_deconv[nai_act_corr]))
        hpge = df_deconv.loc[mask, hpge_act].values
        nai = df_deconv.loc[mask, nai_act].values
        nai_corr = df_deconv.loc[mask, nai_act_corr].values
        
        stats_orig = calculate_statistics(hpge, nai)
        stats_corr = calculate_statistics(hpge, nai_corr)
        
        if stats_orig['RMSE'] > 0:
            reduction = (1 - stats_corr['RMSE'] / stats_orig['RMSE']) * 100
        else:
            reduction = 0
        
        rmse_data.append({
            'name': element_name,
            'rmse_before': stats_orig['RMSE'],
            'rmse_after': stats_corr['RMSE'],
            'reduction': reduction
        })
    
    # Ra-226 (186 keV)
    if "A_Ra_NaI_corrected" in df_186.columns and len(df_186) > 0:
        mask_186 = ~(np.isnan(df_186["A_Ra_HPGe"]) | np.isnan(df_186["A_Ra_NaI"]) | np.isnan(df_186["A_Ra_NaI_corrected"]))
        
        if mask_186.sum() > 0:
            hpge_186 = df_186.loc[mask_186, "A_Ra_HPGe"].values
            nai_186 = df_186.loc[mask_186, "A_Ra_NaI"].values
            nai_186_corr = df_186.loc[mask_186, "A_Ra_NaI_corrected"].values
            
            stats_186_orig = calculate_statistics(hpge_186, nai_186)
            stats_186_corr = calculate_statistics(hpge_186, nai_186_corr)
            
            if stats_186_orig['RMSE'] > 0:
                reduction_186 = (1 - stats_186_corr['RMSE'] / stats_186_orig['RMSE']) * 100
            else:
                reduction_186 = 0
            
            rmse_data.append({
                'name': 'Ra-226 (186 keV)',
                'rmse_before': stats_186_orig['RMSE'],
                'rmse_after': stats_186_corr['RMSE'],
                'reduction': reduction_186
            })
    
    return rmse_data


def add_rmse_dumbbell(
    fig: go.Figure,
    rmse_data: List[Dict[str, Any]],
    row: int,
    col: int
) -> None:
    """
    Přidá dumbbell chart zobrazující zlepšení RMSE.
    
    Parameters:
    -----------
    fig : Figure
        Plotly figure
    rmse_data : list
        Seznam slovníků s RMSE daty
    row, col : int
        Pozice v subplot gridu
    """
    if not rmse_data:
        return
    
    # Seřazení podle RMSE before (největší nahoře)
    rmse_data = sorted(rmse_data, key=lambda x: x['rmse_before'], reverse=True)
    
    y_labels = [d['name'] for d in rmse_data]
    rmse_before = [d['rmse_before'] for d in rmse_data]
    rmse_after = [d['rmse_after'] for d in rmse_data]
    reductions = [d['reduction'] for d in rmse_data]
    
    # Spojovací čáry (dumbbell)
    for name, rb, ra in zip(y_labels, rmse_before, rmse_after):
        fig.add_trace(
            go.Scatter(
                x=[rb, ra],
                y=[name, name],
                mode='lines',
                line=dict(color='gray', width=3),
                showlegend=False,
                hoverinfo='skip'
            ),
            row=row, col=col
        )
    
    # Body "před" (červené)
    fig.add_trace(
        go.Scatter(
            x=rmse_before,
            y=y_labels,
            mode='markers+text',
            marker=dict(color='#e74c3c', size=14, symbol='circle'),
            text=[f'{v:.1f}' for v in rmse_before],
            textposition='top center',
            textfont=dict(size=9, color='#e74c3c'),
            name='Před korekcí',
            hovertemplate='%{y}<br>RMSE před: %{x:.2f} Bq/kg<extra></extra>',
            showlegend=False,
            legendgroup='dumbbell'
        ),
        row=row, col=col
    )
    
    # Body "po" (zelené)
    fig.add_trace(
        go.Scatter(
            x=rmse_after,
            y=y_labels,
            mode='markers+text',
            marker=dict(color='#27ae60', size=14, symbol='circle'),
            text=[f'{v:.1f}' for v in rmse_after],
            textposition='bottom center',
            textfont=dict(size=9, color='#27ae60'),
            name='Po korekci',
            hovertemplate='%{y}<br>RMSE po: %{x:.2f} Bq/kg<extra></extra>',
            showlegend=False,
            legendgroup='dumbbell'
        ),
        row=row, col=col
    )
    
    # Lokální legenda pro RMSE graf (vpravo nahoře uvnitř grafu)
    fig.add_annotation(
        x=0.98,
        y=0.98,
        xref='x9 domain',
        yref='y9 domain',
        text='<span style="color:#e74c3c">●</span> Před korekcí<br><span style="color:#27ae60">●</span> Po korekci',
        showarrow=False,
        font=dict(size=11),
        align='left',
        xanchor='right',
        yanchor='top',
        bgcolor='rgba(255,255,255,0.8)',
        bordercolor='lightgray',
        borderwidth=1
    )
    
    # Anotace s procenty redukce
    for i, (name, reduction) in enumerate(zip(y_labels, reductions)):
        avg_x = (rmse_before[i] + rmse_after[i]) / 2
        fig.add_annotation(
            x=avg_x,
            y=name,
            text=f"<b>-{reduction:.0f}%</b>",
            showarrow=False,
            font=dict(size=11, color='#2c3e50'),
            bgcolor='rgba(255,255,255,0.7)',
            row=row, col=col
        )
