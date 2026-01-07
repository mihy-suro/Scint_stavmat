"""
Analysis core utilities - extracted from callbacks/analysis.py
Heavy regression logic separated for testability and reusability
"""

import numpy as np
import pandas as pd
from scripts.utils import ols, nnls_detailed
from .results_calculations import compile_results_dynamic
from .data_helpers import unpack_excel_data, get_sample_data


def prepare_sample_data(sample_name, excel_data, channel_mapping, print_diagnostics=True):
    """
    Prepare sample spectrum for analysis: extract, normalize, rebin.
    
    Args:
        sample_name: Name of sample to analyze
        excel_data: Dictionary with all data
        channel_mapping: [ch_offset, gain] for rebinning
        print_diagnostics: Whether to print diagnostic info
        
    Returns:
        tuple: (sample_rebinned_cps, sample_rebinned_counts, sample_live_time, sample_idx)
    """
    from scripts.utils import rebin_channels
    
    # Get data
    calib_df, sample_df, _ = unpack_excel_data(excel_data)
    sample_spectrum_counts, sample_live_time, sample_idx = get_sample_data(sample_name, excel_data)
    
    if print_diagnostics:
        print(f"\n{'='*60}")
        print(f"📊 SAMPLE PAIRING CHECK:")
        print(f"{'='*60}")
        print(f"Sample name: {sample_name}")
        print(f"Sample index in list: {sample_idx}")
        print(f"Live time from list: {sample_live_time:.2f} s")
        print(f"All samples in data: {excel_data['sample_names']}")
        print(f"Columns in sample_df: {list(sample_df.columns)}")
        if sample_name in sample_df.columns:
            print(f"Total counts in spectrum: {sample_spectrum_counts.sum():.0f}")
        print(f"{'='*60}\n")
    
    # Convert to CPS
    sample_spectrum_cps = sample_spectrum_counts / sample_live_time if sample_live_time > 0 else sample_spectrum_counts * 0
    
    if print_diagnostics:
        print(f"\n🔍 REBINNING DIAGNOSTICS (Channel-Centric):")
        print(f"Sample spectrum BEFORE rebin:")
        print(f"  Sum (total CPS): {sample_spectrum_cps.sum():.2f}")
        print(f"  Mean CPS/channel: {sample_spectrum_cps.mean():.4f}")
        print(f"  Max CPS: {sample_spectrum_cps.max():.2f}")
        print(f"\nChannel mapping:")
        print(f"  Ref:    ch_offset=0.0, gain=1.0 (identity)")
        print(f"  Sample: ch_offset={channel_mapping[0]:.2f}, gain={channel_mapping[1]:.4f}")
    
    # Rebin to reference detector channels
    sample_rebinned_cps = rebin_channels(channel_mapping, sample_spectrum_cps, n_ref_channels=len(calib_df))
    sample_rebinned_counts = rebin_channels(channel_mapping, sample_spectrum_counts, n_ref_channels=len(calib_df))
    
    if print_diagnostics:
        print(f"Sample spectrum AFTER rebin:")
        print(f"  Sum (total CPS): {sample_rebinned_cps.sum():.2f}")
        print(f"  Conservation ratio: {sample_rebinned_cps.sum() / sample_spectrum_cps.sum():.6f}")
        if abs(sample_rebinned_cps.sum() / sample_spectrum_cps.sum() - 1.0) < 0.01:
            print(f"  ✅ Conserved")
        else:
            print(f"  ❌ NOT CONSERVED!")
    
    return sample_rebinned_cps, sample_rebinned_counts, sample_live_time, sample_idx


