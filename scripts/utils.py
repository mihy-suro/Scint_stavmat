import numpy as np
import pandas as pd
import plotly.express as px
import warnings
from sklearn.linear_model import LinearRegression
from scipy.optimize import nnls, minimize, dual_annealing
from scipy.stats import norm
import statsmodels.api as sm

# Energy calculation (DISPLAY ONLY - not for computation!)
def calculate_display_energy(channel, display_calib):
    """Calculate energy from channel for DISPLAY purposes only.
    
    WARNING: Use this ONLY for axis labels, tooltips, and user info.
    Do NOT use in computational pipelines (rebinning, ROI masking, etc.).
    
    Args:
        channel: Channel number(s) - int, float, or array
        display_calib: [a0, a1, a2] energy calibration coefficients
    
    Returns:
        Energy in keV
    """
    return sum(c * channel**i for i, c in enumerate(display_calib))

# Legacy alias for backward compatibility
def calculate_energy(channel, calib_coeffs):
    """DEPRECATED: Use calculate_display_energy() instead."""
    return calculate_display_energy(channel, calib_coeffs)

def rebin_spectrum(ref_calib, true_calib, counts):
    """Rebin a spectrum using reference and true calibration coefficients.
    
    Converts spectrum from true_calib binning to ref_calib binning while conserving total counts.
    Key: Interpolates spectral DENSITY (counts/keV), not raw counts.
    """
    num_channels = len(counts)
    
    # Channel arrays
    channels = np.arange(num_channels + 1, dtype=np.float64)
    channels_centers = np.arange(num_channels, dtype=np.float64)
    
    # Reference bin edges (where we're rebinning TO)
    E_ref_edges = np.polyval(ref_calib[::-1], channels)
    
    # True energy edges and centers (where spectrum IS)
    E_true_edges = np.polyval(true_calib[::-1], channels)
    E_true_centers = (E_true_edges[:-1] + E_true_edges[1:]) / 2
    
    # Calculate true bin widths
    true_bin_widths = np.diff(E_true_edges)
    
    # Convert counts to spectral density [counts/keV]
    # This is the key: we need to interpolate density, not counts!
    density = counts / true_bin_widths
    
    rebinned_spectrum = np.zeros(num_channels, dtype=np.float64)
    
    for i in range(num_channels):
        E_lower = E_ref_edges[i]
        E_upper = E_ref_edges[i + 1]
        
        if E_upper - E_lower == 0:
            continue
            
        # Fine grid for trapezoidal integration
        Etrap = np.linspace(E_lower, E_upper, num=100)
        
        # Interpolate DENSITY (not counts!)
        density_interp = np.interp(Etrap, E_true_centers, density)
        
        # Integrate density to get total counts in new bin
        rebinned_spectrum[i] = np.trapz(density_interp, Etrap)
    
    return rebinned_spectrum

def rebin_channels(mapping, sample_counts, n_ref_channels=2048):
    """Rebin spectrum from sample channel indexing to reference channel indexing.
    
    This is the CHANNEL-CENTRIC version of rebinning. Uses channel-to-channel
    mapping instead of energy calibrations.
    
    Args:
        mapping: [a0, a1] where ch_ref = a0 + a1 * ch_sample
        sample_counts: Sample spectrum counts (array)
        n_ref_channels: Number of channels in reference grid (default 2048)
    
    Returns:
        rebinned_counts: Spectrum rebinned to reference channel indices
    
    Algorithm:
        For each reference channel i:
            1. Calculate corresponding sample channel: ch_s = (i - a0) / a1
            2. If ch_s out of bounds: rebinned[i] = 0
            3. If ch_s is integer: rebinned[i] = sample[ch_s]
            4. If ch_s is fractional: linear interpolation
        
        Conservation: sum(rebinned) ≈ sum(sample) within 1%
    """
    a0, a1 = mapping[0], mapping[1]
    n_sample = len(sample_counts)
    
    rebinned = np.zeros(n_ref_channels, dtype=np.float64)
    
    for i in range(n_ref_channels):
        # Inverse mapping: find sample channel for this ref channel
        ch_sample = (i - a0) / a1
        
        # Out of bounds check
        if ch_sample < 0 or ch_sample >= n_sample:
            rebinned[i] = 0
            continue
        
        # Integer channel - direct copy
        if abs(ch_sample - round(ch_sample)) < 1e-10:
            ch_int = int(round(ch_sample))
            if 0 <= ch_int < n_sample:
                rebinned[i] = sample_counts[ch_int]
        else:
            # Fractional channel - linear interpolation
            ch_floor = int(np.floor(ch_sample))
            ch_ceil = int(np.ceil(ch_sample))
            
            if ch_ceil >= n_sample:
                ch_ceil = n_sample - 1
            
            if ch_floor < 0:
                ch_floor = 0
            
            frac = ch_sample - ch_floor
            rebinned[i] = (1 - frac) * sample_counts[ch_floor] + frac * sample_counts[ch_ceil]
    
    return rebinned

