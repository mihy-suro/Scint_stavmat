"""
Minimalistická aplikace pro manuální kalibraci spekter
Načte kalibrace z Excel souboru a umožní klikáním vytvořit novou kalibraci
"""

import dash
from dash import dcc, html, Input, Output, State, callback_context, ALL, MATCH
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import base64
import io


# Inicializace aplikace
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Layout
app.layout = dbc.Container([
    html.H2("🔧 Kalibrace scintilačních spekter", className="text-center mt-3 mb-4"),
    
    dbc.Row([
        # Levý panel
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("📁 Načtení dat"),
                dbc.CardBody([
                    dcc.Upload(
                        id='upload-excel',
                        children=html.Div(['Přetáhněte Excel nebo klikněte']),
                        style={
                            'width': '100%', 'height': '50px', 'lineHeight': '50px',
                            'borderWidth': '2px', 'borderStyle': 'dashed',
                            'borderRadius': '5px', 'textAlign': 'center', 'cursor': 'pointer'
                        }
                    ),
                    html.Div(id='upload-status', className='mt-2'),
                ])
            ], className="mb-3"),
            
            dbc.Card([
                dbc.CardHeader("🎯 Výběr spektra"),
                dbc.CardBody([
                    dcc.Dropdown(id='spectrum-selector', placeholder="Vyberte spektrum..."),
                ])
            ], className="mb-3"),
            
            dbc.Card([
                dbc.CardHeader("📍 Manuální kalibrace"),
                dbc.CardBody([
                    html.P("Klikněte na pík a přiřaďte energii:", className="small mb-2"),
                    
                    html.Div(id='peak-table-container'),
                    
                    html.Small(id='last-click', className="text-muted d-block mb-2"),
                    
                    dbc.Button("Vypočítat kalibraci", id='calc-calib', color="success", className="w-100", disabled=True),
                    
                    html.Hr(),
                    html.H6("Výsledná kalibrace:", className="mt-3"),
                    html.Pre(id='calib-result', className="small p-2 bg-light rounded"),
                ])
            ])
        ], width=4),
        
        # Pravý panel - grafy
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("📊 Spektrum"),
                dbc.CardBody([
                    dcc.Graph(id='spectrum-plot', style={'height': '500px'})
                ])
            ], className="mb-3"),
            
            dbc.Card([
                dbc.CardHeader("📈 Kalibrace: Kanál → Energie"),
                dbc.CardBody([
                    dcc.Graph(id='calibration-plot', style={'height': '400px'})
                ])
            ])
        ], width=8),
    ]),
    
    # Stores
    dcc.Store(id='excel-data', storage_type='memory'),
    dcc.Store(id='peak-data', storage_type='memory', data={'peaks': {}, 'last_ch': None}),
    
], fluid=True)


# ==================== CALLBACKS ====================

# Definice energií pro každý radionuklid
ENERGY_PEAKS = {
    'Ra': [186.211, 241.997, 295.224, 351.932, 609.312, 1120.287, 1238.111, 1764.494],
    'K': [1460.822],
    'Th': [238.632, 240.986, 277.37, 300.089, 583.187, 727.330, 860.53, 2614.511]
}

def get_peaks_for_spectrum(spectrum_name):
    """Vrátí seznam energií podle jména spektra"""
    name_upper = spectrum_name.upper()
    if 'RA' in name_upper or '226' in name_upper:
        return ENERGY_PEAKS['Ra']
    elif 'TH' in name_upper or '232' in name_upper:
        return ENERGY_PEAKS['Th']
    elif 'K' in name_upper and ('40' in name_upper or '1461' in name_upper):
        return ENERGY_PEAKS['K']
    else:
        # Default - všechny energie
        return sorted(set(ENERGY_PEAKS['Ra'] + ENERGY_PEAKS['K'] + ENERGY_PEAKS['Th']))


