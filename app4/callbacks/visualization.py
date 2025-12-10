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
    
    
    # ==================== K SOURCE SELECTION ====================
    @app.callback(
        [Output('k-source-roi', 'data'),
         Output('use-k-from-roi1', 'value'),
         Output('use-k-from-roi2', 'value')],
        [Input('use-k-from-roi1', 'value'),
         Input('use-k-from-roi2', 'value')],
        [State('k-source-roi', 'data')],
        prevent_initial_call=True
    )
    def toggle_k_source(roi1_checked, roi2_checked, current_source):
        """Toggle which ROI to use for K coefficient in results"""
        if not callback_context.triggered:
            raise PreventUpdate
        
        trigger_id = callback_context.triggered[0]['prop_id'].split('.')[0]
        
        if trigger_id == 'use-k-from-roi1':
            # Use K from Ra/Th ROI
            return 'roi1', [1], []
        elif trigger_id == 'use-k-from-roi2':
            # Use K from K ROI
            return 'roi2', [], [1]
        
        # Default state
        return current_source, [1] if current_source == 'roi1' else [], [1] if current_source == 'roi2' else []
    
    
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
                         roi1_range, roi2_range, excel_data, ref_a0, ref_a1, ref_a2):
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
                
                # DON'T show ROI overlays - only show merged fit from analysis
                
                # Add merged fit from ROI analysis (ONLY total fit, not individual components)
                roi_info = results.get('roi_info', {})
                if roi_info.get('enabled') and roi_info.get('roi1_components_data') and roi_info.get('roi2_components_data'):
                    roi1_comps = roi_info['roi1_components_data']
                    roi2_comps = roi_info['roi2_components_data']
                    roi1_range_vals = roi_info.get('roi1_range', [])
                    roi2_range_vals = roi_info.get('roi2_range', [])
                    
                    # Validate ROI ranges (now in CHANNELS)
                    if len(roi1_range_vals) == 2 and len(roi2_range_vals) == 2:
                        # Get masks from analysis (these indicate which channels belong to each ROI)
                        roi1_mask = np.array(roi1_comps.get('mask', []))
                        roi2_mask = np.array(roi2_comps.get('mask', []))
                        
                        # Use CURRENT slider values for display range (already calculated above at lines 76-78)
                        # Don't overwrite roi_min/roi_max here - they come from sliders!
                        
                        # Create mask for combined ROI display range - CHANNEL-BASED
                        if roi_min is not None and roi_max is not None:
                            combined_mask = (channels >= roi_min) & (channels <= roi_max)
                        else:
                            combined_mask = np.ones(n_channels, dtype=bool)
                        
                        if combined_mask.any() and len(roi1_mask) == n_channels and len(roi2_mask) == n_channels:
                            # Build merged fit: Ra+Th+K from ROI1 in ROI1 range, Ra+Th from ROI1 + K from ROI2 in ROI2 range
                            merged_fit = np.zeros(n_channels)
                            
                            # Get components
                            ra_component = np.array(roi1_comps['Ra']) if 'Ra' in roi1_comps else np.zeros(n_channels)
                            th_component = np.array(roi1_comps['Th']) if 'Th' in roi1_comps else np.zeros(n_channels)
                            k_roi1_component = np.array(roi1_comps['K']) if 'K' in roi1_comps else np.zeros(n_channels)
                            k_roi2_component = np.array(roi2_comps['K']) if 'K' in roi2_comps else np.zeros(n_channels)
                            
                            # Add Ra and Th everywhere
                            merged_fit += ra_component
                            merged_fit += th_component
                            
                            # Add K: from ROI1 in ROI1 range, from ROI2 in ROI2 range
                            # In ROI1 region (not overlapping with ROI2)
                            roi1_only_mask = roi1_mask & ~roi2_mask
                            merged_fit[roi1_only_mask] += k_roi1_component[roi1_only_mask]
                            
                            # In ROI2 region (use ROI2 K fit)
                            merged_fit[roi2_mask] += k_roi2_component[roi2_mask]
                            
                            # Display only in combined ROI range - X in CHANNELS
                            channels_display = channels[combined_mask]
                            energies_display = energies[combined_mask]
                            merged_fit_display = merged_fit[combined_mask]
                            
                            # ONLY show total merged fit (not individual components)
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
        
        # Show placeholder if no results yet
        if results is None:
            fig = go.Figure()
            fig.update_layout(
                title="ROI #1: Ra/Th (čeká na analýzu)",
                template='plotly_white',
                height=300
            )
            return fig
        
        # Check if ROI data is available
        roi_info = results.get('roi_info', {})
        if not roi_info.get('enabled') or not roi_info.get('roi1_fitted'):
            fig = go.Figure()
            fig.update_layout(
                title="ROI #1: Ra/Th (žádná ROI data)",
                template='plotly_white',
                height=300
            )
            return fig
        
        try:
            # Display calibration for tooltips
            display_calib = [ref_a0, ref_a1, ref_a2]
            
            # Extract data
            sample_rebinned = np.array(results['sample_rebinned'])
            n_channels = len(sample_rebinned)
            roi_info = results['roi_info']
            
            roi1_fitted = np.array(roi_info.get('roi1_fitted', []))
            components = roi_info.get('roi1_components_data', {})
            
            # CHANNEL-CENTRIC: X-axis is channels
            channels = np.arange(n_channels)
            energies = calculate_display_energy(channels, display_calib)
            
            # Use current slider value for display range (dynamic zoom)
            # But data (fitted values) are from analysis
            roi_range = roi1_range if roi1_range else roi_info['roi1_range']
            mask = (channels >= roi_range[0]) & (channels <= roi_range[1])
            
            # Create figure
            fig = go.Figure()
            
            # Sample data (black) - X in CHANNELS
            fig.add_trace(go.Scatter(
                x=channels[mask],
                y=sample_rebinned[mask],
                mode='lines',
                line=dict(color='black', width=2, shape='hv'),
                name='Naměřené',
                customdata=energies[mask],
                hovertemplate='Kanál: %{x}<br>~%{customdata:.1f} keV<br>Počty: %{y:.0f}<extra></extra>'
            ))
            
            # Fitted spectrum (green dash)
            if len(roi1_fitted) > 0:
                fig.add_trace(go.Scatter(
                    x=channels[mask],
                    y=roi1_fitted[mask],
                    mode='lines',
                    line=dict(color='green', width=2, dash='dot'),
                    name='Fit',
                    customdata=energies[mask],
                    hovertemplate='Fit: %{y:.0f} počtů<extra></extra>'
                ))
            
            # Ra component (red dashdot)
            if 'Ra' in components:
                ra_comp = np.array(components['Ra'])
                fig.add_trace(go.Scatter(
                    x=channels[mask],
                    y=ra_comp[mask],
                    mode='lines',
                    line=dict(color='red', width=1, dash='dashdot'),
                    name='Ra-226',
                    opacity=0.6,
                    customdata=energies[mask],
                    hovertemplate='Ra-226: %{y:.0f} počtů<extra></extra>'
                ))
            
            # Th component (orange dashdot)
            if 'Th' in components:
                th_comp = np.array(components['Th'])
                fig.add_trace(go.Scatter(
                    x=channels[mask],
                    y=th_comp[mask],
                    mode='lines',
                    line=dict(color='orange', width=1, dash='dashdot'),
                    name='Th-232',
                    opacity=0.6,
                    customdata=energies[mask],
                    hovertemplate='Th-232: %{y:.0f} počtů<extra></extra>'
                ))
            
            # K component (blue, faint)
            if 'K' in components:
                k_comp = np.array(components['K'])
                fig.add_trace(go.Scatter(
                    x=channels[mask],
                    y=k_comp[mask],
                    mode='lines',
                    line=dict(color='blue', width=1, dash='dashdot'),
                    name='K-40',
                    opacity=0.3,
                    customdata=energies[mask],
                    hovertemplate='K-40: %{y:.0f} počtů<extra></extra>'
                ))
            
            # Background component (gray, very faint)
            if 'BG' in components:
                bg_comp = np.array(components['BG'])
                fig.add_trace(go.Scatter(
                    x=channels[mask],
                    y=bg_comp[mask],
                    mode='lines',
                    line=dict(color='gray', width=1, dash='dot'),
                    name='Pozadí',
                    opacity=0.4,
                    customdata=energies[mask],
                    hovertemplate='Pozadí: %{y:.0f} počtů<extra></extra>'
                ))
            
            fig.update_layout(
                xaxis_title="",
                yaxis_title="Počty",
                yaxis=dict(tickformat='.0f', automargin=False),
                xaxis=dict(range=roi_range, automargin=False, showticklabels=False),
                hovermode='x unified',
                template='plotly_white',
                height=300,
                margin=dict(l=60, r=20, t=40, b=30),
                hoverlabel=dict(align='right', namelength=-1),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="left",
                    x=0,
                    font=dict(size=10)
                )
            )
            
            return fig
            
        except Exception as e:
            fig = go.Figure()
            fig.update_layout(title=f"Chyba: {str(e)}", template='plotly_white', height=300)
            return fig
    
    
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
        
        # Show placeholder if no results yet
        if results is None:
            fig = go.Figure()
            fig.update_layout(
                title="ROI #2: K-40 (čeká na analýzu)",
                template='plotly_white',
                height=300
            )
            return fig
        
        # Check if ROI data is available
        roi_info = results.get('roi_info', {})
        if not roi_info.get('enabled') or not roi_info.get('roi2_fitted'):
            fig = go.Figure()
            fig.update_layout(
                title="ROI #2: K-40 (žádná ROI data)",
                template='plotly_white',
                height=300
            )
            return fig
        
        try:
            # Display calibration for tooltips
            display_calib = [ref_a0, ref_a1, ref_a2]
            
            # Extract data
            sample_rebinned = np.array(results['sample_rebinned'])
            n_channels = len(sample_rebinned)
            roi_info = results['roi_info']
            
            roi2_fitted = np.array(roi_info.get('roi2_fitted', []))
            components = roi_info.get('roi2_components_data', {})
            
            # CHANNEL-CENTRIC: X-axis is channels
            channels = np.arange(n_channels)
            energies = calculate_display_energy(channels, display_calib)
            
            # Use current slider value for display range (dynamic zoom)
            # But data (fitted values) are from analysis
            roi_range = roi2_range if roi2_range else roi_info['roi2_range']
            mask = (channels >= roi_range[0]) & (channels <= roi_range[1])
            
            # Create figure
            fig = go.Figure()
            
            # Sample data (black) - X in CHANNELS
            fig.add_trace(go.Scatter(
                x=channels[mask],
                y=sample_rebinned[mask],
                mode='lines',
                line=dict(color='black', width=2, shape='hv'),
                name='Naměřené',
                customdata=energies[mask],
                hovertemplate='Kanál: %{x}<br>~%{customdata:.1f} keV<br>Počty: %{y:.0f}<extra></extra>'
            ))
            
            # Fitted spectrum (green dash)
            if len(roi2_fitted) > 0:
                fig.add_trace(go.Scatter(
                    x=channels[mask],
                    y=roi2_fitted[mask],
                    mode='lines',
                    line=dict(color='green', width=2, dash='dot'),
                    name='Fit',
                    customdata=energies[mask],
                    hovertemplate='Fit: %{y:.0f} počtů<extra></extra>'
                ))
            
            # K component (blue dashdot, prominent)
            if 'K' in components:
                k_comp = np.array(components['K'])
                fig.add_trace(go.Scatter(
                    x=channels[mask],
                    y=k_comp[mask],
                    mode='lines',
                    line=dict(color='blue', width=1, dash='dashdot'),
                    name='K-40',
                    opacity=0.8,
                    customdata=energies[mask],
                    hovertemplate='K-40: %{y:.0f} počtů<extra></extra>'
                ))
            
            # Ra component (red, faint)
            if 'Ra' in components:
                ra_comp = np.array(components['Ra'])
                fig.add_trace(go.Scatter(
                    x=channels[mask],
                    y=ra_comp[mask],
                    mode='lines',
                    line=dict(color='red', width=1, dash='dashdot'),
                    name='Ra-226',
                    opacity=0.3,
                    customdata=energies[mask],
                    hovertemplate='Ra-226: %{y:.0f} počtů<extra></extra>'
                ))
            
            # Th component (purple, faint)
            if 'Th' in components:
                th_comp = np.array(components['Th'])
                fig.add_trace(go.Scatter(
                    x=channels[mask],
                    y=th_comp[mask],
                    mode='lines',
                    line=dict(color='purple', width=1, dash='dashdot'),
                    name='Th-232',
                    opacity=0.3,
                    customdata=energies[mask],
                    hovertemplate='Th-232: %{y:.0f} počtů<extra></extra>'
                ))
            
            # Background component (gray, very faint)
            if 'BG' in components:
                bg_comp = np.array(components['BG'])
                fig.add_trace(go.Scatter(
                    x=channels[mask],
                    y=bg_comp[mask],
                    mode='lines',
                    line=dict(color='gray', width=1, dash='dot'),
                    name='Pozadí',
                    opacity=0.4,
                    customdata=energies[mask],
                    hovertemplate='Pozadí: %{y:.0f} počtů<extra></extra>'
                ))
            
            fig.update_layout(
                xaxis_title="",
                yaxis_title="Počty",
                yaxis=dict(tickformat='.0f', automargin=False),
                xaxis=dict(range=roi_range, automargin=False, showticklabels=False),
                hovermode='x unified',
                template='plotly_white',
                height=300,
                margin=dict(l=60, r=20, t=40, b=30),
                hoverlabel=dict(align='right', namelength=-1),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="left",
                    x=0,
                    font=dict(size=10)
                )
            )
            
            return fig
            
        except Exception as e:
            fig = go.Figure()
            fig.update_layout(title=f"Chyba: {str(e)}", template='plotly_white', height=300)
            return fig
    
    
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
        
        if results is None:
            fig = go.Figure()
            fig.update_layout(
                template='plotly_white',
                height=120,
                margin=dict(l=60, r=20, t=10, b=30),
                xaxis_title="",
                yaxis_title="Rel. res. (%)"
            )
            return fig
        
        # Check if ROI data is available
        roi_info = results.get('roi_info', {})
        if not roi_info.get('enabled') or not roi_info.get('roi1_fitted'):
            fig = go.Figure()
            fig.update_layout(
                template='plotly_white',
                height=120,
                margin=dict(l=60, r=20, t=10, b=30),
                xaxis_title="",
                yaxis_title="Rel. res. (%)"
            )
            return fig
        
        try:
            # Display calibration for tooltips
            display_calib = [ref_a0, ref_a1, ref_a2]
            
            # Extract data
            sample_rebinned = np.array(results['sample_rebinned'])
            n_channels = len(sample_rebinned)
            roi_info = results['roi_info']
            roi1_fitted = np.array(roi_info.get('roi1_fitted', []))
            
            if len(roi1_fitted) == 0:
                raise PreventUpdate
            
            # CHANNEL-CENTRIC: X-axis is channels
            channels = np.arange(n_channels)
            energies = calculate_display_energy(channels, display_calib)
            
            # Use current slider value for display range (dynamic zoom)
            roi_range = roi1_range if roi1_range else roi_info['roi1_range']
            mask = (channels >= roi_range[0]) & (channels <= roi_range[1])
            
            # Calculate relative residuals: (observed - fitted) / observed (pure relative, not percent)
            with np.errstate(divide='ignore', invalid='ignore'):
                rel_residuals = (sample_rebinned - roi1_fitted) / sample_rebinned
                rel_residuals[~np.isfinite(rel_residuals)] = 0
            
            # Create figure
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=channels[mask],
                y=rel_residuals[mask],
                mode='markers',
                marker=dict(size=3, color='blue'),
                name='Relativní residua',
                customdata=energies[mask],
                hovertemplate='Ch: %{x}<br>~%{customdata:.1f} keV<br>%{y:.3f}<extra></extra>'
            ))
            
            # Zero reference line
            fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
            
            # Sync x-axis range with main plot (CHANNEL range), fallback to ROI range
            xaxis_range = None
            if relayout_data and 'xaxis.range[0]' in relayout_data:
                xaxis_range = [relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']]
            elif relayout_data and 'xaxis.range' in relayout_data:
                xaxis_range = relayout_data['xaxis.range']
            else:
                xaxis_range = roi_range  # Default to ROI range to prevent offset
            
            # Calculate symmetric y-range to align with ROI graph
            y_abs_max = np.max(np.abs(rel_residuals[mask]))
            y_range = [-y_abs_max * 1.1, y_abs_max * 1.1]  # Symmetric around zero
            
            fig.update_layout(
                template='plotly_white',
                height=120,
                margin=dict(l=60, r=20, t=10, b=30),
                xaxis_title="",
                yaxis_title="Rel. res.",
                yaxis=dict(tickformat='.3f', range=y_range, automargin=False),
                xaxis=dict(range=xaxis_range, automargin=False),
                showlegend=False,
                hovermode='x',
                hoverlabel=dict(align='right', namelength=-1)
            )
            
            return fig
            
        except Exception as e:
            fig = go.Figure()
            fig.update_layout(template='plotly_white', height=120, margin=dict(l=60, r=20, t=10, b=30))
            return fig
    
    
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
        
        if results is None:
            fig = go.Figure()
            fig.update_layout(
                template='plotly_white',
                height=120,
                margin=dict(l=60, r=20, t=10, b=30),
                xaxis_title="",
                yaxis_title="Rel. res. (%)"
            )
            return fig
        
        # Check if ROI data is available
        roi_info = results.get('roi_info', {})
        if not roi_info.get('enabled') or not roi_info.get('roi2_fitted'):
            fig = go.Figure()
            fig.update_layout(
                template='plotly_white',
                height=120,
                margin=dict(l=60, r=20, t=10, b=30),
                xaxis_title="",
                yaxis_title="Rel. res. (%)"
            )
            return fig
        
        try:
            # Display calibration for tooltips
            display_calib = [ref_a0, ref_a1, ref_a2]
            
            # Extract data
            sample_rebinned = np.array(results['sample_rebinned'])
            n_channels = len(sample_rebinned)
            roi_info = results['roi_info']
            roi2_fitted = np.array(roi_info.get('roi2_fitted', []))
            
            if len(roi2_fitted) == 0:
                raise PreventUpdate
            
            # CHANNEL-CENTRIC: X-axis is channels
            channels = np.arange(n_channels)
            energies = calculate_display_energy(channels, display_calib)
            
            # Use current slider value for display range (dynamic zoom)
            roi_range = roi2_range if roi2_range else roi_info['roi2_range']
            mask = (channels >= roi_range[0]) & (channels <= roi_range[1])
            
            # Calculate relative residuals: (observed - fitted) / observed (pure relative, not percent)
            with np.errstate(divide='ignore', invalid='ignore'):
                rel_residuals = (sample_rebinned - roi2_fitted) / sample_rebinned
                rel_residuals[~np.isfinite(rel_residuals)] = 0
            
            # Create figure
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=channels[mask],
                y=rel_residuals[mask],
                mode='markers',
                marker=dict(size=3, color='blue'),
                name='Relativní residua',
                customdata=energies[mask],
                hovertemplate='Ch: %{x}<br>~%{customdata:.1f} keV<br>%{y:.3f}<extra></extra>'
            ))
            
            # Zero reference line
            fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
            
            # Sync x-axis range with main plot (CHANNEL range), fallback to ROI range
            xaxis_range = None
            if relayout_data and 'xaxis.range[0]' in relayout_data:
                xaxis_range = [relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']]
            elif relayout_data and 'xaxis.range' in relayout_data:
                xaxis_range = relayout_data['xaxis.range']
            else:
                xaxis_range = roi_range  # Default to ROI range to prevent offset
            
            # Calculate symmetric y-range to align with ROI graph
            y_abs_max = np.max(np.abs(rel_residuals[mask]))
            y_range = [-y_abs_max * 1.1, y_abs_max * 1.1]  # Symmetric around zero
            
            fig.update_layout(
                template='plotly_white',
                height=120,
                margin=dict(l=60, r=20, t=10, b=30),
                xaxis_title="",
                yaxis_title="Rel. res.",
                yaxis=dict(tickformat='.3f', range=y_range, automargin=False),
                xaxis=dict(range=xaxis_range, automargin=False),
                showlegend=False,
                hovermode='x',
                hoverlabel=dict(align='right', namelength=-1)
            )
            
            return fig
            
        except Exception as e:
            fig = go.Figure()
            fig.update_layout(template='plotly_white', height=120, margin=dict(l=60, r=20, t=10, b=30))
            return fig
