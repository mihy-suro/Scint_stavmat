"""
Analysis callbacks - main regression and activity calculation
"""

from .utils import *
from datetime import datetime


def analyze_single_sample(sample_name, excel_data, ref_calib, current_sample_calib, 
                          cut_range, poly_degree, optimize_value, opt_method, 
                          max_iter, regression_method):
    """
    Analyze a single sample - extracted logic for reuse in batch processing
    
    Returns:
        dict: Analysis results or None if error
        str: Calibration method description
        str: Optimization info (or None)
        list: Sample calibration coefficients [a0, a1, a2]
    """
    # Extract cut range
    cut_channel = cut_range[0] if cut_range else 0
    cut_channel_right = cut_range[1] if cut_range else 2048
    
    # Convert data back to DataFrames
    calib_df = pd.DataFrame(excel_data['calibration'])
    sample_df = pd.DataFrame(excel_data['samples'])
    
    sample_idx = excel_data['sample_names'].index(sample_name)
    sample_live_time = excel_data['sample_live_times'][sample_idx]
    
    # Get conversion factors from parameters
    params = excel_data['parameters']
    factor_ra = float(params.get('Ra_faktor', 13.9))
    factor_k = float(params.get('K_faktor', 212))
    factor_th = float(params.get('Th_faktor', 7.4))
    
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
        sample_df_norm[sample_name] = sample_df[sample_name] / sample_live_time
    else:
        sample_df_norm[sample_name] = 0
    
    # Get sample spectrum
    sample_spectrum = sample_df_norm[sample_name].values
    
    # Store original uncut data
    sample_spectrum_uncut = sample_spectrum.copy()
    calib_df_uncut = calib_df.copy()
    
    # Create temporary masked copies for fitting
    mask = (sample_df['CHNL'] > cut_channel) & (sample_df['CHNL'] <= cut_channel_right)
    
    sample_spectrum_for_fit = sample_spectrum.copy()
    sample_spectrum_for_fit[~mask] = 0
    
    calib_df_for_fit = calib_df.copy()
    calib_df_for_fit.loc[~mask, ["Ra", "K", "Th"]] = 0
    
    # Determine calibration coefficients
    is_optimizing = 'optimize' in optimize_value
    is_quadratic = poly_degree == 'quadratic'
    
    # Get initial sample calibration
    if is_quadratic:
        initial_sample_calib = [
            current_sample_calib.get('a0', 9.6229),
            current_sample_calib.get('a1', 1.3793),
            current_sample_calib.get('a2', 0)
        ]
    else:
        initial_sample_calib = [
            current_sample_calib.get('a0', 9.6229),
            current_sample_calib.get('a1', 1.3793)
        ]
    
    if is_optimizing:
        # Dynamic bounds
        a0_start = initial_sample_calib[0]
        a1_start = initial_sample_calib[1]
        
        a0_margin = abs(a0_start) * 0.1
        a0_bounds = (a0_start - a0_margin, a0_start + a0_margin)
        
        a1_margin = abs(a1_start) * 0.1
        a1_bounds = (a1_start - a1_margin, a1_start + a1_margin)
        
        if is_quadratic:
            a2_start = initial_sample_calib[2]
            if abs(a2_start) < 1e-8:
                a2_bounds = (-1e-4, 1e-4)
            else:
                a2_margin = abs(a2_start) * 0.5
                a2_bounds = (a2_start - a2_margin, a2_start + a2_margin)
            bounds = [a0_bounds, a1_bounds, a2_bounds]
        else:
            bounds = [a0_bounds, a1_bounds]
        
        sample_calib, opt_result = find_optimal_calibration(
            ref_calib,
            initial_sample_calib,
            calib_df_for_fit[["Ra", "K", "Th"]].values,
            sample_spectrum_for_fit,
            bounds,
            method=opt_method or 'L-BFGS-B',
            maxiter=max_iter or 1000
        )
        
        # Ensure 3 elements
        if not is_quadratic and len(sample_calib) == 2:
            sample_calib = [sample_calib[0], sample_calib[1], 0]
        
        if is_quadratic:
            calib_method = f"Opt: a₀={sample_calib[0]:.4f}, a₁={sample_calib[1]:.4f}, a₂={sample_calib[2]:.6f}"
        else:
            calib_method = f"Opt: a₀={sample_calib[0]:.4f}, a₁={sample_calib[1]:.4f}"
        
        opt_info = f"{opt_result['method']}, iter={opt_result['iterations']}, R²={opt_result['final_r2']:.6f}"
    else:
        sample_calib = initial_sample_calib
        if not is_quadratic and len(sample_calib) == 2:
            sample_calib = [sample_calib[0], sample_calib[1], 0]
        
        opt_info = None
        if is_quadratic:
            calib_method = f"a₀={sample_calib[0]:.4f}, a₁={sample_calib[1]:.4f}, a₂={sample_calib[2]:.6f}"
        else:
            calib_method = f"a₀={sample_calib[0]:.4f}, a₁={sample_calib[1]:.4f}"
    
    # Rebin sample
    sample_rebinned = rebin_spectrum(ref_calib, sample_calib, sample_spectrum_for_fit)
    
    # Build predictor matrix
    X = calib_df_for_fit[["Ra", "K", "Th"]].values
    component_names = ['Ra', 'K', 'Th']
    
    # Run regression
    if regression_method == 'OLS':
        results_method = compile_results_dynamic(X, sample_rebinned, "OLS", ols, component_names)
    else:
        results_method = compile_results_dynamic(X, sample_rebinned, "NNLS", 
                                      lambda X, y: nnls_detailed(X, y, num_bootstrap=100), component_names)
    
    # Save raw coefficients
    raw_coeffs = results_method['Coefficients'].copy()
    
    # Calculate fitted spectrum
    fitted_spectrum = X @ np.array(list(raw_coeffs.values()))
    
    # Convert to Bq
    results_method['Coefficients']['Ra'] = results_method['Coefficients']['Ra'] / factor_ra
    results_method['Coefficients']['K'] = results_method['Coefficients']['K'] / factor_k
    results_method['Coefficients']['Th'] = results_method['Coefficients']['Th'] / factor_th
    
    results_method['Std Errors']['Ra'] = results_method['Std Errors']['Ra'] / factor_ra
    results_method['Std Errors']['K'] = results_method['Std Errors']['K'] / factor_k
    results_method['Std Errors']['Th'] = results_method['Std Errors']['Th'] / factor_th
    
    # Store results
    results = {
        'sample_name': sample_name,
        'calibration': calib_df_uncut.to_dict('records'),
        'sample_spectrum': sample_rebinned.tolist(),
        'sample_spectrum_uncut': sample_spectrum_uncut.tolist(),
        'bg_names': [],
        'fitted_spectrum': fitted_spectrum.tolist(),
        'raw_coeffs': raw_coeffs,
        'results': results_method,
        'regression_method': regression_method,
        'ref_calib': ref_calib,
        'sample_calib': sample_calib,
        'cut_range_used': [cut_channel, cut_channel_right],
        'calib_method': calib_method
    }
    
    return results, calib_method, opt_info, sample_calib


