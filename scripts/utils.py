import numpy as np
import pandas as pd
import plotly.express as px
import warnings
from sklearn.linear_model import LinearRegression
from scipy.optimize import nnls, minimize, dual_annealing
from scipy.stats import norm
import statsmodels.api as sm

# Rebinning functions
def calculate_energy(channel, calib_coeffs):
    """Calculate energy from channel using polynomial calibration coefficients."""
    return sum(c * channel**i for i, c in enumerate(calib_coeffs))

def rebin_spectrum(ref_calib, true_calib, counts):
    """Rebin a spectrum using reference and true calibration coefficients."""
    num_channels = len(counts)
    rebinned_spectrum = []

    for i in range(num_channels):
        if i == num_channels - 1:
            E_lower = calculate_energy(i, ref_calib)
            E_upper = calculate_energy(i + 1, ref_calib)
        else:
            E_lower = calculate_energy(i, ref_calib)
            E_upper = calculate_energy(i + 1, ref_calib)

        Etrap = np.linspace(E_lower, E_upper, num=1000)
        E_true = np.array([calculate_energy(channel, true_calib) for channel in range(num_channels)], dtype=np.float64)
        integrand = np.interp(Etrap, E_true, counts)
        bin_width = E_upper - E_lower
        rebinned_value = np.trapz(integrand, Etrap) / bin_width if bin_width != 0 else 0

        rebinned_spectrum.append(rebinned_value)

    return np.array(rebinned_spectrum, dtype=np.float64)

def find_optimal_calibration(ref_calib, initial_true_calib, X, sample_spectrum, bounds, method="L-BFGS-B", maxiter=1000, progress_callback=None):
    """Find optimal calibration coefficients for the sample spectrum to maximize R^2.
    
    Args:
        ref_calib: Reference calibration coefficients
        initial_true_calib: Initial guess for calibration coefficients
        X: Predictor matrix
        sample_spectrum: Sample spectrum counts
        bounds: Bounds for optimization
        method: Optimization method
        maxiter: Maximum iterations
        progress_callback: Optional callback function(iteration, r2, coeffs)
    
    Returns:
        tuple: (optimized_coefficients, result_dict)
    """
    iteration_count = [0]  # Mutable container for closure
    
    def objective(true_calib):
        rebinned_spectrum = rebin_spectrum(ref_calib, true_calib, sample_spectrum)
        model = LinearRegression(fit_intercept=False)
        model.fit(X, rebinned_spectrum)
        r2_score = model.score(X, rebinned_spectrum)
        
        iteration_count[0] += 1
        print(f"Current coefficients: {true_calib}, Current R^2: {r2_score}")
        
        # Call progress callback if provided
        if progress_callback is not None:
            try:
                progress_callback(iteration_count[0], r2_score, true_calib.tolist())
            except Exception as e:
                print(f"Progress callback error: {e}")
        
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
