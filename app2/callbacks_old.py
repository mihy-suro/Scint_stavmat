"""
Callback funkce pro Dash aplikaci
"""

from dash import Input, Output, State, html, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import base64
import io
import plotly.graph_objects as go

from processing import (
    rebin_spectrum,
    find_optimal_calibration,
    ols,
    nnls_detailed,
    compile_results,
    normalize_by_live_time,
    subtract_background,
    calculate_energy,
)


def compile_results_dynamic(X, y, method_name, func, component_names):
    """Compile results with dynamic number of components"""
    results = func(X, y)
    return {
        "Method": method_name,
        "Coefficients": dict(zip(component_names, results["coefficients"])),
        "Std Errors": dict(zip(component_names, results["std_errors"])),
        "P Values": dict(zip(component_names, results["p_values"])),
        "R^2": results["R^2"],
        "Adjusted R^2": results["Adjusted R^2"]
    }


def register_callbacks(app):
    """Register all callbacks"""
    
    # ==================== EXCEL UPLOAD & PARSING ====================
    @app.callback(
        [Output('excel-data', 'data'),
         Output('upload-status', 'children'),
         Output('run-analysis', 'disabled'),
         Output('ref-a0', 'value'),
         Output('ref-a1', 'value'),
         Output('ref-a2', 'value'),
         Output('manual-a0', 'value'),
         Output('manual-a1', 'value'),
         Output('cut-channel', 'value')],
        [Input('upload-excel', 'contents'),
         Input('upload-excel', 'filename')]
    )
    def parse_excel(contents, filename):
        """Parse uploaded Excel file"""
        if contents is None:
            raise PreventUpdate
        
        try:
            # Decode file
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            excel_file = pd.ExcelFile(io.BytesIO(decoded))
            
            # Validate required sheets (with encoding tolerance for "Pozadí")
            sheet_names = excel_file.sheet_names
            required_base = ['Kalibrace', 'Vzorky', 'Parametry']
            missing = [s for s in required_base if s not in sheet_names]
            
            # Find "Pozadí" or "Pozad?" (encoding issue)
            pozadi_sheet = None
            for sheet in sheet_names:
                if sheet.startswith('Pozad'):
                    pozadi_sheet = sheet
                    break
            
            if pozadi_sheet is None:
                missing.append('Pozadí')
            
            if missing:
                error = dbc.Alert(f"❌ Chybí povinné sheety: {', '.join(missing)}", color="danger")
                return None, error, True, 9.6229, 1.3793, 0, 9.62228359, 1.37495787, 150
            
            # Read parameters sheet
            params_df = pd.read_excel(excel_file, sheet_name='Parametry', header=None)
            params_dict = dict(zip(params_df[0], params_df[1]))
            
            # Extract parameters with defaults
            skip_rows = int(params_dict.get('skip_rows', 11))
            
            # Read calibration data - detekce názvů sloupců
            calib_sheet = excel_file.parse('Kalibrace')
            calib_headers = calib_sheet.columns[1:].tolist()  # Názvy sloupců kromě prvního
            
            calib_df = pd.read_excel(excel_file, sheet_name='Kalibrace', skiprows=skip_rows, header=None)
            calib_df.columns = ['CHNL'] + calib_headers
            
            # Odstranit řádky s NaN v CHNL před konverzí
            calib_df = calib_df.dropna(subset=['CHNL'])
            calib_df['CHNL'] = calib_df['CHNL'].astype(int)
            
            # Zajistit pořadí Ra, K, Th (i když Excel má jiné pořadí)
            calib_df = calib_df[['CHNL', 'Ra', 'K', 'Th']]
            
            # Read samples data - názvy vzorků jsou v hlavičce sloupců
            samples_sheet = excel_file.parse('Vzorky')
            sample_names = samples_sheet.columns[1:].tolist()  # Column headers kromě prvního
            
            # Live times jsou v řádku kde první sloupec == 'ELIVE'
            elive_row = samples_sheet[samples_sheet.iloc[:, 0] == 'ELIVE']
            if not elive_row.empty:
                sample_live_times = elive_row.iloc[0, 1:].values.astype(float).tolist()
            else:
                # Fallback - hledej řádek s indexem 2 (třetí řádek)
                sample_live_times = samples_sheet.iloc[2, 1:].values.astype(float).tolist()
            
            sample_df = pd.read_excel(excel_file, sheet_name='Vzorky', skiprows=skip_rows, header=None)
            sample_df.columns = ['CHNL'] + sample_names
            
            # Odstranit řádky s NaN v CHNL před konverzí
            sample_df = sample_df.dropna(subset=['CHNL'])
            sample_df['CHNL'] = sample_df['CHNL'].astype(int)
            
            # Read background data - detekce všech sloupců pozadí
            bg_sheet = excel_file.parse(pozadi_sheet)
            bg_names = bg_sheet.columns[1:].tolist()  # Všechny sloupce kromě prvního
            
            # Načíst live times pro každé pozadí z ELIVE řádku
            bg_elive_row = bg_sheet[bg_sheet.iloc[:, 0] == 'ELIVE']
            if not bg_elive_row.empty:
                bg_live_times = bg_elive_row.iloc[0, 1:len(bg_names)+1].values.astype(float).tolist()
            else:
                # Fallback - řádek s indexem 2
                bg_live_times = bg_sheet.iloc[2, 1:len(bg_names)+1].values.astype(float).tolist()
            
            bg_df = pd.read_excel(excel_file, sheet_name=pozadi_sheet, skiprows=skip_rows, header=None)
            bg_df.columns = ['CHNL'] + bg_names
            bg_df['CHNL'] = bg_df['CHNL'].astype(int)
            
            # Store data
            data = {
                'calibration': calib_df.to_dict('records'),
                'samples': sample_df.to_dict('records'),
                'background': bg_df.to_dict('records'),
                'sample_names': sample_names,
                'sample_live_times': sample_live_times,
                'bg_names': bg_names,
                'bg_live_times': bg_live_times,
                'parameters': params_dict,
                'filename': filename
            }
            
            status = dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"✅ Načteno: {filename}",
                html.Br(),
                html.Small(f"Vzorků: {len(sample_names)}, Kanálů: {len(calib_df)}", className="text-muted")
            ], color="success")
            
            # Return parameters from Excel
            return (
                data,
                status,
                False,  # Enable analyze button
                float(params_dict.get('ref_a0', 9.6229)),
                float(params_dict.get('ref_a1', 1.3793)),
                float(params_dict.get('ref_a2', 0)),
                float(params_dict.get('manual_a0', 9.62228359)),
                float(params_dict.get('manual_a1', 1.37495787)),
                int(params_dict.get('cut_channel', 150))
            )
            
        except Exception as e:
            error = dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                f"❌ Chyba: {str(e)}"
            ], color="danger")
            return None, error, True, 9.6229, 1.3793, 0, 9.62228359, 1.37495787, 150
    
    
    # ==================== UPDATE SAMPLE SELECTOR ====================
    @app.callback(
        Output('sample-selector', 'options'),
        Input('excel-data', 'data')
    )
    def update_sample_selector(data):
        """Update sample dropdown"""
        if data is None:
            return []
        return [{'label': name, 'value': name} for name in data['sample_names']]
    
    
    @app.callback(
        [Output('sample-selector', 'value'),
         Output('sample-info', 'children')],
        [Input('sample-selector', 'options'),
         Input('sample-selector', 'value')],
        State('excel-data', 'data')
    )
    def set_default_sample(options, selected, data):
        """Set first sample as default and show live time"""
        if not options:
            return None, ""
        
        # Set default to first if nothing selected
        if selected is None:
            selected = options[0]['value']
        
        # Show live time info
        if data and selected:
            idx = data['sample_names'].index(selected)
            live_time = data['sample_live_times'][idx]
            info = html.Div([
                html.I(className="fas fa-clock me-2"),
                f"Live time: {live_time:.1f} s"
            ])
            return selected, info
        
        return selected, ""
    
    
    # ==================== TOGGLE OPTIMIZATION ====================
    @app.callback(
        Output('manual-calibration', 'style'),
        Input('optimize-calibration', 'value')
    )
    def toggle_manual_calib(optimize_value):
        """Show/hide manual calibration inputs"""
        if 'optimize' in optimize_value:
            return {'display': 'none'}
        return {'display': 'block'}
    
    
    # Clear results when sample changes (to show raw spectrum)
    @app.callback(
        Output('sample-results', 'data', allow_duplicate=True),
        Input('sample-selector', 'value'),
        prevent_initial_call=True
    )
    def clear_results_on_sample_change(selected_sample):
        """Clear analysis results when user changes selected sample"""
        return None
    
    
    # ==================== MAIN ANALYSIS ====================
    @app.callback(
        [Output('sample-results', 'data'),
         Output('analysis-status', 'children'),
         Output('ref-a0', 'value', allow_duplicate=True),
         Output('ref-a1', 'value', allow_duplicate=True)],
        Input('run-analysis', 'n_clicks'),
        [State('excel-data', 'data'),
         State('sample-selector', 'value'),
         State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value'),
         State('manual-a0', 'value'),
         State('manual-a1', 'value'),
         State('cut-channel', 'value'),
         State('optimize-calibration', 'value')],
        prevent_initial_call=True
    )
    def run_analysis(n_clicks, data, selected_sample, ref_a0, ref_a1, ref_a2,
                     manual_a0, manual_a1, cut_channel, optimize_value):
        """Run analysis for selected sample"""
        if data is None or selected_sample is None:
            raise PreventUpdate
        
        try:
            # Convert data back to DataFrames
            calib_df = pd.DataFrame(data['calibration'])
            sample_df = pd.DataFrame(data['samples'])
            bg_df = pd.DataFrame(data['background'])
            
            sample_idx = data['sample_names'].index(selected_sample)
            sample_live_time = data['sample_live_times'][sample_idx]
            bg_names = data['bg_names']
            bg_live_times = data['bg_live_times']
            
            # Get conversion factors from parameters
            params = data['parameters']
            factor_ra = float(params.get('Ra_faktor', 13.9))
            factor_k = float(params.get('K_faktor', 212))
            factor_th = float(params.get('Th_faktor', 7.4))
            
            # Reference calibration
            ref_calib = [ref_a0, ref_a1, ref_a2]
            
            # Normalize calibration spectra to probability density
            for column in ["Ra", "K", "Th"]:
                total_counts = calib_df[column].sum()
                if total_counts > 0:
                    calib_df[column] = calib_df[column] / total_counts
                else:
                    calib_df[column] = 0
            
            # Normalize sample to CPS
            sample_df_norm = sample_df.copy()
            if sample_live_time > 0:
                sample_df_norm[selected_sample] = sample_df[selected_sample] / sample_live_time
            else:
                sample_df_norm[selected_sample] = 0
            
            # Normalize all backgrounds to CPS (každé podle svého live time)
            bg_df_norm = bg_df.copy()
            for i, bg_name in enumerate(bg_names):
                if bg_live_times[i] > 0:
                    bg_df_norm[bg_name] = bg_df[bg_name] / bg_live_times[i]
                else:
                    bg_df_norm[bg_name] = 0
            
            # NEODEČÍTAT pozadí! Použije se jako prediktor v regresi
            sample_spectrum = sample_df_norm[selected_sample].values
            
            # Zero out first N channels
            calib_df.loc[calib_df["CHNL"] <= cut_channel, ["Ra", "K", "Th"]] = 0
            sample_spectrum[sample_df['CHNL'] <= cut_channel] = 0
            for bg_name in bg_names:
                bg_df_norm.loc[bg_df['CHNL'] <= cut_channel, bg_name] = 0
            
            # Determine calibration coefficients
            is_optimizing = 'optimize' in optimize_value
            
            if is_optimizing:
                bounds = [(5, 15), (1.35, 1.45), (0, 1e-5)]
                sample_calib = find_optimal_calibration(
                    ref_calib,
                    ref_calib,
                    calib_df[["Ra", "K", "Th"]].values,
                    sample_spectrum,
                    bounds[:2],  # Only optimize a0, a1
                    method='L-BFGS-B'
                )
                calib_method = f"Optimalizováno: a₀={sample_calib[0]:.6f}, a₁={sample_calib[1]:.6f}"
            else:
                sample_calib = [manual_a0, manual_a1]
                calib_method = "Manuální kalibrace"
            
            # Rebin sample
            sample_rebinned = rebin_spectrum(ref_calib, sample_calib, sample_spectrum)
            
            # Sestavit dynamickou matici prediktorů X = [Ra, K, Th, BG1, BG2, ...]
            X = pd.concat([
                calib_df[["Ra", "K", "Th"]],
                bg_df_norm[bg_names]
            ], axis=1).values
            
            # Component names pro výsledky
            component_names = ['Ra', 'K', 'Th'] + bg_names
            
            # Run regression s dynamickým počtem komponent
            results_ols = compile_results_dynamic(X, sample_rebinned, "OLS", ols, component_names)
            results_nnls = compile_results_dynamic(X, sample_rebinned, "NNLS", 
                                          lambda X, y: nnls_detailed(X, y, num_bootstrap=100), component_names)
            
            # Save raw coefficients for component plotting (BEFORE conversion to Bq)
            raw_ols_coeffs = results_ols['Coefficients'].copy()
            
            # Calculate fitted spectra BEFORE converting to Bq (using raw coefficients)
            fitted_ols = X @ np.array(list(raw_ols_coeffs.values()))
            fitted_nnls = X @ np.array(list(results_nnls['Coefficients'].values()))
            
            # Now convert coefficients to activities [Bq]
            results_ols['Coefficients']['Ra'] = results_ols['Coefficients']['Ra'] / factor_ra
            results_ols['Coefficients']['K'] = results_ols['Coefficients']['K'] / factor_k
            results_ols['Coefficients']['Th'] = results_ols['Coefficients']['Th'] / factor_th
            
            results_nnls['Coefficients']['Ra'] = results_nnls['Coefficients']['Ra'] / factor_ra
            results_nnls['Coefficients']['K'] = results_nnls['Coefficients']['K'] / factor_k
            results_nnls['Coefficients']['Th'] = results_nnls['Coefficients']['Th'] / factor_th
            
            # Convert std errors to Bq
            results_ols['Std Errors']['Ra'] = results_ols['Std Errors']['Ra'] / factor_ra
            results_ols['Std Errors']['K'] = results_ols['Std Errors']['K'] / factor_k
            results_ols['Std Errors']['Th'] = results_ols['Std Errors']['Th'] / factor_th
            
            results_nnls['Std Errors']['Ra'] = results_nnls['Std Errors']['Ra'] / factor_ra
            results_nnls['Std Errors']['K'] = results_nnls['Std Errors']['K'] / factor_k
            results_nnls['Std Errors']['Th'] = results_nnls['Std Errors']['Th'] / factor_th
            
            # Store results
            # Uložit pozadí jako dict kde každý key je bg_name a value je list hodnot
            bg_data_dict = {}
            for bg_name in bg_names:
                bg_data_dict[bg_name] = bg_df_norm[bg_name].tolist()
            
            results = {
                'sample_name': selected_sample,
                'calibration': calib_df.to_dict('records'),
                'sample_spectrum': sample_rebinned.tolist(),
                'background': bg_data_dict,  # Dict of lists
                'bg_names': bg_names,
                'fitted_ols': fitted_ols.tolist(),
                'fitted_nnls': fitted_nnls.tolist(),
                'raw_ols_coeffs': raw_ols_coeffs,  # Raw coefficients for component plotting
                'results_ols': results_ols,
                'results_nnls': results_nnls,
                'ref_calib': ref_calib,
                'calib_method': calib_method
            }
            
            status = dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"✅ Analýza dokončena pro vzorek: {selected_sample}"
            ], color="success")
            
            # If optimization was used, return optimized values to update ref-a0/a1
            if is_optimizing:
                return results, status, sample_calib[0], sample_calib[1]
            else:
                # Don't change ref values if not optimizing
                return results, status, no_update, no_update
            
        except Exception as e:
            error = dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                f"❌ Chyba při analýze: {str(e)}"
            ], color="danger")
            return None, error, no_update, no_update
    
    
    # ==================== VISUALIZATION ====================
    @app.callback(
        Output('spectrum-plot', 'figure'),
        [Input('sample-results', 'data'),
         Input('sample-selector', 'value'),
         Input('cut-channel', 'value'),
         Input('peak-calibration-data', 'data')],
        State('excel-data', 'data')
    )
    def update_plot(results, selected_sample, cut_channel, calib_data, excel_data):
        """Update spectrum plot - show raw after upload, fitted after analysis"""
        
        print(f"\n=== UPDATE_PLOT CALLED ===")
        print(f"results is None: {results is None}")
        print(f"selected_sample: {selected_sample}")
        print(f"cut_channel: {cut_channel}")
        
        # If analysis results available, show them
        if results is not None:
            try:
                print("Attempting to create fitted spectrum plot...")
                
                calib_df = pd.DataFrame(results['calibration'])
                ref_calib = results['ref_calib']
                sample_spectrum = results['sample_spectrum']
                
                # Calculate energies - use range(len) like original script
                energies = [calculate_energy(ch, ref_calib) for ch in range(len(sample_spectrum))]
                
                # Create plot
                fig = go.Figure()
                
                # Sample spectrum
                fig.add_trace(go.Scatter(
                    x=energies,
                    y=results['sample_spectrum'],
                    mode='lines',
                    name='Naměřené',
                    line=dict(color='black', width=2),
                ))
                
                # Fitted spectra
                fig.add_trace(go.Scatter(
                    x=energies,
                    y=results['fitted_ols'],
                    mode='lines',
                    name='Fit (OLS)',
                    line=dict(color='green', width=2, dash='dot'),
                ))
                
                fig.add_trace(go.Scatter(
                    x=energies,
                    y=results['fitted_nnls'],
                    mode='lines',
                    name='Fit (NNLS)',
                    line=dict(color='orange', width=2, dash='dot'),
                ))
                
                # Individual components (Ra, K, Th, BG1, BG2...) from OLS - use RAW coefficients
                calib_df = pd.DataFrame(results['calibration'])
                X_calib = calib_df[['Ra', 'K', 'Th']].values
                raw_coeffs = results['raw_ols_coeffs']
                bg_names = results['bg_names']
                
                # Radioaktivní komponenty
                fig.add_trace(go.Scatter(
                    x=energies,
                    y=X_calib[:, 0] * raw_coeffs['Ra'],
                    mode='lines',
                    name='Ra-226',
                    line=dict(color='red', width=1, dash='dashdot'),
                    opacity=0.7
                ))
                
                fig.add_trace(go.Scatter(
                    x=energies,
                    y=X_calib[:, 1] * raw_coeffs['K'],
                    mode='lines',
                    name='K-40',
                    line=dict(color='blue', width=1, dash='dashdot'),
                    opacity=0.7
                ))
                
                fig.add_trace(go.Scatter(
                    x=energies,
                    y=X_calib[:, 2] * raw_coeffs['Th'],
                    mode='lines',
                    name='Th-232',
                    line=dict(color='purple', width=1, dash='dashdot'),
                    opacity=0.7
                ))
                
                # Pozadí komponenty (dynamicky podle počtu pozadí)
                bg_colors = ['dimgray', 'brown', 'olive', 'teal']  # Barvy pro pozadí
                background_data = results['background']  # Dict of lists
                
                print(f"\n=== DEBUG: Background plotting ===")
                print(f"Type of background_data: {type(background_data)}")
                print(f"Keys: {list(background_data.keys())}")
                print(f"bg_names: {bg_names}")
                
                for i, bg_name in enumerate(bg_names):
                    bg_spectrum = background_data[bg_name]  # Should be a list
                    print(f"\n{bg_name}:")
                    print(f"  Type: {type(bg_spectrum)}")
                    print(f"  Length: {len(bg_spectrum) if hasattr(bg_spectrum, '__len__') else 'N/A'}")
                    print(f"  First 5 values: {bg_spectrum[:5] if isinstance(bg_spectrum, list) else 'NOT A LIST'}")
                    
                    bg_coef = raw_coeffs.get(bg_name, 1.0)
                    print(f"  Coefficient: {bg_coef} (type: {type(bg_coef)})")
                    
                    color = bg_colors[i % len(bg_colors)]
                    
                    # Multiply spectrum by coefficient
                    bg_y = np.array(bg_spectrum) * bg_coef
                    print(f"  bg_y type: {type(bg_y)}")
                    print(f"  bg_y shape: {bg_y.shape}")
                    print(f"  bg_y first 5: {bg_y[:5]}")
                    
                    fig.add_trace(go.Scatter(
                        x=energies,
                        y=bg_y,
                        mode='lines',
                        name=f'BG: {bg_name}',
                        line=dict(color=color, width=1, dash='dashdot'),
                        opacity=0.6
                    ))
                
                print(f"=== DEBUG END ===\n")
                
                fig.update_layout(
                    title=f"Spektrum vzorku: {results['sample_name']}",
                    xaxis_title="Energie (keV)",
                    yaxis_title="Intenzita (CPS)",
                    hovermode='x unified',
                    template='plotly_white',
                    legend=dict(x=0.7, y=0.98)
                )
                
                # Add green crosses for calibration peaks
                if calib_data and 'peaks' in calib_data and results:
                    ref_calib = results['ref_calib']
                    sample_spectrum = results['sample_spectrum']
                    
                    for energy_str, channel in calib_data['peaks'].items():
                        if channel != '-':
                            # Convert channel to energy using ref_calib
                            energy_val = ref_calib[0] + ref_calib[1] * channel
                            
                            # Find intensity at that channel
                            if 0 <= channel < len(sample_spectrum):
                                intensity = sample_spectrum[channel]
                                
                                fig.add_trace(go.Scatter(
                                    x=[energy_val],
                                    y=[intensity],
                                    mode='markers',
                                    marker=dict(
                                        symbol='x',
                                        size=12,
                                        color='green',
                                        line=dict(width=2)
                                    ),
                                    name=f'{energy_str} keV',
                                    showlegend=False,
                                    hovertemplate=f'Kalibrace: {energy_str} keV<br>CH {channel}<extra></extra>'
                                ))
                
                return fig
                
            except Exception as e:
                print(f"\n!!! EXCEPTION in fitted spectrum plotting !!!")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {str(e)}")
                import traceback
                traceback.print_exc()
                
                fig = go.Figure()
                fig.update_layout(title=f"Chyba: {str(e)}", template='plotly_white')
                return fig
        
        # If no analysis yet but Excel loaded and sample selected, show raw spectrum
        if excel_data is not None and selected_sample is not None:
            try:
                sample_df = pd.DataFrame(excel_data['samples'])
                sample_idx = excel_data['sample_names'].index(selected_sample)
                sample_live_time = excel_data['sample_live_times'][sample_idx]
                
                # Get parameters for energy calculation
                params = excel_data['parameters']
                ref_a0 = float(params.get('ref_a0', 9.6229))
                ref_a1 = float(params.get('ref_a1', 1.3793))
                ref_a2 = float(params.get('ref_a2', 0))
                ref_calib = [ref_a0, ref_a1, ref_a2]
                
                # Calculate energies
                energies = [calculate_energy(ch, ref_calib) for ch in sample_df['CHNL']]
                
                # Normalize to CPS
                counts = sample_df[selected_sample].values / sample_live_time
                
                # Apply cut channel (vynulovat první N kanálů)
                if cut_channel is not None and cut_channel > 0:
                    counts = counts.copy()
                    counts[sample_df['CHNL'] <= cut_channel] = 0
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=energies,
                    y=counts,
                    mode='lines',
                    name='Raw spektrum',
                    line=dict(color='blue', width=1.5),
                ))
                
                fig.update_layout(
                    title=f"Raw spektrum: {selected_sample} (cut ≤ {cut_channel})",
                    xaxis_title="Energie (keV)",
                    yaxis_title="Intenzita (CPS)",
                    hovermode='x unified',
                    template='plotly_white'
                )
                
                # Add green crosses for calibration peaks
                if calib_data and 'peaks' in calib_data:
                    for energy_str, channel in calib_data['peaks'].items():
                        if channel != '-':
                            # Convert channel to energy
                            energy_val = ref_calib[0] + ref_calib[1] * channel
                            
                            # Find intensity at that channel
                            ch_idx = sample_df['CHNL'].tolist().index(channel) if channel in sample_df['CHNL'].tolist() else None
                            if ch_idx is not None:
                                intensity = counts[ch_idx]
                                
                                fig.add_trace(go.Scatter(
                                    x=[energy_val],
                                    y=[intensity],
                                    mode='markers',
                                    marker=dict(
                                        symbol='x',
                                        size=12,
                                        color='green',
                                        line=dict(width=2)
                                    ),
                                    name=f'{energy_str} keV',
                                    showlegend=False,
                                    hovertemplate=f'Kalibrace: {energy_str} keV<br>CH {channel}<extra></extra>'
                                ))
                
                return fig
                
            except Exception as e:
                fig = go.Figure()
                fig.update_layout(title=f"Chyba: {str(e)}", template='plotly_white')
                return fig
        
        # Default empty plot
        fig = go.Figure()
        fig.update_layout(
            title="Načtěte data a vyberte vzorek...",
            template='plotly_white'
        )
        return fig
    
    
    @app.callback(
        [Output('results-table', 'data'),
         Output('results-table', 'columns'),
         Output('detailed-stats', 'children')],
        Input('sample-results', 'data')
    )
    def update_results_table(results):
        """Update results table"""
        if results is None:
            return [], [], "Žádná data"
        
        try:
            ols_res = results['results_ols']
            nnls_res = results['results_nnls']
            bg_names = results.get('bg_names', [])
            
            # Extract values from nested structure
            ols_coeff = ols_res['Coefficients']
            ols_stderr = ols_res['Std Errors']
            nnls_coeff = nnls_res['Coefficients']
            nnls_stderr = nnls_res['Std Errors']
            
            # Create radioactivity table data (Ra, K, Th in Bq)
            table_data = [
                {
                    'Method': 'OLS',
                    'Ra (Bq)': f"{ols_coeff['Ra']:.4f}",
                    'K (Bq)': f"{ols_coeff['K']:.4f}",
                    'Th (Bq)': f"{ols_coeff['Th']:.4f}",
                    'Ra_stderr': f"{ols_stderr['Ra']:.4f}",
                    'K_stderr': f"{ols_stderr['K']:.4f}",
                    'Th_stderr': f"{ols_stderr['Th']:.4f}",
                    'R²': f"{ols_res['R^2']:.6f}",
                    'Adj R²': f"{ols_res['Adjusted R^2']:.6f}",
                },
                {
                    'Method': 'NNLS',
                    'Ra (Bq)': f"{nnls_coeff['Ra']:.4f}",
                    'K (Bq)': f"{nnls_coeff['K']:.4f}",
                    'Th (Bq)': f"{nnls_coeff['Th']:.4f}",
                    'Ra_stderr': f"{nnls_stderr['Ra']:.4f}",
                    'K_stderr': f"{nnls_stderr['K']:.4f}",
                    'Th_stderr': f"{nnls_stderr['Th']:.4f}",
                    'R²': f"{nnls_res['R^2']:.6f}",
                    'Adj R²': f"{nnls_res['Adjusted R^2']:.6f}",
                }
            ]
            
            # Add background coefficients to table (raw values, ideally ~1.0)
            for bg_name in bg_names:
                table_data[0][f'{bg_name}'] = f"{ols_coeff[bg_name]:.4f}"
                table_data[0][f'{bg_name}_stderr'] = f"{ols_stderr[bg_name]:.4f}"
                table_data[1][f'{bg_name}'] = f"{nnls_coeff[bg_name]:.4f}"
                table_data[1][f'{bg_name}_stderr'] = f"{nnls_stderr[bg_name]:.4f}"
            
            columns = [{"name": col, "id": col} for col in table_data[0].keys()]
            
            # Detailed stats
            bg_text_ols = "\n".join([f"  {bg}: {ols_coeff[bg]:.4f}  (stderr: {ols_stderr[bg]:.4f})" for bg in bg_names])
            bg_text_nnls = "\n".join([f"  {bg}: {nnls_coeff[bg]:.4f}  (stderr: {nnls_stderr[bg]:.4f})" for bg in bg_names])
            
            detailed = f"""
Vzorek: {results['sample_name']}
Kalibrace: {results['calib_method']}
{'='*60}

OLS výsledky:
  Radioaktivita:
    Ra-226: {ols_coeff['Ra']:.4f} Bq  (stderr: {ols_stderr['Ra']:.4f})
    K-40:   {ols_coeff['K']:.4f} Bq  (stderr: {ols_stderr['K']:.4f})
    Th-232: {ols_coeff['Th']:.4f} Bq  (stderr: {ols_stderr['Th']:.4f})
  
  Pozadí (koeficienty, očekáváno ~1.0):
{bg_text_ols}
  
  R² = {ols_res['R^2']:.6f}
  Adjusted R² = {ols_res['Adjusted R^2']:.6f}

NNLS výsledky:
  Radioaktivita:
    Ra-226: {nnls_coeff['Ra']:.4f} Bq  (stderr: {nnls_stderr['Ra']:.4f})
    K-40:   {nnls_coeff['K']:.4f} Bq  (stderr: {nnls_stderr['K']:.4f})
    Th-232: {nnls_coeff['Th']:.4f} Bq  (stderr: {nnls_stderr['Th']:.4f})
  
  Pozadí (koeficienty, očekáváno ~1.0):
{bg_text_nnls}
  
  R² = {nnls_res['R^2']:.6f}
  Adjusted R² = {nnls_res['Adjusted R^2']:.6f}
            """
            
            return table_data, columns, detailed
            
        except Exception as e:
            return [], [], f"Chyba: {str(e)}"
    
    
    # ==================== EXPORT CSV ====================
    @app.callback(
        Output("download-csv", "data"),
        Input("export-csv", "n_clicks"),
        State('results-table', 'data'),
        State('sample-results', 'data'),
        prevent_initial_call=True
    )
    def export_csv(n_clicks, table_data, results):
        """Export results to CSV"""
        if table_data and results:
            df = pd.DataFrame(table_data)
            filename = f"results_{results['sample_name']}.csv"
            return dict(content=df.to_csv(index=False), filename=filename)
        raise PreventUpdate
    
    
    # ==================== MANUAL PEAK CALIBRATION ====================
    @app.callback(
        [Output('calib-status', 'children'),
         Output('peak-calibration-data', 'data'),
         Output('select-e-238', 'color'),
         Output('select-e-295', 'color'),
         Output('select-e-352', 'color'),
         Output('select-e-609', 'color'),
         Output('select-e-1461', 'color')],
        [Input('spectrum-plot', 'clickData'),
         Input('select-e-238', 'n_clicks'),
         Input('select-e-295', 'n_clicks'),
         Input('select-e-352', 'n_clicks'),
         Input('select-e-609', 'n_clicks'),
         Input('select-e-1461', 'n_clicks')],
        [State('peak-calibration-data', 'data'),
         State('sample-selector', 'value'),
         State('excel-data', 'data')]
    )
    def handle_peak_calibration(click_data, n238, n295, n352, n609, n1461, calib_data, selected_sample, excel_data):
        """Handle energy selection and graph clicks for manual calibration"""
        from dash import callback_context
        
        if not callback_context.triggered:
            raise PreventUpdate
        
        trigger_id = callback_context.triggered[0]['prop_id'].split('.')[0]
        
        # Initialize
        if calib_data is None:
            calib_data = {'peaks': {}, 'active_energy': None}
        
        # Default button colors
        colors = ['light', 'light', 'light', 'light', 'light']
        energy_list = ['238', '295', '352', '609', '1461']
        
        # Highlight active energy
        if calib_data.get('active_energy'):
            idx = energy_list.index(calib_data['active_energy'])
            colors[idx] = 'primary'
        
        # Handle energy button clicks - activate energy
        energy_map = {
            'select-e-238': '238',
            'select-e-295': '295',
            'select-e-352': '352',
            'select-e-609': '609',
            'select-e-1461': '1461'
        }
        
        if trigger_id in energy_map:
            energy = energy_map[trigger_id]
            calib_data['active_energy'] = energy
            idx = energy_list.index(energy)
            colors[idx] = 'primary'
            status = f"Energie {energy} keV aktivní - klikněte na pík v grafu"
            return status, calib_data, *colors
        
        # Handle graph click - assign channel to active energy
        if trigger_id == 'spectrum-plot' and click_data and calib_data.get('active_energy'):
            # Get channel from clicked point
            x_value = click_data['points'][0]['x']
            
            # If looking at raw spectrum (channels) or fitted (energy), convert accordingly
            if excel_data and selected_sample and 'parameters' in excel_data:
                params = excel_data['parameters']
                ref_a0 = float(params.get('ref_a0', 9.6229))
                ref_a1 = float(params.get('ref_a1', 1.3793))
                
                # Assume x is energy, convert to channel
                channel = int((x_value - ref_a0) / ref_a1)
            else:
                channel = int(x_value)
            
            energy = calib_data['active_energy']
            calib_data['peaks'][energy] = channel
            
            status = f"✓ {energy} keV → Kanál {channel} (klikněte znovu pro přepsání)"
            
            # Keep energy active, change to green
            idx = energy_list.index(energy)
            colors[idx] = 'success'
            
            return status, calib_data, *colors
        
        status = "Vyberte energii a klikněte na pík v grafu"
        return status, calib_data, *colors
    
    
    @app.callback(
        [Output('peak-ch-238', 'children'),
         Output('peak-ch-295', 'children'),
         Output('peak-ch-352', 'children'),
         Output('peak-ch-609', 'children'),
         Output('peak-ch-1461', 'children'),
         Output('calculate-calibration', 'disabled')],
        Input('peak-calibration-data', 'data')
    )
    def update_peak_displays(calib_data):
        """Update channel displays in table"""
        if not calib_data or 'peaks' not in calib_data:
            return "-", "-", "-", "-", "-", True
        
        peaks = calib_data['peaks']
        values = [peaks.get(e, '-') for e in ['238', '295', '352', '609', '1461']]
        
        # Enable calculate button if at least 2 peaks defined
        num_peaks = sum(1 for v in values if v != '-')
        disabled = num_peaks < 2
        
        return *values, disabled
    
    
    @app.callback(
        Output('calibration-fit-plot', 'figure'),
        [Input('peak-calibration-data', 'data'),
         Input('ref-a0', 'value'),
         Input('ref-a1', 'value'),
         Input('manual-a0', 'value'),
         Input('manual-a1', 'value')]
    )
    def plot_calibration_fit(calib_data, ref_a0, ref_a1, manual_a0, manual_a1):
        """Plot active calibration - shows manual peaks if available, otherwise just the active equation"""
        fig = go.Figure()
        
        # Determine which calibration is active
        has_manual_peaks = (calib_data and 'peaks' in calib_data and 
                           any(ch != '-' for ch in calib_data['peaks'].values()))
        
        # If manual calibration was done, show points + fit
        if has_manual_peaks and manual_a0 is not None and manual_a1 is not None:
            # Extract peak data
            energies = []
            channels = []
            for energy_str, channel in calib_data['peaks'].items():
                if channel != '-':
                    energies.append(float(energy_str))
                    channels.append(float(channel))
            
            energies = np.array(energies)
            channels = np.array(channels)
            
            # Plot points (green markers)
            fig.add_trace(go.Scatter(
                x=channels,
                y=energies,
                mode='markers',
                name='Definované píky',
                marker=dict(size=10, color='green', symbol='circle'),
                text=[f"{e:.0f} keV" for e in energies],
                hovertemplate='CH %{x}<br>%{text}<extra></extra>'
            ))
            
            # Plot fit line using manual_a0, manual_a1
            ch_range = np.linspace(0, max(channels) * 1.1, 100)
            e_fit = manual_a0 + manual_a1 * ch_range
            
            fig.add_trace(go.Scatter(
                x=ch_range,
                y=e_fit,
                mode='lines',
                name=f'Manuální: E = {manual_a0:.2f} + {manual_a1:.4f}·CH',
                line=dict(color='blue', dash='dash', width=2)
            ))
            
            # Residuals
            fitted_e = manual_a0 + manual_a1 * channels
            residuals = energies - fitted_e
            
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
            
            title = "Aktivní kalibrace: Manuální"
        
        # Otherwise, show reference calibration (from Excel or optimized)
        elif ref_a0 is not None and ref_a1 is not None:
            ch_range = np.linspace(0, 2048, 100)
            e_fit = ref_a0 + ref_a1 * ch_range
            
            fig.add_trace(go.Scatter(
                x=ch_range,
                y=e_fit,
                mode='lines',
                name=f'Referenční: E = {ref_a0:.2f} + {ref_a1:.4f}·CH',
                line=dict(color='orange', dash='solid', width=2)
            ))
            
            title = "Aktivní kalibrace: Referenční (Excel/Optimalizace)"
        
        else:
            # No calibration available
            fig.update_layout(
                title="Žádná kalibrace k dispozici",
                xaxis_title="Kanál",
                yaxis_title="Energie (keV)",
                template='plotly_white'
            )
            return fig
        
        fig.update_layout(
            title=title,
            xaxis_title="Kanál",
            yaxis_title="Energie (keV)",
            hovermode='closest',
            template='plotly_white',
            legend=dict(x=0.05, y=0.95)
        )
        
        return fig
    
    
    @app.callback(
        [Output('ref-a0', 'value', allow_duplicate=True),
         Output('ref-a1', 'value', allow_duplicate=True),
         Output('manual-a0', 'value', allow_duplicate=True),
         Output('manual-a1', 'value', allow_duplicate=True),
         Output('calib-result-display', 'children')],
        Input('calculate-calibration', 'n_clicks'),
        State('peak-calibration-data', 'data'),
        prevent_initial_call=True
    )
    def calculate_and_apply_calibration(n_clicks, calib_data):
        """Calculate linear calibration from selected peaks and apply"""
        if not calib_data or 'peaks' not in calib_data:
            raise PreventUpdate
        
        peaks = calib_data['peaks']
        
        # Extract energy-channel pairs
        energies = []
        channels = []
        for energy_str, channel in peaks.items():
            if channel != '-':
                energies.append(float(energy_str))
                channels.append(float(channel))
        
        if len(energies) < 2:
            raise PreventUpdate
        
        # Linear fit: E = a0 + a1 * CH
        energies = np.array(energies)
        channels = np.array(channels)
        
        A = np.vstack([np.ones(len(channels)), channels]).T
        a0, a1 = np.linalg.lstsq(A, energies, rcond=None)[0]
        
        # Calculate residuals
        fitted = a0 + a1 * channels
        residuals = energies - fitted
        
        result_text = dbc.Alert([
            html.H6("✓ Kalibrace vypočtena:", className="alert-heading"),
            html.P([
                f"a₀ = {a0:.6f} keV",
                html.Br(),
                f"a₁ = {a1:.6f} keV/CH",
                html.Br(),
                html.Br(),
                html.Small(f"Použito {len(energies)} píků, max. reziduální chyba: {np.max(np.abs(residuals)):.2f} keV")
            ], className="mb-0")
        ], color="success", className="mt-2")
        
        # Update both ref and manual calibration
        return a0, a1, a0, a1, result_text

