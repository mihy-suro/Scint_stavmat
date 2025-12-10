"""
Analysis callbacks - main regression and activity calculation
"""

from .utils import *
from datetime import datetime


def register_analysis_callbacks(app):
    """Register analysis-related callbacks"""
    
    # ==================== AUTO-LOAD PREVIOUS RESULTS ====================
    @app.callback(
        Output('sample-results', 'data', allow_duplicate=True),
        Input('sample-selector', 'value'),
        State('accumulated-results', 'data'),
        prevent_initial_call=True
    )
    def load_previous_results_if_available(selected_sample, accumulated_results):
        """Load previous analysis results if returning to analyzed sample"""
        if not selected_sample or not accumulated_results:
            return None
        
        # Search for existing results
        for result in accumulated_results:
            if isinstance(result, dict) and result.get('sample_name') == selected_sample:
                return result  # Load previous analysis
        
        # No previous analysis found - return None to clear results
        return None
    
    # ==================== MAIN ANALYSIS ====================
    @app.callback(
        [Output('sample-results', 'data'),
         Output('accumulated-results', 'data', allow_duplicate=True),
         Output('manual-a0', 'value', allow_duplicate=True),
         Output('manual-a1', 'value', allow_duplicate=True),
         Output('manual-a2', 'value', allow_duplicate=True),
         Output('status-log', 'children', allow_duplicate=True),
         Output('run-analysis', 'children', allow_duplicate=True),
         Output('run-analysis', 'color', allow_duplicate=True)],
        Input('run-analysis', 'n_clicks'),
        [State('excel-data', 'data'),
         State('sample-selector', 'value'),
         State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value'),
         State('current-sample-calib', 'data'),
         State('polynomial-degree', 'value'),
         State('optimize-calibration', 'value'),
         State('optimization-method', 'value'),
         State('max-iterations', 'value'),
         State('regression-method', 'value'),
         State('accumulated-results', 'data'),
         State('roi1-range', 'data'),
         State('roi2-range', 'data'),
         State('k-source-roi', 'data')],
        prevent_initial_call=True
    )
    def run_analysis(n_clicks, data, selected_sample, ref_a0, ref_a1, ref_a2,
                     current_sample_calib, poly_degree,
                     optimize_value, opt_method, max_iter, regression_method, accumulated_results,
                     roi1_range, roi2_range, k_source_roi):
        """Run analysis for selected sample"""
        if data is None or selected_sample is None:
            raise PreventUpdate
        
        try:
            # Reference channel mapping (identity mapping for reference detector)
            ref_mapping = [0.0, 1.0]  # ch_ref = 0.0 + 1.0 * ch_sample (identity)
            
            # Display calibration for approximate energy display
            display_calib = [ref_a0, ref_a1, ref_a2]
            
            # ROI analysis always enabled - validate ROI ranges (now in channels)
            use_roi = roi1_range and roi2_range
            if use_roi:
                # Validate ROI ranges
                if None in roi1_range or None in roi2_range:
                    use_roi = False
            
            # Default K source if not set
            if not k_source_roi:
                k_source_roi = 'roi1'
            
            # Use shared analysis function
            results, calib_method, opt_info, channel_mapping = analyze_single_sample(
                selected_sample, data, ref_mapping, current_sample_calib,
                poly_degree, optimize_value, opt_method,
                max_iter, regression_method,
                roi1_range=roi1_range if use_roi else None,
                roi2_range=roi2_range if use_roi else None,
                enable_roi=use_roi,
                k_source_roi=k_source_roi
            )
            
            # Add to accumulated results
            if accumulated_results is None:
                accumulated_results = []
            
            # Check if sample already in accumulated results, if so replace it
            existing_idx = None
            for idx, res in enumerate(accumulated_results):
                # Safety check - ensure res is a dict with sample_name
                if isinstance(res, dict) and 'sample_name' in res:
                    if res['sample_name'] == selected_sample:
                        existing_idx = idx
                        break
            
            if existing_idx is not None:
                accumulated_results[existing_idx] = results
            else:
                accumulated_results.append(results)
            
            # Build status message
            status_lines = [
                html.I(className="fas fa-check-circle text-success me-1"),
                f"✅ Analýza dokončena: {selected_sample}",
                html.Br(),
                f"Kalibrace: {calib_method}",
                html.Br(),
                f"Metoda: {regression_method}"
            ]
            
            if use_roi:
                # Calculate approximate energy for display
                roi1_energy_min = display_calib[0] + display_calib[1] * roi1_range[0]
                roi1_energy_max = display_calib[0] + display_calib[1] * roi1_range[1]
                roi2_energy_min = display_calib[0] + display_calib[1] * roi2_range[0]
                roi2_energy_max = display_calib[0] + display_calib[1] * roi2_range[1]
                
                status_lines.extend([
                    html.Br(),
                    f"🎯 ROI #1: ch {roi1_range[0]:.0f}-{roi1_range[1]:.0f} (~{roi1_energy_min:.0f}-{roi1_energy_max:.0f} keV, Ra/Th)",
                    html.Br(),
                    f"🎯 ROI #2: ch {roi2_range[0]:.0f}-{roi2_range[1]:.0f} (~{roi2_energy_min:.0f}-{roi2_energy_max:.0f} keV, K-40)"
                ])
            
            if opt_info:
                status_lines.extend([html.Br(), opt_info])
            
            status_msg = html.Div([
                html.Small(status_lines, className="text-success")
            ])
            
            # If optimization was used, return channel mapping values
            # NOTE: Manual calibration inputs are kept for backward compatibility with UI
            # but store actual channel mapping in results
            is_optimizing = 'optimize' in optimize_value
            if is_optimizing:
                # Return mapping values (a0=0, a1=actual, a2=0 for display)
                return results, accumulated_results, 0.0, channel_mapping[1], 0.0, status_msg, [html.I(className="fas fa-check me-2"), "Hotovo!"], 'success'
            else:
                return results, accumulated_results, no_update, no_update, no_update, status_msg, [html.I(className="fas fa-check me-2"), "Hotovo!"], 'success'
            
        except Exception as e:
            print(f"\n!!! ERROR in analysis: {str(e)} !!!")
            import traceback
            traceback.print_exc()
            
            error_msg = html.Div([
                html.Small([
                    html.I(className="fas fa-exclamation-triangle text-danger me-1"),
                    f"❌ Chyba: {str(e)}"
                ], className="text-danger")
            ])
            
            return None, no_update, no_update, no_update, no_update, error_msg, [html.I(className="fas fa-times me-2"), "Chyba"], 'danger'
    
    
    # ==================== SAMPLE SELECTOR - AUTO, NEXT & PREVIOUS ====================
    @app.callback(
        [Output('sample-selector', 'value'),
         Output('status-log', 'children', allow_duplicate=True),
         Output('run-analysis', 'children', allow_duplicate=True),
         Output('run-analysis', 'color', allow_duplicate=True)],
        [Input('sample-selector', 'options'),
         Input('next-sample-button', 'n_clicks'),
         Input('previous-sample-button', 'n_clicks')],
        [State('sample-selector', 'value'),
         State('excel-data', 'data')],
        prevent_initial_call=True
    )
    def handle_sample_selection(sample_options, next_clicks, prev_clicks, current_sample, excel_data):
        """Handle auto-selection of first sample, next button, and previous button clicks"""
        ctx = callback_context
        
        if not ctx.triggered:
            raise PreventUpdate
        
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        # Reset button to default state
        button_content = [html.I(className="fas fa-play me-2"), "Analyzovat"]
        button_color = 'primary'
        
        # Case 1: Options changed (new data loaded) - select first sample
        if trigger_id == 'sample-selector':
            if not sample_options:
                return None, no_update, no_update, no_update
            
            selected = sample_options[0]['value']
            
            # Show sample info
            if excel_data and selected:
                idx = excel_data['sample_names'].index(selected)
                live_time = excel_data['sample_live_times'][idx]
                
                status_msg = html.Div([
                    html.Small([
                        html.I(className="fas fa-vial text-info me-1"),
                        f"🔬 Vzorek načten: {selected}",
                        html.Br(),
                        f"Live time: {live_time:.1f} s"
                    ], className="text-info")
                ])
                
                return selected, status_msg, button_content, button_color
            
            return selected, no_update, button_content, button_color
        
        # Case 2: Next button clicked - move to next sample
        elif trigger_id == 'next-sample-button':
            if not sample_options or not current_sample:
                raise PreventUpdate
            
            # Find current sample index
            sample_values = [opt['value'] for opt in sample_options]
            try:
                current_idx = sample_values.index(current_sample)
            except ValueError:
                raise PreventUpdate
            
            # Check if there's a next sample
            if current_idx >= len(sample_values) - 1:
                status_msg = html.Div([
                    html.Small([
                        html.I(className="fas fa-info-circle text-info me-1"),
                        "ℹ️ Již jste na posledním vzorku"
                    ], className="text-info")
                ])
                return no_update, status_msg, no_update, no_update
            
            # Get next sample
            next_sample = sample_values[current_idx + 1]
            total_samples = len(sample_values)
            
            print(f"\n=== NEXT SAMPLE: [{current_idx + 2}/{total_samples}] {next_sample} ===")
            
            status_msg = html.Div([
                html.Small([
                    html.I(className="fas fa-arrow-right text-primary me-1"),
                    f"➡️ Načten vzorek {current_idx + 2}/{total_samples}: {next_sample}",
                    html.Br(),
                    "Klikněte 'Analyzovat' pro zpracování"
                ], className="text-primary")
            ])
            
            return next_sample, status_msg, button_content, button_color
        
        # Case 3: Previous button clicked - move to previous sample
        elif trigger_id == 'previous-sample-button':
            if not sample_options or not current_sample:
                raise PreventUpdate
            
            # Find current sample index
            sample_values = [opt['value'] for opt in sample_options]
            try:
                current_idx = sample_values.index(current_sample)
            except ValueError:
                raise PreventUpdate
            
            # Check if there's a previous sample
            if current_idx == 0:
                status_msg = html.Div([
                    html.Small([
                        html.I(className="fas fa-info-circle text-info me-1"),
                        "ℹ️ Již jste na prvním vzorku"
                    ], className="text-info")
                ])
                return no_update, status_msg, no_update, no_update
            
            # Get previous sample
            prev_sample = sample_values[current_idx - 1]
            total_samples = len(sample_values)
            
            print(f"\n=== PREVIOUS SAMPLE: [{current_idx}/{total_samples}] {prev_sample} ===")
            
            status_msg = html.Div([
                html.Small([
                    html.I(className="fas fa-arrow-left text-primary me-1"),
                    f"⬅️ Načten vzorek {current_idx}/{total_samples}: {prev_sample}",
                    html.Br(),
                    "Klikněte 'Analyzovat' pro zpracování"
                ], className="text-primary")
            ])
            
            return prev_sample, status_msg, button_content, button_color
        
        raise PreventUpdate


