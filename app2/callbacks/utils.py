"""
Shared utilities and constants for callbacks
"""

from dash import Input, Output, State, html, no_update, dcc, callback_context
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import base64
import io
import plotly.graph_objects as go

from processing import (
    rebin_spectrum,
    find_optimal_calibration,
    ols,
    nnls_detailed,
    compile_results,
    normalize_by_live_time,
    subtract_background,
    calculate_energy,
)


# Constants
CALIBRATION_ENERGIES = [238, 295, 352, 609, 1461, 1764.494, 2614.511]
ENERGY_MAP = {
    'select-e-238': '238',
    'select-e-295': '295',
    'select-e-352': '352',
    'select-e-609': '609',
    'select-e-1461': '1461',
    'select-e-1764': '1764',
    'select-e-2614': '2614'
}


def compile_results_dynamic(X, y, method_name, func, component_names):
    """Compile results with dynamic number of components"""
    results = func(X, y)
    return {
        "Method": method_name,
        "Coefficients": dict(zip(component_names, results["coefficients"])),
        "Std Errors": dict(zip(component_names, results["std_errors"])),
        "P Values": dict(zip(component_names, results["p_values"])),
        "R^2": results["R^2"],
        "Adjusted R^2": results["Adjusted R^2"]
    }


def convert_energy_to_channel(energy, calib_coeffs):
    """Convert energy to channel using calibration coefficients
    
    Args:
        energy: Energy value in keV
        calib_coeffs: List [a0, a1, a2] where E = a0 + a1*CH + a2*CH^2
    
    Returns:
        Channel number (int)
    """
    a0, a1, a2 = calib_coeffs[0], calib_coeffs[1], calib_coeffs[2] if len(calib_coeffs) > 2 else 0
    
    # Linear approximation: CH = (E - a0) / a1
    # For quadratic, would need to solve: a2*CH^2 + a1*CH + (a0 - E) = 0
    if abs(a2) < 1e-8:  # Linear calibration
        return int((energy - a0) / a1)
    else:
        # Quadratic formula
        discriminant = a1**2 - 4*a2*(a0 - energy)
        if discriminant < 0:
            return int((energy - a0) / a1)  # Fallback to linear
        ch = (-a1 + np.sqrt(discriminant)) / (2 * a2)
        return int(ch)
