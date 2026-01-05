"""
Results calculation utilities - activity index, uncertainties, coefficient extraction
"""

import numpy as np


def calculate_activity_index(ra, th, k):
    """
    Calculate activity index: Ra/300 + Th/200 + K/3000
    
    Args:
        ra: Ra-226 activity (Bq/kg)
        th: Th-232 activity (Bq/kg)
        k: K-40 activity (Bq/kg)
        
    Returns:
        float: Activity index
    """
    return ra / 300 + th / 200 + k / 3000


def calculate_index_uncertainty(ra, ra_err, th, th_err, k, k_err):
    """
    Calculate uncertainty of activity index using error propagation.
    
    Formula: σ_I = sqrt((∂I/∂Ra × σ_Ra)² + (∂I/∂Th × σ_Th)² + (∂I/∂K × σ_K)²)
    where I = Ra/300 + Th/200 + K/3000
    
    Args:
        ra, th, k: Activity values
        ra_err, th_err, k_err: Activity uncertainties
        
    Returns:
        float: Index uncertainty
    """
    # Partial derivatives
    dI_dRa = 1 / 300
    dI_dTh = 1 / 200
    dI_dK = 1 / 3000
    
    # Error propagation
    sigma_I = np.sqrt(
        (dI_dRa * ra_err)**2 +
        (dI_dTh * th_err)**2 +
        (dI_dK * k_err)**2
    )
    
    return sigma_I


def extract_coefficients_from_results(result_entry, k_source_roi=None):
    """
    Extract Ra, K, Th coefficients and errors from results entry.
    Handles both standard and ROI analysis results.
    
    Args:
        result_entry: Results dictionary
        k_source_roi: If ROI analysis, which ROI to use for K ('roi1' or 'roi2')
        
    Returns:
        tuple: (ra, k, th, ra_err, k_err, th_err) or (None, None, None, None, None, None)
    """
    if not isinstance(result_entry, dict):
        return None, None, None, None, None, None
    
    results = result_entry.get('results', {})
    coeffs = results.get('Coefficients', {})
    std_errs = results.get('Std Errors', {})
    
    # Check if ROI analysis
    roi_info = result_entry.get('roi_info', {})
    is_roi_analysis = roi_info.get('enabled', False)
    
    if is_roi_analysis and k_source_roi:
        # Extract from ROI-specific results
        roi_key = f'{k_source_roi}_results'
        roi_results = roi_info.get(roi_key)
        
        if roi_results:
            ra = coeffs.get('Ra', 0)
            k = roi_results.get('Coefficients', {}).get('K', coeffs.get('K', 0))
            th = coeffs.get('Th', 0)
            
            ra_err = std_errs.get('Ra', 0)
            k_err = roi_results.get('Std Errors', {}).get('K', std_errs.get('K', 0))
            th_err = std_errs.get('Th', 0)
        else:
            # Fallback to merged coefficients
            ra = coeffs.get('Ra', 0)
            k = coeffs.get('K', 0)
            th = coeffs.get('Th', 0)
            ra_err = std_errs.get('Ra', 0)
            k_err = std_errs.get('K', 0)
            th_err = std_errs.get('Th', 0)
    else:
        # Standard analysis
        ra = coeffs.get('Ra', 0)
        k = coeffs.get('K', 0)
        th = coeffs.get('Th', 0)
        ra_err = std_errs.get('Ra', 0)
        k_err = std_errs.get('K', 0)
        th_err = std_errs.get('Th', 0)
    
    return ra, k, th, ra_err, k_err, th_err


def format_activity_result(activity, uncertainty, precision=2):
    """
    Format activity result with uncertainty.
    
    Args:
        activity: Activity value
        uncertainty: Uncertainty value
        precision: Decimal places for rounding
        
    Returns:
        str: Formatted string like "123.45 ± 5.67"
    """
    if activity is None or uncertainty is None:
        return "N/A"
    
    return f"{activity:.{precision}f} ± {uncertainty:.{precision}f}"


def calculate_detection_limit(background_cps, efficiency, live_time, confidence_level=3.0):
    """
    Calculate minimum detectable activity (MDA).
    
    Args:
        background_cps: Background count rate (CPS)
        efficiency: Detection efficiency (counts/Bq)
        live_time: Measurement live time (s)
        confidence_level: Number of standard deviations (default 3σ)
        
    Returns:
        float: MDA in Bq
    """
    if efficiency == 0 or live_time == 0:
        return np.inf
    
    # MDA = (confidence_level × sqrt(bg_counts)) / (efficiency × live_time)
    bg_counts = background_cps * live_time
    mda = (confidence_level * np.sqrt(bg_counts)) / (efficiency * live_time)
    
    return mda


def compile_results_dynamic(X, y, method_name, func, component_names):
    """
    Compile regression results with dynamic component names.
    
    Args:
        X: Design matrix
        y: Response vector
        method_name: Name of regression method
        func: Regression function (e.g., ols, nnls_detailed)
        component_names: List of component names for coefficients
        
    Returns:
        dict: Compiled results with named coefficients
    """
    results = func(X, y)
    return {
        "Method": method_name,
        "Coefficients": dict(zip(component_names, results["coefficients"])),
        "Std Errors": dict(zip(component_names, results["std_errors"])),
        "P Values": dict(zip(component_names, results["p_values"])),
        "R^2": results["R^2"],
        "Adjusted R^2": results["Adjusted R^2"]
    }