def find_optimal_channel_mapping(X_ref, sample_counts, initial_mapping, roi_channels=None, method="L-BFGS-B", maxiter=1000):
    """Find optimal channel-to-channel mapping to maximize R².
    
    This is the CHANNEL-CENTRIC version of calibration optimization.
    Finds [a0, a1] mapping instead of energy calibration coefficients.
    
    Args:
        X_ref: Calibration matrix [N_ref × 3] on reference channels
        sample_counts: Sample spectrum [N_sample] on sample channels
        initial_mapping: [a0, a1] initial guess for ch_ref = a0 + a1*ch_sample
        roi_channels: [ch_min, ch_max] or None (if None, uses full spectrum)
        method: Optimization method (L-BFGS-B, Powell, Nelder-Mead)
        maxiter: Maximum iterations
    
    Returns:
        optimal_mapping: [a0, a1]
        result_dict: {'success', 'iterations', 'final_r2', 'method', 'converged'}
    """
    iteration_count = [0]
    n_ref_channels = len(X_ref)
    
    def objective(mapping):
        # Rebin sample to reference grid
        rebinned = rebin_channels(mapping, sample_counts, n_ref_channels)
        
        # Apply ROI mask if provided
        if roi_channels is not None:
            ch_min, ch_max = roi_channels
            mask = (np.arange(n_ref_channels) >= ch_min) & (np.arange(n_ref_channels) <= ch_max)
            X_fit = X_ref[mask]
            y_fit = rebinned[mask]
        else:
            X_fit = X_ref
            y_fit = rebinned
        
        # Fit and calculate R²
        model = LinearRegression(fit_intercept=False)
        model.fit(X_fit, y_fit)
        r2 = model.score(X_fit, y_fit)
        
        iteration_count[0] += 1
        roi_info = f" (ROI ch {roi_channels[0]}-{roi_channels[1]})" if roi_channels else ""
        print(f"Iteration {iteration_count[0]}: mapping={mapping}, R²={r2:.6f}{roi_info}")
        
        return -r2  # Minimize negative R²
    
    # Bounds: a0 within ±50 channels, a1 within 0.9-1.1 (±10% gain)
    a0_bounds = (initial_mapping[0] - 50, initial_mapping[0] + 50)
    a1_bounds = (0.9, 1.1)
    bounds = [a0_bounds, a1_bounds]
    
    if method == "L-BFGS-B":
        result = minimize(
            objective,
            initial_mapping,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": maxiter}
        )
    elif method == "Powell":
        result = minimize(
            objective,
            initial_mapping,
            method="Powell",
            bounds=bounds,
            options={"maxiter": maxiter}
        )
    elif method == "Nelder-Mead":
        warnings.warn("Nelder-Mead does not support bounds. Using L-BFGS-B instead.", UserWarning)
        result = minimize(
            objective,
            initial_mapping,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": maxiter}
        )
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    result_dict = {
        'success': result.success,
        'message': result.message if hasattr(result, 'message') else str(result),
        'iterations': iteration_count[0],
        'final_r2': -result.fun,
        'method': method,
        'converged': result.success
    }
    
    return result.x, result_dict

