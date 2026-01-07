"""
ROI visualization - deconvolution analysis plots for Ra/Th and K-40 regions
"""

from .utils import *


def register_roi_callbacks(app):
    """Register ROI and residuals visualization callbacks"""
    
    # ==================== ROI #1 PLOT (Ra/Th) ====================
    @app.callback(
        Output('spectrum-plot-roi1', 'figure'),
        [Input('sample-results', 'data'),
         Input('roi1-range', 'data')],
        [State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value')]
    )
    def update_plot_roi1(results, roi1_range, ref_a0, ref_a1, ref_a2):
        """Update ROI #1 plot - CHANNEL-CENTRIC: zoomed Ra/Th region with fit and components"""
        ref_calib = [ref_a0, ref_a1, ref_a2]
        return create_roi_plot(results, roi_num=1, roi_range=roi1_range, 
                              ref_calib=ref_calib, emphasis='Ra/Th')
    
    
    # ==================== ROI #2 PLOT (K-40) ====================
    @app.callback(
        Output('spectrum-plot-roi2', 'figure'),
        [Input('sample-results', 'data'),
         Input('roi2-range', 'data')],
        [State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value')]
    )
    def update_plot_roi2(results, roi2_range, ref_a0, ref_a1, ref_a2):
        """Update ROI #2 plot - CHANNEL-CENTRIC: zoomed K-40 region with fit and components"""
        ref_calib = [ref_a0, ref_a1, ref_a2]
        return create_roi_plot(results, roi_num=2, roi_range=roi2_range, 
                              ref_calib=ref_calib, emphasis='K')
    
    
    # ==================== ROI #1 RESIDUALS PLOT ====================
    @app.callback(
        Output('residuals-plot-roi1', 'figure'),
        [Input('sample-results', 'data'),
         Input('roi1-range', 'data'),
         Input('spectrum-plot-roi1', 'relayoutData')],
        [State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value')]
    )
    def update_residuals_roi1(results, roi1_range, relayout_data, ref_a0, ref_a1, ref_a2):
        """Display relative residuals for ROI #1 with zoom sync - CHANNEL-CENTRIC"""
        ref_calib = [ref_a0, ref_a1, ref_a2]
        return create_residuals_plot(results, roi_num=1, roi_range=roi1_range, 
                                    ref_calib=ref_calib, relayout_data=relayout_data)
    
    
    # ==================== ROI #2 RESIDUALS PLOT ====================
    @app.callback(
        Output('residuals-plot-roi2', 'figure'),
        [Input('sample-results', 'data'),
         Input('roi2-range', 'data'),
         Input('spectrum-plot-roi2', 'relayoutData')],
        [State('ref-a0', 'value'),
         State('ref-a1', 'value'),
         State('ref-a2', 'value')]
    )
    def update_residuals_roi2(results, roi2_range, relayout_data, ref_a0, ref_a1, ref_a2):
        """Display relative residuals for ROI #2 with zoom sync - CHANNEL-CENTRIC"""
        ref_calib = [ref_a0, ref_a1, ref_a2]
        return create_residuals_plot(results, roi_num=2, roi_range=roi2_range, 
                                    ref_calib=ref_calib, relayout_data=relayout_data)
