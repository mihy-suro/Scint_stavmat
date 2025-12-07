import pandas as pd
import plotly.io as pio
import numpy as np
from pathlib import Path
from utils import (
    plot_calibration_spectra,
    rebin_spectrum,
    find_optimal_calibration,
    ols,
    nnls_detailed,
    compile_results,
    create_summary_table,
    plot_spectrum,
    normalize_by_live_time,
    subtract_background,
)
import statsmodels.api as sm


# Configure Plotly to render in the browser
pio.renderers.default = "browser"

# Load calibration data
file_path = Path(__file__).parent.parent / "Spektra - CeBr.xlsx"
sheet_name = "CeBr EFF"
calib_data = pd.ExcelFile(file_path)
calib_df = pd.read_excel(
    calib_data, sheet_name=sheet_name, skiprows=11, header=None
)
calib_df.columns = ["Channel"] + list(calib_data.parse(sheet_name).iloc[0, 1:].values)
calib_df["Channel"] = calib_df["Channel"].astype(int)

calib_df.columns = ["CHNL", "Ra", "K", "Th"]


# Normalize calibration spectra to express probability density
for column in ["Ra", "K", "Th"]:
    total_counts = calib_df[column].sum()
    calib_df[column] = calib_df[column] / total_counts
    
    
# Load sample data
sheet_name = "CeBr vzorky"
sample_data = pd.ExcelFile(file_path)
sample_df = pd.read_excel(
    sample_data, sheet_name=sheet_name, skiprows=11, header=None
)
sample_df.columns = ["Channel"] + list(sample_data.parse(sheet_name).iloc[0, 1:].values)
sample_df["Channel"] = sample_df["Channel"].astype(int)

# Adjust column structure for CHNL, SAMP1, and SAMP2
sample_df = sample_df.iloc[:, :3]
sample_df.columns = ["CHNL", "SAMP1", "SAMP2"]

# Load background data
sheet_name = "CeBr pozadí"
background_df = pd.read_excel(
    file_path, sheet_name=sheet_name, skiprows=11, header=None
)
background_df.columns = ["Channel"] + list(background_df.iloc[0, 1:].values)
background_df["Channel"] = background_df["Channel"].astype(int)
background_df.columns = ["CHNL", "BG"]

# Read live times for samples
sample_live_time = sample_data.parse(sheet_name="CeBr vzorky").iloc[2, 1:3].values.astype(float)

# Read live time for background (assuming only one background column)
background_live_time = sample_data.parse(sheet_name="CeBr pozadí").iloc[2, 1:].values.astype(float)

# Normalize spectra to counts-per-second (CPS)
sample_df = normalize_by_live_time(sample_df, sample_live_time)
background_df = normalize_by_live_time(background_df, background_live_time)

# Subtract background from samples
sample_df = subtract_background(sample_df, background_df)

# Zero first 150 channels of sample and calibration spectra
cut = 150
calib_df.loc[calib_df["CHNL"] <= cut, ["Ra", "K", "Th"]] = 0
sample_df.loc[sample_df["CHNL"] <= cut, ["SAMP1", "SAMP2"]] = 0
background_df.loc[sample_df["CHNL"] <= cut, ["BG"]] = 0

# Define calibration coefficients and bounds
ref_calib = [9.6229, 1.3793, 0]  # Example: Reference calibration coefficients
initial_true_calib = ref_calib  # Starting coefficients for optimization
bounds = [(5, 15), (1.35, 1.45), (0, 1E-5)]  # Example bounds for calibration coefficients

# Flag for whether to optimize calibration coefficients
optimize_coefficients = False  # Set to False to use manually supplied coefficients
optimization_method = "L-BFGS-B"  # Options: "L-BFGS-B", "Powell", "Nelder-Mead", "Dual Annealing"

if optimize_coefficients:
    # Optimize calibration coefficients for SAMP1
    optimal_calib_samp1 = find_optimal_calibration(
        ref_calib,
        initial_true_calib,
        calib_df[["Ra", "K", "Th"]].values,
        sample_df["SAMP1"].values,
        bounds[:len(ref_calib)],
        method=optimization_method,
    )
    print(f"Optimized coefficients for SAMP1: {optimal_calib_samp1}")

    # Use the same optimization for SAMP2
    optimal_calib_samp2 = optimal_calib_samp1
else:
    # Manually supply calibration coefficients
    optimal_calib_samp1 = [9.62228359, 1.37495787]  # Example manually supplied coefficients
    optimal_calib_samp2 = optimal_calib_samp1
    print(f"Using manually supplied coefficients for SAMP1 and SAMP2: {optimal_calib_samp1}")

# Rebin the sample spectra using the chosen coefficients
sample_df["SAMP1"] = rebin_spectrum(ref_calib, optimal_calib_samp1, sample_df["SAMP1"].values)
sample_df["SAMP2"] = rebin_spectrum(ref_calib, optimal_calib_samp2, sample_df["SAMP2"].values)

# Run regression for SAMP1 and SAMP2
methods = [
    ("OLS", ols),
    ("NNLS", nnls_detailed),
]

results_samp1 = [
    compile_results(
        calib_df[["Ra", "K", "Th"]].values,
        sample_df["SAMP1"].values,
        method_name,
        func,
    )
    for method_name, func in methods
]

results_samp2 = [
    compile_results(
        calib_df[["Ra", "K", "Th"]].values,
        sample_df["SAMP2"].values,
        method_name,
        func,
    )
    for method_name, func in methods
]


# Create summary tables
summary_samp1 = create_summary_table(results_samp1, "SAMP1")
summary_samp2 = create_summary_table(results_samp2, "SAMP2")

# Print results
print("SAMP1 Regression Summary")
print(summary_samp1.to_string(index=False))

print("\nSAMP2 Regression Summary")
print(summary_samp2.to_string(index=False))

# Plot example spectra with fitted models and background
plot_spectrum(
    "SAMP1",
    sample_df["SAMP1"].values,
    calib_df[["Ra", "K", "Th"]].values,
    results_samp1,
    ref_calib,
    background_df["BG"].values
)

plot_spectrum(
    "SAMP2",
    sample_df["SAMP2"].values,
    calib_df[["Ra", "K", "Th"]].values,
    results_samp2,
    ref_calib,
    background_df["BG"].values
)
# Plot calibration spectra
plot_calibration_spectra(calib_df, ref_calib)


# Print detailed OLS summary for SAMP1
calib_df["Ra"] = calib_df["Ra"] / 13.9
calib_df["K"] = calib_df["K"] / 212
calib_df["Th"] = calib_df["Th"] / 7.4

X_samp1 = calib_df[["Ra", "K", "Th"]].values
y_samp1 = sample_df["SAMP1"].values

ols_model_samp1 = sm.OLS(y_samp1, sm.add_constant(X_samp1)).fit()
print("\nDetailed OLS Summary for SAMP1:")
print(ols_model_samp1.summary())


