"""
Data loading callbacks - YAML config and SPE file loading
"""

from .utils import *
import yaml
import os
from pathlib import Path
from dash import no_update, html
import dash_bootstrap_components as dbc

# Import data loading utilities
from utils import (
    load_detector_configuration,
    load_multiple_spe_files,
    create_status_message
)


def register_data_loading_callbacks(app):
    """Register data loading and file upload callbacks"""
    
    # ==================== LOAD DETECTOR CONFIG ====================
    @app.callback(
        [Output('excel-data', 'data'),
         Output('run-analysis', 'disabled', allow_duplicate=True),
         Output('run-analysis-next', 'disabled', allow_duplicate=True),
         Output('ref-a0', 'value'),
         Output('ref-a1', 'value'),
         Output('ref-a2', 'value'),
         Output('manual-a0', 'value'),
         Output('manual-a1', 'value'),
         Output('roi1-range-slider', 'value', allow_duplicate=True),
         Output('roi2-range-slider', 'value', allow_duplicate=True),
         Output('status-log', 'children', allow_duplicate=True)],
        Input('detector-selector', 'value'),
        prevent_initial_call='initial_duplicate'
    )
    def load_detector_config(detector_name):
        """Load detector configuration from YAML and calibration SPE files"""
        if detector_name is None:
            raise PreventUpdate
        
        try:
            # Use utility function to load complete configuration
            config_data = load_detector_configuration(detector_name)
            
            # Extract data
            excel_data = config_data['excel_data']
            display_calib = config_data['display_calib']
            manual_calib = config_data['manual_calib']
            roi_ranges = config_data['roi_ranges']
            status_info = config_data['status_info']
            
            # Build status message
            bg_text = ", BG" if status_info['has_bg'] else ""
            status_msg = html.Div([
                html.Small([
                    html.I(className="fas fa-check-circle text-success me-1"),
                    f"✅ Načtena konfigurace: {status_info['detector_name']}",
                    html.Br(),
                    f"Kalibrační spektra: Ra, K, Th{bg_text} ({status_info['num_channels']} kanálů)",
                    html.Br(),
                    f"Aktivity etalonů: Ra={status_info['activities']['Ra']:.0f} Bq, "
                    f"K={status_info['activities']['K']:.0f} Bq, "
                    f"Th={status_info['activities']['Th']:.0f} Bq",
                    html.Br(),
                    f"ROI #1: kanály {status_info['roi1']['range'][0]}-{status_info['roi1']['range'][1]} "
                    f"(~{status_info['roi1']['kev'][0]:.0f}-{status_info['roi1']['kev'][1]:.0f} keV)",
                    html.Br(),
                    f"ROI #2: kanály {status_info['roi2']['range'][0]}-{status_info['roi2']['range'][1]} "
                    f"(~{status_info['roi2']['kev'][0]:.0f}-{status_info['roi2']['kev'][1]:.0f} keV)"
                ], className="text-success")
            ])
            
            return (
                excel_data,
                True,  # Disable analyze button until sample loaded
                True,  # Disable analyze+next button until sample loaded
                display_calib[0],  # ref-a0
                display_calib[1],  # ref-a1
                display_calib[2],  # ref-a2
                manual_calib[0],   # manual-a0
                manual_calib[1],   # manual-a1
                roi_ranges[0],     # roi1-range
                roi_ranges[1],     # roi2-range
                status_msg
            )
            
        except Exception as e:
            print(f"\n!!! ERROR loading detector config: {str(e)} !!!")
            import traceback
            traceback.print_exc()
            
            error_msg = create_status_message('error', f"Chyba při načítání konfigurace: {str(e)}")
            
            return None, True, True, 9.6229, 1.3793, 0, 9.6229, 1.3793, [200, 800], [700, 1640], error_msg
    
    
    # ==================== UPDATE SAMPLE SELECTOR ====================
    @app.callback(
        Output('sample-selector', 'options'),
        Input('excel-data', 'data')
    )
    def update_sample_selector(data):
        """Update sample dropdown"""
        if data is None:
            return []
        return [{'label': name, 'value': name} for name in data['sample_names']]
    
    
    # ==================== TOGGLE OPTIMIZATION ====================
    @app.callback(
        Output('manual-calibration', 'style'),
        Input('optimize-calibration', 'value')
    )
    def toggle_manual_calib(optimize_value):
        """Show/hide manual calibration inputs"""
        if 'optimize' in optimize_value:
            return {'display': 'none'}
        return {'display': 'block'}
    
    
    # ==================== SPE SAMPLE UPLOAD ====================
    @app.callback(
        [Output('excel-data', 'data', allow_duplicate=True),
         Output('sample-selector', 'options', allow_duplicate=True),
         Output('spe-status', 'children'),
         Output('run-analysis', 'disabled', allow_duplicate=True),
         Output('run-analysis-next', 'disabled', allow_duplicate=True),
         Output('status-log', 'children', allow_duplicate=True)],
        [Input('upload-spe', 'contents'),
         Input('upload-spe', 'filename')],
        State('excel-data', 'data'),
        prevent_initial_call=True
    )
    def load_sample_spe(contents_list, filenames_list, excel_data):
        """Load uploaded SPE sample files into excel_data structure"""
        if not contents_list or not excel_data:
            raise PreventUpdate
        
        # Use utility function to load files
        loaded_samples, errors = load_multiple_spe_files(contents_list, filenames_list, excel_data)
        
        # Build minimal status badge for SPE upload area
        if loaded_samples:
            spe_status = dbc.Badge(
                f"✓ {len(loaded_samples)} vzorků",
                color="success",
                className="mb-1"
            )
        else:
            spe_status = dbc.Badge(
                f"✗ {len(errors)} chyb",
                color="danger",
                className="mb-1"
            )
        
        # Build detailed status message for status-log
        status_lines = []
        if loaded_samples:
            status_lines.extend([
                html.I(className="fas fa-upload text-success me-1"),
                f"✅ Nahráno {len(loaded_samples)} vzorků:",
                html.Br()
            ])
            for sample in loaded_samples[:5]:  # Show first 5
                status_lines.append(f"  • {sample}")
                status_lines.append(html.Br())
            if len(loaded_samples) > 5:
                status_lines.append(f"  ... a {len(loaded_samples) - 5} dalších")
                status_lines.append(html.Br())
        
        if errors:
            status_lines.extend([
                html.I(className="fas fa-exclamation-triangle text-warning me-1"),
                f"⚠️ {len(errors)} chyb:",
                html.Br()
            ])
            for err in errors[:3]:  # Show first 3 errors
                status_lines.append(f"  • {err}")
                status_lines.append(html.Br())
            if len(errors) > 3:
                status_lines.append(f"  ... a {len(errors) - 3} dalších")
                status_lines.append(html.Br())
        
        status_msg = html.Div([
            html.Small(status_lines, className="text-muted")
        ])
        
        # Update dropdown options
        new_options = [{'label': name, 'value': name} for name in excel_data['sample_names']]
        
        # Enable analyze button if we have samples
        enable_analysis = len(excel_data['sample_names']) > 0
        
        return excel_data, new_options, spe_status, not enable_analysis, not enable_analysis, status_msg
    
    
    
    
    
    # ==================== ENABLE/DISABLE NAVIGATION BUTTONS ====================
    @app.callback(
        [Output('previous-sample-button', 'disabled'),
         Output('next-sample-button', 'disabled')],
        [Input('sample-selector', 'value'),
         Input('sample-selector', 'options')]
    )
    def update_navigation_buttons(selected_sample, sample_options):
        """Enable/disable previous and next buttons based on current position"""
        if not selected_sample or not sample_options:
            return True, True  # Disable both if no sample selected
        
        sample_values = [opt['value'] for opt in sample_options]
        try:
            current_idx = sample_values.index(selected_sample)
            
            # Disable Previous if on first sample
            disable_prev = (current_idx == 0)
            
            # Disable Next if on last sample
            disable_next = (current_idx >= len(sample_values) - 1)
            
            return disable_prev, disable_next
        except ValueError:
            return True, True  # Disable both if sample not found