def find_optimal_calibration(ref_calib, initial_true_calib, X, sample_spectrum, bounds, method="L-BFGS-B", maxiter=1000, roi_mask=None):
    """Find optimal calibration coefficients for the sample spectrum to maximize R^2.
    
    Args:
        ref_calib: Reference calibration coefficients
        initial_true_calib: Initial guess for calibration coefficients
        X: Predictor matrix
        sample_spectrum: Sample spectrum counts
        bounds: Bounds for optimization
        method: Optimization method
        maxiter: Maximum iterations
        roi_mask: Optional boolean mask for ROI region (if None, uses full spectrum)
    
    Returns:
        tuple: (optimized_coefficients, result_dict)
    """
    iteration_count = [0]  # Mutable container for closure
    
    def objective(true_calib):
        rebinned_spectrum = rebin_spectrum(ref_calib, true_calib, sample_spectrum)
        
        # Apply ROI mask if provided
        if roi_mask is not None:
            X_masked = X[roi_mask]
            y_masked = rebinned_spectrum[roi_mask]
        else:
            X_masked = X
            y_masked = rebinned_spectrum
        
        model = LinearRegression(fit_intercept=False)
        model.fit(X_masked, y_masked)
        r2_score = model.score(X_masked, y_masked)
        
        iteration_count[0] += 1
        roi_info = f" (ROI)" if roi_mask is not None else ""
        print(f"Current coefficients: {true_calib}, Current R^2{roi_info}: {r2_score}")
        
        return -r2_score  # Minimize negative R^2

    if method == "L-BFGS-B":
        result = minimize(
            objective,
            initial_true_calib,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": maxiter},
        )
    elif method == "Powell":
        result = minimize(
            objective,
            initial_true_calib,
            method="Powell",
            bounds=bounds,
            options={"maxiter": maxiter},
        )
    elif method == "Nelder-Mead":
        if bounds is not None:
            warnings.warn("Nelder-Mead does not support bounds. Ignoring bounds.", UserWarning)
        result = minimize(
            objective,
            initial_true_calib,
            method="Nelder-Mead",
            options={"maxiter": maxiter},
        )
    elif method == "Dual Annealing":
        result = dual_annealing(
            objective,
            bounds=bounds,
            maxiter=maxiter,
            seed=42,  # Optional, for reproducibility
        )
    else:
        raise ValueError(f"Unsupported optimization method: {method}")

    # Create result dictionary
    result_dict = {
        'success': result.success,
        'message': result.message if hasattr(result, 'message') else str(result),
        'iterations': iteration_count[0],
        'final_r2': -result.fun,  # Convert back from negative
        'method': method,
        'converged': result.success
    }

    return result.x, result_dict

# Regression methods
def ols(X, y):
    # Apply Poisson noise correction to y only
    y_corrected = y / np.sqrt(np.maximum(y, 1))

    # Fit the model using statsmodels without adding a constant (no intercept)
    model = sm.OLS(y_corrected, X).fit()

    # Extract regression results
    return {
        "coefficients": model.params,
        "std_errors": model.bse,
        "p_values": model.pvalues,
        "R^2": model.rsquared,
        "Adjusted R^2": model.rsquared_adj,
        "summary": model.summary().as_text()
    }