@app.callback(
    [Output('excel-data', 'data'),
     Output('upload-status', 'children'),
     Output('spectrum-selector', 'options')],
    Input('upload-excel', 'contents'),
    State('upload-excel', 'filename')
)
def load_excel(contents, filename):
    """Načte Excel soubor s kalibračními spektry"""
    if contents is None:
        return None, "", []
    
    try:
        # Decode base64
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        excel_file = pd.ExcelFile(io.BytesIO(decoded))
        
        # Načíst Kalibrace sheet
        calib_df = pd.read_excel(excel_file, sheet_name='Kalibrace')
        
        # Názvy spekter (sloupce kromě prvního)
        spectrum_names = calib_df.columns[1:].tolist()
        
        # Načíst data s skip_rows (typicky 11)
        skip_rows = 11
        data_df = pd.read_excel(excel_file, sheet_name='Kalibrace', skiprows=skip_rows, header=None)
        data_df.columns = ['CHNL'] + spectrum_names
        
        # Odstranit NaN
        data_df = data_df.dropna(subset=['CHNL'])
        data_df['CHNL'] = data_df['CHNL'].astype(int)
        
        # Uložit
        data = {
            'spectra': data_df.to_dict('records'),
            'spectrum_names': spectrum_names
        }
        
        status = dbc.Alert(f"✅ Načteno: {filename} ({len(spectrum_names)} spekter)", color="success")
        options = [{'label': name, 'value': name} for name in spectrum_names]
        
        return data, status, options
        
    except Exception as e:
        return None, dbc.Alert(f"❌ Chyba: {str(e)}", color="danger"), []


@app.callback(
    Output('peak-table-container', 'children'),
    Input('spectrum-selector', 'value')
)
def update_peak_table(selected_spectrum):
    """Vytvoří tabulku s energiemi podle vybraného spektra"""
    if not selected_spectrum:
        return html.P("Nejprve vyberte spektrum", className="text-muted small")
    
    energies = get_peaks_for_spectrum(selected_spectrum)
    
    rows = []
    for energy in energies:
        energy_id = f"e{int(energy*1000)}"  # e186211 pro 186.211 keV
        rows.append(html.Tr([
            html.Td(f"{energy:.3f}"),
            html.Td(html.Span(id={'type': 'ch-display', 'index': energy_id}, children="-")),
            html.Td(dbc.Button("Set", id={'type': 'btn-set', 'index': energy_id}, 
                              size="sm", color="info", outline=True))
        ]))
    
    table = dbc.Table([
        html.Thead([html.Tr([html.Th("Energie (keV)"), html.Th("Kanál"), html.Th("")])]),
        html.Tbody(rows)
    ], size="sm", bordered=True, style={'maxHeight': '400px', 'overflowY': 'auto', 'display': 'block'})
    
    return table


@app.callback(
    Output('spectrum-plot', 'figure'),
    [Input('spectrum-selector', 'value'),
     Input('peak-data', 'data')],
    State('excel-data', 'data')
)
def update_plot(selected_spectrum, peak_data, excel_data):
    """Vykreslí vybrané spektrum s označenými píky"""
    fig = go.Figure()
    
    if excel_data and selected_spectrum:
        df = pd.DataFrame(excel_data['spectra'])
        
        # Spektrum
        fig.add_trace(go.Scatter(
            x=df['CHNL'],
            y=df[selected_spectrum],
            mode='lines',
            name=selected_spectrum,
            line=dict(color='blue', width=1.5)
        ))
        
        # Označit poslední kliknutý kanál (žlutá vertikální čára)
        if peak_data and peak_data.get('last_ch') is not None:
            last_ch = peak_data['last_ch']
            fig.add_vline(
                x=last_ch,
                line=dict(color='orange', width=2, dash='dash'),
                annotation_text=f"CH {last_ch}",
                annotation_position="top"
            )
        
        # Označit potvrzené píky (zelené kříže s energiemi)
        if peak_data and 'peaks' in peak_data:
            for energy_str, channel in peak_data['peaks'].items():
                if channel != '-':
                    # Najít intenzitu v daném kanálu
                    intensity = df.loc[df['CHNL'] == channel, selected_spectrum].values
                    if len(intensity) > 0:
                        fig.add_trace(go.Scatter(
                            x=[channel],
                            y=[intensity[0]],
                            mode='markers+text',
                            name=f"{energy_str} keV",
                            marker=dict(size=12, color='green', symbol='x', line=dict(width=2)),
                            text=[f"{energy_str} keV"],
                            textposition="top center",
                            showlegend=False
                        ))
        
        fig.update_layout(
            title=f"Spektrum: {selected_spectrum}",
            xaxis_title="Kanál",
            yaxis_title="Intenzita (counts)",
            hovermode='x',
            template='plotly_white'
        )
    else:
        fig.update_layout(title="Nejprve nahrajte Excel a vyberte spektrum")
    
    return fig