def analyze_single_sample(sample_name, excel_data, ref_calib, current_sample_calib, 
                          poly_degree, optimize_value, opt_method, 
                          max_iter, regression_method, roi1_range=None, roi2_range=None, enable_roi=False, k_source_roi='roi1'):
    """
    Analyze a single sample - extracted logic for reuse in batch processing
    
    Args:
        roi1_range: [min_keV, max_keV] for Ra/Th region (optional)
        roi2_range: [min_keV, max_keV] for K-40 region (optional)
        enable_roi: Boolean to enable dual ROI analysis
        k_source_roi: 'roi1' or 'roi2' - which ROI to use for K coefficient in final results
    
    Returns:
        dict: Analysis results or None if error
        str: Calibration method description
        str: Optimization info (or None)
        list: Sample calibration coefficients [a0, a1, a2]
    """
    
    # Convert data back to DataFrames
    calib_df = pd.DataFrame(excel_data['calibration'])
    sample_df = pd.DataFrame(excel_data['samples'])
    
    sample_idx = excel_data['sample_names'].index(sample_name)
    sample_live_time = excel_data['sample_live_times'][sample_idx]
    
    # DIAGNOSTICS: Print pairing information
    print(f"\n{'='*60}")
    print(f"📊 SAMPLE PAIRING CHECK:")
    print(f"{'='*60}")
    print(f"Sample name: {sample_name}")
    print(f"Sample index in list: {sample_idx}")
    print(f"Live time from list: {sample_live_time:.2f} s")
    print(f"All samples in data: {excel_data['sample_names']}")
    print(f"All live times: {[f'{lt:.2f}' for lt in excel_data['sample_live_times']]}")
    print(f"Columns in sample_df: {list(sample_df.columns)}")
    if sample_name in sample_df.columns:
        sample_total_counts = sample_df[sample_name].sum()
        print(f"Total counts in spectrum: {sample_total_counts:.0f}")
    else:
        print(f"⚠️ WARNING: {sample_name} NOT FOUND in sample_df columns!")
    print(f"{'='*60}\n")
    
    # Note: Calibration spectra are already normalized to CPS/Bq in data_loading.py
    # No additional normalization needed here - coefficients will directly give Bq
    
    # Get raw sample spectrum (in counts)
    sample_spectrum_counts = sample_df[sample_name].values
    
    # Create CPS version for regression calculations
    sample_df_norm = sample_df.copy()
    if sample_live_time > 0:
        sample_df_norm[sample_name] = sample_df[sample_name] / sample_live_time
    else:
        sample_df_norm[sample_name] = 0
    
    # Get sample spectrum in CPS (use for regression - matches calibration units)
    sample_spectrum = sample_df_norm[sample_name].values
    
    # CHANNEL-CENTRIC: Helper function now creates channel mask (much simpler!)
    from .utils import create_channel_mask
    
    # Create ROI masks early if needed for optimization
    optimization_roi_channels = None
    if enable_roi and roi1_range and roi2_range:
        # ROI ranges are now DIRECTLY in channels (no energy conversion needed!)
        # For optimization with dual ROI: combine both ROI regions (union)
        mask_roi1 = create_channel_mask(roi1_range, len(sample_spectrum))
        mask_roi2 = create_channel_mask(roi2_range, len(sample_spectrum))
        optimization_roi_mask = mask_roi1 | mask_roi2  # Union of both ROIs
        # Also store channel range for optimization function
        optimization_roi_channels = [
            min(roi1_range[0], roi2_range[0]),
            max(roi1_range[1], roi2_range[1])
        ]
    
    # CHANNEL-CENTRIC: Calibration is now channel mapping, not energy calibration
    is_optimizing = 'optimize' in optimize_value
    
    # Get initial channel mapping (identity by default)
    # Note: poly_degree is ignored in channel-centric (always linear mapping)
    initial_channel_mapping = [
        current_sample_calib.get('ch_a0', 0.0),  # Channel offset
        current_sample_calib.get('ch_a1', 1.0)   # Gain ratio
    ]
    
    # CHANNEL-CENTRIC: Optimization now finds channel mapping, not energy calibration
    if is_optimizing:
        # Import channel-centric optimization function
        from scripts.utils import find_optimal_channel_mapping, rebin_channels
        
        # Optimize channel mapping
        channel_mapping, opt_result = find_optimal_channel_mapping(
            calib_df[["Ra", "K", "Th"]].values,
            sample_spectrum,
            initial_channel_mapping,
            roi_channels=optimization_roi_channels,
            method=opt_method or 'L-BFGS-B',
            maxiter=max_iter or 1000
        )
        
        calib_method = f"Opt: ch_offset={channel_mapping[0]:.2f}, gain={channel_mapping[1]:.4f}"
        opt_info = f"{opt_result['method']}, iter={opt_result['iterations']}, R²={opt_result['final_r2']:.6f}"
    else:
        from scripts.utils import rebin_channels
        channel_mapping = initial_channel_mapping
        opt_info = None
        calib_method = f"ch_offset={channel_mapping[0]:.2f}, gain={channel_mapping[1]:.4f}"
    
    # DIAGNOSTICS: Check sample spectrum before rebinning
    print(f"\n🔍 REBINNING DIAGNOSTICS (Channel-Centric):")
    print(f"Sample spectrum BEFORE rebin:")
    print(f"  Sum (total CPS): {sample_spectrum.sum():.2f}")
    print(f"  Mean CPS/channel: {sample_spectrum.mean():.4f}")
    print(f"  Max CPS: {sample_spectrum.max():.2f}")
    
    # Check channel mapping
    print(f"\nChannel mapping:")
    print(f"  Ref:    ch_offset=0.0, gain=1.0 (identity)")
    print(f"  Sample: ch_offset={channel_mapping[0]:.2f}, gain={channel_mapping[1]:.4f}")
    print(f"  Interpretation: ref_ch = {channel_mapping[0]:.2f} + {channel_mapping[1]:.4f} × sample_ch")
    
    # CHANNEL-CENTRIC: Rebin using channel mapping (not energy calibration!)
    sample_rebinned = rebin_channels(channel_mapping, sample_spectrum, n_ref_channels=len(calib_df))
    
    # Also rebin the counts version for display
    sample_rebinned_counts = rebin_channels(channel_mapping, sample_spectrum_counts, n_ref_channels=len(calib_df))
    
    print(f"Sample spectrum AFTER rebin:")
    print(f"  Sum (total CPS): {sample_rebinned.sum():.2f}")
    print(f"  Mean CPS/channel: {sample_rebinned.mean():.4f}")
    print(f"  Max CPS: {sample_rebinned.max():.2f}")
    print(f"  Conservation ratio: {sample_rebinned.sum() / sample_spectrum.sum():.6f}")
    if abs(sample_rebinned.sum() / sample_spectrum.sum() - 1.0) < 0.01:
        print(f"  ✅ Conserved")
    else:
        print(f"  ❌ NOT CONSERVED!")
    
    print(f"\nSample spectrum AFTER rebin (COUNTS for display):")
    print(f"  Sum (total counts): {sample_rebinned_counts.sum():.0f}")
    print(f"  Mean counts/channel: {sample_rebinned_counts.mean():.4f}")
    print(f"  Max counts: {sample_rebinned_counts.max():.0f}")
    
    print(f"\nSample spectrum AFTER rebin (COUNTS for display):")
    print(f"  Sum (total counts): {sample_rebinned_counts.sum():.0f}")
    print(f"  Mean counts/channel: {sample_rebinned_counts.mean():.4f}")
    print(f"  Max counts: {sample_rebinned_counts.max():.0f}")
    
    # Build predictor matrix - include background if available
    has_background = 'BG' in calib_df.columns
    if has_background:
        X = calib_df[["Ra", "K", "Th", "BG"]].values
        component_names = ['Ra', 'K', 'Th', 'BG']
    else:
        X = calib_df[["Ra", "K", "Th"]].values
        component_names = ['Ra', 'K', 'Th']
    
    # Check calibration matrix
    print(f"\nCalibration matrix X (first 3 channels):")
    print(f"  Ra: {X[:3, 0]}")
    print(f"  K:  {X[:3, 1]}")  
    print(f"  Th: {X[:3, 2]}")
    if has_background:
        print(f"  BG: {X[:3, 3]}")
    print(f"  Sum of Ra calibration: {X[:, 0].sum():.6e}")
    print(f"  Sum of K calibration: {X[:, 1].sum():.6e}")
    print(f"  Sum of Th calibration: {X[:, 2].sum():.6e}")
    if has_background:
        print(f"  Sum of BG calibration: {X[:, 3].sum():.6e}")
    
    # Run regression - either dual ROI or standard
    if enable_roi and roi1_range and roi2_range:
        print(f"\n{'='*60}")
        print(f"DUAL ROI ANALYSIS (Channel-Centric)")
        print(f"{'='*60}")
        print(f"ROI #1 (Ra/Th): channels {roi1_range[0]}-{roi1_range[1]}")
        print(f"ROI #2 (K-40):  channels {roi2_range[0]}-{roi2_range[1]}")
        
        # CHANNEL-CENTRIC: Region 1 - Create channel mask (no energy conversion!)
        mask_roi1 = create_channel_mask(roi1_range, len(sample_rebinned))
        X_roi1 = X.copy()
        y_roi1 = sample_rebinned.copy()
        X_roi1[~mask_roi1] = 0
        y_roi1[~mask_roi1] = 0
        
        print(f"\n→ Fitting ROI #1 ({np.sum(mask_roi1)} channels)...")
        
        # Fit on ROI1
        if regression_method == 'OLS':
            results_roi1 = compile_results_dynamic(X_roi1, y_roi1, "OLS", ols, component_names)
        else:
            results_roi1 = compile_results_dynamic(X_roi1, y_roi1, "NNLS", 
                                          lambda X, y: nnls_detailed(X, y, num_bootstrap=50), component_names)
        
        ra_coeff = results_roi1['Coefficients']['Ra']
        th_coeff = results_roi1['Coefficients']['Th']
        k_coeff_roi1 = results_roi1['Coefficients']['K']
        
        print(f"  Ra: {ra_coeff:.2e}, K: {k_coeff_roi1:.2e}, Th: {th_coeff:.2e}")
        
        # CHANNEL-CENTRIC: Region 2 - Create channel mask
        mask_roi2 = create_channel_mask(roi2_range, len(sample_rebinned))
        X_roi2 = X.copy()
        y_roi2 = sample_rebinned.copy()
        X_roi2[~mask_roi2] = 0
        y_roi2[~mask_roi2] = 0
        
        print(f"\n→ Fitting ROI #2 ({np.sum(mask_roi2)} channels)...")
        
        # Fit on ROI2
        if regression_method == 'OLS':
            results_roi2 = compile_results_dynamic(X_roi2, y_roi2, "OLS", ols, component_names)
        else:
            results_roi2 = compile_results_dynamic(X_roi2, y_roi2, "NNLS", 
                                          lambda X, y: nnls_detailed(X, y, num_bootstrap=50), component_names)
        
        k_coeff_roi2 = results_roi2['Coefficients']['K']
        ra_roi2 = results_roi2['Coefficients']['Ra']
        th_roi2 = results_roi2['Coefficients']['Th']
        
        print(f"  Ra: {ra_roi2:.2e}, K: {k_coeff_roi2:.2e}, Th: {th_roi2:.2e}")
        
        # Select K coefficient based on k_source_roi
        print(f"\n→ Merging coefficients...")
        if k_source_roi == 'roi2':
            k_coeff = k_coeff_roi2
            print(f"  Using K from ROI #2: {k_coeff:.2e}")
        else:  # roi1 or default
            k_coeff = k_coeff_roi1
            print(f"  Using K from ROI #1: {k_coeff:.2e}")
        
        # Merge coefficients: Ra, Th from ROI1; K from selected ROI; BG average from both ROIs
        if has_background:
            bg_coeff = (results_roi1['Coefficients']['BG'] + results_roi2['Coefficients']['BG']) / 2
            merged_coeffs = np.array([ra_coeff, k_coeff, th_coeff, bg_coeff])
            print(f"  BG (averaged): {bg_coeff:.2e}")
        else:
            merged_coeffs = np.array([ra_coeff, k_coeff, th_coeff])
        
        # Calculate full fitted spectrum using merged coefficients
        fitted_spectrum = X @ merged_coeffs
        
        # Calculate global R² on FULL spectrum
        ss_res = np.sum((sample_rebinned - fitted_spectrum)**2)
        ss_tot = np.sum((sample_rebinned - np.mean(sample_rebinned))**2)
        r2_global = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        n, p = X.shape
        r2_adj = 1 - (1 - r2_global) * (n - 1) / (n - p) if n > p else r2_global
        
        # Package merged results (BG coefficient NOT included in Coefficients - only used for fitting)
        results_method = {
            "Method": f"{regression_method} (ROI dual)",
            "Coefficients": {'Ra': ra_coeff, 'K': k_coeff, 'Th': th_coeff},  # BG excluded from results
            "Std Errors": {
                'Ra': results_roi1['Std Errors']['Ra'],
                'K': results_roi2['Std Errors']['K'] if k_source_roi == 'roi2' else results_roi1['Std Errors']['K'],
                'Th': results_roi1['Std Errors']['Th']
            },
            "P Values": {'Ra': 0, 'K': 0, 'Th': 0},
            "R^2": r2_global,
            "Adjusted R^2": r2_adj
        }
        
        print(f"\n→ Final merged coefficients:")
        print(f"  Ra: {ra_coeff:.2e} (from ROI1)")
        print(f"  K:  {k_coeff:.2e} (from {'ROI2' if k_source_roi == 'roi2' else 'ROI1'})")
        print(f"  Th: {th_coeff:.2e} (from ROI1)")
        print(f"  Global R²: {r2_global:.6f}")
        print(f"{'='*60}\n")
        
        # Store ROI-specific fitted spectra using INDEPENDENT coefficients from each ROI fit
        # These are in CPS, convert to counts for display
        if has_background:
            roi1_fitted_cps = X_roi1 @ np.array([
                results_roi1['Coefficients']['Ra'],
                results_roi1['Coefficients']['K'],
                results_roi1['Coefficients']['Th'],
                results_roi1['Coefficients']['BG']
            ])
            roi2_fitted_cps = X_roi2 @ np.array([
                results_roi2['Coefficients']['Ra'],
                results_roi2['Coefficients']['K'],
                results_roi2['Coefficients']['Th'],
                results_roi2['Coefficients']['BG']
            ])
        else:
            roi1_fitted_cps = X_roi1 @ np.array([
                results_roi1['Coefficients']['Ra'],
                results_roi1['Coefficients']['K'],
                results_roi1['Coefficients']['Th']
            ])
            roi2_fitted_cps = X_roi2 @ np.array([
                results_roi2['Coefficients']['Ra'],
                results_roi2['Coefficients']['K'],
                results_roi2['Coefficients']['Th']
            ])
        roi1_fitted = roi1_fitted_cps * sample_live_time
        roi2_fitted = roi2_fitted_cps * sample_live_time
        
        # Store component contributions using INDEPENDENT coefficients from each ROI fit
        # Use ORIGINAL matrix X (not masked) for full spectrum component coverage
        # Convert to counts for display
        roi1_components_data = {
            'Ra': (X[:, 0] * results_roi1['Coefficients']['Ra'] * sample_live_time).tolist(),
            'K': (X[:, 1] * results_roi1['Coefficients']['K'] * sample_live_time).tolist(),
            'Th': (X[:, 2] * results_roi1['Coefficients']['Th'] * sample_live_time).tolist(),
            'mask': mask_roi1.tolist()  # Store mask for ROI1 range
        }
        roi2_components_data = {
            'Ra': (X[:, 0] * results_roi2['Coefficients']['Ra'] * sample_live_time).tolist(),
            'K': (X[:, 1] * results_roi2['Coefficients']['K'] * sample_live_time).tolist(),
            'Th': (X[:, 2] * results_roi2['Coefficients']['Th'] * sample_live_time).tolist(),
            'mask': mask_roi2.tolist()  # Store mask for ROI2 range
        }
        
        # Add background components if available
        if has_background:
            roi1_components_data['BG'] = (X[:, 3] * results_roi1['Coefficients']['BG'] * sample_live_time).tolist()
            roi2_components_data['BG'] = (X[:, 3] * results_roi2['Coefficients']['BG'] * sample_live_time).tolist()
        
    else:
        # Standard single regression
        if regression_method == 'OLS':
            results_method = compile_results_dynamic(X, sample_rebinned, "OLS", ols, component_names)
        else:
            results_method = compile_results_dynamic(X, sample_rebinned, "NNLS", 
                                          lambda X, y: nnls_detailed(X, y, num_bootstrap=100), component_names)
        
        # Calculate fitted spectrum (in CPS from regression)
        fitted_spectrum_cps = X @ np.array(list(results_method['Coefficients'].values()))
        
        # Convert to counts for display
        fitted_spectrum = fitted_spectrum_cps * sample_live_time
        
        # Initialize empty ROI data for non-ROI mode
        roi1_fitted = []
        roi2_fitted = []
        roi1_components_data = {}
        roi2_components_data = {}
    
    # Save raw coefficients - EXCLUDE BG from results (only Ra, K, Th reported as activities)
    raw_coeffs = {k: v for k, v in results_method['Coefficients'].items() if k != 'BG'}
    
    # Also remove BG from results_method Coefficients for consistency
    if has_background and 'BG' in results_method['Coefficients']:
        bg_coeff_for_fit = results_method['Coefficients'].pop('BG')  # Remove but save for logging
        if 'BG' in results_method['Std Errors']:
            results_method['Std Errors'].pop('BG')
        if 'BG' in results_method['P Values']:
            results_method['P Values'].pop('BG')
        print(f"\n📊 Background coefficient (used for fit, not reported): {bg_coeff_for_fit:.2e}")
    
    # Note: Coefficients are already in Bq because calibration spectra 
    # were normalized to CPS/Bq in data_loading.py
    # No conversion needed here
    
    # Store results
    results = {
        'sample_name': sample_name,
        'calibration': calib_df.to_dict('records'),
        'sample_spectrum': sample_rebinned_counts.tolist(),  # Store as counts for display
        'sample_rebinned': sample_rebinned_counts.tolist(),  # Store as counts for display
        'bg_names': [],
        'fitted_spectrum': fitted_spectrum.tolist(),
        'raw_coeffs': raw_coeffs,
        'results': results_method,
        'regression_method': regression_method,
        # CHANNEL-CENTRIC: Store channel mapping instead of energy calibration
        'channel_mapping': channel_mapping,  # [ch_offset, gain]
        'calib_method': calib_method,
        'roi_info': {
            'enabled': enable_roi,
            'roi1_range': roi1_range if enable_roi else None,  # Now in CHANNELS
            'roi2_range': roi2_range if enable_roi else None,  # Now in CHANNELS
            'roi1_components': ['Ra', 'Th'] if enable_roi else [],
            'roi2_components': ['K'] if enable_roi else [],
            'roi1_fitted': roi1_fitted.tolist() if enable_roi else [],
            'roi2_fitted': roi2_fitted.tolist() if enable_roi else [],
            'roi1_components_data': roi1_components_data if enable_roi else {},
            'roi2_components_data': roi2_components_data if enable_roi else {},
            'roi1_results': results_roi1 if enable_roi else None,
            'roi2_results': results_roi2 if enable_roi else None
        }
    }
    
    return results, calib_method, opt_info, channel_mapping
