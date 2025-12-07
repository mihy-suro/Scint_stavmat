"""
Callback registration for all modules
"""

from .data_loading import register_data_loading_callbacks
from .calibration import register_calibration_callbacks
from .analysis import register_analysis_callbacks
from .visualization import register_visualization_callbacks
from .results import register_results_callbacks


def register_all_callbacks(app):
    """Register all callbacks from different modules"""
    register_data_loading_callbacks(app)
    register_calibration_callbacks(app)
    register_analysis_callbacks(app)
    register_visualization_callbacks(app)
    register_results_callbacks(app)