def nnls_detailed(X, y, num_bootstrap=100):
    """Perform Non-Negative Least Squares (NNLS) regression with detailed statistics."""
    # Apply Poisson noise correction
    y_corrected = y / np.sqrt(np.maximum(y, 1))
    X_corrected = X / np.sqrt(np.maximum(X, 1))

    # Solve NNLS
    coef, _ = nnls(X_corrected, y_corrected)
    residuals = y_corrected - X_corrected @ coef
    r2 = 1 - np.sum(residuals**2) / np.sum((y_corrected - np.mean(y_corrected))**2)
    n, p = X_corrected.shape
    r2_adj = 1 - (1 - r2) * (n - 1) / (n - p - 1)

    # Bootstrapping for standard errors
    coef_bootstrap = []
    for _ in range(num_bootstrap):
        indices = np.random.choice(len(y_corrected), len(y_corrected), replace=True)
        X_sample = X_corrected[indices]
        y_sample = y_corrected[indices]
        coef_sample, _ = nnls(X_sample, y_sample)
        coef_bootstrap.append(coef_sample)

    coef_bootstrap = np.array(coef_bootstrap)
    std_errors = coef_bootstrap.std(axis=0)
    
    # Prevent division by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        t_stats = np.where(std_errors != 0, coef / std_errors, 0)
    
    p_values = [2 * (1 - norm.cdf(np.abs(t))) for t in t_stats]

    return {
        "coefficients": coef,
        "std_errors": std_errors,
        "p_values": p_values,
        "R^2": r2,
        "Adjusted R^2": r2_adj
    }


# Compile regression results
def compile_results(X, y, method_name, func):
    results = func(X, y)
    return {
        "Method": method_name,
        "Coefficients": dict(zip(["Ra", "K", "Th"], results["coefficients"])),
        "Std Errors": dict(zip(["Ra", "K", "Th"], results["std_errors"])),
        "P Values": dict(zip(["Ra", "K", "Th"], results["p_values"])),
        "R^2": results["R^2"],
        "Adjusted R^2": results["Adjusted R^2"]
    }

def create_summary_table(results, sample_name):
    """Create a summary table from regression results."""
    summary = []
    for result in results:
        row = {
            "Sample": sample_name,
            "Method": result["Method"],
            **result["Coefficients"],
            "R^2": result["R^2"],
            "Adjusted R^2": result["Adjusted R^2"],
        }
        summary.append(row)
    return pd.DataFrame(summary)

# Spectrum preprocessing functions
def normalize_by_live_time(df, live_time):
    """Normalize each spectrum column by its respective live time."""
    spectrum_columns = df.columns[1:]
    if len(spectrum_columns) != len(live_time):
        raise ValueError("Number of live time values does not match the number of spectrum columns.")

    for col, lt in zip(spectrum_columns, live_time):
        df[col] = df[col] / lt

    return df

def subtract_background(sample_df, background_df):
    """Subtract background spectrum from each sample spectrum."""
    for col in sample_df.columns[1:]:
        sample_df[col] -= background_df.iloc[:, 1].values
    return sample_df

# Plotting functions
def plot_spectrum(sample_name, sample_y, X, models, ref_calib, background=None):
    data = []

    # Calculate energy values based on reference calibration
    energies = [calculate_energy(ch, ref_calib) for ch in range(len(sample_y))]

    # Add actual sample spectrum
    data.append(pd.DataFrame({
        "Energy": energies,
        "Channel": range(len(sample_y)),
        "Intensity": sample_y,
        "Type": f"{sample_name} (Actual)"
    }))

    # Add fitted spectra for each model
    for model in models:
        method = model["Method"]
        coefficients = np.array(list(model["Coefficients"].values()))  # Extract coefficients dynamically
        fitted_y = X @ coefficients  # Calculate the fitted spectrum
        data.append(pd.DataFrame({
            "Energy": energies,
            "Channel": range(len(fitted_y)),
            "Intensity": fitted_y,
            "Type": f"Fitted ({method})"
        }))

    # Add background spectrum if provided
    if background is not None:
        data.append(pd.DataFrame({
            "Energy": energies,
            "Channel": range(len(background)),
            "Intensity": background,
            "Type": "Background"
        }))

    # Combine all data into a single DataFrame
    plot_data = pd.concat(data)

    # Plot using Plotly Express
    fig = px.line(
        plot_data,
        x="Energy",
        y="Intensity",
        color="Type",
        title=f"Spectrum and Fitted Spectra ({sample_name})",
        labels={"Energy": "Energy (keV)", "Intensity": "Intensity"},
        hover_data={"Channel": True, "Energy": ":.2f"}
    )

    # Show the plot
    fig.show()



