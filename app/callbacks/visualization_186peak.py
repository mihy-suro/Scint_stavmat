"""
186 keV peak visualization - Ra-226 single peak analysis
"""

from .utils import *


def register_186peak_callbacks(app):
    """Register 186 keV peak visualization callbacks"""
    
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
