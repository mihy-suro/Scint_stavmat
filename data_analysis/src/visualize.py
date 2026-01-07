#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visualize.py - Vizualizace porovnání HPGe vs NaI(Tl) měření

Vytváří interaktivní grafy:
- Řádek 1: K-40 (před | po korekci)
- Řádek 2: Th-232 (před | po korekci)
- Řádek 3: Ra-226 (před | po korekci)
- Řádek 4: Ra-226 186 keV (před | po korekci)
- Řádek 5: RMSE dumbbell chart (zlepšení po korekci)

Vstup: comparison_input.xlsx (vytvořený pomocí build_input.py)
Výstup: comparison_results_*.html

Konfigurace: config.yaml
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Import z lokálních modulů
from .density_correction_utils import optimize_all_elements, apply_correction
from .viz_config import (
    VizConfig, get_viz_config,
    CORRECTION_MODEL, REFERENCE_DENSITY, RELATIVE_UNCERTAINTY_NAI,
    OUTLIER_THRESHOLD, ELEMENTS_DECONV, ELEMENT_186, METHOD_186_KEV
)
from .viz_data import (
    load_comparison_data, prepare_comparison_df,
    apply_uncertainty_expansion, calculate_density, get_column_names
)
from .viz_stats import calculate_zscore, calculate_statistics, identify_outliers
from .viz_scatter import (
    prepare_customdata, add_scatter_trace, add_identity_line,
    add_correction_annotation, plot_element_comparison
)
from .viz_rmse_chart import collect_rmse_data, add_rmse_dumbbell