def plot_calibration_spectra(calib_df, ref_calib):
    """Plot calibration spectra normalized to probability density."""
    data = []
    for column in ["Ra", "K", "Th"]:
        energies = calib_df["CHNL"].apply(lambda ch: calculate_energy(ch, ref_calib))
        total_counts = calib_df[column].sum()
        normalized_intensity = calib_df[column] / total_counts
        data.append(pd.DataFrame({
            "Energy": energies,
            "Channel": calib_df["CHNL"],
            "Intensity": normalized_intensity,
            "Type": f"Calibration ({column})"
        }))

    plot_data = pd.concat(data)
    fig = px.line(plot_data, x="Energy", y="Intensity", color="Type",
                  title="Calibration Spectra (Normalized to Probability Density)",
                  labels={"Energy": "Energy (keV)", "Intensity": "Probability Density"},
                  hover_data={"Channel": True, "Energy": ":.2f"})
    fig.show()


def parse_spe_file(content_string):
    """Parse SPE file format and extract metadata and channel data.
    
    Args:
        content_string: Decoded string content of SPE file
        
    Returns:
        dict with keys: SIDENT, ELIVE, ECOFFSET, ECSLOPE, ECQUAD, CHANNELS, channels (list)
        
    Raises:
        ValueError: If required tags are missing or format is invalid
    """
    lines = content_string.strip().split('\n')
    result = {
        'SIDENT': None,
        'ELIVE': None,
        'ECOFFSET': None,
        'ECSLOPE': None,
        'ECQUAD': None,
        'CHANNELS': None,
        'channels': []
    }
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Parse SPEC_ID (sample name on next line)
        if line.startswith('$SPEC_ID:'):
            if i + 1 < len(lines):
                result['SIDENT'] = lines[i + 1].strip()
                i += 2
                continue
        
        # Parse MEAS_TIM (first number is ELIVE)
        elif line.startswith('$MEAS_TIM:'):
            if i + 1 < len(lines):
                meas_line = lines[i + 1].strip().split()
                if len(meas_line) >= 1:
                    result['ELIVE'] = float(meas_line[0])
                i += 2
                continue
        
        # Parse MCA_CAL (calibration coefficients)
        elif line.startswith('$MCA_CAL:'):
            if i + 2 < len(lines):
                # Skip the "3" line, read coefficients from next line
                cal_line = lines[i + 2].strip().split()
                if len(cal_line) >= 3:
                    result['ECOFFSET'] = float(cal_line[0])
                    result['ECSLOPE'] = float(cal_line[1])
                    result['ECQUAD'] = float(cal_line[2])
                i += 3
                continue
        
        # Parse DATA section
        elif line.startswith('$DATA:'):
            if i + 1 < len(lines):
                # Parse "0 N" to get number of channels
                data_header = lines[i + 1].strip().split()
                if len(data_header) >= 2:
                    max_channel = int(data_header[1])
                    result['CHANNELS'] = max_channel + 1
                    
                    # Read channel data
                    j = i + 2
                    while j < len(lines) and len(result['channels']) < result['CHANNELS']:
                        data_line = lines[j].strip()
                        
                        # Stop at next tag or ROI section
                        if data_line.startswith('$'):
                            break
                        
                        # Parse counts (one per line in SPE format)
                        if data_line:
                            try:
                                result['channels'].append(int(data_line))
                            except ValueError:
                                break
                        j += 1
                    
                    i = j
                    continue
        
        i += 1
    
    # Validate required fields
    # SIDENT is optional - will be set from filename if missing
    if result['CHANNELS'] is None:
        raise ValueError("Missing $DATA: tag in SPE file")
    if result['ECOFFSET'] is None or result['ECSLOPE'] is None:
        raise ValueError("Missing or incomplete $MCA_CAL: tag in SPE file")
    
    # Pad channels if incomplete
    if len(result['channels']) < result['CHANNELS']:
        result['channels'].extend([0] * (result['CHANNELS'] - len(result['channels'])))
    
    return result
