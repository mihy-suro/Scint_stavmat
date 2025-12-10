"""
Data loading callbacks - YAML config and SPE file loading
"""

from .utils import *
import yaml
import os
from pathlib import Path


def register_data_loading_callbacks(app):
    """Register data loading and file upload callbacks"""
    
    # ==================== LOAD DETECTOR CONFIG ====================
    @app.callback(
        [Output('excel-data', 'data'),
         Output('run-analysis', 'disabled', allow_duplicate=True),
         Output('ref-a0', 'value'),
         Output('ref-a1', 'value'),
         Output('ref-a2', 'value'),
         Output('manual-a0', 'value'),
         Output('manual-a1', 'value'),
         Output('roi1-range-slider', 'value', allow_duplicate=True),
         Output('roi2-range-slider', 'value', allow_duplicate=True),
         Output('status-log', 'children', allow_duplicate=True)],
        Input('detector-selector', 'value'),
        prevent_initial_call=True
    )
    def load_detector_config(detector_name):
        """Load detector configuration from YAML and calibration SPE files"""
        if detector_name is None:
            raise PreventUpdate
        
        try:
            # Load YAML configuration
            config_path = Path(__file__).parent.parent / 'config' / 'detectors.yaml'
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if detector_name not in config:
                error = dbc.Alert(f"❌ Detektor '{detector_name}' nenalezen v konfiguraci", color="danger")
                return None, True, 9.6229, 1.3793, 0, 9.6229, 1.3793, [0, 1200], [1400, 1520], error
            
            detector_config = config[detector_name]
            
            # CHANNEL-CENTRIC: Extract channel mapping instead of energy calibration
            channel_mapping = detector_config.get('channel_mapping', {'ref_a0': 0.0, 'ref_a1': 1.0})
            ref_ch_a0 = float(channel_mapping['ref_a0'])
            ref_ch_a1 = float(channel_mapping['ref_a1'])
            
            # Extract display calibration (for UI only)
            display_calib = detector_config.get('display_calibration', {'a0': 9.6229, 'a1': 1.3793, 'a2': 0.0})
            display_a0 = float(display_calib['a0'])
            display_a1 = float(display_calib['a1'])
            display_a2 = float(display_calib.get('a2', 0.0))
            
            # CHANNEL-CENTRIC: ROI ranges now in CHANNELS (not keV)
            roi_ranges = detector_config.get('roi_ranges', {'roi1': [138, 573], 'roi2': [504, 1182]})
            roi1_range = roi_ranges.get('roi1', [138, 573])
            roi2_range = roi_ranges.get('roi2', [504, 1182])
            
            # Calculate approximate keV for display
            roi1_kev_min = display_a0 + display_a1 * roi1_range[0]
            roi1_kev_max = display_a0 + display_a1 * roi1_range[1]
            roi2_kev_min = display_a0 + display_a1 * roi2_range[0]
            roi2_kev_max = display_a0 + display_a1 * roi2_range[1]
            
            # Load calibration SPE files
            base_path = Path(__file__).parent.parent
            calib_spectra = detector_config['calibration_spectra']
            
            from scripts.utils import parse_spe_file
            
            # Parse Ra, K, Th, BG SPE files
            ra_path = base_path / calib_spectra['Ra']
            k_path = base_path / calib_spectra['K']
            th_path = base_path / calib_spectra['Th']
            bg_path = base_path / calib_spectra.get('BG')  # Background is optional
            
            # Read and parse files
            with open(ra_path, 'r', encoding='utf-8', errors='ignore') as f:
                ra_spe = parse_spe_file(f.read())
            with open(k_path, 'r', encoding='utf-8', errors='ignore') as f:
                k_spe = parse_spe_file(f.read())
            with open(th_path, 'r', encoding='utf-8', errors='ignore') as f:
                th_spe = parse_spe_file(f.read())
            
            # Read background if available
            bg_spe = None
            if bg_path and bg_path.exists():
                with open(bg_path, 'r', encoding='utf-8', errors='ignore') as f:
                    bg_spe = parse_spe_file(f.read())
            
            # Extract live times from calibration spectra
            ra_live_time = float(ra_spe.get('ELIVE', 1.0))
            k_live_time = float(k_spe.get('ELIVE', 1.0))
            th_live_time = float(th_spe.get('ELIVE', 1.0))
            bg_live_time = float(bg_spe.get('ELIVE', 1.0)) if bg_spe else 1.0
            
            # Get standard activities [Bq] from config
            standard_activities = detector_config.get('standard_activities', {})
            ra_activity = float(standard_activities.get('Ra', 1001.4))
            k_activity = float(standard_activities.get('K', 21330.0))
            th_activity = float(standard_activities.get('Th', 1020.0))
            
            # Build calibration DataFrame
            max_channels = max(len(ra_spe['channels']), len(k_spe['channels']), len(th_spe['channels']))
            if bg_spe:
                max_channels = max(max_channels, len(bg_spe['channels']))
            
            # Normalize calibration spectra to CPS/Bq (divide by live_time AND activity)
            # This way regression coefficients will directly give activity in Bq
            # For background: normalize to CPS only (activity = 1)
            ra_channels = ra_spe['channels'][:max_channels] + [0] * (max_channels - len(ra_spe['channels']))
            k_channels = k_spe['channels'][:max_channels] + [0] * (max_channels - len(k_spe['channels']))
            th_channels = th_spe['channels'][:max_channels] + [0] * (max_channels - len(th_spe['channels']))
            bg_channels = bg_spe['channels'][:max_channels] + [0] * (max_channels - len(bg_spe['channels'])) if bg_spe else [0] * max_channels
            
            calib_df = pd.DataFrame()
            calib_df['CHNL'] = range(max_channels)
            # Normalize: counts / live_time / activity = CPS/Bq
            calib_df['Ra'] = [c / ra_live_time / ra_activity for c in ra_channels]
            calib_df['K'] = [c / k_live_time / k_activity for c in k_channels]
            calib_df['Th'] = [c / th_live_time / th_activity for c in th_channels]
            # Background: normalize to CPS only (coefficient will be dimensionless scaling factor)
            calib_df['BG'] = [c / bg_live_time for c in bg_channels]
            
            # Store data structure (compatible with analysis callbacks)
            data = {
                'calibration': calib_df.to_dict('records'),
                'samples': [],  # Empty - samples loaded via SPE upload
                'sample_names': [],
                'sample_live_times': [],
                'parameters': {
                    # CHANNEL-CENTRIC: Store channel mapping
                    'ref_ch_a0': ref_ch_a0,
                    'ref_ch_a1': ref_ch_a1,
                    # Store display calibration (for UI only)
                    'display_a0': display_a0,
                    'display_a1': display_a1,
                    'display_a2': display_a2,
                    # Store activities for reference
                    'Ra_activity': ra_activity,
                    'K_activity': k_activity,
                    'Th_activity': th_activity,
                    # Store calibration live times for reference
                    'Ra_live_time': ra_live_time,
                    'K_live_time': k_live_time,
                    'Th_live_time': th_live_time,
                    'BG_live_time': bg_live_time,
                    'has_background': bg_spe is not None
                },
                'detector_name': detector_name
            }
            
            status_msg = html.Div([
                html.Small([
                    html.I(className="fas fa-check-circle text-success me-1"),
                    f"✅ Načtena konfigurace: {detector_name}",
                    html.Br(),
                    f"Kalibrační spektra: Ra, K, Th" + (", BG" if bg_spe else "") + f" ({max_channels} kanálů)",
                    html.Br(),
                    f"Aktivity etalonů: Ra={ra_activity:.0f} Bq, K={k_activity:.0f} Bq, Th={th_activity:.0f} Bq",
                    html.Br(),
                    f"ROI #1: kanály {roi1_range[0]}-{roi1_range[1]} (~{roi1_kev_min:.0f}-{roi1_kev_max:.0f} keV)",
                    html.Br(),
                    f"ROI #2: kanály {roi2_range[0]}-{roi2_range[1]} (~{roi2_kev_min:.0f}-{roi2_kev_max:.0f} keV)"
                ], className="text-success")
            ])
            
            return (
                data,
                True,  # Disable analyze button until sample loaded
                display_a0,  # Display calibration for UI
                display_a1,
                display_a2,
                display_a0,  # Initial manual values
                display_a1,
                roi1_range,  # Now in CHANNELS
                roi2_range,
                status_msg
            )
            
        except Exception as e:
            print(f"\n!!! ERROR loading detector config: {str(e)} !!!")
            import traceback
            traceback.print_exc()
            
            error_msg = html.Div([
                html.Small([
                    html.I(className="fas fa-exclamation-circle text-danger me-1"),
                    f"❌ Chyba při načítání konfigurace: {str(e)}"
                ], className="text-danger")
            ])
            
            return None, True, 9.6229, 1.3793, 0, 9.6229, 1.3793, [200, 800], [700, 1640], error_msg
    
    
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
        
        from scripts.utils import parse_spe_file
        
        # Handle single file
        if not isinstance(contents_list, list):
            contents_list = [contents_list]
            filenames_list = [filenames_list]
        
        loaded_samples = []
        errors = []
        
        for content, filename in zip(contents_list, filenames_list):
            try:
                # Decode file
                content_type, content_string = content.split(',')
                decoded_bytes = base64.b64decode(content_string)
                
                # Try multiple encodings
                decoded = None
                for encoding in ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']:
                    try:
                        decoded = decoded_bytes.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                if decoded is None:
                    decoded = decoded_bytes.decode('latin1', errors='ignore')
                
                # Parse SPE
                spe_data = parse_spe_file(decoded)
                
                # Use filename (without extension) as sample ID
                import os
                sample_id = os.path.splitext(filename)[0]
                
                # Add to excel_data structure
                excel_data['sample_names'].append(sample_id)
                excel_data['sample_live_times'].append(spe_data['ELIVE'])
                
                # Convert channel data to DataFrame format
                channels = spe_data['channels']
                
                # If this is first sample, create samples structure
                if not excel_data['samples']:
                    for ch_num, count in enumerate(channels):
                        excel_data['samples'].append({'CHNL': ch_num, sample_id: count})
                else:
                    # Add to existing structure
                    for ch_num, count in enumerate(channels):
                        if ch_num < len(excel_data['samples']):
                            excel_data['samples'][ch_num][sample_id] = count
                        else:
                            # Extend if needed
                            new_row = {'CHNL': ch_num, sample_id: count}
                            excel_data['samples'].append(new_row)
                
                loaded_samples.append(sample_id)
                
            except Exception as e:
                errors.append(f"{filename}: {str(e)}")
                print(f"Error loading {filename}: {e}")
                import traceback
                traceback.print_exc()
        
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
            for i, sample in enumerate(loaded_samples[:5]):  # Show first 5
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
            for i, err in enumerate(errors[:3]):  # Show first 3 errors
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
        
        return excel_data, new_options, spe_status, not enable_analysis, status_msg
    
    
    
    
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