def create_visualization(
    df_deconv: pd.DataFrame,
    df_186: pd.DataFrame,
    correction_results: dict,
    output_path: Path,
    correction_186: dict = None,
    outlier_threshold: float = 3.0
) -> go.Figure:
    """
    Vytvoří 5-řádkovou vizualizaci porovnání HPGe vs NaI(Tl).
    
    Layout:
    - Řádek 1: K-40 (před | po korekci)
    - Řádek 2: Th-232 (před | po korekci)
    - Řádek 3: Ra-226 (před | po korekci)
    - Řádek 4: Ra-226 186 keV (před | po korekci)
    - Řádek 5: RMSE dumbbell chart (colspan=2)
    
    Parameters:
    -----------
    df_deconv : DataFrame
        Data z dekonvoluční analýzy (K-40, Th-232, Ra-226)
    df_186 : DataFrame
        Data z 186 keV analýzy (Ra-226)
    correction_results : dict
        Korekční parametry pro dekonvoluční prvky
    output_path : Path
        Cesta pro uložení HTML
    correction_186 : dict, optional
        Korekční parametry pro 186 keV
    outlier_threshold : float
        Z-score práh pro identifikaci outlierů
        
    Returns:
    --------
    go.Figure : Plotly figure
    """
    config = get_viz_config()
    element_order = config.element_order
    
    # Názvy subplotů
    subplot_titles = []
    for elem in element_order:
        subplot_titles.extend([elem, f"{elem} (korigováno)"])
    subplot_titles.extend(["Ra-226 (186 keV)", "Ra-226 (186 keV) korigováno"])
    subplot_titles.append("Zlepšení RMSE po korekci")
    
    # Vytvoření 5×2 gridu - řádek 5 má colspan=2
    fig = make_subplots(
        rows=5, cols=2,
        subplot_titles=subplot_titles,
        horizontal_spacing=0.08,
        vertical_spacing=0.06,
        specs=[
            [{}, {}],   # Řádek 1: K-40
            [{}, {}],   # Řádek 2: Th-232
            [{}, {}],   # Řádek 3: Ra-226
            [{}, {}],   # Řádek 4: Ra-226 186 keV
            [{"colspan": 2}, None]  # Řádek 5: RMSE chart
        ],
        row_heights=[0.2, 0.2, 0.2, 0.2, 0.2]
    )
    
    # ========================================
    # ŘÁDKY 1-3: Dekonvoluční data (K, Th, Ra)
    # ========================================
    first_element = True
    
    for row_idx, element_name in enumerate(element_order):
        row = row_idx + 1
        activity_col, uncertainty_col = ELEMENTS_DECONV[element_name]
        
        correction_params = correction_results.get(element_name, None)
        
        plot_element_comparison(
            fig=fig,
            df=df_deconv,
            element_name=element_name,
            activity_col=activity_col,
            uncertainty_col=uncertainty_col,
            row=row,
            correction_params=correction_params,
            correction_model=CORRECTION_MODEL,
            outlier_threshold=outlier_threshold,
            show_colorbar=first_element,
            show_legend=first_element
        )
        
        # Popisky os
        fig.update_xaxes(title_text="HPGe [Bq/kg]", row=row, col=1)
        fig.update_yaxes(title_text="NaI(Tl) [Bq/kg]", row=row, col=1)
        fig.update_xaxes(title_text="HPGe [Bq/kg]", row=row, col=2)
        fig.update_yaxes(title_text="NaI corr [Bq/kg]", row=row, col=2)
        
        first_element = False
    
    # ========================================
    # ŘÁDEK 4: Ra-226 (186 keV)
    # ========================================
    if len(df_186) > 0:
        plot_186_kev(
            fig=fig,
            df_186=df_186,
            correction_186=correction_186,
            correction_model=CORRECTION_MODEL,
            outlier_threshold=outlier_threshold,
            row=4
        )
    
    # ========================================
    # ŘÁDEK 5: RMSE Dumbbell chart
    # ========================================
    rmse_data = collect_rmse_data(df_deconv, df_186, ELEMENTS_DECONV)
    add_rmse_dumbbell(fig, rmse_data, row=5, col=1)
    
    fig.update_xaxes(title_text="RMSE [Bq/kg]", row=5, col=1)
    fig.update_yaxes(title_text="", row=5, col=1)
    
    # ========================================
    # Layout
    # ========================================
    fig.update_layout(
        title_text="Porovnání metod: HPGe vs NaI(Tl)",
        height=config.figure_height,
        width=config.figure_width,
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


def plot_186_kev(
    fig: go.Figure,
    df_186: pd.DataFrame,
    correction_186: dict,
    correction_model: str,
    outlier_threshold: float,
    row: int
) -> None:
    """
    Vykreslí porovnání pro Ra-226 (186 keV).
    
    Parameters:
    -----------
    fig : Figure
        Plotly figure
    df_186 : DataFrame
        Data z 186 keV analýzy
    correction_186 : dict
        Korekční parametry
    correction_model : str
        Typ korekčního modelu
    outlier_threshold : float
        Práh z-score
    row : int
        Řádek v subplot gridu
    """
    hpge_act = "A_Ra_HPGe"
    nai_act = "A_Ra_NaI"
    nai_act_corr = "A_Ra_NaI_corrected"
    hpge_unc = "U_Ra_HPGe"
    nai_unc = "U_Ra_NaI"
    
    cols = get_column_names(df_186)
    df_plot = df_186.dropna(subset=[hpge_act, nai_act]).copy()
    
    if len(df_plot) == 0:
        return
    
    density = calculate_density(df_plot)
    
    # Z-score pro původní data
    U_hpge = df_plot[hpge_unc].values if hpge_unc in df_plot.columns else np.ones(len(df_plot))
    U_nai = df_plot[nai_unc].values if nai_unc in df_plot.columns else np.ones(len(df_plot))
    zscore_orig = calculate_zscore(df_plot[hpge_act].values, df_plot[nai_act].values, U_hpge, U_nai)
    is_outlier = zscore_orig >= outlier_threshold
    
    customdata = prepare_customdata(
        df_plot, cols['weight'], cols['description'],
        hpge_unc, nai_unc, zscore_orig, density
    )
    
    # ---- Sloupec 1: Původní data ----
    df_normal = df_plot[~is_outlier]
    if len(df_normal) > 0:
        add_scatter_trace(
            fig, df_normal, hpge_act, nai_act, row, 1,
            customdata[~is_outlier], cols['weight'],
            hpge_unc, nai_unc,
            is_outlier=False, is_corrected=False,
            show_colorbar=False, show_legend=False,
            legend_group='original', name='Měření 186keV'
        )
    
    df_outlier = df_plot[is_outlier]
    if len(df_outlier) > 0:
        add_scatter_trace(
            fig, df_outlier, hpge_act, nai_act, row, 1,
            customdata[is_outlier], cols['weight'],
            hpge_unc, nai_unc,
            is_outlier=True, is_corrected=False,
            show_colorbar=False, show_legend=False,
            legend_group='outlier', name='Outlier 186keV'
        )
    
    add_identity_line(fig, df_plot[hpge_act].values, df_plot[nai_act].values, row, 1)
    
    # ---- Sloupec 2: Korigovaná data ----
    if nai_act_corr in df_plot.columns:
        zscore_corr = calculate_zscore(df_plot[hpge_act].values, df_plot[nai_act_corr].values, U_hpge, U_nai)
        is_outlier_corr = zscore_corr >= outlier_threshold
        
        customdata_corr = prepare_customdata(
            df_plot, cols['weight'], cols['description'],
            hpge_unc, nai_unc, zscore_corr, density
        )
        
        df_normal_corr = df_plot[~is_outlier_corr]
        if len(df_normal_corr) > 0:
            add_scatter_trace(
                fig, df_normal_corr, hpge_act, nai_act_corr, row, 2,
                customdata_corr[~is_outlier_corr], cols['weight'],
                hpge_unc, nai_unc,
                is_outlier=False, is_corrected=True,
                show_colorbar=False, show_legend=False,
                legend_group='corrected', name='Korigováno 186keV'
            )
        
        df_outlier_corr = df_plot[is_outlier_corr]
        if len(df_outlier_corr) > 0:
            add_scatter_trace(
                fig, df_outlier_corr, hpge_act, nai_act_corr, row, 2,
                customdata_corr[is_outlier_corr], cols['weight'],
                hpge_unc, nai_unc,
                is_outlier=True, is_corrected=True,
                show_colorbar=False, show_legend=False,
                legend_group='outlier', name='Outlier 186keV corr'
            )
        
        add_identity_line(fig, df_plot[hpge_act].values, df_plot[nai_act_corr].values, row, 2)
        
        if correction_186:
            add_correction_annotation(fig, correction_186, correction_model, row, 2)
    
    # Popisky os
    fig.update_xaxes(title_text="HPGe Ra-226 [Bq/kg]", row=row, col=1)
    fig.update_yaxes(title_text="NaI(Tl) Ra-226 (186 keV) [Bq/kg]", row=row, col=1)
    fig.update_xaxes(title_text="HPGe Ra-226 [Bq/kg]", row=row, col=2)
    fig.update_yaxes(title_text="NaI corr Ra-226 (186 keV) [Bq/kg]", row=row, col=2)


def run_visualization(input_file: Path, output_dir: Path, outlier_threshold: float = 3.0) -> Path:
    """
    Hlavní funkce pro vizualizaci.
    
    Provede kompletní pipeline:
    1. Načtení dat
    2. Příprava DataFrames
    3. Optimalizace korekčních faktorů
    4. Aplikace korekcí
    5. Vytvoření vizualizace
    6. Statistické shrnutí
    
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
    print("\n" + "=" * 60)
    print("VIZUALIZACE POROVNÁNÍ HPGe vs NaI(Tl)")
    print("=" * 60)
    
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
    df_186 = prepare_comparison_df(df, METHOD_186_KEV)
    df_186 = apply_uncertainty_expansion(df_186, ELEMENT_186, RELATIVE_UNCERTAINTY_NAI)
    if len(df_186) > 0:
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
    correction_186 = None
    if len(df_186) > 0:
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
    df_deconv = apply_corrections_to_df(df_deconv, ELEMENTS_DECONV, correction_results)
    
    # 5b) Aplikace korekcí na 186 keV data
    if correction_186 and len(df_186) > 0:
        print("    Aplikace korekcí na 186 keV data...")
        df_186 = apply_correction_186(df_186, correction_186)
    
    # 6) Vytvoření vizualizace
    print("\n6) Vytváření vizualizace...")
    output_file = output_dir / "comparison_results_plot.html"
    
    create_visualization(df_deconv, df_186, correction_results, output_file, correction_186, outlier_threshold)
    
    # 7) Statistické shrnutí
    print_statistics_summary(df_deconv, df_186)
    
    print("\n" + "=" * 60)
    print(f"Hotovo! Výstup: {output_file.name}")
    print("=" * 60 + "\n")
    
    return output_file


def apply_corrections_to_df(
    df: pd.DataFrame,
    elements: dict,
    correction_results: dict
) -> pd.DataFrame:
    """Aplikuje korekce na DataFrame."""
    df = df.copy()
    
    for element_name, (activity_col, _) in elements.items():
        nai_act = f"{activity_col}_NaI"
        nai_act_corr = f"{activity_col}_NaI_corrected"
        
        params = correction_results.get(element_name, {})
        
        if CORRECTION_MODEL == 'scaled_exponential':
            a_val = params.get('a', 1.0)
            b_val = params.get('b', 0.0)
            c_val = 0.0
        elif CORRECTION_MODEL == 'scaled_exponential_quadratic':
            a_val = params.get('a', 1.0)
            b_val = params.get('b', 0.0)
            c_val = params.get('c', 0.0)
        else:
            a_val = 1.0
            b_val = params.get('b', 0.0)
            c_val = params.get('c', 0.0)
        
        df[nai_act_corr] = apply_correction(
            df[nai_act].values,
            df['density'].values,
            b=b_val,
            c=c_val,
            a=a_val,
            model=CORRECTION_MODEL,
            rho_ref=REFERENCE_DENSITY
        )
    
    return df


def apply_correction_186(df: pd.DataFrame, correction_186: dict) -> pd.DataFrame:
    """Aplikuje korekce na 186 keV data."""
    df = df.copy()
    
    nai_act = "A_Ra_NaI"
    nai_act_corr = "A_Ra_NaI_corrected"
    
    if CORRECTION_MODEL == 'scaled_exponential':
        a_val = correction_186.get('a', 1.0)
        b_val = correction_186.get('b', 0.0)
        c_val = 0.0
    elif CORRECTION_MODEL == 'scaled_exponential_quadratic':
        a_val = correction_186.get('a', 1.0)
        b_val = correction_186.get('b', 0.0)
        c_val = correction_186.get('c', 0.0)
    else:
        a_val = 1.0
        b_val = correction_186.get('b', 0.0)
        c_val = correction_186.get('c', 0.0)
    
    df[nai_act_corr] = apply_correction(
        df[nai_act].values,
        df['density'].values,
        b=b_val,
        c=c_val,
        a=a_val,
        model=CORRECTION_MODEL,
        rho_ref=REFERENCE_DENSITY
    )
    
    return df


def print_statistics_summary(df_deconv: pd.DataFrame, df_186: pd.DataFrame) -> None:
    """Vytiskne statistické shrnutí."""
    print("\n" + "=" * 60)
    print("STATISTICKÉ SHRNUTÍ")
    print("=" * 60)
    
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
        
        delta_r2 = stats_corr['R2'] - stats_orig['R2']
        rmse_reduction = (1 - stats_corr['RMSE'] / stats_orig['RMSE']) * 100 if stats_orig['RMSE'] > 0 else 0
        print(f"  Zlepšení:   ΔR²={delta_r2:+.4f}, RMSE redukce={rmse_reduction:.1f}%")
    
    # 186 keV
    if len(df_186) > 0 and "A_Ra_NaI_corrected" in df_186.columns:
        print("\n--- Ra-226 (186 keV) ---")
        hpge_186 = df_186["A_Ra_HPGe"].values
        nai_186 = df_186["A_Ra_NaI"].values
        nai_186_corr = df_186["A_Ra_NaI_corrected"].values
        
        stats_186 = calculate_statistics(hpge_186, nai_186)
        stats_186_corr = calculate_statistics(hpge_186, nai_186_corr)
        
        print(f"  Původní:    n={stats_186['n']}, R²={stats_186['R2']:.4f}, RMSE={stats_186['RMSE']:.2f} Bq/kg")
        print(f"  Korigované: R²={stats_186_corr['R2']:.4f}, RMSE={stats_186_corr['RMSE']:.2f} Bq/kg")
        
        delta_r2 = stats_186_corr['R2'] - stats_186['R2']
        rmse_reduction = (1 - stats_186_corr['RMSE'] / stats_186['RMSE']) * 100 if stats_186['RMSE'] > 0 else 0
        print(f"  Zlepšení:   ΔR²={delta_r2:+.4f}, RMSE redukce={rmse_reduction:.1f}%")


if __name__ == "__main__":
    # Pro samostatné testování
    script_dir = Path(__file__).parent
    
    # Najít nejnovější comparison_input
    input_file = script_dir / "comparison_input.xlsx"
    if input_file.exists():
        run_visualization(input_file, script_dir)
    else:
        print("Soubor comparison_input.xlsx nenalezen. Spusťte nejprve build_input.py")
