#!/usr/bin/env python
"""
Minimalistická Dash aplikace pro stanovení referenční čisté plochy 
Ra-226 @ 186 keV píku v kalibračním spektru.

Výsledná hodnota (net_cps_per_bq) se uloží do YAML configu 
a použije pro rychlý výpočet aktivity v hlavní aplikaci.

Spuštění:
    python calibrate_186_peak.py

Autor: Scint_stavmat project
"""

import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import numpy as np
import yaml

# Import from project
from utils.config_loader import load_yaml_config, load_calibration_spectra


# ============================================================
# Configuration
# ============================================================

DEFAULT_DETECTOR = 'NaI(Tl)'
CONFIG_PATH = Path(__file__).parent.parent / 'config' / 'detectors.yaml'

# Initial ROI around 186 keV (will be calculated from energy calibration)
DEFAULT_ROI_CENTER = 128  # Approximate channel for 186 keV
DEFAULT_ROI_WIDTH = 20
DEFAULT_ZOOM_MARGIN = 30


# ============================================================
# Data Loading
# ============================================================

def load_ra_calibration_spectrum(detector_name):
    """Load Ra calibration spectrum and return normalized to CPS/Bq."""
    try:
        config = load_yaml_config(detector_name, CONFIG_PATH)
        calib_data = load_calibration_spectra(config)
        
        # Extract Ra spectrum
        ra_spe = calib_data['ra_spe']
        ra_counts = np.array(ra_spe['channels'], dtype=float)
        ra_live_time = calib_data['live_times']['Ra']
        
        # Get standard activity
        ra_activity = config['standard_activities']['Ra']
        
        # Energy calibration for display
        display_calib = config['display_calibration']
        a0 = display_calib['a0']
        a1 = display_calib['a1']
        a2 = display_calib.get('a2', 0)
        
        # Peak analysis config
        peak_config = config.get('peak_analysis', {})
        
        # Normalize to CPS/Bq
        ra_cps = ra_counts / ra_live_time
        ra_cps_per_bq = ra_cps / ra_activity
        
        # Calculate channel for 186 keV
        if a2 != 0:
            # Quadratic
            discriminant = a1**2 - 4*a2*(a0 - 186.0)
            if discriminant >= 0:
                ch_186 = int((-a1 + np.sqrt(discriminant)) / (2*a2))
            else:
                ch_186 = DEFAULT_ROI_CENTER
        else:
            ch_186 = int((186.0 - a0) / a1)
        
        return {
            'ra_counts': ra_counts,
            'ra_cps': ra_cps,
            'ra_cps_per_bq': ra_cps_per_bq,
            'live_time': ra_live_time,
            'activity': ra_activity,
            'energy_calib': [a0, a1, a2],
            'ch_186': ch_186,
            'peak_config': peak_config,
            'detector_name': detector_name
        }
    except Exception as e:
        print(f"Error loading calibration: {e}")
        import traceback
        traceback.print_exc()
        return None


def calculate_net_area(spectrum, roi_left, roi_right, bg_margin=5):
    """Calculate net area with linear background subtraction."""
    roi_left = max(0, int(roi_left))
    roi_right = min(len(spectrum) - 1, int(roi_right))
    
    if roi_right - roi_left < 2 * bg_margin:
        return None
    
    # Extract ROI
    roi_spectrum = spectrum[roi_left:roi_right + 1]
    n_channels = len(roi_spectrum)
    
    # Calculate linear background
    bg_left_val = np.mean(roi_spectrum[:bg_margin])
    bg_right_val = np.mean(roi_spectrum[-bg_margin:])
    bg_values = np.linspace(bg_left_val, bg_right_val, n_channels)
    
    # Calculate areas
    gross_area = np.sum(roi_spectrum)
    bg_area = np.sum(bg_values)
    net_area = gross_area - bg_area
    
    return {
        'gross': gross_area,
        'background': bg_area,
        'net': net_area,
        'roi_spectrum': roi_spectrum,
        'bg_values': bg_values,
        'bg_left': bg_left_val,
        'bg_right': bg_right_val
    }


