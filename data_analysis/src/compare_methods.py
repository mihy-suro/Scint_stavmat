"""
Porovnání výsledků měření pomocí HPGe a NaI(Tl) scintilační spektrometrie

Skript načte data z Excel souboru a vytvoří interaktivní scatter ploty
pro porovnání obou metod pro K-40, Ra-226 a Th-232.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os

# Import korekčních funkcí pro sampoabsorpci
from .density_correction_utils import optimize_all_elements, apply_correction

# ============================================================
# KONFIGURACE
# ============================================================
# Relativní nejistota NaI(Tl) k přidání k měření (např. 0.05 = 5%)
# Celková nejistota se vypočítá metodou šíření chyb:
# U_total = sqrt(U_original^2 + (A * rel_uncertainty)^2)
RELATIVE_UNCERTAINTY_NAI = 0.1  # relativní nejistota

# Korekce sampoabsorpce - referenční hustota [g/cm³]
# Hustota kalibračního vzorku nebo typického vzorku (voda = 1.0 g/cm³)
REFERENCE_DENSITY = 1.0  # g/cm³

# Model korekce: 'exponential', 'linear', 'power', 'quadratic_centered'
CORRECTION_MODEL = 'quadratic_centered'
# ============================================================

def calculate_total_uncertainty(activity, original_uncertainty, relative_uncertainty):
    """
    Vypočítá celkovou nejistotu metodou šíření chyb.
    
    Parameters:
    -----------
    activity : float or array
        Hodnota aktivity
    original_uncertainty : float or array
        Původní nejistota měření
    relative_uncertainty : float
        Relativní nejistota (např. 0.05 pro 5%)
    
    Returns:
    --------
    float or array
        Celková nejistota
    """
    additional_uncertainty = activity * relative_uncertainty
    total_uncertainty = np.sqrt(original_uncertainty**2 + additional_uncertainty**2)
    return total_uncertainty


def main(excel_file: str = None):
    """
    Hlavní funkce pro porovnání metod HPGe vs NaI(Tl).
    
    Parameters:
    -----------
    excel_file : str, optional
        Cesta k Excel souboru s daty. Pokud není zadána, hledá vysldky_scint.xlsx
    """
    from pathlib import Path
    
    if excel_file is None:
        # Legacy behavior - hledá soubor v input/ adresáři
        script_dir = Path(__file__).parent.parent
        excel_file = script_dir / "input" / "vysldky_scint.xlsx"
    else:
        excel_file = Path(excel_file)
    
    if not excel_file.exists():
        raise FileNotFoundError(
            f"Soubor nenalezen: {excel_file}\n"
            f"Tento skript je legacy a vyžaduje specifický vstupní soubor."
        )
    
    df = pd.read_excel(excel_file, sheet_name="porovnani")

    print("Načtená data:")
    print(df.head(10))
    print("\nSloupce:", df.columns.tolist())
    print("\nMetody:", df['Metoda'].unique())
    print("\nPočet vzorků:", df['Kniha analýz'].nunique())

    # Pivot dat pro srovnání metod
    # Rozdělíme data podle metody
    df_hpge = df[df['Metoda'] == 'HPGe'].copy()
    df_nai = df[df['Metoda'] == 'NaI(Tl)'].copy()
    # Aplikace rozšířené nejistoty na NaI(Tl) data
    for col_prefix in ['Ra', 'K', 'Th']:
        activity_col = f'A_{col_prefix}'
        uncertainty_col = f'U_{col_prefix}'
        
        if activity_col in df_nai.columns and uncertainty_col in df_nai.columns:
            df_nai[uncertainty_col] = calculate_total_uncertainty(
                df_nai[activity_col],
            df_nai[uncertainty_col],
            RELATIVE_UNCERTAINTY_NAI
        )
        print(f"Aplikována rozšířená nejistota ({RELATIVE_UNCERTAINTY_NAI*100:.1f}%) na {uncertainty_col} pro NaI(Tl)")

# Spojíme data podle ID vzorku (Kniha analýz)
df_compare = df_hpge.merge(
    df_nai,
    on='Kniha analýz',
    suffixes=('_HPGe', '_NaI'),
    how='inner'
)

print(f"\nPočet vzorků pro porovnání: {len(df_compare)}")
print("\nSloupce po sloučení:", df_compare.columns.tolist())

# Vytvoření scatter plotů pro každý prvek
elements = {
    'Ra-226': ('A_Ra', 'U_Ra'),
    'K-40': ('A_K', 'U_K'),
    'Th-232': ('A_Th', 'U_Th')
}

# Kontrola dostupných sloupců pro každý prvek
available_elements = {}
for element, (activity_col, uncertainty_col) in elements.items():
    hpge_act = f"{activity_col}_HPGe"
    nai_act = f"{activity_col}_NaI"
    if hpge_act in df_compare.columns and nai_act in df_compare.columns:
        available_elements[element] = (activity_col, uncertainty_col)
        print(f"\n{element}: OK")
    else:
        print(f"\n{element}: Sloupce nenalezeny")

# ============================================================
# OPTIMALIZACE KOREKCE SAMPOABSORPCE
# ============================================================
# Najde optimální korekční faktory pro každý prvek
correction_results = optimize_all_elements(
    df_compare,
    available_elements,
    model=CORRECTION_MODEL,
    rho_ref=REFERENCE_DENSITY,
    verbose=True
)

# Aplikace korekcí na NaI data - vytvoření nových sloupců
weight_col = 'Hmotnost [kg]_HPGe' if 'Hmotnost [kg]_HPGe' in df_compare.columns else 'Hmotnost [kg]'
volume_col = 'Objem [l]_HPGe' if 'Objem [l]_HPGe' in df_compare.columns else 'Objem [l]'
df_compare['density'] = df_compare[weight_col] / df_compare[volume_col]

for element_name, (activity_col, uncertainty_col) in available_elements.items():
    nai_act = f"{activity_col}_NaI"
    nai_act_corr = f"{activity_col}_NaI_corrected"
    
    # Aplikace korekce
    b_val = correction_results[element_name]['b']
    c_val = correction_results[element_name].get('c', 0.0)
    
    df_compare[nai_act_corr] = apply_correction(
        df_compare[nai_act].values,
        df_compare['density'].values,
        b=b_val,
        c=c_val,
        model=CORRECTION_MODEL,
        rho_ref=REFERENCE_DENSITY
    )
    print(f"Vytvořen sloupec: {nai_act_corr}")

# ============================================================

# Funkce pro vytvoření scatter plotu s error bary
def create_comparison_plot(df, element_name, activity_col, uncertainty_col, corrected=False):
    """
    Vytvoří scatter plot porovnávající HPGe a NaI(Tl) měření
    
    Parameters:
    -----------
    corrected : bool
        Pokud True, použije korigovaná NaI data
    """
    hpge_act = f"{activity_col}_HPGe"
    # Výběr sloupce podle toho, zda chceme korigovaná data
    nai_act = f"{activity_col}_NaI_corrected" if corrected else f"{activity_col}_NaI"
    hpge_unc = f"{uncertainty_col}_HPGe"
    nai_unc = f"{uncertainty_col}_NaI"
    
    # Odstranění chybějících dat
    df_plot = df.dropna(subset=[hpge_act, nai_act])
    
    if len(df_plot) == 0:
        print(f"Žádná data pro {element_name}")
        return None
    
    # Vytvoření scatter plotu
    fig = go.Figure()
    
    # Získání hmotnosti pro barevnou škálu
    # Hmotnost může být v _HPGe nebo _NaI sloupci, použijeme HPGe
    weight_col = 'Hmotnost [kg]_HPGe' if 'Hmotnost [kg]_HPGe' in df_plot.columns else 'Hmotnost [kg]'
    volume_col = 'Objem [l]_HPGe' if 'Objem [l]_HPGe' in df_plot.columns else 'Objem [l]'
    desc_col = 'Popis vzorku_HPGe' if 'Popis vzorku_HPGe' in df_plot.columns else 'Popis vzorku'
    
    # Výpočet hustoty v g/cm³
    density = df_plot[weight_col] / df_plot[volume_col]
    
    # Data body s error bary
    fig.add_trace(go.Scatter(
        x=df_plot[hpge_act],
        y=df_plot[nai_act],
        mode='markers',
        marker=dict(
            size=10,
            color=df_plot[weight_col],
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(
                title='Hmotnost<br>[kg]',
                thickness=15,
                len=0.7
            ),
            opacity=0.8,
            line=dict(width=1, color='white')
        ),
        error_x=dict(
            type='data',
            array=df_plot[hpge_unc] if hpge_unc in df_plot.columns else None,
            visible=True,
            color='rgba(128, 128, 128, 0.3)',
            thickness=1,
            width=3
        ),
        error_y=dict(
            type='data',
            array=df_plot[nai_unc] if nai_unc in df_plot.columns else None,
            visible=True,
            color='rgba(128, 128, 128, 0.3)',
            thickness=1,
            width=3
        ),
        text=df_plot['Kniha analýz'],
        customdata=np.column_stack((df_plot[weight_col], density, df_plot[desc_col], 
                                     df_plot[hpge_unc] if hpge_unc in df_plot.columns else np.zeros(len(df_plot)),
                                     df_plot[nai_unc] if nai_unc in df_plot.columns else np.zeros(len(df_plot)))),
        hovertemplate='<b>%{text}</b><br>' +
                      '%{customdata[2]}<br>' +
                      f'HPGe: %{{x:.2f}} ± %{{customdata[3]:.2f}} Bq/kg<br>' +
                      f'NaI(Tl): %{{y:.2f}} ± %{{customdata[4]:.2f}} Bq/kg<br>' +
                      'Hmotnost: %{customdata[0]:.3f} kg<br>' +
                      'Hustota: %{customdata[1]:.3f} g/cm³<br>' +
                      '<extra></extra>',
        name='Měření'
    ))
    
    # Přidání ideální linie (1:1)
    max_val = max(df_plot[hpge_act].max(), df_plot[nai_act].max())
    min_val = min(df_plot[hpge_act].min(), df_plot[nai_act].min())
    
    fig.add_trace(go.Scatter(
        x=[min_val, max_val],
        y=[min_val, max_val],
        mode='lines',
        line=dict(color='red', dash='dash', width=2),
        name='1:1 linie',
        hoverinfo='skip'
    ))
    
    # Lineární fit
    from scipy import stats
    slope, intercept, r_value, p_value, std_err = stats.linregress(
        df_plot[hpge_act], df_plot[nai_act]
    )
    
    x_fit = np.linspace(min_val, max_val, 100)
    y_fit = slope * x_fit + intercept
    
    fig.add_trace(go.Scatter(
        x=x_fit,
        y=y_fit,
        mode='lines',
        line=dict(color='green', width=2),
        name=f'Fit: y={slope:.3f}x+{intercept:.3f}<br>R²={r_value**2:.3f}',
        hoverinfo='skip'
    ))
    
    # Formátování grafu
    fig.update_layout(
        title=f'Porovnání metod HPGe vs NaI(Tl) - {element_name}',
        xaxis_title=f'HPGe Aktivita [Bq/kg]',
        yaxis_title=f'NaI(Tl) Aktivita [Bq/kg]',
        hovermode='closest',
        width=800,
        height=700,
        showlegend=True,
        template='plotly_white',
        font=dict(size=12)
    )
    
    # Stejné škály na obou osách
    fig.update_xaxes(scaleanchor="y", scaleratio=1)
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    
    return fig

# Vytvoření grafů pro každý dostupný prvek
figures = {}
# Jednotlivé grafy se negenerují, pouze kombinovaný
# for element_name, (activity_col, uncertainty_col) in available_elements.items():
#     print(f"\nVytvářím graf pro {element_name}...")
#     fig = create_comparison_plot(df_compare, element_name, activity_col, uncertainty_col)
#     if fig is not None:
#         figures[element_name] = fig

# Vytvoření kombinovaného grafu se všemi prvky
if len(available_elements) > 0:
    print("\nVytvářím kombinovaný graf (původní + korigovaná data)...")
    
    # Subplot s 2 řádky x N sloupci
    # Řádek 1: Původní data
    # Řádek 2: Korigovaná data
    n_elements = len(available_elements)
    rows, cols = 2, n_elements
    
    # Vytvoření subplot titles
    element_names = list(available_elements.keys())
    subplot_titles = element_names + [f"{name} (corrected)" for name in element_names]
    
    fig_combined = make_subplots(
        rows=rows, cols=cols,
        subplot_titles=subplot_titles,
        horizontal_spacing=0.08,
        vertical_spacing=0.15
    )
    
    # ŘÁDEK 1: Původní data
    for idx, (element_name, (activity_col, uncertainty_col)) in enumerate(available_elements.items()):
        row = 1
        col = idx + 1
        
        hpge_act = f"{activity_col}_HPGe"
        nai_act = f"{activity_col}_NaI"
        hpge_unc = f"{uncertainty_col}_HPGe"
        nai_unc = f"{uncertainty_col}_NaI"
        
        df_plot = df_compare.dropna(subset=[hpge_act, nai_act])
        
        if len(df_plot) > 0:
            # Získání hmotnosti pro barevnou škálu
            weight_col = 'Hmotnost [kg]_HPGe' if 'Hmotnost [kg]_HPGe' in df_plot.columns else 'Hmotnost [kg]'
            volume_col = 'Objem [l]_HPGe' if 'Objem [l]_HPGe' in df_plot.columns else 'Objem [l]'
            desc_col = 'Popis vzorku_HPGe' if 'Popis vzorku_HPGe' in df_plot.columns else 'Popis vzorku'
            
            # Výpočet hustoty v g/cm³
            density = df_plot[weight_col] / df_plot[volume_col]
            
            # Data body
            fig_combined.add_trace(
                go.Scatter(
                    x=df_plot[hpge_act],
                    y=df_plot[nai_act],
                    mode='markers',
                    marker=dict(
                        size=8,
                        color=df_plot[weight_col],
                        colorscale='Viridis',
                        showscale=(idx == 0),  # Zobrazit colorbar pouze u prvního grafu
                        colorbar=dict(
                            title='Hmotnost<br>[kg]',
                            thickness=15,
                            len=0.35,
                            y=0.75,
                            x=1.02
                        ) if idx == 0 else None,
                        opacity=0.8,
                        line=dict(width=0.5, color='white')
                    ),
                    error_x=dict(
                        type='data',
                        array=df_plot[hpge_unc] if hpge_unc in df_plot.columns else None,
                        color='rgba(128, 128, 128, 0.3)',
                        thickness=1,
                        width=2
                    ),
                    error_y=dict(
                        type='data',
                        array=df_plot[nai_unc] if nai_unc in df_plot.columns else None,
                        color='rgba(128, 128, 128, 0.3)',
                        thickness=1,
                        width=2
                    ),
                    text=df_plot['Kniha analýz'],
                    customdata=np.column_stack((df_plot[weight_col], density, df_plot[desc_col],
                                                 df_plot[hpge_unc] if hpge_unc in df_plot.columns else np.zeros(len(df_plot)),
                                                 df_plot[nai_unc] if nai_unc in df_plot.columns else np.zeros(len(df_plot)))),
                    hovertemplate=f'<b>%{{text}}</b><br>%{{customdata[2]}}<br>HPGe: %{{x:.2f}} ± %{{customdata[3]:.2f}} Bq/kg<br>NaI(Tl): %{{y:.2f}} ± %{{customdata[4]:.2f}} Bq/kg<br>Hmotnost: %{{customdata[0]:.3f}} kg<br>Hustota: %{{customdata[1]:.3f}} g/cm³<extra></extra>',
                    showlegend=(idx == 0),
                    name='Měření',
                    legendgroup='original'
                ),
                row=row, col=col
            )
            
            # 1:1 linie
            max_val = max(df_plot[hpge_act].max(), df_plot[nai_act].max())
            min_val = min(df_plot[hpge_act].min(), df_plot[nai_act].min())
            
            fig_combined.add_trace(
                go.Scatter(
                    x=[min_val, max_val],
                    y=[min_val, max_val],
                    mode='lines',
                    line=dict(color='red', dash='dash', width=1),
                    showlegend=(idx == 0),
                    name='1:1',
                    hoverinfo='skip',
                    legendgroup='lines'
                ),
                row=row, col=col
            )
            
            # Osy
            fig_combined.update_xaxes(title_text="HPGe [Bq/kg]", row=row, col=col)
            fig_combined.update_yaxes(title_text="NaI(Tl) [Bq/kg]", row=row, col=col)
    
    # ŘÁDEK 2: Korigovaná data
    for idx, (element_name, (activity_col, uncertainty_col)) in enumerate(available_elements.items()):
        row = 2
        col = idx + 1
        
        hpge_act = f"{activity_col}_HPGe"
        nai_act_corr = f"{activity_col}_NaI_corrected"
        hpge_unc = f"{uncertainty_col}_HPGe"
        nai_unc = f"{uncertainty_col}_NaI"
        
        df_plot = df_compare.dropna(subset=[hpge_act, nai_act_corr])
        
        if len(df_plot) > 0:
            # Získání hmotnosti pro barevnou škálu
            weight_col = 'Hmotnost [kg]_HPGe' if 'Hmotnost [kg]_HPGe' in df_plot.columns else 'Hmotnost [kg]'
            volume_col = 'Objem [l]_HPGe' if 'Objem [l]_HPGe' in df_plot.columns else 'Objem [l]'
            desc_col = 'Popis vzorku_HPGe' if 'Popis vzorku_HPGe' in df_plot.columns else 'Popis vzorku'
            
            # Výpočet hustoty v g/cm³
            density = df_plot[weight_col] / df_plot[volume_col]
            
            # Data body - korigovaná
            fig_combined.add_trace(
                go.Scatter(
                    x=df_plot[hpge_act],
                    y=df_plot[nai_act_corr],
                    mode='markers',
                    marker=dict(
                        size=8,
                        color=df_plot[weight_col],
                        colorscale='Viridis',
                        showscale=(idx == 0),  # Zobrazit colorbar pouze u prvního grafu
                        colorbar=dict(
                            title='Hmotnost<br>[kg]',
                            thickness=15,
                            len=0.35,
                            y=0.25,
                            x=1.02
                        ) if idx == 0 else None,
                        opacity=0.8,
                        line=dict(width=0.5, color='white')
                    ),
                    error_x=dict(
                        type='data',
                        array=df_plot[hpge_unc] if hpge_unc in df_plot.columns else None,
                        color='rgba(128, 128, 128, 0.3)',
                        thickness=1,
                        width=2
                    ),
                    error_y=dict(
                        type='data',
                        array=df_plot[nai_unc] if nai_unc in df_plot.columns else None,
                        color='rgba(128, 128, 128, 0.3)',
                        thickness=1,
                        width=2
                    ),
                    text=df_plot['Kniha analýz'],
                    customdata=np.column_stack((df_plot[weight_col], density, df_plot[desc_col],
                                                 df_plot[hpge_unc] if hpge_unc in df_plot.columns else np.zeros(len(df_plot)),
                                                 df_plot[nai_unc] if nai_unc in df_plot.columns else np.zeros(len(df_plot)))),
                    hovertemplate=f'<b>%{{text}}</b><br>%{{customdata[2]}}<br>HPGe: %{{x:.2f}} ± %{{customdata[3]:.2f}} Bq/kg<br>NaI(Tl) corr: %{{y:.2f}} ± %{{customdata[4]:.2f}} Bq/kg<br>Hmotnost: %{{customdata[0]:.3f}} kg<br>Hustota: %{{customdata[1]:.3f}} g/cm³<extra></extra>',
                    showlegend=(idx == 0),
                    name='Měření (corr)',
                    legendgroup='corrected'
                ),
                row=row, col=col
            )
            
            # 1:1 linie
            max_val = max(df_plot[hpge_act].max(), df_plot[nai_act_corr].max())
            min_val = min(df_plot[hpge_act].min(), df_plot[nai_act_corr].min())
            
            fig_combined.add_trace(
                go.Scatter(
                    x=[min_val, max_val],
                    y=[min_val, max_val],
                    mode='lines',
                    line=dict(color='red', dash='dash', width=1),
                    showlegend=False,
                    name='1:1',
                    hoverinfo='skip',
                    legendgroup='lines'
                ),
                row=row, col=col
            )
            
            # Anotace s korekčním faktorem
            b_value = correction_results[element_name]['b']
            if CORRECTION_MODEL == 'quadratic_centered':
                c_value = correction_results[element_name]['c']
                annotation_text = f"b = {b_value:.3f}<br>c = {c_value:.3f}"
            else:
                annotation_text = f"b = {b_value:.3f}"
            
            fig_combined.add_annotation(
                text=annotation_text,
                xref=f"x{col + n_elements}", yref=f"y{col + n_elements}",
                x=0.05, y=0.95,
                xanchor='left', yanchor='top',
                showarrow=False,
                bgcolor='rgba(255, 255, 255, 0.8)',
                bordercolor='gray',
                borderwidth=1,
                font=dict(size=10)
            )
            
            # Osy
            fig_combined.update_xaxes(title_text="HPGe [Bq/kg]", row=row, col=col)
            fig_combined.update_yaxes(title_text="NaI(Tl) corr [Bq/kg]", row=row, col=col)
    
    fig_combined.update_layout(
        title_text="Porovnání metod HPGe vs NaI(Tl) - Původní a korigovaná data",
        height=900,
        width=1800,
        showlegend=True,
        template='plotly_white'
    )
    
    combined_output_path = os.path.join(script_dir, "comparison_all_elements.html")
    fig_combined.write_html(combined_output_path)
    print(f"  Uloženo: {combined_output_path}")

# Statistické shrnutí
print("\n" + "="*60)
print("STATISTICKÉ SHRNUTÍ - PŮVODNÍ DATA")
print("="*60)

for element_name, (activity_col, uncertainty_col) in available_elements.items():
    hpge_act = f"{activity_col}_HPGe"
    nai_act = f"{activity_col}_NaI"
    
    df_plot = df_compare.dropna(subset=[hpge_act, nai_act])
    
    if len(df_plot) > 0:
        from scipy import stats
        
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            df_plot[hpge_act], df_plot[nai_act]
        )
        
        # Relativní rozdíly
        rel_diff = (df_plot[nai_act] - df_plot[hpge_act]) / df_plot[hpge_act] * 100
        
        print(f"\n{element_name}:")
        print(f"  Počet vzorků: {len(df_plot)}")
        print(f"  Lineární fit: y = {slope:.3f}x + {intercept:.3f}")
        print(f"  R² = {r_value**2:.4f}")
        print(f"  p-value = {p_value:.4e}")
        print(f"  Průměrná relativní odchylka: {rel_diff.mean():.2f}%")
        print(f"  Medián relativní odchylky: {rel_diff.median():.2f}%")
        print(f"  Směrodatná odchylka rel. odchylky: {rel_diff.std():.2f}%")

print("\n" + "="*60)
print("STATISTICKÉ SHRNUTÍ - KORIGOVANÁ DATA")
print("="*60)

for element_name, (activity_col, uncertainty_col) in available_elements.items():
    hpge_act = f"{activity_col}_HPGe"
    nai_act_corr = f"{activity_col}_NaI_corrected"
    
    df_plot = df_compare.dropna(subset=[hpge_act, nai_act_corr])
    
    if len(df_plot) > 0:
        from scipy import stats
        
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            df_plot[hpge_act], df_plot[nai_act_corr]
        )
        
        # Relativní rozdíly
        rel_diff = (df_plot[nai_act_corr] - df_plot[hpge_act]) / df_plot[hpge_act] * 100
        
        # Korekční faktor z optimalizace
        corr_res = correction_results[element_name]
        
        print(f"\n{element_name}:")
        print(f"  Korekční faktor b = {corr_res['b']:.4f} ± {corr_res['b_uncertainty']:.4f}")
        print(f"  Počet vzorků: {len(df_plot)}")
        print(f"  Lineární fit: y = {slope:.3f}x + {intercept:.3f}")
        print(f"  R² = {r_value**2:.4f}  (bylo: {corr_res['R2_before']:.4f}, Δ = {r_value**2 - corr_res['R2_before']:+.4f})")
        print(f"  p-value = {p_value:.4e}")
        print(f"  RMSE = {corr_res['RMSE_after']:.3f} Bq/kg  (bylo: {corr_res['RMSE_before']:.3f}, redukce: {(1 - corr_res['RMSE_after']/corr_res['RMSE_before'])*100:.1f}%)")
        print(f"  Průměrná relativní odchylka: {rel_diff.mean():.2f}%")
        print(f"  Medián relativní odchylky: {rel_diff.median():.2f}%")
        print(f"  Směrodatná odchylka rel. odchylky: {rel_diff.std():.2f}%")

print("\n" + "="*60)
print("Hotovo! Grafy uloženy jako HTML soubory.")
print("="*60)
