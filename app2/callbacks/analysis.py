"""
Analysis callbacks - main regression and activity calculation
"""

from .utils import *


def register_analysis_callbacks(app):
    """Register main analysis callbacks"""
    
    # ==================== MAIN ANALYSIS ====================
    @app.callback(
        [Output('sample-results', 'data'),
         Output('manual-a0', 'value', allow_duplicate=True),
         Output('manual-a1', 'value', allow_duplicate=True),
         Output('status-log', 'children', allow_duplicate=True),
         Output('optimization-progress', 'data'),
         Output('progress-interval', 'disabled')],
        Input('run-analysis', 'n_clicks'),
        [State('excel-data', 'data'),
         State('sample-selector', 'value'),
         State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value'),
         State('current-sample-calib', 'data'),
         State('cut-channel', 'value'),
         State('cut-channel-right', 'value'),
         State('polynomial-degree', 'value'),
         State('optimize-calibration', 'value'),
         State('optimization-method', 'value'),
         State('max-iterations', 'value'),
         State('include-background', 'value')],
        prevent_initial_call=True
    )
    def run_analysis(n_clicks, data, selected_sample, ref_a0, ref_a1, ref_a2,
                     current_sample_calib, cut_channel, cut_channel_right, poly_degree,
                     optimize_value, opt_method, max_iter, include_bg_value):
        """Run analysis for selected sample"""
        if data is None or selected_sample is None:
            raise PreventUpdate
        
        try:
            # Convert data back to DataFrames
            calib_df = pd.DataFrame(data['calibration'])
            sample_df = pd.DataFrame(data['samples'])
            bg_df = pd.DataFrame(data['background'])
            
            sample_idx = data['sample_names'].index(selected_sample)
            sample_live_time = data['sample_live_times'][sample_idx]
            bg_names = data['bg_names']
            bg_live_times = data['bg_live_times']
            
            # Get conversion factors from parameters
            params = data['parameters']
            factor_ra = float(params.get('Ra_faktor', 13.9))
            factor_k = float(params.get('K_faktor', 212))
            factor_th = float(params.get('Th_faktor', 7.4))
            
            # Reference calibration
            ref_calib = [ref_a0, ref_a1, ref_a2]
            
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
                sample_df_norm[selected_sample] = sample_df[selected_sample] / sample_live_time
            else:
                sample_df_norm[selected_sample] = 0
            
            # Normalize all backgrounds to CPS (každé podle svého live time)
            bg_df_norm = bg_df.copy()
            for i, bg_name in enumerate(bg_names):
                if bg_live_times[i] > 0:
                    bg_df_norm[bg_name] = bg_df[bg_name] / bg_live_times[i]
                else:
                    bg_df_norm[bg_name] = 0
            
            # NEODEČÍTAT pozadí! Použije se jako prediktor v regresi
            sample_spectrum = sample_df_norm[selected_sample].values
            
            # Zero out first N channels (left cutoff)
            calib_df.loc[calib_df["CHNL"] <= cut_channel, ["Ra", "K", "Th"]] = 0
            sample_spectrum[sample_df['CHNL'] <= cut_channel] = 0
            for bg_name in bg_names:
                bg_df_norm.loc[bg_df['CHNL'] <= cut_channel, bg_name] = 0
            
            # Zero out channels beyond M (right cutoff)
            calib_df.loc[calib_df["CHNL"] > cut_channel_right, ["Ra", "K", "Th"]] = 0
            sample_spectrum[sample_df['CHNL'] > cut_channel_right] = 0
            for bg_name in bg_names:
                bg_df_norm.loc[bg_df['CHNL'] > cut_channel_right, bg_name] = 0
            
            # Determine calibration coefficients
            is_optimizing = 'optimize' in optimize_value
            is_quadratic = poly_degree == 'quadratic'
            
            # Get initial sample calibration from store (current UI values)
            if is_quadratic:
                initial_sample_calib = [
                    current_sample_calib.get('a0', 9.6229),
                    current_sample_calib.get('a1', 1.3793),
                    current_sample_calib.get('a2', 0)
                ]
            else:
                # For linear calibration, only optimize a0 and a1
                initial_sample_calib = [
                    current_sample_calib.get('a0', 9.6229),
                    current_sample_calib.get('a1', 1.3793)
                ]
            
            # Initialize optimization progress
            progress_data = {'iteration': 0, 'r2': 0, 'coeffs': [], 'running': False}
            progress_disabled = True
            
            if is_optimizing:
                # Dynamic bounds based on starting vector (±10% for a0 and a1)
                a0_start = initial_sample_calib[0]
                a1_start = initial_sample_calib[1]
                
                # a0 bounds: ±10% around starting value
                a0_bounds = (a0_start * 0.9, a0_start * 1.1)
                
                # a1 bounds: ±10% around starting value
                a1_bounds = (a1_start * 0.9, a1_start * 1.1)
                
                if is_quadratic:
                    # For quadratic, allow a2 to vary symmetrically around starting value
                    a2_start = initial_sample_calib[2]
                    if abs(a2_start) < 1e-8:
                        # If starting from ~0, allow small range
                        a2_bounds = (-1e-4, 1e-4)
                    else:
                        # Otherwise ±50% around starting value
                        a2_bounds = (a2_start * 0.5, a2_start * 1.5)
                    bounds = [a0_bounds, a1_bounds, a2_bounds]
                    print(f"\n=== Optimization bounds (3D - quadratic) ===")
                    print(f"a₀: {a0_bounds[0]:.4f} - {a0_bounds[1]:.4f} (start: {a0_start:.4f})")
                    print(f"a₁: {a1_bounds[0]:.6f} - {a1_bounds[1]:.6f} (start: {a1_start:.6f})")
                    print(f"a₂: {a2_bounds[0]:.6e} - {a2_bounds[1]:.6e} (start: {a2_start:.6e})")
                else:
                    # For linear, optimize only a0 and a1 (2D)
                    bounds = [a0_bounds, a1_bounds]
                    print(f"\n=== Optimization bounds (2D - linear) ===")
                    print(f"a₀: {a0_bounds[0]:.4f} - {a0_bounds[1]:.4f} (start: {a0_start:.4f})")
                    print(f"a₁: {a1_bounds[0]:.6f} - {a1_bounds[1]:.6f} (start: {a1_start:.6f})")
                
                initial_for_opt = initial_sample_calib  # Use current UI values as start
                
                # Progress callback to store data in a shared location
                progress_storage = {'iteration': 0, 'r2': 0, 'coeffs': []}
                
                def progress_callback(iteration, r2, coeffs):
                    progress_storage['iteration'] = iteration
                    progress_storage['r2'] = r2
                    progress_storage['coeffs'] = coeffs
                
                sample_calib, opt_result = find_optimal_calibration(
                    ref_calib,
                    initial_for_opt,
                    calib_df[["Ra", "K", "Th"]].values,
                    sample_spectrum,
                    bounds,  # Now correctly sized: 2 elements for linear, 3 for quadratic
                    method=opt_method or 'L-BFGS-B',
                    maxiter=max_iter or 1000,
                    progress_callback=progress_callback
                )
                
                # Ensure sample_calib has 3 elements for consistency
                if not is_quadratic and len(sample_calib) == 2:
                    sample_calib = [sample_calib[0], sample_calib[1], 0]
                
                # Build calibration method string
                if is_quadratic:
                    calib_method = f"Optimalizováno: a₀={sample_calib[0]:.4f}, a₁={sample_calib[1]:.4f}, a₂={sample_calib[2]:.6f}"
                else:
                    calib_method = f"Optimalizováno: a₀={sample_calib[0]:.4f}, a₁={sample_calib[1]:.4f}"
                
                # Store optimization result info
                opt_info = f"Metoda: {opt_result['method']}, Iterace: {opt_result['iterations']}, R²: {opt_result['final_r2']:.6f}, Konvergence: {'Ano' if opt_result['converged'] else 'Ne'}"
                print(f"\n=== Optimization Results ===")
                print(opt_info)
            else:
                sample_calib = initial_sample_calib
                # Ensure sample_calib has 3 elements for consistency with rebin_spectrum
                if not is_quadratic and len(sample_calib) == 2:
                    sample_calib = [sample_calib[0], sample_calib[1], 0]
                
                opt_info = None
                if is_quadratic:
                    calib_method = f"Kalibrace vzorku: a₀={sample_calib[0]:.4f}, a₁={sample_calib[1]:.4f}, a₂={sample_calib[2]:.6f}"
                else:
                    calib_method = f"Kalibrace vzorku: a₀={sample_calib[0]:.4f}, a₁={sample_calib[1]:.4f}"
            
            # Rebin sample
            sample_rebinned = rebin_spectrum(ref_calib, sample_calib, sample_spectrum)
            
            # Check if background should be included
            include_bg = 'include' in include_bg_value
            
            # Sestavit matici prediktorů - s nebo bez pozadí
            if include_bg:
                X = pd.concat([
                    calib_df[["Ra", "K", "Th"]],
                    bg_df_norm[bg_names]
                ], axis=1).values
                component_names = ['Ra', 'K', 'Th'] + bg_names
                fit_info = f"s pozadím ({len(bg_names)}x)"
            else:
                X = calib_df[["Ra", "K", "Th"]].values
                component_names = ['Ra', 'K', 'Th']
                fit_info = "bez pozadí"
            
            print(f"Fit mode: {fit_info}")
            
            # Run regression s dynamickým počtem komponent
            results_ols = compile_results_dynamic(X, sample_rebinned, "OLS", ols, component_names)
            results_nnls = compile_results_dynamic(X, sample_rebinned, "NNLS", 
                                          lambda X, y: nnls_detailed(X, y, num_bootstrap=100), component_names)
            
            # Save raw coefficients for component plotting (BEFORE conversion to Bq)
            raw_ols_coeffs = results_ols['Coefficients'].copy()
            
            # Calculate fitted spectra BEFORE converting to Bq (using raw coefficients)
            fitted_ols = X @ np.array(list(raw_ols_coeffs.values()))
            fitted_nnls = X @ np.array(list(results_nnls['Coefficients'].values()))
            
            # Now convert coefficients to activities [Bq]
            results_ols['Coefficients']['Ra'] = results_ols['Coefficients']['Ra'] / factor_ra
            results_ols['Coefficients']['K'] = results_ols['Coefficients']['K'] / factor_k
            results_ols['Coefficients']['Th'] = results_ols['Coefficients']['Th'] / factor_th
            
            results_nnls['Coefficients']['Ra'] = results_nnls['Coefficients']['Ra'] / factor_ra
            results_nnls['Coefficients']['K'] = results_nnls['Coefficients']['K'] / factor_k
            results_nnls['Coefficients']['Th'] = results_nnls['Coefficients']['Th'] / factor_th
            
            # Convert std errors to Bq
            results_ols['Std Errors']['Ra'] = results_ols['Std Errors']['Ra'] / factor_ra
            results_ols['Std Errors']['K'] = results_ols['Std Errors']['K'] / factor_k
            results_ols['Std Errors']['Th'] = results_ols['Std Errors']['Th'] / factor_th
            
            results_nnls['Std Errors']['Ra'] = results_nnls['Std Errors']['Ra'] / factor_ra
            results_nnls['Std Errors']['K'] = results_nnls['Std Errors']['K'] / factor_k
            results_nnls['Std Errors']['Th'] = results_nnls['Std Errors']['Th'] / factor_th
            
            # Store results
            # Uložit pozadí jako dict kde každý key je bg_name a value je list hodnot
            if include_bg:
                bg_data_dict = {}
                for bg_name in bg_names:
                    bg_data_dict[bg_name] = bg_df_norm[bg_name].tolist()
                bg_names_result = bg_names
            else:
                bg_data_dict = {}
                bg_names_result = []
            
            results = {
                'sample_name': selected_sample,
                'calibration': calib_df.to_dict('records'),
                'sample_spectrum': sample_rebinned.tolist(),
                'background': bg_data_dict,  # Dict of lists
                'bg_names': bg_names_result,
                'fitted_ols': fitted_ols.tolist(),
                'fitted_nnls': fitted_nnls.tolist(),
                'raw_ols_coeffs': raw_ols_coeffs,  # Raw coefficients for component plotting
                'results_ols': results_ols,
                'results_nnls': results_nnls,
                'ref_calib': ref_calib,
                'calib_method': calib_method,
                'fit_mode': fit_info
            }
            
            print(f"\n=== Analysis completed for sample: {selected_sample} ===")
            print(f"Calibration method: {calib_method}")
            print(f"Fit mode: {fit_info}")
            
            # Build status message
            status_lines = [
                html.I(className="fas fa-check-circle text-success me-1"),
                f"✅ Analýza dokončena: {selected_sample}",
                html.Br(),
                f"Kalibrace: {calib_method[:60]}...",
                html.Br(),
                f"Fit: {fit_info}"
            ]
            
            # Add optimization info if available
            if opt_info:
                status_lines.extend([
                    html.Br(),
                    f"Opt: {opt_info[:80]}..."
                ])
            
            status_msg = html.Div([
                html.Small(status_lines, className="text-success")
            ])
            
            # If optimization was used, return optimized values to update manual calibration
            if is_optimizing:
                return results, sample_calib[0], sample_calib[1], status_msg, progress_data, progress_disabled
            else:
                # Don't change calibration if not optimizing
                return results, no_update, no_update, status_msg, progress_data, progress_disabled
            
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
            
            progress_data = {'iteration': 0, 'r2': 0, 'coeffs': [], 'running': False}
            return None, no_update, no_update, error_msg, progress_data, True
