"""
Visualization callbacks - main entry point and ROI slider synchronization
"""

from .utils import *
from .visualization_full_spectrum import register_full_spectrum_callbacks
from .visualization_roi import register_roi_callbacks
from .visualization_186peak import register_186peak_callbacks


def register_visualization_callbacks(app):
    """Register all visualization callbacks"""
    
    # ==================== ROI SLIDER SYNC ====================
    @app.callback(
        [Output('roi1-range', 'data'),
         Output('roi2-range', 'data')],
        [Input('roi1-range-slider', 'value'),
         Input('roi2-range-slider', 'value')]
    )
    def sync_roi_sliders(roi1_slider, roi2_slider):
        """Sync RangeSlider values to stores"""
        return roi1_slider, roi2_slider
    
    # Register sub-modules
    register_full_spectrum_callbacks(app)
    register_roi_callbacks(app)
    register_186peak_callbacks(app)