def build_calibration_matrix(excel_data, use_background, print_diagnostics=True):
    """
    Build calibration matrix X and component names.
    
    Args:
        excel_data: Dictionary with calibration data
        use_background: Whether to include background component
        print_diagnostics: Whether to print diagnostic info
        
    Returns:
        tuple: (X_matrix, component_names)
    """
    calib_df, _, _ = unpack_excel_data(excel_data)
    
    if use_background and 'BG' in calib_df.columns:
        X = calib_df[["Ra", "K", "Th", "BG"]].values
        component_names = ['Ra', 'K', 'Th', 'BG']
    else:
        X = calib_df[["Ra", "K", "Th"]].values
        component_names = ['Ra', 'K', 'Th']
    
    if print_diagnostics:
        print(f"\nCalibration matrix X (first 3 channels):")
        print(f"  Ra: {X[:3, 0]}")
        print(f"  K:  {X[:3, 1]}")
        print(f"  Th: {X[:3, 2]}")
        if use_background and len(component_names) == 4:
            print(f"  BG: {X[:3, 3]}")
        print(f"  Sum of Ra calibration: {X[:, 0].sum():.6e}")
        print(f"  Sum of K calibration: {X[:, 1].sum():.6e}")
        print(f"  Sum of Th calibration: {X[:, 2].sum():.6e}")
        if use_background and len(component_names) == 4:
            print(f"  Sum of BG calibration: {X[:, 3].sum():.6e}")
    
    return X, component_names


def perform_single_regression(X, y_rebinned, regression_method, component_names):
    """
    Perform standard (non-ROI) regression analysis.
    
    Args:
        X: Calibration matrix
        y_rebinned: Rebinned sample spectrum (CPS)
        regression_method: 'OLS' or 'NNLS'
        component_names: List of component names
        
    Returns:
        dict: Regression results
    """
    if regression_method == 'OLS':
        results = compile_results_dynamic(X, y_rebinned, "OLS", ols, component_names)
    else:
        results = compile_results_dynamic(
            X, y_rebinned, "NNLS",
            lambda X, y: nnls_detailed(X, y, num_bootstrap=100),
            component_names
        )
    
    return results


