"""
Analysis callbacks - main regression and activity calculation
"""

import dash
from dash import html, no_update, callback_context
from dash.exceptions import PreventUpdate
from .utils import *
from datetime import datetime
import copy
import numpy as np
import pandas as pd

# Import analysis utilities
from utils import (
    prepare_sample_data,
    build_calibration_matrix,
    perform_single_regression,
    perform_dual_roi_regression,
    package_analysis_results,
    optimize_channel_mapping_wrapper,
    validate_roi_ranges,
    has_background_data,
    get_sample_data,
    create_status_message
)

# Import peak analysis for Ra-226 @ 186 keV
from utils.peak_analysis import calculate_ra226_from_186kev_peak


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
        [Output('sample-results', 'data', allow_duplicate=True),
         Output('accumulated-results', 'data', allow_duplicate=True),
         Output('manual-a0', 'value', allow_duplicate=True),
         Output('manual-a1', 'value', allow_duplicate=True),
         Output('manual-a2', 'value', allow_duplicate=True),
         Output('status-log', 'children', allow_duplicate=True),
         Output('run-analysis', 'children', allow_duplicate=True),
         Output('run-analysis', 'color', allow_duplicate=True),
         Output('result-186-data', 'data', allow_duplicate=True)],
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
         State('use-background', 'value'),
         State('accumulated-results', 'data'),
         State('roi1-range', 'data'),
         State('roi2-range', 'data'),
         State('peak-186-roi-left', 'data'),
         State('peak-186-roi-right', 'data'),
         State('input-186-interference', 'value')],
        prevent_initial_call=True
    )
    def run_analysis(n_clicks, data, selected_sample, ref_a0, ref_a1, ref_a2,
                     current_sample_calib, poly_degree,
                     optimize_value, opt_method, max_iter, regression_method, use_bg_checkbox,
                     accumulated_results, roi1_range, roi2_range, peak_186_roi_left, peak_186_roi_right,
                     interference_factor):
        """Run analysis for selected sample including 186 keV peak analysis"""
        if data is None or selected_sample is None:
            raise PreventUpdate
        
        # K coefficient always from ROI2 (K ROI)
        k_source_roi = 'roi2'
        
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
            
            # Use shared analysis function (K always from roi2)
            # Pass reference energy calibration for channel mapping derivation
            # Create peak-186 ROI from left/right boundaries
            peak_186_roi = [peak_186_roi_left or 113, peak_186_roi_right or 143]
            
            results, calib_method, opt_info, channel_mapping = analyze_single_sample(
                selected_sample, data, ref_mapping, current_sample_calib,
                poly_degree, optimize_value, opt_method,
                max_iter, regression_method, use_bg_checkbox,
                roi1_range=roi1_range if use_roi else None,
                roi2_range=roi2_range if use_roi else None,
                enable_roi=use_roi,
                k_source_roi=k_source_roi,
                ref_a0=ref_a0,
                ref_a1=ref_a1,
                peak_186_roi=peak_186_roi
            )
            
            # ==================== 186 keV Peak Analysis (integrated) ====================
            ra_peak_result = None
            try:
                # Validate interference factor
                if interference_factor is None or interference_factor <= 0:
                    interference_factor = 0.575
                
                # Get sample data for 186 keV analysis
                sample_rebinned_counts = np.array(results.get('sample_rebinned', []))
                sample_live_time = results.get('sample_live_time', None)
                
                if sample_live_time and len(sample_rebinned_counts) > 0:
                    sample_cps = sample_rebinned_counts / sample_live_time
                    
                    # Get pre-calibrated net_cps_per_bq from config
                    peak_calibration = data.get('peak_calibration', {})
                    precalib_net_cps_per_bq = peak_calibration.get('ra_186_net_cps_per_bq')
                    
                    if precalib_net_cps_per_bq:
                        # Energy calibration
                        energy_calib = [ref_a0 or 9.6229, ref_a1 or 1.3793, ref_a2 or 0]
                        
                        # Config
                        config_186 = data.get('peak_analysis_config', {}).copy()
                        roi_left = int(peak_186_roi_left or 113)
                        roi_right = int(peak_186_roi_right or 143)
                        config_186['manual_roi'] = [roi_left, roi_right]
                        
                        # Calculate Ra-226 from 186 keV peak
                        ra_peak_result = calculate_ra226_from_186kev_peak(
                            sample_cps=sample_cps,
                            energy_calib=energy_calib,
                            config=config_186,
                            manual_roi=[roi_left, roi_right],
                            sample_live_time=sample_live_time,
                            precalib_net_cps_per_bq=precalib_net_cps_per_bq,
                            interference_factor=interference_factor
                        )
                        
                        if ra_peak_result:
                            ra_peak_result['sample_live_time'] = sample_live_time
                            results['ra_peak_186'] = ra_peak_result
                            print(f"[186 Analysis] Ra₁₈₆: {ra_peak_result.get('activity', 0):.1f} ± {ra_peak_result.get('uncertainty', 0):.1f} Bq")
                    else:
                        print("[186 Analysis] Skipped - no peak_calibration.ra_186_net_cps_per_bq in config")
            except Exception as e186:
                print(f"[186 Analysis] Warning: {str(e186)}")
            
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
            
            # Add 186 keV result to status if available
            if ra_peak_result:
                act = ra_peak_result.get('activity', 0)
                unc = ra_peak_result.get('uncertainty', 0)
                status_lines.extend([
                    html.Br(),
                    f"☢️ Ra₁₈₆: {act:.1f} ± {unc:.1f} Bq"
                ])
            
            if opt_info:
                status_lines.extend([html.Br(), opt_info])
            
            status_msg = html.Div([
                html.Small(status_lines, className="text-success")
            ])
            
            # Return results (including 186 keV in result-186-data for graph)
            return (results, accumulated_results, no_update, no_update, no_update, status_msg, 
                    [html.I(className="fas fa-check me-2"), "Hotovo!"], 'success',
                    ra_peak_result)
            
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
            
            return (None, no_update, no_update, no_update, no_update, error_msg, 
                    [html.I(className="fas fa-times me-2"), "Chyba"], 'danger',
                    None)  # No 186 result on error
    
    
    # ==================== RUN ANALYSIS + NEXT SAMPLE ====================
    @app.callback(
        [Output('sample-selector', 'value', allow_duplicate=True),
         Output('run-analysis', 'n_clicks', allow_duplicate=True)],
        Input('run-analysis-next', 'n_clicks'),
        [State('sample-selector', 'value'),
         State('sample-selector', 'options'),
         State('run-analysis', 'n_clicks')],
        prevent_initial_call=True
    )
    def run_analysis_and_next(n_clicks, current_sample, options, current_run_clicks):
        """Trigger analysis and then move to next sample"""
        if not n_clicks or not options or not current_sample:
            raise PreventUpdate
        
        # Find current index
        sample_values = [opt['value'] for opt in options]
        try:
            current_idx = sample_values.index(current_sample)
        except ValueError:
            raise PreventUpdate
        
        # Trigger analysis by incrementing run-analysis n_clicks
        new_clicks = (current_run_clicks or 0) + 1
        
        # Move to next sample if available
        if current_idx < len(sample_values) - 1:
            next_sample = sample_values[current_idx + 1]
            return next_sample, new_clicks
        else:
            # Already at last sample, just run analysis
            return no_update, new_clicks
    
    
    # ==================== SAMPLE SELECTOR - AUTO, NEXT & PREVIOUS ====================
    @app.callback(
        [Output('sample-selector', 'value', allow_duplicate=True),
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
        
        # Skip if background is selected (background is not in excel_data)
        if current_sample and current_sample.startswith('BG:'):
            raise PreventUpdate
        
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        # Reset button to default state
        button_content = [html.I(className="fas fa-play me-2"), "Analyzovat"]
        button_color = 'primary'
        
        # Case 1: Options changed (new data loaded) - select first sample
        if trigger_id == 'sample-selector':
            if not sample_options:
                return None, no_update, no_update, no_update
            
            # Select first non-background sample
            selected = None
            for opt in sample_options:
                if not opt['value'].startswith('BG:'):
                    selected = opt['value']
                    break
            
            if not selected:
                # Only background options available
                return None, no_update, no_update, no_update
            
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
    
    @app.callback(
        Output('sample-selector', 'value', allow_duplicate=True),
        Input('sample-selector', 'options'),
        prevent_initial_call=True
    )
    def auto_select_first_sample(options):
        """Automaticky vybere první vzorek při načtení dat"""
        if options and len(options) > 0:
            return options[0]['value']
        return no_update


    @app.callback(
        [Output('sample-selector', 'value', allow_duplicate=True),
         Output('prev-sample-btn', 'disabled'),
         Output('next-sample-btn', 'disabled')],
        [Input('prev-sample-btn', 'n_clicks'),
         Input('next-sample-btn', 'n_clicks')],
        [State('sample-selector', 'value'),
         State('sample-selector', 'options')],
        prevent_initial_call=True
    )
    def navigate_samples(prev_clicks, next_clicks, current_sample, options):
        """Navigace mezi vzorky pomocí tlačítek Předchozí/Další"""
        if not options or len(options) == 0:
            return no_update, True, True
        
        ctx = callback_context
        if not ctx.triggered:
            return no_update, no_update, no_update
        
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        # Najdeme aktuální index
        current_idx = 0
        for i, opt in enumerate(options):
            if opt['value'] == current_sample:
                current_idx = i
                break
        
        new_idx = current_idx
        
        # Změníme index podle tlačítka
        if trigger_id == 'prev-sample-btn' and current_idx > 0:
            new_idx = current_idx - 1
        elif trigger_id == 'next-sample-btn' and current_idx < len(options) - 1:
            new_idx = current_idx + 1
        
        # Nastavíme disabled state tlačítek
        prev_disabled = (new_idx == 0)
        next_disabled = (new_idx == len(options) - 1)
        
        return options[new_idx]['value'], prev_disabled, next_disabled

    # ==================== AUTO-UPDATE 186 keV ON SLIDER/INTERFERENCE CHANGE ====================
    @app.callback(
        [Output('result-186-data', 'data', allow_duplicate=True),
         Output('accumulated-results', 'data', allow_duplicate=True),
         Output('sample-results', 'data', allow_duplicate=True)],
        [Input('peak-186-roi-left', 'data'),
         Input('peak-186-roi-right', 'data'),
         Input('input-186-interference', 'value')],
        [State('sample-results', 'data'),
         State('excel-data', 'data'),
         State('sample-selector', 'value'),
         State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value'),
         State('accumulated-results', 'data')],
        prevent_initial_call=True
    )
    def auto_update_186_on_change(roi_left, roi_right, interference_factor,
                                   sample_results, excel_data, selected_sample,
                                   ref_a0, ref_a1, ref_a2, accumulated_results):
        """Auto-update 186 keV analysis when slider or interference factor changes"""
        # Only update if we have sample results from main analysis
        if sample_results is None or excel_data is None:
            raise PreventUpdate
        
        # Check if sample has been analyzed (has sample_rebinned)
        sample_rebinned_counts = sample_results.get('sample_rebinned', [])
        sample_live_time = sample_results.get('sample_live_time', None)
        
        if not sample_rebinned_counts or sample_live_time is None:
            raise PreventUpdate
        
        try:
            # Validate inputs
            roi_left = int(roi_left or 113)
            roi_right = int(roi_right or 143)
            if interference_factor is None or interference_factor <= 0:
                interference_factor = 0.575
            
            sample_cps = np.array(sample_rebinned_counts) / sample_live_time
            
            # Get pre-calibrated value
            peak_calibration = excel_data.get('peak_calibration', {})
            precalib_net_cps_per_bq = peak_calibration.get('ra_186_net_cps_per_bq')
            
            if not precalib_net_cps_per_bq:
                raise PreventUpdate
            
            # Energy calibration
            energy_calib = [ref_a0 or 9.6229, ref_a1 or 1.3793, ref_a2 or 0]
            
            # Config
            config = excel_data.get('peak_analysis_config', {}).copy()
            config['manual_roi'] = [roi_left, roi_right]
            
            # Calculate
            ra_peak_result = calculate_ra226_from_186kev_peak(
                sample_cps=sample_cps,
                energy_calib=energy_calib,
                config=config,
                manual_roi=[roi_left, roi_right],
                sample_live_time=sample_live_time,
                precalib_net_cps_per_bq=precalib_net_cps_per_bq,
                interference_factor=interference_factor
            )
            
            if ra_peak_result is None:
                raise PreventUpdate
            
            ra_peak_result['sample_live_time'] = sample_live_time
            
            # Update sample_results
            sample_results = copy.deepcopy(sample_results)
            sample_results['ra_peak_186'] = ra_peak_result
            
            # Update accumulated_results
            if accumulated_results:
                for i, res in enumerate(accumulated_results):
                    if isinstance(res, dict) and res.get('sample_name') == selected_sample:
                        accumulated_results[i]['ra_peak_186'] = ra_peak_result
                        break
            
            return ra_peak_result, accumulated_results, sample_results
            
        except Exception as e:
            print(f"[186 Auto-Update] Error: {str(e)}")
            raise PreventUpdate


def analyze_single_sample(sample_name, excel_data, ref_calib, current_sample_calib, 
                          poly_degree, optimize_value, opt_method, 
                          max_iter, regression_method, use_bg_checkbox, roi1_range=None, roi2_range=None, 
                          enable_roi=False, k_source_roi='roi2', ref_a0=None, ref_a1=None,
                          peak_186_roi=None):
    """
    Analyze a single sample - refactored to use utility modules.
    
    Args:
        sample_name: Name of sample to analyze
        excel_data: Dictionary with all data
        ref_calib: Reference calibration (unused in channel-centric)
        current_sample_calib: Current sample calibration dict (contains a0, a1, a2)
        poly_degree: Polynomial degree (unused in channel-centric)
        optimize_value: List with 'optimize' if optimization enabled
        opt_method: Optimization method
        max_iter: Maximum iterations for optimization
        regression_method: 'OLS' or 'NNLS'
        use_bg_checkbox: Checkbox state for background usage
        roi1_range: [min_ch, max_ch] for ROI1 (optional)
        roi2_range: [min_ch, max_ch] for ROI2 (optional)
        enable_roi: Whether to use dual ROI analysis
        k_source_roi: 'roi1' or 'roi2' - which ROI provides K coefficient (default: 'roi2')
        peak_186_roi: [left_ch, right_ch] for Ra-226 @ 186 keV peak ROI boundaries
        ref_a0: Reference detector energy calibration a0 (keV offset)
        ref_a1: Reference detector energy calibration a1 (keV/channel)
    
    Returns:
        tuple: (results_dict, calib_method, opt_info, channel_mapping)
    """
    
    # Step 1: Determine channel mapping (optimize or use current)
    is_optimizing = 'optimize' in optimize_value
    
    # Derive channel mapping from energy calibration coefficients
    # Formula: ch_ref = ch_offset + ch_gain * ch_sample
    # Where: ch_offset = (a0_sample - a0_ref) / a1_ref
    #        ch_gain = a1_sample / a1_ref
    sample_a0 = current_sample_calib.get('a0', ref_a0 or 0.0)
    sample_a1 = current_sample_calib.get('a1', ref_a1 or 1.0)
    
    if ref_a0 is not None and ref_a1 is not None and ref_a1 != 0:
        # Calculate channel mapping from energy calibration
        ch_offset = (sample_a0 - ref_a0) / ref_a1
        ch_gain = sample_a1 / ref_a1
        initial_channel_mapping = [ch_offset, ch_gain]
    else:
        # Fallback to identity mapping
        initial_channel_mapping = [0.0, 1.0]
    
    if is_optimizing:
        # Build calibration matrix for optimization (Ra, K, Th only - no BG)
        calib_df = pd.DataFrame(excel_data['calibration'])
        X_calib = calib_df[["Ra", "K", "Th"]].values
        
        # Get sample spectrum in CPS
        sample_spectrum_counts, sample_live_time, _ = get_sample_data(sample_name, excel_data)
        sample_spectrum_cps = sample_spectrum_counts / sample_live_time if sample_live_time > 0 else sample_spectrum_counts * 0
        
        # SEPARÁTNÍ OPTIMALIZACE PRO KAŽDOU ROI
        if enable_roi and roi1_range and roi2_range:
            # Optimize channel mapping for ROI1 (Ra/Th)
            print(f"\n{'='*60}")
            print(f"OPTIMALIZACE ROI #1 (Ra/Th): ch {roi1_range[0]}-{roi1_range[1]}")
            print(f"{'='*60}")
            channel_mapping_roi1, opt_result_roi1 = optimize_channel_mapping_wrapper(
                X_calib, sample_spectrum_cps, initial_channel_mapping,
                roi_channels=roi1_range,
                method=opt_method or 'L-BFGS-B',
                maxiter=max_iter or 1000
            )
            
            # Optimize channel mapping for ROI2 (K-40)
            print(f"\n{'='*60}")
            print(f"OPTIMALIZACE ROI #2 (K-40): ch {roi2_range[0]}-{roi2_range[1]}")
            print(f"{'='*60}")
            channel_mapping_roi2, opt_result_roi2 = optimize_channel_mapping_wrapper(
                X_calib, sample_spectrum_cps, initial_channel_mapping,
                roi_channels=roi2_range,
                method=opt_method or 'L-BFGS-B',
                maxiter=max_iter or 1000
            )
            
            # Use ROI1 mapping as primary (for display purposes)
            channel_mapping = channel_mapping_roi1
            calib_method = (f"Opt ROI1: offset={channel_mapping_roi1[0]:.2f}, gain={channel_mapping_roi1[1]:.4f} | "
                           f"ROI2: offset={channel_mapping_roi2[0]:.2f}, gain={channel_mapping_roi2[1]:.4f}")
            opt_info = (f"ROI1: R²={opt_result_roi1['final_r2']:.6f} | "
                       f"ROI2: R²={opt_result_roi2['final_r2']:.6f}")
        else:
            # Non-ROI mode: single optimization over full spectrum
            channel_mapping, opt_result = optimize_channel_mapping_wrapper(
                X_calib, sample_spectrum_cps, initial_channel_mapping,
                roi_channels=None,
                method=opt_method or 'L-BFGS-B',
                maxiter=max_iter or 1000
            )
            channel_mapping_roi1 = channel_mapping
            channel_mapping_roi2 = channel_mapping
            calib_method = f"Opt: ch_offset={channel_mapping[0]:.2f}, gain={channel_mapping[1]:.4f}"
            opt_info = f"{opt_result['method']}, iter={opt_result['iterations']}, R²={opt_result['final_r2']:.6f}"
    else:
        channel_mapping = initial_channel_mapping
        channel_mapping_roi1 = initial_channel_mapping
        channel_mapping_roi2 = initial_channel_mapping
        opt_info = f"Manuální režim: a₀={sample_a0:.4f}, a₁={sample_a1:.4f} → offset={channel_mapping[0]:.2f}, gain={channel_mapping[1]:.4f}"
        calib_method = f"Manual: ch_offset={channel_mapping[0]:.2f}, gain={channel_mapping[1]:.4f}"
    
    # Step 2: Prepare sample data (normalize, rebin)
    # For ROI mode: rebin separately for each ROI with its own mapping
    from scripts.utils import rebin_channels
    
    if enable_roi and roi1_range and roi2_range:
        # Get raw sample data
        sample_spectrum_counts_raw, sample_live_time, _ = get_sample_data(sample_name, excel_data)
        sample_spectrum_cps_raw = sample_spectrum_counts_raw / sample_live_time if sample_live_time > 0 else sample_spectrum_counts_raw * 0
        
        # Number of reference channels
        calib_df = pd.DataFrame(excel_data['calibration'])
        n_ref = len(calib_df)
        
        # Rebin for ROI1 (Ra/Th)
        sample_rebinned_roi1_cps = rebin_channels(channel_mapping_roi1, sample_spectrum_cps_raw, n_ref)
        sample_rebinned_roi1_counts = rebin_channels(channel_mapping_roi1, sample_spectrum_counts_raw, n_ref)
        
        # Rebin for ROI2 (K-40)
        sample_rebinned_roi2_cps = rebin_channels(channel_mapping_roi2, sample_spectrum_cps_raw, n_ref)
        sample_rebinned_roi2_counts = rebin_channels(channel_mapping_roi2, sample_spectrum_counts_raw, n_ref)
        
        print(f"\n🔄 SEPARÁTNÍ REBINOVÁNÍ:")
        print(f"  ROI1 mapping: offset={channel_mapping_roi1[0]:.2f}, gain={channel_mapping_roi1[1]:.4f}")
        print(f"  ROI2 mapping: offset={channel_mapping_roi2[0]:.2f}, gain={channel_mapping_roi2[1]:.4f}")
        
        # For backward compatibility, use ROI1 rebinned as primary
        sample_rebinned_cps = sample_rebinned_roi1_cps
        sample_rebinned_counts = sample_rebinned_roi1_counts
    else:
        # Standard single rebinning
        sample_rebinned_cps, sample_rebinned_counts, sample_live_time, _ = prepare_sample_data(
            sample_name, excel_data, channel_mapping, print_diagnostics=True
        )
        sample_rebinned_roi1_cps = sample_rebinned_cps
        sample_rebinned_roi2_cps = sample_rebinned_cps
        sample_rebinned_roi1_counts = sample_rebinned_counts
        sample_rebinned_roi2_counts = sample_rebinned_counts
    
    # Step 3: Build calibration matrix (with optional background)
    has_background_in_data = has_background_data(excel_data)
    use_background = bool(use_bg_checkbox) and has_background_in_data
    
    X, component_names = build_calibration_matrix(excel_data, use_background, print_diagnostics=True)
    
    # Step 4: Perform regression (dual ROI or standard)
    if enable_roi and roi1_range and roi2_range:
        # Dual ROI analysis - pass separate rebinned spectra for each ROI
        results_method, results_roi1, results_roi2, mask_roi1, mask_roi2 = perform_dual_roi_regression(
            X, sample_rebinned_roi1_cps, sample_rebinned_roi2_cps, roi1_range, roi2_range,
            regression_method, component_names, k_source_roi,
            print_diagnostics=True
        )
        
        # Build ROI-specific data for visualization
        if use_background:
            roi1_fitted_cps = X @ np.array([
                results_roi1['Coefficients']['Ra'],
                results_roi1['Coefficients']['K'],
                results_roi1['Coefficients']['Th'],
                results_roi1['Coefficients']['BG']
            ])
            roi2_fitted_cps = X @ np.array([
                results_roi2['Coefficients']['Ra'],
                results_roi2['Coefficients']['K'],
                results_roi2['Coefficients']['Th'],
                results_roi2['Coefficients']['BG']
            ])
        else:
            roi1_fitted_cps = X @ np.array([
                results_roi1['Coefficients']['Ra'],
                results_roi1['Coefficients']['K'],
                results_roi1['Coefficients']['Th']
            ])
            roi2_fitted_cps = X @ np.array([
                results_roi2['Coefficients']['Ra'],
                results_roi2['Coefficients']['K'],
                results_roi2['Coefficients']['Th']
            ])
        
        roi1_fitted = roi1_fitted_cps * sample_live_time
        roi2_fitted = roi2_fitted_cps * sample_live_time
        
        # Component data
        roi1_components_data = {
            'Ra': (X[:, 0] * results_roi1['Coefficients']['Ra'] * sample_live_time).tolist(),
            'K': (X[:, 1] * results_roi1['Coefficients']['K'] * sample_live_time).tolist(),
            'Th': (X[:, 2] * results_roi1['Coefficients']['Th'] * sample_live_time).tolist(),
            'mask': mask_roi1.tolist()
        }
        roi2_components_data = {
            'Ra': (X[:, 0] * results_roi2['Coefficients']['Ra'] * sample_live_time).tolist(),
            'K': (X[:, 1] * results_roi2['Coefficients']['K'] * sample_live_time).tolist(),
            'Th': (X[:, 2] * results_roi2['Coefficients']['Th'] * sample_live_time).tolist(),
            'mask': mask_roi2.tolist()
        }
        
        if use_background:
            roi1_components_data['BG'] = (X[:, 3] * results_roi1['Coefficients']['BG'] * sample_live_time).tolist()
            roi2_components_data['BG'] = (X[:, 3] * results_roi2['Coefficients']['BG'] * sample_live_time).tolist()
        
        # Calculate global fitted spectrum
        merged_coeffs = [
            results_method['Coefficients']['Ra'],
            results_method['Coefficients']['K'],
            results_method['Coefficients']['Th']
        ]
        if use_background and 'BG' in component_names:
            # BG was already merged in perform_dual_roi_regression
            bg_avg = (results_roi1['Coefficients']['BG'] + results_roi2['Coefficients']['BG']) / 2
            merged_coeffs.append(bg_avg)
        
        fitted_spectrum_cps = X @ np.array(merged_coeffs)
        fitted_spectrum = fitted_spectrum_cps * sample_live_time
        
        # Package ROI data
        roi_data = {
            'enabled': True,
            'roi1_range': roi1_range,
            'roi2_range': roi2_range,
            'roi1_channel_mapping': channel_mapping_roi1,
            'roi2_channel_mapping': channel_mapping_roi2,
            'roi1_sample_rebinned': sample_rebinned_roi1_counts.tolist(),
            'roi2_sample_rebinned': sample_rebinned_roi2_counts.tolist(),
            'roi1_components': ['Ra', 'Th'],
            'roi2_components': ['K'],
            'roi1_fitted': roi1_fitted.tolist(),
            'roi2_fitted': roi2_fitted.tolist(),
            'roi1_components_data': roi1_components_data,
            'roi2_components_data': roi2_components_data,
            'roi1_results': results_roi1,
            'roi2_results': results_roi2,
            'fitted_spectrum': fitted_spectrum.tolist()
        }
    else:
        # Standard single regression
        results_method = perform_single_regression(X, sample_rebinned_cps, regression_method, component_names)
        
        # Calculate fitted spectrum
        fitted_cps = X @ np.array(list(results_method['Coefficients'].values()))
        fitted_spectrum = fitted_cps * sample_live_time
        
        roi_data = {
            'enabled': False,
            'roi1_range': None,
            'roi2_range': None,
            'roi1_components': [],
            'roi2_components': [],
            'roi1_fitted': [],
            'roi2_fitted': [],
            'roi1_components_data': {},
            'roi2_components_data': {},
            'roi1_results': None,
            'roi2_results': None,
            'fitted_spectrum': fitted_spectrum.tolist()
        }
    
    # Step 5: Package results
    results = package_analysis_results(
        sample_name, excel_data, sample_rebinned_counts,
        results_method, regression_method, channel_mapping,
        calib_method, enable_roi, roi1_range, roi2_range,
        roi_data, use_background
    )
    
    # Ra-226 @ 186 keV peak analysis is now done separately via "Analyzovat 186" button
    # Initialize as None - will be filled when user clicks the 186 keV analysis button
    results['ra_peak_186'] = None
    
    return results, calib_method, opt_info, channel_mapping