@app.callback(
    [Output('last-click', 'children'),
     Output('peak-data', 'data')],
    [Input('spectrum-plot', 'clickData'),
     Input({'type': 'btn-set', 'index': ALL}, 'n_clicks')],
    [State('peak-data', 'data'),
     State('spectrum-selector', 'value')]
)
def handle_clicks(click_data, btn_clicks, peak_data, selected_spectrum):
    """Zpracuje kliky na graf a tlačítka Set"""
    if not callback_context.triggered:
        return "Klikněte na pík v grafu", peak_data
    
    trigger = callback_context.triggered[0]['prop_id']
    
    # Inicializace
    if peak_data is None:
        peak_data = {'peaks': {}, 'last_ch': None}
    
    # Klik na graf - uloží kanál
    if 'spectrum-plot' in trigger and click_data:
        channel = int(click_data['points'][0]['x'])
        peak_data['last_ch'] = channel
        return f"Poslední klik: Kanál {channel}", peak_data
    
    # Klik na Set tlačítko
    if 'btn-set' in trigger and peak_data.get('last_ch'):
        # Najít který button byl kliknut
        import json
        trigger_dict = json.loads(trigger.split('.')[0])
        energy_id = trigger_dict['index']
        
        # Získat energii ze selected_spectrum
        if selected_spectrum:
            energies = get_peaks_for_spectrum(selected_spectrum)
            # Najít energii podle ID
            for energy in energies:
                if f"e{int(energy*1000)}" == energy_id:
                    channel = peak_data['last_ch']
                    peak_data['peaks'][str(energy)] = channel
                    return f"✓ Nastaveno: {energy:.3f} keV → Kanál {channel}", peak_data
    
    return "Klikněte na pík v grafu", peak_data


@app.callback(
    Output({'type': 'ch-display', 'index': MATCH}, 'children'),
    Input('peak-data', 'data'),
    State({'type': 'ch-display', 'index': MATCH}, 'id')
)
def update_channel_display(peak_data, component_id):
    """Aktualizuje zobrazení kanálu v tabulce"""
    if not peak_data or 'peaks' not in peak_data:
        return "-"
    
    # Získat energii z ID
    energy_id = component_id['index']
    # e186211 -> 186.211
    energy_value = int(energy_id[1:]) / 1000.0
    energy_str = str(energy_value)
    
    # Najít v peaks
    for e_key, channel in peak_data['peaks'].items():
        if abs(float(e_key) - energy_value) < 0.001:  # Tolerance for float comparison
            return str(channel)
    
    return "-"


@app.callback(
    Output('calc-calib', 'disabled'),
    Input('peak-data', 'data')
)
def enable_calc_button(peak_data):
    """Povolit tlačítko pokud máme alespoň 2 píky"""
    if not peak_data or 'peaks' not in peak_data:
        return True
    
    num_peaks = len([v for v in peak_data['peaks'].values() if v != '-'])
    return num_peaks < 2


