"""
Visualization callbacks - spectrum plotting with components and markers
"""

from .utils import *


def register_visualization_callbacks(app):
    """Register visualization callbacks"""
    
    # ==================== SPECTRUM PLOT ====================
    @app.callback(
        Output('spectrum-plot', 'figure'),
        [Input('sample-results', 'data'),
         Input('sample-selector', 'value'),
         Input('cut-channel', 'value'),
         Input('peak-calibration-data', 'data'),
         Input('current-sample-calib', 'data')],
        State('excel-data', 'data')
    )
    def update_plot(results, selected_sample, cut_channel, calib_data, current_sample_calib, excel_data):
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
                
                # Get sample calibration from store (current UI values)
                sample_calib = [
                    current_sample_calib.get('a0', 9.6229),
                    current_sample_calib.get('a1', 1.3793),
                    current_sample_calib.get('a2', 0)
                ]
                
                # Calculate energies using current sample calibration
                energies = [calculate_energy(ch, sample_calib) for ch in sample_df['CHNL']]
                
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
                            # Convert channel to energy using sample_calib
                            energy_val = sample_calib[0] + sample_calib[1] * channel
                            
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
