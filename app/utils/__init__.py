"""
Utility modules for app - business logic, calculations, and helpers.

This package contains pure functions and utilities that are independent
of Dash callbacks and can be tested in isolation.
"""

# Analysis utilities
from .analysis_core import (
    prepare_sample_data,
    build_calibration_matrix,
    perform_single_regression,
    perform_dual_roi_regression,
    package_analysis_results
)

from .channel_processing import (
    optimize_channel_mapping_wrapper,
    rebin_sample_spectrum
)

# Data handling utilities
from .config_loader import (
    load_yaml_config,
    load_calibration_spectra,
    build_calibration_dataframe,
    load_detector_configuration
)

from .spe_handler import (
    decode_spe_upload,
    load_multiple_spe_files,
    merge_spe_into_dataframe,
    clean_background_from_samples
)

from .data_helpers import (
    unpack_excel_data,
    get_sample_data,
    validate_roi_ranges,
    safe_dict_get,
    has_background_data,
    create_channel_mask
)

# UI and display utilities
from .ui_builders import (
    create_status_message,
    create_error_alert,
    create_info_badge,
    create_loading_message
)

from .results_calculations import (
    calculate_activity_index,
    calculate_index_uncertainty,
    extract_coefficients_from_results,
    format_activity_result,
    compile_results_dynamic
)

# Plotting utilities
from .plot_builders import (
    create_spectrum_figure,
    add_sample_trace,
    add_fit_trace,
    add_component_trace,
    add_roi_components,
    add_calibration_markers,
    add_roi_overlay,
    configure_spectrum_layout,
    create_placeholder_figure,
    create_error_figure
)

from .plot_components import (
    create_roi_plot,
    create_residuals_plot,
    calculate_display_energy
)

# Peak analysis for Ra-226 @ 186 keV
from .peak_analysis import (
    calculate_ra226_from_186kev_peak,
    find_peak_in_roi,
    calculate_net_area,
    smooth_spectrum,
    energy_to_channel
)

__all__ = [
    # Analysis
    'prepare_sample_data',
    'build_calibration_matrix',
    'perform_single_regression',
    'perform_dual_roi_regression',
    'package_analysis_results',
    'optimize_channel_mapping_wrapper',
    'rebin_sample_spectrum',
    
    # Data handling
    'load_yaml_config',
    'load_calibration_spectra',
    'build_calibration_dataframe',
    'load_detector_configuration',
    'decode_spe_upload',
    'load_multiple_spe_files',
    'merge_spe_into_dataframe',
    'clean_background_from_samples',
    'unpack_excel_data',
    'get_sample_data',
    'validate_roi_ranges',
    'safe_dict_get',
    'has_background_data',
    
    # UI
    'create_status_message',
    'create_error_alert',
    'create_info_badge',
    'create_loading_message',
    
    # Results
    'calculate_activity_index',
    'calculate_index_uncertainty',
    'extract_coefficients_from_results',
    'format_activity_result',
    'compile_results_dynamic',
    
    # Plotting
    'create_roi_plot',
    'create_residuals_plot',
    'calculate_display_energy',
    'create_spectrum_figure',
    'add_sample_trace',
    'add_fit_trace',
    'add_component_trace',
    'add_roi_components',
    'add_calibration_markers',
    'add_roi_overlay',
    'configure_spectrum_layout',
    'create_placeholder_figure',
    'create_error_figure',
    
    # Peak analysis
    'calculate_ra226_from_186kev_peak',
    'find_peak_in_roi',
    'calculate_net_area',
    'smooth_spectrum',
    'energy_to_channel',
]