def save_to_config(detector_name, net_cps_per_bq, roi_left, roi_right):
    """Save calibrated value to detectors.yaml"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Add or update peak_calibration section
        if 'peak_calibration' not in config[detector_name]:
            config[detector_name]['peak_calibration'] = {}
        
        config[detector_name]['peak_calibration']['ra_186_net_cps_per_bq'] = float(net_cps_per_bq)
        config[detector_name]['peak_calibration']['ra_186_roi'] = [int(roi_left), int(roi_right)]
        
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        return True, f"Uloženo: {net_cps_per_bq:.6f} cps/Bq pro {detector_name}"
    except Exception as e:
        return False, f"Chyba při ukládání: {str(e)}"


# ============================================================
# Dash Application
# ============================================================

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="Kalibrace 186 keV píku"
)

app.layout = dbc.Container([
    # Header
    html.H3("☢️ Kalibrace Ra-226 @ 186 keV píku", className="text-center mt-3 mb-3"),
    
    # Detector selector
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("Detektor:", className="fw-bold"),
                            dcc.Dropdown(
                                id='detector-select',
                                options=[
                                    {'label': 'NaI(Tl)', 'value': 'NaI(Tl)'},
                                    {'label': 'CeBr₃', 'value': 'CeBr3'}
                                ],
                                value=DEFAULT_DETECTOR,
                                clearable=False
                            ),
                        ], width=3),
                        dbc.Col([
                            html.Label("Info:", className="fw-bold"),
                            html.Div(id='calib-info', className="text-muted small")
                        ], width=9),
                    ])
                ])
            ], className="mb-3")
        ], width=12)
    ]),
    
    # Main content
    dbc.Row([
        # Graph
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Spektrum Ra kalibrace @ 186 keV"),
                dbc.CardBody([
                    dcc.Graph(id='spectrum-graph', style={'height': '400px'}),
                    
                    # ROI Slider (4 values: zoom_left, peak_left, peak_right, zoom_right)
                    html.Label("ROI hranice (vnější = zoom, vnitřní = peak):", className="fw-bold small mt-2"),
                    dcc.RangeSlider(
                        id='roi-slider',
                        min=0,
                        max=300,
                        step=1,
                        value=[80, 115, 145, 180],  # [zoom_left, peak_left, peak_right, zoom_right]
                        marks={i: str(i) for i in range(0, 301, 50)},
                        tooltip={"placement": "bottom", "always_visible": True},
                        allowCross=False,
                        pushable=3
                    ),
                ])
            ])
        ], width=8),
        
        # Results panel
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("📊 Výsledky"),
                dbc.CardBody([
                    html.Div(id='results-panel'),
                    html.Hr(),
                    dbc.Button(
                        [html.I(className="fas fa-save me-2"), "Uložit do configu"],
                        id='save-button',
                        color='success',
                        className='w-100 mt-2'
                    ),
                    html.Div(id='save-status', className="mt-2 small")
                ])
            ], className="mb-3"),
            
            dbc.Card([
                dbc.CardHeader("ℹ️ Návod"),
                dbc.CardBody([
                    html.Small([
                        html.Strong("Postup:"), html.Br(),
                        "1. Vyberte detektor", html.Br(),
                        "2. Upravte vnitřní hranice (peak ROI)", html.Br(),
                        "3. Zkontrolujte, že pozadí je správně", html.Br(),
                        "4. Uložte hodnotu do configu", html.Br(),
                        html.Br(),
                        html.Strong("Slider:"), html.Br(),
                        "• Vnější handles = zoom oblast", html.Br(),
                        "• Vnitřní handles = peak ROI", html.Br(),
                    ], className="text-muted")
                ])
            ])
        ], width=4)
    ]),
    
    # Store for calibration data
    dcc.Store(id='calib-data-store')
    
], fluid=True)


# ============================================================
# Callbacks
# ============================================================

@app.callback(
    [Output('calib-data-store', 'data'),
     Output('calib-info', 'children'),
     Output('roi-slider', 'value'),
     Output('roi-slider', 'min'),
     Output('roi-slider', 'max')],
    Input('detector-select', 'value')
)
def load_calibration(detector_name):
    """Load calibration data when detector changes."""
    if detector_name is None:
        return None, "Vyberte detektor", [80, 115, 145, 180], 0, 300
    
    data = load_ra_calibration_spectrum(detector_name)
    
    if data is None:
        return None, "❌ Chyba při načítání dat", [80, 115, 145, 180], 0, 300
    
    # Prepare info text
    info = (f"Ra aktivita: {data['activity']:.1f} Bq | "
            f"Live time: {data['live_time']:.1f} s | "
            f"186 keV ≈ CH {data['ch_186']}")
    
    # Set initial ROI around 186 keV channel
    ch_186 = data['ch_186']
    roi_width = data['peak_config'].get('roi_half_width', 15)
    zoom_margin = 40
    
    zoom_left = max(0, ch_186 - zoom_margin)
    peak_left = max(0, ch_186 - roi_width)
    peak_right = min(len(data['ra_cps_per_bq']) - 1, ch_186 + roi_width)
    zoom_right = min(len(data['ra_cps_per_bq']) - 1, ch_186 + zoom_margin)
    
    slider_value = [zoom_left, peak_left, peak_right, zoom_right]
    slider_max = min(500, len(data['ra_cps_per_bq']) - 1)
    
    # Convert numpy arrays to lists for JSON serialization
    store_data = {
        'ra_cps_per_bq': data['ra_cps_per_bq'].tolist(),
        'ra_counts': data['ra_counts'].tolist(),
        'live_time': data['live_time'],
        'activity': data['activity'],
        'energy_calib': data['energy_calib'],
        'ch_186': ch_186,
        'detector_name': detector_name,
        'bg_margin': data['peak_config'].get('bg_margin', 5)
    }
    
    return store_data, info, slider_value, 0, slider_max


@app.callback(
    [Output('spectrum-graph', 'figure'),
     Output('results-panel', 'children')],
    [Input('roi-slider', 'value'),
     Input('calib-data-store', 'data')]
)
def update_graph(slider_values, calib_data):
    """Update graph and results when ROI changes."""
    fig = go.Figure()
    
    if calib_data is None or slider_values is None or len(slider_values) != 4:
        fig.update_layout(
            template='plotly_white',
            annotations=[{'text': 'Načtěte kalibrační data...', 'x': 0.5, 'y': 0.5,
                         'xref': 'paper', 'yref': 'paper', 'showarrow': False}]
        )
        return fig, html.Div("Nejsou data", className="text-muted")
    
    zoom_left, peak_left, peak_right, zoom_right = slider_values
    
    spectrum = np.array(calib_data['ra_cps_per_bq'])
    energy_calib = calib_data['energy_calib']
    bg_margin = calib_data.get('bg_margin', 5)
    
    # Ensure bounds
    zoom_left = max(0, int(zoom_left))
    zoom_right = min(len(spectrum) - 1, int(zoom_right))
    peak_left = max(zoom_left, int(peak_left))
    peak_right = min(zoom_right, int(peak_right))
    
    # Extract zoom region
    zoom_channels = np.arange(zoom_left, zoom_right + 1)
    zoom_spectrum = spectrum[zoom_left:zoom_right + 1]
    
    # Calculate energies for display
    a0, a1, a2 = energy_calib
    zoom_energies = a0 + a1 * zoom_channels + a2 * zoom_channels**2
    
    # Y-axis range
    y_min = max(0, np.min(zoom_spectrum) * 0.9)
    y_max = np.max(zoom_spectrum) * 1.1
    
    # Add spectrum
    fig.add_trace(go.Scatter(
        x=zoom_channels,
        y=zoom_spectrum,
        mode='lines',
        name='Ra spektrum (cps/Bq)',
        line=dict(color='black', width=2, shape='hv'),
        customdata=zoom_energies,
        hovertemplate='CH: %{x}<br>E: %{customdata:.1f} keV<br>CPS/Bq: %{y:.6f}<extra></extra>'
    ))
    
    # Calculate net area
    result = calculate_net_area(spectrum, peak_left, peak_right, bg_margin)
    
    if result is not None:
        # Add background line
        peak_channels = np.arange(peak_left, peak_right + 1)
        fig.add_trace(go.Scatter(
            x=peak_channels,
            y=result['bg_values'],
            mode='lines',
            name='Pozadí',
            line=dict(color='gray', width=2, dash='dash')
        ))
        
        # Yellow fill for net area
        fig.add_trace(go.Scatter(
            x=peak_channels,
            y=result['bg_values'],
            mode='lines',
            line=dict(width=0),
            showlegend=False,
            hoverinfo='skip'
        ))
        fig.add_trace(go.Scatter(
            x=peak_channels,
            y=result['roi_spectrum'],
            mode='lines',
            fill='tonexty',
            fillcolor='rgba(255, 215, 0, 0.5)',
            line=dict(width=0),
            name=f'Net: {result["net"]:.6f}',
            hoverinfo='skip'
        ))
        
        # Results panel
        rel_unc = np.sqrt(result['gross']) / result['net'] * 100 if result['net'] > 0 else 0
        
        results_html = html.Div([
            html.H5(f"Net: {result['net']:.6f} cps/Bq", className="text-success"),
            html.Hr(),
            html.Table([
                html.Tr([html.Td("Gross:"), html.Td(f"{result['gross']:.6f}")]),
                html.Tr([html.Td("Background:"), html.Td(f"{result['background']:.6f}")]),
                html.Tr([html.Td("Net:"), html.Td(f"{result['net']:.6f}")]),
                html.Tr([html.Td("Rel. unc.:"), html.Td(f"~{rel_unc:.1f}%")]),
                html.Tr([html.Td("ROI:"), html.Td(f"CH {peak_left}-{peak_right}")]),
            ], className="table table-sm"),
        ])
    else:
        results_html = html.Div("ROI příliš malé", className="text-danger")
    
    # Add vertical lines for peak boundaries
    shapes = [
        dict(type='line', x0=peak_left, x1=peak_left, y0=y_min, y1=y_max,
             line=dict(color='orange', width=2)),
        dict(type='line', x0=peak_right, x1=peak_right, y0=y_min, y1=y_max,
             line=dict(color='orange', width=2)),
    ]
    
    # Layout
    fig.update_layout(
        template='plotly_white',
        margin=dict(t=30, b=40, l=50, r=20),
        xaxis=dict(title='Kanál', range=[zoom_left - 2, zoom_right + 2]),
        yaxis=dict(title='CPS / Bq', range=[y_min, y_max]),
        legend=dict(orientation='h', yanchor='top', y=-0.15, x=0),
        shapes=shapes,
        hovermode='x unified'
    )
    
    return fig, results_html


@app.callback(
    Output('save-status', 'children'),
    Input('save-button', 'n_clicks'),
    [State('roi-slider', 'value'),
     State('calib-data-store', 'data')],
    prevent_initial_call=True
)
def save_calibration(n_clicks, slider_values, calib_data):
    """Save calibration to config file."""
    if calib_data is None or slider_values is None:
        return html.Span("❌ Nejsou data k uložení", className="text-danger")
    
    zoom_left, peak_left, peak_right, zoom_right = slider_values
    spectrum = np.array(calib_data['ra_cps_per_bq'])
    bg_margin = calib_data.get('bg_margin', 5)
    
    result = calculate_net_area(spectrum, peak_left, peak_right, bg_margin)
    
    if result is None or result['net'] <= 0:
        return html.Span("❌ Neplatná hodnota net area", className="text-danger")
    
    success, message = save_to_config(
        calib_data['detector_name'],
        result['net'],
        peak_left,
        peak_right
    )
    
    if success:
        return html.Span(f"✅ {message}", className="text-success")
    else:
        return html.Span(f"❌ {message}", className="text-danger")


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Kalibrace Ra-226 @ 186 keV píku")
    print("="*60)
    print(f"Config: {CONFIG_PATH}")
    print("Spouštím na http://127.0.0.1:8052")
    print("="*60 + "\n")
    
    app.run(debug=True, port=8052)