@app.callback(
    Output('calib-result', 'children'),
    Input('calc-calib', 'n_clicks'),
    State('peak-data', 'data'),
    prevent_initial_call=True
)
def calculate_calibration(n_clicks, peak_data):
    """Vypočítá lineární kalibraci E = a0 + a1*CH"""
    if not peak_data or 'peaks' not in peak_data:
        return "Nejsou definovány píky"
    
    # Extrahuj energie a kanály
    energies = []
    channels = []
    for energy_str, channel in peak_data['peaks'].items():
        if channel != '-':
            energies.append(float(energy_str))
            channels.append(float(channel))
    
    if len(energies) < 2:
        return "Potřeba alespoň 2 píky"
    
    # Lineární fit: E = a0 + a1*CH
    energies = np.array(energies)
    channels = np.array(channels)
    
    # Least squares
    A = np.vstack([np.ones(len(channels)), channels]).T
    a0, a1 = np.linalg.lstsq(A, energies, rcond=None)[0]
    
    # Výpočet reziduí
    fitted = a0 + a1 * channels
    residuals = energies - fitted
    
    result = f"""Kalibrace: E = a₀ + a₁·CH

a₀ = {a0:.6f} keV
a₁ = {a1:.6f} keV/CH

Použité píky:
"""
    for e, ch, res in zip(energies, channels, residuals):
        result += f"  {e:7.1f} keV @ CH {ch:4.0f}  (Δ = {res:+6.2f} keV)\n"
    
    return result


@app.callback(
    Output('calibration-plot', 'figure'),
    Input('peak-data', 'data')
)
def plot_calibration(peak_data):
    """Vykreslí graf kanál vs energie s fitovanou přímkou"""
    fig = go.Figure()
    
    if not peak_data or 'peaks' not in peak_data or len(peak_data['peaks']) == 0:
        fig.update_layout(
            title="Zatím nejsou definovány žádné píky",
            xaxis_title="Kanál",
            yaxis_title="Energie (keV)",
            template='plotly_white'
        )
        return fig
    
    # Extrahuj energie a kanály
    energies = []
    channels = []
    for energy_str, channel in peak_data['peaks'].items():
        if channel != '-':
            energies.append(float(energy_str))
            channels.append(float(channel))
    
    if len(energies) == 0:
        fig.update_layout(
            title="Zatím nejsou definovány žádné píky",
            xaxis_title="Kanál",
            yaxis_title="Energie (keV)",
            template='plotly_white'
        )
        return fig
    
    energies = np.array(energies)
    channels = np.array(channels)
    
    # Zobrazit píky
    fig.add_trace(go.Scatter(
        x=channels,
        y=energies,
        mode='markers',
        name='Píky',
        marker=dict(size=10, color='red'),
        text=[f"{e:.1f} keV" for e in energies],
        hovertemplate='CH %{x}<br>%{text}<extra></extra>'
    ))
    
    # Pokud máme alespoň 2 píky, fituj přímku
    if len(energies) >= 2:
        # Lineární fit
        A = np.vstack([np.ones(len(channels)), channels]).T
        a0, a1 = np.linalg.lstsq(A, energies, rcond=None)[0]
        
        # Vytvoř body fitu
        ch_range = np.linspace(0, max(channels) * 1.1, 100)
        e_fit = a0 + a1 * ch_range
        
        fig.add_trace(go.Scatter(
            x=ch_range,
            y=e_fit,
            mode='lines',
            name=f'Fit: E = {a0:.2f} + {a1:.4f}·CH',
            line=dict(color='blue', dash='dash')
        ))
        
        # Přidat rezidua jako error bars
        fitted_energies = a0 + a1 * channels
        residuals = energies - fitted_energies
        
        fig.add_trace(go.Scatter(
            x=channels,
            y=energies,
            mode='markers',
            marker=dict(size=0),
            error_y=dict(
                type='data',
                array=np.abs(residuals),
                visible=True,
                color='rgba(255,0,0,0.3)'
            ),
            showlegend=False,
            hoverinfo='skip'
        ))
    
    fig.update_layout(
        title="Kalibrace: Kanál → Energie",
        xaxis_title="Kanál",
        yaxis_title="Energie (keV)",
        hovermode='closest',
        template='plotly_white',
        legend=dict(x=0.05, y=0.95)
    )
    
    return fig


if __name__ == '__main__':
    app.run(debug=True, port=8052)
