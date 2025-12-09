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
         Input('cut-channel-range', 'value'),
         Input('peak-calibration-data', 'data'),
         Input('current-sample-calib', 'data')],
        State('excel-data', 'data')
    )
    def update_plot(results, selected_sample, cut_range, calib_data, current_sample_calib, excel_data):
        """Update spectrum plot - show raw after upload, fitted after analysis"""
        
        # Extract left and right cutoffs from range slider
        cut_left = cut_range[0] if cut_range else 0
        cut_right = cut_range[1] if cut_range else 2048
        
        print(f"\n=== UPDATE_PLOT CALLED ===")
        print(f"results is None: {results is None}")
        print(f"selected_sample: {selected_sample}")
        print(f"cut_range: {cut_left}-{cut_right}")

        
        # If analysis results available, show them
        if results is not None:
            try:
                print("Attempting to create fitted spectrum plot...")
                
                # Get UNCUT data from results
                calib_df_uncut = pd.DataFrame(results['calibration'])  # Now uncut
                ref_calib = results['ref_calib']
                sample_calib = results['sample_calib']
                sample_spectrum_uncut = np.array(results['sample_spectrum_uncut'])
                raw_coeffs = results['raw_coeffs']  # Single method raw coefficients
                regression_method = results.get('regression_method', 'OLS')
                
                # Create mask for current cutoff range
                n_channels = len(sample_spectrum_uncut)
                channel_indices = np.arange(n_channels)
                mask = (channel_indices > cut_left) & (channel_indices <= cut_right)
                
                # Apply current cutoff to sample spectrum and rebin
                sample_spectrum_masked = sample_spectrum_uncut.copy()
                sample_spectrum_masked[~mask] = 0
                sample_rebinned = rebin_spectrum(ref_calib, sample_calib, sample_spectrum_masked)
                
                # Apply current cutoff to calibration spectra
                calib_df_masked = calib_df_uncut.copy()
                calib_df_masked.loc[~mask, ["Ra", "K", "Th"]] = 0
                X_calib = calib_df_masked[['Ra', 'K', 'Th']].values
                
                # Build predictor matrix with current cutoff (only Ra, K, Th)
                X = X_calib
                component_values = [raw_coeffs['Ra'], raw_coeffs['K'], raw_coeffs['Th']]
                
                # Recalculate fitted spectrum with current cutoff
                fitted_spectrum = X @ np.array(component_values)
                
                # Calculate energies
                energies = [calculate_energy(ch, ref_calib) for ch in range(len(sample_rebinned))]
                
                # Create plot
                fig = go.Figure()
                
                # Sample spectrum
                channels = list(range(len(sample_rebinned)))
                fig.add_trace(go.Scatter(
                    x=energies,
                    y=sample_rebinned,
                    mode='lines',
                    name='Naměřené',
                    line=dict(color='black', width=2),
                    customdata=channels,
                    hovertemplate='Energie: %{x:.2f} keV<br>Kanál: %{customdata}<br>Intenzita: %{y:.2f} CPS<extra></extra>'
                ))
                
                # Fitted spectrum (single method)
                fit_color = 'green' if regression_method == 'OLS' else 'orange'
                fig.add_trace(go.Scatter(
                    x=energies,
                    y=fitted_spectrum,
                    mode='lines',
                    name=f'Fit ({regression_method})',
                    line=dict(color=fit_color, width=2, dash='dot'),
                    customdata=channels,
                    hovertemplate='Energie: %{x:.2f} keV<br>Kanál: %{customdata}<br>Fit: %{y:.2f} CPS<extra></extra>'
                ))
                
                # Radioaktivní komponenty
                fig.add_trace(go.Scatter(
                    x=energies,
                    y=X_calib[:, 0] * raw_coeffs['Ra'],
                    mode='lines',
                    name='Ra-226',
                    line=dict(color='red', width=1, dash='dashdot'),
                    opacity=0.7,
                    customdata=channels,
                    hovertemplate='Energie: %{x:.2f} keV<br>Kanál: %{customdata}<br>Ra-226: %{y:.2f} CPS<extra></extra>'
                ))
                
                fig.add_trace(go.Scatter(
                    x=energies,
                    y=X_calib[:, 1] * raw_coeffs['K'],
                    mode='lines',
                    name='K-40',
                    line=dict(color='blue', width=1, dash='dashdot'),
                    opacity=0.7,
                    customdata=channels,
                    hovertemplate='Energie: %{x:.2f} keV<br>Kanál: %{customdata}<br>K-40: %{y:.2f} CPS<extra></extra>'
                ))
                
                fig.add_trace(go.Scatter(
                    x=energies,
                    y=X_calib[:, 2] * raw_coeffs['Th'],
                    mode='lines',
                    name='Th-232',
                    line=dict(color='purple', width=1, dash='dashdot'),
                    opacity=0.7,
                    customdata=channels,
                    hovertemplate='Energie: %{x:.2f} keV<br>Kanál: %{customdata}<br>Th-232: %{y:.2f} CPS<extra></extra>'
                ))
                
                fig.update_layout(
                    title=f"Spektrum vzorku: {results['sample_name']}",
                    xaxis_title="Energie (keV)",
                    yaxis_title="Intenzita (CPS)",
                    hovermode='x unified',
                    template='plotly_white',
                    legend=dict(x=0.7, y=0.98),
                    xaxis=dict(showspikes=True, spikemode='across', spikethickness=1, spikecolor='gray', spikedash='dash'),
                    hoverdistance=100
                )
                
                # Add green crosses for calibration peaks
                if calib_data and 'peaks' in calib_data and results:
                    ref_calib = results['ref_calib']
                    
                    for energy_str, channel in calib_data['peaks'].items():
                        if channel != '-':
                            # Convert channel to energy using ref_calib (with quadratic term)
                            energy_val = calculate_energy(channel, ref_calib)
                            
                            # Find intensity at that channel in rebinned spectrum
                            if 0 <= channel < len(sample_rebinned):
                                intensity = sample_rebinned[channel]
                                
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
                
                # Apply cutoffs (zero out channels outside the selected range)
                if cut_range is not None:
                    counts = counts.copy()
                    counts[sample_df['CHNL'] <= cut_left] = 0
                    counts[sample_df['CHNL'] > cut_right] = 0
                
                fig = go.Figure()
                channels = sample_df['CHNL'].values
                fig.add_trace(go.Scatter(
                    x=energies,
                    y=counts,
                    mode='lines',
                    name='Raw spektrum',
                    line=dict(color='blue', width=1.5),
                    customdata=channels,
                    hovertemplate='Energie: %{x:.2f} keV<br>Kanál: %{customdata}<br>Intenzita: %{y:.2f} CPS<extra></extra>'
                ))
                
                fig.update_layout(
                    title=f"Raw spektrum: {selected_sample} (rozsah: {cut_left}-{cut_right})",
                    xaxis_title="Energie (keV)",
                    yaxis_title="Intenzita (CPS)",
                    hovermode='x unified',
                    template='plotly_white',
                    xaxis=dict(showspikes=True, spikemode='across', spikethickness=1, spikecolor='gray', spikedash='dash'),
                    hoverdistance=100
                )
                
                # Add green crosses for calibration peaks
                if calib_data and 'peaks' in calib_data:
                    for energy_str, channel in calib_data['peaks'].items():
                        if channel != '-':
                            # Convert channel to energy using sample_calib (with quadratic term)
                            energy_val = calculate_energy(channel, sample_calib)
                            
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
    
    
    # ==================== RESIDUALS PLOT ====================
    @app.callback(
        [Output('residuals-plot', 'figure'),
         Output('residuals-card', 'style')],
        Input('sample-results', 'data')
    )
    def update_residuals_plot(results):
        """Display residuals after analysis"""
        
        if results is None:
            # Hide card when no results
            return go.Figure(), {'display': 'none'}
        
        try:
            # Get data from results (use uncut data stored in results)
            sample_spectrum = np.array(results['sample_spectrum_uncut'])
            fitted_spectrum = np.array(results['fitted_spectrum'])
            regression_method = results.get('regression_method', 'OLS')
            ref_calib = results['ref_calib']
            cut_range = results.get('cut_range_used', [0, len(sample_spectrum)])
            
            # Apply same cutoff as was used in analysis
            cut_left, cut_right = cut_range
            mask = np.zeros(len(sample_spectrum), dtype=bool)
            mask[cut_left:cut_right] = True
            
            sample_masked = sample_spectrum[mask]
            fitted_masked = fitted_spectrum  # Already matches cut range
            
            # Calculate residuals
            residuals = sample_masked - fitted_masked
            
            # Calculate energies (only for masked region)
            energies = [calculate_energy(ch, ref_calib) for ch in range(cut_left, cut_right)]
            
            # Create figure
            fig = go.Figure()
            
            # Single method residuals with dynamic color
            resid_color = 'green' if regression_method == 'OLS' else 'orange'
            fig.add_trace(go.Scatter(
                x=energies,
                y=residuals,
                mode='lines',
                name=f'Residua ({regression_method})',
                line=dict(color=resid_color, width=1.5),
            ))
            
            # Zero line
            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            
            fig.update_layout(
                xaxis_title="Energie (keV)",
                yaxis_title="Residua (CPS)",
                hovermode='x unified',
                template='plotly_white',
                margin=dict(l=50, r=20, t=30, b=40),
                legend=dict(x=0.7, y=0.98)
            )
            
            # Show card
            return fig, {'display': 'block'}
            
        except Exception as e:
            print(f"Error in residuals plot: {e}")
            return go.Figure(), {'display': 'none'}
