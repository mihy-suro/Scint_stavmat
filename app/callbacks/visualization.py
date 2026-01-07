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
    
    
    # ==================== ROI 186 keV SLIDER SYNC (4-value slider) ====================
    @app.callback(
        [Output('roi-186-range', 'data'),
         Output('peak-186-roi-left', 'data'),
         Output('peak-186-roi-right', 'data')],
        Input('roi-186-slider', 'value')
    )
    def sync_roi_186_slider(slider_values):
        """Sync 4-value slider to stores: [zoom_left, peak_left, peak_right, zoom_right]"""
        if slider_values is None or len(slider_values) != 4:
            # Fallback to defaults
            return [100, 160], 120, 140
        
        zoom_left, peak_left, peak_right, zoom_right = slider_values
        return [zoom_left, zoom_right], peak_left, peak_right
    
    
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
                # NOTE: With separate ROI mappings, the fit is NOT displayed on full spectrum
                # because each ROI uses different rebinned spectrum. Fit is shown only in ROI graphs.
                roi_info = results.get('roi_info', {})
                if roi_info.get('enabled'):
                    roi1_range_vals = roi_info.get('roi1_range', [])
                    roi2_range_vals = roi_info.get('roi2_range', [])
                    
                    # Check if we have separate mappings (new behavior)
                    has_separate_mappings = (roi_info.get('roi1_channel_mapping') is not None and 
                                            roi_info.get('roi2_channel_mapping') is not None)
                    
                    # Validate ROI ranges (now in CHANNELS)
                    if len(roi1_range_vals) == 2 and len(roi2_range_vals) == 2:
                        # Add ROI overlays (keep them visible)
                        # ROI #1 (Ra/Th) - Orange
                        roi1_e_min = display_calib[0] + display_calib[1] * roi1_range_vals[0]
                        roi1_e_max = display_calib[0] + display_calib[1] * roi1_range_vals[1]
                        
                        # Get channel mapping info for annotation
                        roi1_mapping = roi_info.get('roi1_channel_mapping', [0, 1])
                        roi2_mapping = roi_info.get('roi2_channel_mapping', [0, 1])
                        
                        if has_separate_mappings:
                            roi1_label = f'Ra/Th ({roi1_e_min:.0f}-{roi1_e_max:.0f} keV)\\noffset={roi1_mapping[0]:.1f}, gain={roi1_mapping[1]:.3f}'
                        else:
                            roi1_label = f'Ra/Th ({roi1_e_min:.0f}-{roi1_e_max:.0f} keV)'
                        
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
                        
                        # Add info annotation about separate mappings
                        if has_separate_mappings:
                            fig.add_annotation(
                                x=0.5, y=1.02,
                                xref='paper', yref='paper',
                                text='ℹ️ Fit zobrazen pouze v ROI grafech (separátní mapování)',
                                showarrow=False,
                                font=dict(size=10, color='gray'),
                                xanchor='center'
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
    
    
    # ==================== Ra-226 @ 186 keV PEAK VISUALIZATION ====================
    @app.callback(
        [Output('spectrum-plot-186', 'figure'),
         Output('live-186-netarea', 'children')],
        [Input('sample-results', 'data'),
         Input('result-186-data', 'data'),
         Input('roi-186-range', 'data'),
         Input('peak-186-roi-left', 'data'),
         Input('peak-186-roi-right', 'data'),
         Input('sample-selector', 'value')],
        [State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value'),
         State('excel-data', 'data')]
    )
    def update_plot_186(results, result_186, roi_186_range, peak_roi_left, peak_roi_right, selected_sample, 
                        ref_a0, ref_a1, ref_a2, excel_data):
        """Visualize Ra-226 @ 186 keV peak with net area calculation
        
        Shows:
        - Raw spectrum (black line) in zoom region
        - Linear background (dashed line) within peak ROI
        - Net area filled in yellow (only between peak ROI boundaries)
        - Static vertical lines marking peak ROI boundaries
        - Calibration spectrum scaled to calculated activity (after 186 analysis)
        
        Slider controls:
        - Outer handles: zoom range (what's visible in graph)
        - Inner handles: peak ROI boundaries (where net area is calculated)
        """
        print(f"\n[186 Plot] update_plot_186 called")
        print(f"[186 Plot] result_186 is None: {result_186 is None}")
        print(f"[186 Plot] results has ra_peak_186: {results.get('ra_peak_186') is not None if results else False}")
        
        fig = go.Figure()
        display_calib = [ref_a0 or 9.6229, ref_a1 or 1.3793, ref_a2 or 0]
        live_text = "Net area: - | CH: -"
        
        # Default display range from slider (zoom)
        if roi_186_range is None:
            roi_186_range = [100, 160]
        roi_min, roi_max = int(roi_186_range[0]), int(roi_186_range[1])
        
        # Peak ROI boundaries (from inner slider handles)
        if peak_roi_left is None:
            peak_roi_left = 120
        if peak_roi_right is None:
            peak_roi_right = 140
        peak_roi_left = int(peak_roi_left)
        peak_roi_right = int(peak_roi_right)
        
        # Try to get spectrum data - either from results or raw excel_data
        spectrum = None
        
        # First try from results (rebinned spectrum)
        if results is not None:
            spectrum = results.get('sample_rebinned', None)
            if spectrum:
                spectrum = np.array(spectrum)
        
        # If no results yet, try raw spectrum from excel_data
        if spectrum is None and excel_data is not None and selected_sample is not None:
            try:
                sample_df = pd.DataFrame(excel_data['samples'])
                if selected_sample in sample_df.columns:
                    spectrum = sample_df[selected_sample].values
            except Exception:
                pass
        
        # No spectrum available
        if spectrum is None:
            fig.update_layout(
                template='plotly_white',
                margin=dict(t=30, b=30, l=40, r=20),
                xaxis_title='Kanál',
                yaxis_title='Počty',
                annotations=[{
                    'text': 'Vyberte vzorek...',
                    'xref': 'paper', 'yref': 'paper',
                    'x': 0.5, 'y': 0.5,
                    'showarrow': False,
                    'font': {'size': 12, 'color': 'gray'}
                }]
            )
            return fig, live_text
        
        # Ensure zoom ROI is within spectrum bounds
        roi_min = max(0, roi_min)
        roi_max = min(len(spectrum) - 1, roi_max)
        
        # Clamp peak ROI to be within zoom range
        peak_roi_left = max(roi_min, min(peak_roi_left, roi_max))
        peak_roi_right = max(roi_min, min(peak_roi_right, roi_max))
        if peak_roi_left > peak_roi_right:
            peak_roi_left, peak_roi_right = peak_roi_right, peak_roi_left
        
        # Extract zoom ROI data (for display)
        zoom_channels = np.arange(roi_min, roi_max + 1)
        zoom_counts = spectrum[roi_min:roi_max + 1]
        
        # Calculate energies for display
        zoom_energies = np.array([display_calib[0] + display_calib[1] * ch + display_calib[2] * ch**2 
                                  for ch in zoom_channels])
        
        # Calculate Y-axis range from visible data (0.9*min to 1.1*max)
        y_min_data = np.min(zoom_counts) if len(zoom_counts) > 0 else 0
        y_max_data = np.max(zoom_counts) if len(zoom_counts) > 0 else 100
        y_min = max(0, y_min_data * 0.9)
        y_max = y_max_data * 1.1
        
        # Add raw spectrum in zoom region (black line)
        fig.add_trace(go.Scatter(
            x=zoom_channels,
            y=zoom_counts,
            mode='lines',
            name='Spektrum',
            line=dict(color='black', width=2, shape='hv'),
            customdata=zoom_energies,
            hovertemplate='CH: %{x}<br>E: %{customdata:.1f} keV<br>Počty: %{y:.0f}<extra></extra>'
        ))
        
        # Calculate net area within peak ROI boundaries
        peak_channels = np.arange(peak_roi_left, peak_roi_right + 1)
        peak_counts = spectrum[peak_roi_left:peak_roi_right + 1]
        
        net_area = 0
        activity_estimate = 0
        
        if len(peak_counts) >= 5:
            # Estimate linear background from edges (5 channels each side)
            bg_left_val = np.mean(peak_counts[:5])
            bg_right_val = np.mean(peak_counts[-5:])
            bg_slope = (bg_right_val - bg_left_val) / (peak_roi_right - peak_roi_left) if peak_roi_right != peak_roi_left else 0
            bg_values = bg_left_val + bg_slope * (peak_channels - peak_roi_left)
            
            # Calculate net area
            gross_area = np.sum(peak_counts)
            bg_area = np.sum(bg_values)
            net_area = gross_area - bg_area
            
            # Background line (dashed gray)
            fig.add_trace(go.Scatter(
                x=peak_channels,
                y=bg_values,
                mode='lines',
                name='Pozadí',
                line=dict(color='gray', width=2, dash='dash'),
                hoverinfo='skip'
            ))
            
            # Yellow fill for net area - background trace first, then spectrum with fill
            fig.add_trace(go.Scatter(
                x=peak_channels,
                y=bg_values,
                mode='lines',
                line=dict(width=0),
                showlegend=False,
                hoverinfo='skip'
            ))
            
            fig.add_trace(go.Scatter(
                x=peak_channels,
                y=peak_counts,
                mode='lines',
                fill='tonexty',
                fillcolor='rgba(255, 215, 0, 0.5)',
                line=dict(width=0),
                name=f'Net: {net_area:.0f}',
                hoverinfo='skip'
            ))
            
            # Update live text
            live_text = f"Net area: {net_area:.0f} | CH: {peak_roi_left}-{peak_roi_right}"
        
        # Check if we have peak analysis results from separate 186 analysis
        # Priority: result_186 (from separate callback) > results['ra_peak_186']
        peak_analysis = result_186 if result_186 is not None else (results.get('ra_peak_186') if results else None)
        
        if peak_analysis is not None:
            # Show activity from analysis
            activity = peak_analysis.get('activity', 0)
            uncertainty = peak_analysis.get('uncertainty', 0)
            net_area_result = peak_analysis.get('net_area_sample', net_area)
            peak_channel = peak_analysis.get('peak_channel_sample', (peak_roi_left + peak_roi_right) // 2)
            
            # Peak marker (red dotted line)
            fig.add_trace(go.Scatter(
                x=[peak_channel, peak_channel],
                y=[y_min, y_max],
                mode='lines',
                name=f'Pík @ CH {peak_channel}',
                line=dict(color='red', width=2, dash='dot'),
                hoverinfo='skip'
            ))
            
            # Activity annotation
            fig.add_annotation(
                x=peak_channel,
                y=y_max * 0.85,
                text=f'Ra₁₈₆: {activity:.1f}±{uncertainty:.1f} Bq',
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowcolor='red',
                font=dict(size=10, color='red'),
                bgcolor='rgba(255,255,255,0.8)',
                bordercolor='red',
                borderwidth=1
            )
            
            live_text = f"Net area: {net_area_result:.0f} | Ra₁₈₆: {activity:.1f}±{uncertainty:.1f} Bq"
        
        # Add static vertical lines for peak ROI boundaries (orange)
        shapes = [
            # Left peak boundary
            dict(
                type='line',
                x0=peak_roi_left, x1=peak_roi_left,
                y0=y_min, y1=y_max,
                line=dict(color='orange', width=2, dash='solid')
            ),
            # Right peak boundary
            dict(
                type='line',
                x0=peak_roi_right, x1=peak_roi_right,
                y0=y_min, y1=y_max,
                line=dict(color='orange', width=2, dash='solid')
            )
        ]
        
        # Configure layout
        fig.update_layout(
            template='plotly_white',
            margin=dict(t=30, b=40, l=50, r=20),
            xaxis=dict(
                title='Kanál',
                range=[roi_min - 2, roi_max + 2]
            ),
            yaxis=dict(
                title='Počty',
                range=[y_min, y_max]
            ),
            showlegend=False,  # No legend needed - simple graph
            hovermode='x unified',
            shapes=shapes,
            dragmode='pan'
        )
        
        return fig, live_text