def perform_dual_roi_regression(X, y_rebinned_roi1, y_rebinned_roi2, roi1_range, roi2_range, 
                                regression_method, component_names, 
                                k_source_roi='roi2', print_diagnostics=True):
    """
    Perform dual ROI regression: fit ROI1 for Ra/Th, ROI2 for K, merge results.
    
    Each ROI uses its own rebinned spectrum (optimized with separate channel mapping).
    
    Args:
        X: Calibration matrix
        y_rebinned_roi1: Rebinned sample spectrum for ROI1 (CPS) - optimized for Ra/Th region
        y_rebinned_roi2: Rebinned sample spectrum for ROI2 (CPS) - optimized for K-40 region
        roi1_range: [min_ch, max_ch] for Ra/Th region
        roi2_range: [min_ch, max_ch] for K region
        regression_method: 'OLS' or 'NNLS'
        component_names: List of component names
        k_source_roi: 'roi1' or 'roi2' - which ROI provides K coefficient (default: 'roi2')
        print_diagnostics: Whether to print diagnostics
        
    Returns:
        tuple: (merged_results, results_roi1, results_roi2, mask_roi1, mask_roi2)
    """
    from .data_helpers import create_channel_mask
    
    if print_diagnostics:
        print(f"\n{'='*60}")
        print(f"DUAL ROI ANALYSIS (Channel-Centric, Separate Mappings)")
        print(f"{'='*60}")
        print(f"ROI #1 (Ra/Th): channels {roi1_range[0]}-{roi1_range[1]}")
        print(f"ROI #2 (K-40):  channels {roi2_range[0]}-{roi2_range[1]}")
        print(f"Using SEPARATE rebinned spectra for each ROI")
    
    # Create masks for ROI regions
    mask_roi1 = create_channel_mask(roi1_range, len(y_rebinned_roi1))
    mask_roi2 = create_channel_mask(roi2_range, len(y_rebinned_roi2))
    
    # ROI 1: Mask and fit using ROI1-specific rebinned spectrum
    X_roi1 = X.copy()
    y_roi1 = y_rebinned_roi1.copy()
    X_roi1[~mask_roi1] = 0
    y_roi1[~mask_roi1] = 0
    
    if print_diagnostics:
        print(f"\n→ Fitting ROI #1 ({np.sum(mask_roi1)} channels)...")
    
    if regression_method == 'OLS':
        results_roi1 = compile_results_dynamic(X_roi1, y_roi1, "OLS", ols, component_names)
    else:
        results_roi1 = compile_results_dynamic(
            X_roi1, y_roi1, "NNLS",
            lambda X, y: nnls_detailed(X, y, num_bootstrap=50),
            component_names
        )
    
    ra_coeff = results_roi1['Coefficients']['Ra']
    th_coeff = results_roi1['Coefficients']['Th']
    k_coeff_roi1 = results_roi1['Coefficients']['K']
    
    if print_diagnostics:
        print(f"  Ra: {ra_coeff:.2e}, K: {k_coeff_roi1:.2e}, Th: {th_coeff:.2e}")
    
    # ROI 2: Mask and fit using ROI2-specific rebinned spectrum
    X_roi2 = X.copy()
    y_roi2 = y_rebinned_roi2.copy()
    X_roi2[~mask_roi2] = 0
    y_roi2[~mask_roi2] = 0
    
    if print_diagnostics:
        print(f"\n→ Fitting ROI #2 ({np.sum(mask_roi2)} channels)...")
    
    if regression_method == 'OLS':
        results_roi2 = compile_results_dynamic(X_roi2, y_roi2, "OLS", ols, component_names)
    else:
        results_roi2 = compile_results_dynamic(
            X_roi2, y_roi2, "NNLS",
            lambda X, y: nnls_detailed(X, y, num_bootstrap=50),
            component_names
        )
    
    k_coeff_roi2 = results_roi2['Coefficients']['K']
    
    if print_diagnostics:
        print(f"  Ra: {results_roi2['Coefficients']['Ra']:.2e}, K: {k_coeff_roi2:.2e}, Th: {results_roi2['Coefficients']['Th']:.2e}")
    
    # Merge coefficients
    if print_diagnostics:
        print(f"\n→ Merging coefficients...")
    
    k_coeff = k_coeff_roi2 if k_source_roi == 'roi2' else k_coeff_roi1
    
    if print_diagnostics:
        print(f"  Using K from {'ROI #2' if k_source_roi == 'roi2' else 'ROI #1'}: {k_coeff:.2e}")
    
    # Build merged coefficient array
    has_bg = 'BG' in component_names
    if has_bg:
        bg_coeff = (results_roi1['Coefficients']['BG'] + results_roi2['Coefficients']['BG']) / 2
        merged_coeffs = np.array([ra_coeff, k_coeff, th_coeff, bg_coeff])
        if print_diagnostics:
            print(f"  BG (averaged): {bg_coeff:.2e}")
    else:
        merged_coeffs = np.array([ra_coeff, k_coeff, th_coeff])
    
    # Calculate ROI-specific R² values (since each ROI has its own rebinned spectrum)
    # ROI1 R²
    fitted_roi1 = X @ np.array([results_roi1['Coefficients']['Ra'], 
                                 results_roi1['Coefficients']['K'], 
                                 results_roi1['Coefficients']['Th']] + 
                                ([results_roi1['Coefficients']['BG']] if has_bg else []))
    ss_res_roi1 = np.sum((y_rebinned_roi1[mask_roi1] - fitted_roi1[mask_roi1])**2)
    ss_tot_roi1 = np.sum((y_rebinned_roi1[mask_roi1] - np.mean(y_rebinned_roi1[mask_roi1]))**2)
    r2_roi1 = 1 - (ss_res_roi1 / ss_tot_roi1) if ss_tot_roi1 > 0 else 0
    
    # ROI2 R²
    fitted_roi2 = X @ np.array([results_roi2['Coefficients']['Ra'], 
                                 results_roi2['Coefficients']['K'], 
                                 results_roi2['Coefficients']['Th']] + 
                                ([results_roi2['Coefficients']['BG']] if has_bg else []))
    ss_res_roi2 = np.sum((y_rebinned_roi2[mask_roi2] - fitted_roi2[mask_roi2])**2)
    ss_tot_roi2 = np.sum((y_rebinned_roi2[mask_roi2] - np.mean(y_rebinned_roi2[mask_roi2]))**2)
    r2_roi2 = 1 - (ss_res_roi2 / ss_tot_roi2) if ss_tot_roi2 > 0 else 0
    
    # Combined R² as weighted average
    n_roi1 = np.sum(mask_roi1)
    n_roi2 = np.sum(mask_roi2)
    r2_combined = (r2_roi1 * n_roi1 + r2_roi2 * n_roi2) / (n_roi1 + n_roi2) if (n_roi1 + n_roi2) > 0 else 0
    
    n, p = X.shape
    r2_adj = 1 - (1 - r2_combined) * (n - 1) / (n - p) if n > p else r2_combined
    
    # Package merged results
    merged_results = {
        "Method": f"{regression_method} (ROI dual, separate mappings)",
        "Coefficients": {'Ra': ra_coeff, 'K': k_coeff, 'Th': th_coeff},  # BG excluded
        "Std Errors": {
            'Ra': results_roi1['Std Errors']['Ra'],
            'K': results_roi2['Std Errors']['K'] if k_source_roi == 'roi2' else results_roi1['Std Errors']['K'],
            'Th': results_roi1['Std Errors']['Th']
        },
        "P Values": {'Ra': 0, 'K': 0, 'Th': 0},
        "R^2": r2_combined,
        "R^2_ROI1": r2_roi1,
        "R^2_ROI2": r2_roi2,
        "Adjusted R^2": r2_adj
    }
    
    if print_diagnostics:
        print(f"\n→ Final merged coefficients:")
        print(f"  Ra: {ra_coeff:.2e} (from ROI1)")
        print(f"  K:  {k_coeff:.2e} (from {'ROI2' if k_source_roi == 'roi2' else 'ROI1'})")
        print(f"  Th: {th_coeff:.2e} (from ROI1)")
        print(f"  R² ROI1: {r2_roi1:.6f}")
        print(f"  R² ROI2: {r2_roi2:.6f}")
        print(f"  R² Combined: {r2_combined:.6f}")
        print(f"{'='*60}\n")
    
    return merged_results, results_roi1, results_roi2, mask_roi1, mask_roi2


