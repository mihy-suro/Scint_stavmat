"""
Calibration callbacks - manual peak calibration and calibration plot
"""

from .utils import *
from dash import callback_context


def register_calibration_callbacks(app):
    """Register manual calibration callbacks"""
    
    # ==================== SYNC UI TO STORE ====================
    @app.callback(
        Output('current-sample-calib', 'data'),
        [Input('manual-a0', 'value'),
         Input('manual-a1', 'value'),
         Input('manual-a2', 'value')]
    )
    def sync_sample_calibration(a0, a1, a2):
        """Sync UI fields to store - any change updates sample calib"""
        if a0 is None or a1 is None:
            raise PreventUpdate
        return {'a0': a0, 'a1': a1, 'a2': a2 or 0}
    
    
    # ==================== MANUAL PEAK CALIBRATION ====================
    @app.callback(
        [Output('peak-calibration-data', 'data'),
         Output('select-e-186', 'color'),
         Output('select-e-238', 'color'),
         Output('select-e-295', 'color'),
         Output('select-e-352', 'color'),
         Output('select-e-609', 'color'),
         Output('select-e-1461', 'color'),
         Output('select-e-1764', 'color'),
         Output('select-e-2614', 'color')],
        [Input('spectrum-plot-full', 'clickData'),
         Input('select-e-186', 'n_clicks'),
         Input('select-e-238', 'n_clicks'),
         Input('select-e-295', 'n_clicks'),
         Input('select-e-352', 'n_clicks'),
         Input('select-e-609', 'n_clicks'),
         Input('select-e-1461', 'n_clicks'),
         Input('select-e-1764', 'n_clicks'),
         Input('select-e-2614', 'n_clicks')],
        [State('peak-calibration-data', 'data'),
         State('sample-selector', 'value'),
         State('excel-data', 'data'),
         State('current-sample-calib', 'data')]
    )
    def handle_peak_calibration(click_data, n186, n238, n295, n352, n609, n1461, n1764, n2614, calib_data, selected_sample, excel_data, current_sample_calib):
        """Handle energy selection and graph clicks for manual calibration"""
        if not callback_context.triggered:
            raise PreventUpdate
        
        trigger_id = callback_context.triggered[0]['prop_id'].split('.')[0]
        
        # Initialize
        if calib_data is None:
            calib_data = {'peaks': {}, 'active_energy': None}
        
        # Default button colors
        colors = ['light', 'light', 'light', 'light', 'light', 'light', 'light', 'light']
        energy_list = ['186', '238', '295', '352', '609', '1461', '1764', '2614']
        
        # Mark assigned energies as success (green)
        for i, e in enumerate(energy_list):
            if calib_data.get('peaks', {}).get(e, '-') != '-':
                colors[i] = 'success'
        
        # Highlight active energy as primary (blue)
        if calib_data.get('active_energy'):
            idx = energy_list.index(calib_data['active_energy'])
            colors[idx] = 'primary'
        
        # Handle energy button clicks - activate energy
        if trigger_id in ENERGY_MAP:
            energy = ENERGY_MAP[trigger_id]
            calib_data['active_energy'] = energy
            idx = energy_list.index(energy)
            colors[idx] = 'primary'
            print(f"Energy {energy} keV activated - click peak in graph")
            return calib_data, *colors
        
        # Handle graph click - assign channel to active energy
        if trigger_id == 'spectrum-plot-full' and click_data and calib_data.get('active_energy'):
            # CHANNEL-CENTRIC: X is now channel (not energy)
            channel_clicked = int(click_data['points'][0]['x'])
            
            # Get approximate energy from customdata for display
            if 'customdata' in click_data['points'][0]:
                energy_approx = click_data['points'][0]['customdata']
            else:
                energy_approx = 0  # Fallback
            
            energy = calib_data['active_energy']
            calib_data['peaks'][energy] = channel_clicked
            
            print(f"✓ {energy} keV → Channel {channel_clicked} (approx. {energy_approx:.1f} keV)")
            
            # Mark current energy as success (green)
            current_idx = energy_list.index(energy)
            colors[current_idx] = 'success'
            
            # Auto-advance to next unassigned energy
            next_energy_found = False
            for i, e in enumerate(energy_list):
                if calib_data['peaks'].get(e, '-') == '-':
                    # Found next unassigned energy - activate it
                    calib_data['active_energy'] = e
                    colors[i] = 'primary'
                    next_energy_found = True
                    print(f"→ Auto-switched to {e} keV")
                    break
            
            # If all energies assigned, deactivate
            if not next_energy_found:
                calib_data['active_energy'] = None
                print("✓ All peaks assigned!")
            
            return calib_data, *colors
        
        return calib_data, *colors
        
        return calib_data, *colors
    
    
    @app.callback(
        [Output('peak-ch-186', 'children'),
         Output('peak-ch-238', 'children'),
         Output('peak-ch-295', 'children'),
         Output('peak-ch-352', 'children'),
         Output('peak-ch-609', 'children'),
         Output('peak-ch-1461', 'children'),
         Output('peak-ch-1764', 'children'),
         Output('peak-ch-2614', 'children'),
         Output('calculate-calibration', 'disabled')],
        Input('peak-calibration-data', 'data')
    )
    def update_peak_displays(calib_data):
        """Update channel displays in table"""
        if not calib_data or 'peaks' not in calib_data:
            return "-", "-", "-", "-", "-", "-", "-", "-", True
        
        peaks = calib_data['peaks']
        values = [peaks.get(e, '-') for e in ['186', '238', '295', '352', '609', '1461', '1764', '2614']]
        
        # Enable calculate button if at least 2 peaks defined
        num_peaks = sum(1 for v in values if v != '-')
        disabled = num_peaks < 2
        
        return *values, disabled
    
    
    @app.callback(
        Output('calibration-fit-plot', 'figure'),
        [Input('peak-calibration-data', 'data'),
         Input('current-sample-calib', 'data')]
    )
    def plot_calibration_fit(calib_data, current_sample_calib):
        """Plot active calibration - shows manual peaks if available, otherwise just the active equation"""
        fig = go.Figure()
        
        if not current_sample_calib:
            raise PreventUpdate
        
        a0 = current_sample_calib.get('a0', 9.6229)
        a1 = current_sample_calib.get('a1', 1.3793)
        a2 = current_sample_calib.get('a2', 0)
        
        # Determine which calibration is active
        has_manual_peaks = (calib_data and 'peaks' in calib_data and 
                           any(ch != '-' for ch in calib_data['peaks'].values()))
        
        # If manual calibration was done, show points + fit
        if has_manual_peaks:
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
            
            # Plot fit line using current calibration (linear or quadratic)
            ch_range = np.linspace(0, max(channels) * 1.1, 100)
            
            # Check if quadratic
            if abs(a2) > 1e-8:  # Quadratic
                e_fit = a0 + a1 * ch_range + a2 * ch_range**2
                fit_label = f'Manuální: E = {a0:.2f} + {a1:.4f}·CH + {a2:.6f}·CH²'
            else:  # Linear
                e_fit = a0 + a1 * ch_range
                fit_label = f'Manuální: E = {a0:.2f} + {a1:.4f}·CH'
            
            fig.add_trace(go.Scatter(
                x=ch_range,
                y=e_fit,
                mode='lines',
                name=fit_label,
                line=dict(color='blue', dash='dash', width=2)
            ))
            
            # Residuals (check if quadratic from a2 value)
            if abs(a2) > 1e-8:  # Quadratic
                fitted_e = a0 + a1 * channels + a2 * channels**2
            else:  # Linear
                fitted_e = a0 + a1 * channels
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
        
        # Otherwise, show current calibration (from Excel or optimized)
        elif a0 is not None and a1 is not None:
            ch_range = np.linspace(0, 2048, 100)
            
            # Check if quadratic
            if a2 is not None and abs(a2) > 1e-8:
                e_fit = a0 + a1 * ch_range + a2 * ch_range**2
                label = f'Aktuální: E = {a0:.2f} + {a1:.4f}·CH + {a2:.6f}·CH²'
            else:
                e_fit = a0 + a1 * ch_range
                label = f'Aktuální: E = {a0:.2f} + {a1:.4f}·CH'
            
            fig.add_trace(go.Scatter(
                x=ch_range,
                y=e_fit,
                mode='lines',
                name=label,
                line=dict(color='orange', dash='solid', width=2)
            ))
            
            title = "Aktivní kalibrace: Excel/Optimalizace/Manuální"
        
        else:
            # No calibration available
            fig.update_layout(
                xaxis_title="Kanál",
                yaxis_title="Energie (keV)",
                template='plotly_white'
            )
            return fig
        
        fig.update_layout(
            xaxis_title="Kanál",
            yaxis_title="Energie (keV)",
            hovermode='closest',
            template='plotly_white',
            legend=dict(
                orientation="h",
                yanchor="top",
                y=1.15,
                xanchor="left",
                x=0
            ),
            margin=dict(t=40, b=40, l=50, r=20)
        )
        
        return fig
    
    
    @app.callback(
        [Output('manual-a0', 'value', allow_duplicate=True),
         Output('manual-a1', 'value', allow_duplicate=True),
         Output('manual-a2', 'value', allow_duplicate=True),
         Output('ref-a0', 'value', allow_duplicate=True),
         Output('ref-a1', 'value', allow_duplicate=True),
         Output('ref-a2', 'value', allow_duplicate=True)],
        Input('calculate-calibration', 'n_clicks'),
        [State('peak-calibration-data', 'data'),
         State('polynomial-degree', 'value')],
        prevent_initial_call=True
    )
    def calculate_and_apply_calibration(n_clicks, calib_data, poly_degree):
        """Calculate calibration from selected peaks (linear or quadratic) and apply"""
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
        
        is_quadratic = poly_degree == 'quadratic'
        min_points = 3 if is_quadratic else 2
        
        if len(energies) < min_points:
            raise PreventUpdate
        
        # Fit: E = a0 + a1 * CH (+ a2 * CH^2 for quadratic)
        energies = np.array(energies)
        channels = np.array(channels)
        
        if is_quadratic:
            # Quadratic fit: E = a0 + a1*CH + a2*CH^2
            A = np.vstack([np.ones(len(channels)), channels, channels**2]).T
            coeffs = np.linalg.lstsq(A, energies, rcond=None)[0]
            a0, a1, a2 = coeffs[0], coeffs[1], coeffs[2]
            fitted = a0 + a1 * channels + a2 * channels**2
        else:
            # Linear fit: E = a0 + a1 * CH
            A = np.vstack([np.ones(len(channels)), channels]).T
            coeffs = np.linalg.lstsq(A, energies, rcond=None)[0]
            a0, a1, a2 = coeffs[0], coeffs[1], 0
            fitted = a0 + a1 * channels
        
        # Calculate residuals (for internal use only, not displayed)
        residuals = energies - fitted
        
        print(f"\n=== Manual calibration calculated ===")
        print(f"Polynomial degree: {'Quadratic' if is_quadratic else 'Linear'}")
        print(f"a₀ = {a0:.6f} keV")
        print(f"a₁ = {a1:.6f} keV/CH")
        if is_quadratic:
            print(f"a₂ = {a2:.9f} keV/CH²")
        print(f"Used {len(energies)} peaks, max residual error: {np.max(np.abs(residuals)):.2f} keV")
        
        # Update manual (visible) and ref (hidden) calibration with same values
        return a0, a1, a2, a0, a1, a2
    
    
    # ==================== RESET CALIBRATION ====================
    @app.callback(
        [Output('manual-a0', 'value', allow_duplicate=True),
         Output('manual-a1', 'value', allow_duplicate=True),
         Output('peak-calibration-data', 'data', allow_duplicate=True),
         Output('status-log', 'children', allow_duplicate=True)],
        Input('reset-calibration', 'n_clicks'),
        [State('ref-a0', 'value'),
         State('ref-a1', 'value')],
        prevent_initial_call=True
    )
    def reset_calibration(n_clicks, ref_a0, ref_a1):
        """Reset calibration to Excel values and clear manual calibration table"""
        print(f"\n=== Calibration reset to Excel values ===")
        print(f"a₀ = {ref_a0:.6f} keV")
        print(f"a₁ = {ref_a1:.6f} keV/CH")
        
        # Clear peak calibration data
        empty_calib_data = {'peaks': {}, 'active_energy': None}
        
        status_msg = html.Div([
            html.Small([
                html.I(className="fas fa-undo text-warning me-1"),
                "🔄 Kalibrace resetována na hodnoty z Excel"
            ], className="text-warning")
        ])
        
        return ref_a0, ref_a1, empty_calib_data, status_msg
    
    
    # ==================== POLYNOMIAL DEGREE TOGGLE ====================
    @app.callback(
        Output('a2-input-container', 'style'),
        Input('polynomial-degree', 'value')
    )
    def toggle_a2_input(degree):
        """Show/hide a2 input based on polynomial degree"""
        if degree == 'quadratic':
            return {'display': 'block'}
        else:
            return {'display': 'none'}
    
    
    # ==================== INDIVIDUAL PEAK RESET ====================
    @app.callback(
        Output('peak-calibration-data', 'data', allow_duplicate=True),
        [Input('reset-peak-186', 'n_clicks'),
         Input('reset-peak-238', 'n_clicks'),
         Input('reset-peak-295', 'n_clicks'),
         Input('reset-peak-352', 'n_clicks'),
         Input('reset-peak-609', 'n_clicks'),
         Input('reset-peak-1461', 'n_clicks'),
         Input('reset-peak-1764', 'n_clicks'),
         Input('reset-peak-2614', 'n_clicks')],
        State('peak-calibration-data', 'data'),
        prevent_initial_call=True
    )
    def reset_individual_peak(n186, n238, n295, n352, n609, n1461, n1764, n2614, calib_data):
        """Reset individual calibration peak when X button clicked"""
        if not callback_context.triggered:
            raise PreventUpdate
        
        trigger_id = callback_context.triggered[0]['prop_id'].split('.')[0]
        
        # Map reset button ID to energy
        reset_map = {
            'reset-peak-186': '186',
            'reset-peak-238': '238',
            'reset-peak-295': '295',
            'reset-peak-352': '352',
            'reset-peak-609': '609',
            'reset-peak-1461': '1461',
            'reset-peak-1764': '1764',
            'reset-peak-2614': '2614'
        }
        
        if trigger_id not in reset_map:
            raise PreventUpdate
        
        # Initialize if needed
        if calib_data is None:
            calib_data = {'peaks': {}, 'active_energy': None}
        
        # Remove the peak from data
        energy = reset_map[trigger_id]
        if 'peaks' in calib_data and energy in calib_data['peaks']:
            del calib_data['peaks'][energy]
            print(f"✓ Peak {energy} keV reset")
        
        # Clear active energy if it was the one we just reset
        if calib_data.get('active_energy') == energy:
            calib_data['active_energy'] = None
        
        return calib_data
    
    
    # ==================== RESET ALL PEAKS ====================
    @app.callback(
        [Output('peak-calibration-data', 'data', allow_duplicate=True),
         Output('status-log', 'children', allow_duplicate=True)],
        Input('reset-all-peaks', 'n_clicks'),
        prevent_initial_call=True
    )
    def reset_all_peaks(n_clicks):
        """Reset all calibration peaks"""
        if not n_clicks:
            raise PreventUpdate
        
        print("✓ All peaks reset")
        
        empty_calib_data = {'peaks': {}, 'active_energy': None}
        
        status_msg = html.Div([
            html.Small([
                html.I(className="fas fa-eraser text-warning me-1"),
                "🧹 Všechny kalibrační body smazány"
            ], className="text-warning")
        ])
        
        return empty_calib_data, status_msg
    
    
    # ==================== OPTIMIZATION SETTINGS TOGGLE ====================
    @app.callback(
        Output('optimization-settings-collapse', 'is_open'),
        Input('optimize-calibration', 'value')
    )
    def toggle_optimization_settings(optimize_value):
        """Show/hide optimization settings when optimization is enabled"""
        return 'optimize' in (optimize_value or [])


