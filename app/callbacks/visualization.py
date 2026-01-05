"""
Visualization callbacks - spectrum plotting with components and markers
"""

from .utils import *


def register_visualization_callbacks(app):
    """Register visualization callbacks"""
    
    # ==================== ROI SLIDER SYNC ====================
    @app.callback(
        [Output('roi1-range', 'data'),
         Output('roi2-range', 'data')],
        [Input('roi1-range-slider', 'value'),
         Input('roi2-range-slider', 'value')]
    )
    def sync_roi_sliders(roi1_slider, roi2_slider):
        """Sync RangeSlider values to stores"""
        return roi1_slider, roi2_slider
    
    
    # ==================== FULL SPECTRUM PLOT ====================
    @app.callback(
        [Output('spectrum-plot-full', 'figure'),
         Output('spectrum-plot-full-header', 'children')],
        [Input('sample-results', 'data'),
         Input('sample-selector', 'value'),
         Input('peak-calibration-data', 'data'),
         Input('current-sample-calib', 'data'),
         Input('roi1-range', 'data'),
         Input('roi2-range', 'data')],
        [State('excel-data', 'data'),
         State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value')]
    )
    def update_plot_full(results, selected_sample, calib_data, current_sample_calib, 
                         roi1_range, roi2_range,
                         excel_data, ref_a0, ref_a1, ref_a2):
        """Update full spectrum plot - CHANNEL-CENTRIC: X-axis in channels, energy in tooltips"""
        
        print(f"[DEBUG] update_plot_full called: roi1_range={roi1_range}, roi2_range={roi2_range}")

        # Display calibration for energy tooltips
        display_calib = [ref_a0, ref_a1, ref_a2]
        
        # Calculate display range from CURRENT slider values (for dynamic zoom)
        roi_min, roi_max = None, None
        if roi1_range and roi2_range and None not in roi1_range and None not in roi2_range:
            roi_min = min(roi1_range[0], roi2_range[0])
            roi_max = max(roi1_range[1], roi2_range[1])
        
        # If analysis results available, use them
        if results is not None:
            try:
                # Get rebinned spectrum data
                sample_rebinned = np.array(results['sample_rebinned'])
                n_channels = len(sample_rebinned)
                
                # CHANNEL-CENTRIC: X-axis is channels, energy in customdata
                channels = np.arange(n_channels)
                energies = calculate_display_energy(channels, display_calib)
                
                # Create plot
                fig = go.Figure()
                
                # Sample spectrum (black line) - X-axis in CHANNELS
                fig.add_trace(go.Scatter(
                    x=channels,
                    y=sample_rebinned,
                    mode='lines',
                    line=dict(color='black', width=2, shape='hv'),
                    name='Naměřené',
                    customdata=energies,
                    hovertemplate='Kanál: %{x}<br>Energie: ~%{customdata:.1f} keV<br>Počty: %{y:.0f}<extra></extra>'
                ))
                
                # Add merged fit from ROI analysis using ACTUAL fitted values (same as ROI graphs)
                roi_info = results.get('roi_info', {})
                if roi_info.get('enabled') and roi_info.get('roi1_fitted') and roi_info.get('roi2_fitted'):
                    roi1_fitted = np.array(roi_info['roi1_fitted'])
                    roi2_fitted = np.array(roi_info['roi2_fitted'])
                    roi1_range_vals = roi_info.get('roi1_range', [])
                    roi2_range_vals = roi_info.get('roi2_range', [])
                    
                    # Validate ROI ranges (now in CHANNELS)
                    if len(roi1_range_vals) == 2 and len(roi2_range_vals) == 2:
                        # Create masks for each ROI region
                        roi1_mask = (channels >= roi1_range_vals[0]) & (channels <= roi1_range_vals[1])
                        roi2_mask = (channels >= roi2_range_vals[0]) & (channels <= roi2_range_vals[1])
                        
                        # Create mask for combined ROI display range - CHANNEL-BASED
                        if roi_min is not None and roi_max is not None:
                            combined_mask = (channels >= roi_min) & (channels <= roi_max)
                        else:
                            combined_mask = np.ones(n_channels, dtype=bool)
                        
                        if combined_mask.any():
                            # Build merged fit using ACTUAL fitted values from ROI analysis
                            # In overlap region: ROI1 (Ra/Th) takes priority
                            merged_fit = np.zeros(n_channels)
                            
                            # First apply ROI2 fit (K region) - this will be overwritten in overlap
                            merged_fit[roi2_mask] = roi2_fitted[roi2_mask]
                            
                            # Then apply ROI1 fit (Ra/Th region) - this overwrites overlap
                            merged_fit[roi1_mask] = roi1_fitted[roi1_mask]
                            
                            # Display only in combined ROI range where we have fit data
                            display_mask = combined_mask & (roi1_mask | roi2_mask)
                            channels_display = channels[display_mask]
                            energies_display = energies[display_mask]
                            merged_fit_display = merged_fit[display_mask]
                            
                            # Show total merged fit (same as ROI graphs)
                            fig.add_trace(go.Scatter(
                                x=channels_display,
                                y=merged_fit_display,
                                mode='lines',
                                line=dict(color='green', width=2.5, shape='hv'),
                                name='Fit (Ra+Th+K)',
                                opacity=0.85,
                                customdata=energies_display,
                                hovertemplate='Fit: %{y:.0f} počtů<br>~%{customdata:.1f} keV<extra></extra>'
                            ))
                            
                            # Add ROI overlays (keep them visible)
                            # ROI #1 (Ra/Th) - Orange
                            roi1_e_min = display_calib[0] + display_calib[1] * roi1_range_vals[0]
                            roi1_e_max = display_calib[0] + display_calib[1] * roi1_range_vals[1]
                            fig.add_vrect(
                                x0=roi1_range_vals[0], x1=roi1_range_vals[1],
                                fillcolor='rgba(255, 165, 0, 0.15)',
                                layer='below', line_width=0,
                                annotation_text=f'Ra/Th ({roi1_e_min:.0f}-{roi1_e_max:.0f} keV)',
                                annotation_position='top left',
                                annotation_font_size=10
                            )
                            
                            # ROI #2 (K-40) - Blue
                            roi2_e_min = display_calib[0] + display_calib[1] * roi2_range_vals[0]
                            roi2_e_max = display_calib[0] + display_calib[1] * roi2_range_vals[1]
                            fig.add_vrect(
                                x0=roi2_range_vals[0], x1=roi2_range_vals[1],
                                fillcolor='rgba(0, 123, 255, 0.15)',
                                layer='below', line_width=0,
                                annotation_text=f'K-40 ({roi2_e_min:.0f}-{roi2_e_max:.0f} keV)',
                                annotation_position='top right',
                                annotation_font_size=10
                            )
                
                # Add calibration peak markers if available - X in CHANNELS
                if calib_data and 'peaks' in calib_data:
                    for energy_str, channel in calib_data['peaks'].items():
                        if channel != '-':
                            if 0 <= channel < n_channels:
                                intensity = sample_rebinned[channel]
                                energy_val = display_calib[0] + display_calib[1] * channel
                                
                                fig.add_trace(go.Scatter(
                                    x=[channel],
                                    y=[intensity],
                                    mode='markers',
                                    marker=dict(symbol='x', size=12, color='green', line=dict(width=2)),
                                    name=f'{energy_str} keV',
                                    showlegend=False,
                                    hovertemplate=f'Kalibrace: {energy_str} keV<br>CH {channel}<br>~{energy_val:.1f} keV<extra></extra>'
                                ))
                
                # Calculate initial y-axis range for displayed region (CHANNEL-BASED)
                yaxis_config = {}
                if roi_min is not None and roi_max is not None:
                    display_mask = (channels >= roi_min) & (channels <= roi_max)
                    if display_mask.any():
                        y_visible = sample_rebinned[display_mask]
                        y_max = np.max(y_visible)
                        yaxis_config = dict(range=[0, y_max * 1.1])  # Initial range only, user can zoom
                
                fig.update_layout(
                    xaxis_title="Kanál",
                    yaxis_title="Počty",
                    hovermode='x unified',
                    template='plotly_white',
                    legend=dict(x=0.7, y=0.98),
                    margin=dict(l=60, r=20, t=20, b=40),
                    xaxis=dict(
                        range=[roi_min, roi_max] if roi_min is not None else None,
                        showspikes=True, 
                        spikemode='across', 
                        spikethickness=1, 
                        spikecolor='gray', 
                        spikedash='dash'
                    ),
                    yaxis=yaxis_config,
                    hoverdistance=100,
                    hoverlabel=dict(align='right', namelength=-1)
                )
                
                header_text = f"📊 Celé spektrum: {results['sample_name']}"
                return fig, header_text
                
            except Exception as e:
                pass
                
                fig = go.Figure()
                fig.update_layout(template='plotly_white', margin=dict(t=20))
                return fig, "📊 Celé spektrum: Chyba"
        
        # If no analysis yet but Excel loaded and sample selected, show raw spectrum
        if excel_data is not None and selected_sample is not None:
            try:
                sample_df = pd.DataFrame(excel_data['samples'])
                sample_idx = excel_data['sample_names'].index(selected_sample)
                sample_live_time = excel_data['sample_live_times'][sample_idx]
                
                # Get channels and raw counts (no normalization for display)
                channels = sample_df['CHNL'].values
                counts = sample_df[selected_sample].values  # Raw counts
                
                # Calculate approximate energies for tooltips
                energies = calculate_display_energy(channels, display_calib)
                
                fig = go.Figure()
                
                # Sample spectrum - X in CHANNELS
                fig.add_trace(go.Scatter(
                    x=channels,
                    y=counts,
                    mode='lines',
                    name='Naměřené',
                    line=dict(color='black', width=2, shape='hv'),
                    customdata=energies,
                    hovertemplate='Kanál: %{x}<br>Energie: ~%{customdata:.1f} keV<br>Počty: %{y:.0f}<extra></extra>'
                ))
                
                # Add ROI overlays if ranges configured (CHANNEL-BASED)
                if roi1_range and roi2_range:
                    if None not in roi1_range:
                        # ROI #1 (Ra/Th) - Orange - channel mask
                        roi1_mask = (channels >= roi1_range[0]) & (channels <= roi1_range[1])
                        if roi1_mask.any():
                            roi1_e_min = display_calib[0] + display_calib[1] * roi1_range[0]
                            roi1_e_max = display_calib[0] + display_calib[1] * roi1_range[1]
                            fig.add_trace(go.Scatter(
                                x=channels[roi1_mask],
                                y=counts[roi1_mask],
                                mode='lines',
                                line=dict(width=0, shape='hv'),
                                fill='tozeroy',
                                fillcolor='rgba(255, 165, 0, 0.2)',
                                name=f'ROI #1 Ra/Th (ch {roi1_range[0]}-{roi1_range[1]}, ~{roi1_e_min:.0f}-{roi1_e_max:.0f} keV)',
                                hoverinfo='skip',
                                showlegend=True
                            ))
                    
                    if None not in roi2_range:
                        # ROI #2 (K-40) - Blue - channel mask
                        roi2_mask = (channels >= roi2_range[0]) & (channels <= roi2_range[1])
                        if roi2_mask.any():
                            roi2_e_min = display_calib[0] + display_calib[1] * roi2_range[0]
                            roi2_e_max = display_calib[0] + display_calib[1] * roi2_range[1]
                            fig.add_trace(go.Scatter(
                                x=channels[roi2_mask],
                                y=counts[roi2_mask],
                                mode='lines',
                                line=dict(width=0, shape='hv'),
                                fill='tozeroy',
                                fillcolor='rgba(0, 123, 255, 0.2)',
                                name=f'ROI #2 K-40 (ch {roi2_range[0]}-{roi2_range[1]}, ~{roi2_e_min:.0f}-{roi2_e_max:.0f} keV)',
                                hoverinfo='skip',
                                showlegend=True
                            ))
                
                # Calculate initial y-axis range for displayed region (CHANNEL-BASED)
                yaxis_config = {}
                if roi_min is not None and roi_max is not None:
                    display_mask = (channels >= roi_min) & (channels <= roi_max)
                    if display_mask.any():
                        y_visible = counts[display_mask]
                        y_max = np.max(y_visible)
                        yaxis_config = dict(range=[0, y_max * 1.1])  # Initial range only, user can zoom
                
                # Create uirevision key that changes when ROI ranges change
                ui_key = f"roi_{roi1_range}_{roi2_range}" if roi1_range and roi2_range else "default"
                
                fig.update_layout(
                    xaxis_title="Kanál",
                    yaxis_title="Počty",
                    hovermode='x unified',
                    template='plotly_white',
                    legend=dict(x=0.7, y=0.98),
                    margin=dict(l=60, r=20, t=20, b=40),
                    uirevision=ui_key,  # Reset zoom when ROI changes
                    xaxis=dict(
                        range=[roi_min, roi_max] if roi_min is not None else None,
                        autorange=False if roi_min is not None else True,
                        showspikes=True, 
                        spikemode='across', 
                        spikethickness=1, 
                        spikecolor='gray', 
                        spikedash='dash'
                    ),
                    yaxis=yaxis_config,
                    hoverdistance=100,
                    hoverlabel=dict(align='right', namelength=-1)
                )
                
                # Add calibration peak markers - X in CHANNELS
                if calib_data and 'peaks' in calib_data:
                    for energy_str, channel in calib_data['peaks'].items():
                        if channel != '-':
                            ch_idx = sample_df['CHNL'].tolist().index(channel) if channel in sample_df['CHNL'].tolist() else None
                            if ch_idx is not None:
                                intensity = counts[ch_idx]
                                energy_val = display_calib[0] + display_calib[1] * channel
                                
                                fig.add_trace(go.Scatter(
                                    x=[channel],
                                    y=[intensity],
                                    mode='markers',
                                    marker=dict(symbol='x', size=12, color='green', line=dict(width=2)),
                                    name=f'{energy_str} keV',
                                    showlegend=False,
                                    hovertemplate=f'Kalibrace: {energy_str} keV<br>CH {channel}<br>~{energy_val:.1f} keV<extra></extra>'
                                ))
                
                header_text = f"📊 Celé spektrum: {selected_sample}"
                return fig, header_text
                
            except Exception as e:
                fig = go.Figure()
                fig.update_layout(template='plotly_white', margin=dict(t=20))
                return fig, "📊 Celé spektrum"
        
        # Default empty plot
        fig = go.Figure()
        fig.update_layout(
            template='plotly_white',
            margin=dict(t=20)
        )
        return fig, "📊 Celé spektrum"
    
    
    # ==================== ROI #1 PLOT (Ra/Th) ====================
    @app.callback(
        Output('spectrum-plot-roi1', 'figure'),
        [Input('sample-results', 'data'),
         Input('roi1-range', 'data')],
        [State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value')]
    )
    def update_plot_roi1(results, roi1_range, ref_a0, ref_a1, ref_a2):
        """Update ROI #1 plot - CHANNEL-CENTRIC: zoomed Ra/Th region with fit and components"""
        ref_calib = [ref_a0, ref_a1, ref_a2]
        return create_roi_plot(results, roi_num=1, roi_range=roi1_range, 
                              ref_calib=ref_calib, emphasis='Ra/Th')
    
    
    # ==================== ROI #2 PLOT (K-40) ====================
    @app.callback(
        Output('spectrum-plot-roi2', 'figure'),
        [Input('sample-results', 'data'),
         Input('roi2-range', 'data')],
        [State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value')]
    )
    def update_plot_roi2(results, roi2_range, ref_a0, ref_a1, ref_a2):
        """Update ROI #2 plot - CHANNEL-CENTRIC: zoomed K-40 region with fit and components"""
        ref_calib = [ref_a0, ref_a1, ref_a2]
        return create_roi_plot(results, roi_num=2, roi_range=roi2_range, 
                              ref_calib=ref_calib, emphasis='K')
    
    
    # ==================== ROI #1 RESIDUALS PLOT ====================
    @app.callback(
        Output('residuals-plot-roi1', 'figure'),
        [Input('sample-results', 'data'),
         Input('roi1-range', 'data'),
         Input('spectrum-plot-roi1', 'relayoutData')],
        [State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value')]
    )
    def update_residuals_roi1(results, roi1_range, relayout_data, ref_a0, ref_a1, ref_a2):
        """Display relative residuals for ROI #1 with zoom sync - CHANNEL-CENTRIC"""
        ref_calib = [ref_a0, ref_a1, ref_a2]
        return create_residuals_plot(results, roi_num=1, roi_range=roi1_range, 
                                    ref_calib=ref_calib, relayout_data=relayout_data)
    
    
    # ==================== ROI #2 RESIDUALS PLOT ====================
    @app.callback(
        Output('residuals-plot-roi2', 'figure'),
        [Input('sample-results', 'data'),
         Input('roi2-range', 'data'),
         Input('spectrum-plot-roi2', 'relayoutData')],
        [State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value')]
    )
    def update_residuals_roi2(results, roi2_range, relayout_data, ref_a0, ref_a1, ref_a2):
        """Display relative residuals for ROI #2 with zoom sync - CHANNEL-CENTRIC"""
        ref_calib = [ref_a0, ref_a1, ref_a2]
        return create_residuals_plot(results, roi_num=2, roi_range=roi2_range, 
                                    ref_calib=ref_calib, relayout_data=relayout_data)