def package_analysis_results(sample_name, excel_data, sample_rebinned_counts, 
                             results_method, regression_method, channel_mapping,
                             calib_method, enable_roi, roi1_range, roi2_range,
                             roi_data=None, use_background=False):
    """
    Package all analysis results into final dictionary.
    
    Args:
        sample_name: Name of analyzed sample
        excel_data: Source data dictionary
        sample_rebinned_counts: Rebinned spectrum in counts
        results_method: Regression results dictionary
        regression_method: 'OLS' or 'NNLS'
        channel_mapping: [ch_offset, gain]
        calib_method: Description string
        enable_roi: Whether ROI analysis was used
        roi1_range: ROI1 channel range or None
        roi2_range: ROI2 channel range or None
        roi_data: Optional dict with ROI-specific data
        use_background: Whether background was used
        
    Returns:
        dict: Complete analysis results package
    """
    calib_df, _, _ = unpack_excel_data(excel_data)
    
    # Get sample live time for later use
    sample_live_time = excel_data['sample_live_times'][excel_data['sample_names'].index(sample_name)]
    
    # Extract coefficients (BG already removed from results_method)
    raw_coeffs = {k: v for k, v in results_method['Coefficients'].items()}
    
    # Log BG if it was used
    if use_background and 'BG' in results_method.get('Coefficients', {}):
        bg_coeff = results_method['Coefficients'].pop('BG')
        if 'BG' in results_method.get('Std Errors', {}):
            results_method['Std Errors'].pop('BG')
        if 'BG' in results_method.get('P Values', {}):
            results_method['P Values'].pop('BG')
        print(f"\n📊 Background coefficient (used for fit, not reported): {bg_coeff:.2e}")
    
    # Build base results
    results = {
        'sample_name': sample_name,
        'sample_live_time': sample_live_time,  # Important for 186 keV analysis
        'calibration': calib_df.to_dict('records'),
        'sample_spectrum': sample_rebinned_counts.tolist(),
        'sample_rebinned': sample_rebinned_counts.tolist(),
        'bg_names': [],
        'raw_coeffs': raw_coeffs,
        'results': results_method,
        'regression_method': regression_method,
        'channel_mapping': channel_mapping,
        'calib_method': calib_method,
    }
    
    # Add ROI info if available
    if roi_data:
        results['roi_info'] = roi_data
        results['fitted_spectrum'] = roi_data.get('fitted_spectrum', [])
    else:
        # Standard analysis - calculate fitted spectrum
        X, _ = build_calibration_matrix(excel_data, use_background, print_diagnostics=False)
        fitted_cps = X @ np.array(list(raw_coeffs.values()))
        fitted_counts = fitted_cps * sample_live_time
        
        results['fitted_spectrum'] = fitted_counts.tolist()
        results['roi_info'] = {
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
            'roi2_results': None
        }
    
    return results