def register_analysis_callbacks(app):
    """Register main analysis callbacks"""
    
    # ==================== RESET BUTTON AFTER PLOT UPDATE ====================
    @app.callback(
        [Output('run-analysis', 'children'),
         Output('run-analysis', 'color')],
        Input('results-table', 'data'),
        prevent_initial_call=True
    )
    def reset_button_after_plot(table_data):
        """Reset button to original state after results table is updated"""
        return [html.I(className="fas fa-play me-2"), "Analyzovat"], 'primary'
    
    # ==================== MAIN ANALYSIS ====================
    @app.callback(
        [Output('sample-results', 'data'),
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
         State('cut-channel-range', 'value'),
         State('polynomial-degree', 'value'),
         State('optimize-calibration', 'value'),
         State('optimization-method', 'value'),
         State('max-iterations', 'value'),
         State('regression-method', 'value')],
        prevent_initial_call=True
    )
    def run_analysis(n_clicks, data, selected_sample, ref_a0, ref_a1, ref_a2,
                     current_sample_calib, cut_range, poly_degree,
                     optimize_value, opt_method, max_iter, regression_method):
        """Run analysis for selected sample"""
        if data is None or selected_sample is None:
            raise PreventUpdate
        
        try:
            # Reference calibration
            ref_calib = [ref_a0, ref_a1, ref_a2]
            
            # Use shared analysis function
            results, calib_method, opt_info, sample_calib = analyze_single_sample(
                selected_sample, data, ref_calib, current_sample_calib,
                cut_range, poly_degree, optimize_value, opt_method,
                max_iter, regression_method
            )
            
            print(f"\n=== Analysis completed for sample: {selected_sample} ===")
            print(f"Calibration method: {calib_method}")
            
            # Build status message
            status_lines = [
                html.I(className="fas fa-check-circle text-success me-1"),
                f"✅ Analýza dokončena: {selected_sample}",
                html.Br(),
                f"Kalibrace: {calib_method}",
                html.Br(),
                f"Metoda: {regression_method}"
            ]
            
            if opt_info:
                status_lines.extend([
                    html.Br(),
                    f"Opt: {opt_info}"
                ])
            
            status_msg = html.Div([
                html.Small(status_lines, className="text-success")
            ])
            
            # If optimization was used, return optimized values
            is_optimizing = 'optimize' in optimize_value
            if is_optimizing:
                return results, sample_calib[0], sample_calib[1], sample_calib[2], status_msg, [html.I(className="fas fa-check me-2"), "Hotovo!"], 'success'
            else:
                return results, no_update, no_update, no_update, status_msg, [html.I(className="fas fa-check me-2"), "Hotovo!"], 'success'
            
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
            
            return None, no_update, no_update, no_update, error_msg, [html.I(className="fas fa-times me-2"), "Chyba"], 'danger'
    
    
    # ==================== BATCH PROCESSING - START ====================
    @app.callback(
        [Output('batch-queue', 'data'),
         Output('batch-counter', 'data'),
         Output('batch-progress', 'value'),
         Output('batch-progress-label', 'children'),
         Output('batch-progress-container', 'style', allow_duplicate=True),
         Output('run-batch-analysis', 'disabled', allow_duplicate=True),
         Output('run-analysis', 'disabled', allow_duplicate=True),
         Output('status-log', 'children', allow_duplicate=True)],
        Input('run-batch-analysis', 'n_clicks'),
        State('excel-data', 'data'),
        prevent_initial_call=True
    )
    def start_batch_processing(n_clicks, excel_data):
        """Initialize batch queue and start processing"""
        if excel_data is None:
            raise PreventUpdate
        
        sample_names = excel_data['sample_names']
        total_samples = len(sample_names)
        
        if total_samples == 0:
            raise PreventUpdate
        
        print(f"\n=== BATCH START: {total_samples} samples ===")
        
        # Initialize queue with all samples (no trigger field)
        batch_queue = {
            'remaining': sample_names.copy(),
            'current_index': 0,
            'total': total_samples,
            'processing': True,
            'errors': []
        }
        
        status_msg = html.Div([
            html.Small([
                html.I(className="fas fa-cog fa-spin text-primary me-1"),
                f"🔄 Spouštím dávkové zpracování {total_samples} vzorků..."
            ], className="text-primary")
        ])
        
        # Show progress bar at 0%, disable buttons, counter=1 triggers worker
        return batch_queue, 1, 0, f"0% (0/{total_samples})", {'display': 'block'}, True, True, status_msg
    
    
    # ==================== BATCH PROCESSING - WORKER ====================
    @app.callback(
        [Output('batch-queue', 'data', allow_duplicate=True),
         Output('batch-counter', 'data', allow_duplicate=True),
         Output('accumulated-results', 'data', allow_duplicate=True),
         Output('sample-results', 'data', allow_duplicate=True),
         Output('batch-progress-container', 'style', allow_duplicate=True),
         Output('run-batch-analysis', 'disabled', allow_duplicate=True),
         Output('run-analysis', 'disabled', allow_duplicate=True),
         Output('status-log', 'children', allow_duplicate=True)],
        Input('batch-counter', 'data'),
        [State('batch-queue', 'data'),
         State('accumulated-results', 'data'),
         State('excel-data', 'data'),
         State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value'),
         State('current-sample-calib', 'data'),
         State('cut-channel-range', 'value'),
         State('polynomial-degree', 'value'),
         State('optimize-calibration', 'value'),
         State('optimization-method', 'value'),
         State('max-iterations', 'value'),
         State('regression-method', 'value')],
        prevent_initial_call=True
    )
    def process_next_sample(counter, batch_queue, accumulated_results, excel_data, 
                           ref_a0, ref_a1, ref_a2, current_sample_calib,
                           cut_range, poly_degree, optimize_value, opt_method, 
                           max_iter, regression_method):
        """Process one sample from queue and update results"""
        
        # Check if counter and queue are valid
        if counter is None or not batch_queue or not batch_queue.get('processing'):
            raise PreventUpdate
        
        print(f"\n=== PROCESS_NEXT_SAMPLE CALLED (counter={counter}) ===")
        print(f"batch_queue: {batch_queue}")
        
        remaining = batch_queue['remaining']
        print(f"  -> Remaining samples: {len(remaining)} - {remaining}")
        
        # Check if queue is empty - finalize
        if not remaining:
            total = batch_queue['total']
            success_count = total - len(batch_queue.get('errors', []))
            error_count = len(batch_queue.get('errors', []))
            
            status_msg = html.Div([
                html.Small([
                    html.I(className="fas fa-check-circle text-success me-1"),
                    f"✅ Dávkové zpracování dokončeno: {success_count}/{total} vzorků úspěšně"
                ], className="text-success" if error_count == 0 else "text-warning"),
                html.Br() if error_count > 0 else None,
                html.Small([
                    html.I(className="fas fa-exclamation-triangle text-warning me-1"),
                    f"⚠️ {error_count} vzorků selhalo"
                ], className="text-warning") if error_count > 0 else None
            ])
            
            print(f"\n=== BATCH COMPLETE: {success_count}/{total} successful ===")
            
            # Mark as not processing, hide progress bar, re-enable buttons, DON'T update counter (stops recursion)
            batch_queue['processing'] = False
            return (batch_queue, no_update, no_update, no_update, 
                    {'display': 'none'}, False, False, status_msg)
        
        # Get next sample to process
        sample_name = remaining[0]
        current_idx = batch_queue['current_index']
        total = batch_queue['total']
        
        print(f"\n[{current_idx + 1}/{total}] Processing: {sample_name}")
        
        try:
            # Analyze this sample
            results, calib_method, opt_info, sample_calib = analyze_single_sample(
                sample_name, excel_data, 
                [ref_a0, ref_a1, ref_a2],
                current_sample_calib, cut_range, poly_degree,
                optimize_value, opt_method, max_iter, regression_method
            )
            
            if results:
                # Add to accumulated results
                if accumulated_results is None:
                    accumulated_results = []
                accumulated_results.append(results)
                
                # Extract for logging
                res = results['results']
                coeff = res['Coefficients']
                
                status_msg = html.Div([
                    html.Small([
                        html.I(className="fas fa-check text-success me-1"),
                        f"✓ [{current_idx + 1}/{total}] {sample_name}: Ra={coeff['Ra']:.3f}, K={coeff['K']:.3f}, Th={coeff['Th']:.3f} Bq"
                    ], className="text-success")
                ])
                
                print(f"✓ [{current_idx + 1}/{total}] {sample_name}: Ra={coeff['Ra']:.3f}, K={coeff['K']:.3f}, Th={coeff['Th']:.3f} Bq")
            else:
                batch_queue['errors'].append(sample_name)
                results = None
                status_msg = html.Div([
                    html.Small([
                        html.I(className="fas fa-exclamation-triangle text-warning me-1"),
                        f"⚠ [{current_idx + 1}/{total}] {sample_name}: CHYBA při analýze"
                    ], className="text-warning")
                ])
                print(f"✗ [{current_idx + 1}/{total}] {sample_name}: CHYBA")
                
        except Exception as e:
            batch_queue['errors'].append(sample_name)
            results = None
            status_msg = html.Div([
                html.Small([
                    html.I(className="fas fa-exclamation-triangle text-warning me-1"),
                    f"⚠ [{current_idx + 1}/{total}] {sample_name}: {str(e)[:50]}"
                ], className="text-warning")
            ])
            print(f"✗ [{current_idx + 1}/{total}] {sample_name}: CHYBA - {str(e)}")
        
        # Update queue - remove processed sample
        new_queue = {
            'remaining': remaining[1:],  # Remove first item
            'current_index': current_idx + 1,
            'total': total,
            'processing': True,
            'errors': batch_queue['errors']
        }
        
        print(f"  -> Returning new queue with {len(new_queue['remaining'])} remaining samples")
        print(f"  -> New queue: {new_queue}")
        print(f"  -> Incrementing counter: {counter} -> {counter + 1}")
        
        # Return updated queue, incremented counter (triggers recursion), updated results
        return new_queue, counter + 1, accumulated_results, results, no_update, no_update, no_update, status_msg
    
    
    # ==================== BATCH PROCESSING - PROGRESS & FINALIZATION ====================
    @app.callback(
        [Output('batch-progress', 'value', allow_duplicate=True),
         Output('batch-progress-label', 'children', allow_duplicate=True)],
        Input('batch-queue', 'data'),
        prevent_initial_call=True
    )
    def update_batch_progress(batch_queue):
        """Update progress bar during batch processing"""
        
        if not batch_queue or not batch_queue.get('processing'):
            raise PreventUpdate
        
        total = batch_queue['total']
        remaining_count = len(batch_queue['remaining'])
        processed = total - remaining_count
        
        # Calculate progress
        if total > 0:
            progress = int((processed / total) * 100)
        else:
            progress = 0
        
        # Update progress bar
        return progress, f"{progress}% ({processed}/{total})"


