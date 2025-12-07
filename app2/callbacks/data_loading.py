"""
Data loading callbacks - Excel upload and parsing
"""

from .utils import *


def register_data_loading_callbacks(app):
    """Register data loading and file upload callbacks"""
    
    # ==================== EXCEL UPLOAD & PARSING ====================
    @app.callback(
        [Output('excel-data', 'data'),
         Output('run-analysis', 'disabled'),
         Output('ref-a0', 'value'),
         Output('ref-a1', 'value'),
         Output('ref-a2', 'value'),
         Output('manual-a0', 'value'),
         Output('manual-a1', 'value'),
         Output('cut-channel', 'value'),
         Output('status-log', 'children')],
        [Input('upload-excel', 'contents'),
         Input('upload-excel', 'filename')]
    )
    def parse_excel(contents, filename):
        """Parse uploaded Excel file"""
        if contents is None:
            raise PreventUpdate
        
        try:
            # Decode file
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            excel_file = pd.ExcelFile(io.BytesIO(decoded))
            
            # Validate required sheets (with encoding tolerance for "Pozadí")
            sheet_names = excel_file.sheet_names
            required_base = ['Kalibrace', 'Vzorky', 'Parametry']
            missing = [s for s in required_base if s not in sheet_names]
            
            # Find "Pozadí" or "Pozad?" (encoding issue)
            pozadi_sheet = None
            for sheet in sheet_names:
                if sheet.startswith('Pozad'):
                    pozadi_sheet = sheet
                    break
            
            if pozadi_sheet is None:
                missing.append('Pozadí')
            
            if missing:
                error = dbc.Alert(f"❌ Chybí povinné sheety: {', '.join(missing)}", color="danger")
                return None, error, True, 9.6229, 1.3793, 0, 9.62228359, 1.37495787, 150
            
            # Read parameters sheet
            params_df = pd.read_excel(excel_file, sheet_name='Parametry', header=None)
            params_dict = dict(zip(params_df[0], params_df[1]))
            
            # Extract parameters with defaults
            skip_rows = int(params_dict.get('skip_rows', 11))
            
            # Read calibration data - detekce názvů sloupců
            calib_sheet = excel_file.parse('Kalibrace')
            calib_headers = calib_sheet.columns[1:].tolist()  # Názvy sloupců kromě prvního
            
            calib_df = pd.read_excel(excel_file, sheet_name='Kalibrace', skiprows=skip_rows, header=None)
            calib_df.columns = ['CHNL'] + calib_headers
            
            # Odstranit řádky s NaN v CHNL před konverzí
            calib_df = calib_df.dropna(subset=['CHNL'])
            calib_df['CHNL'] = calib_df['CHNL'].astype(int)
            
            # Zajistit pořadí Ra, K, Th (i když Excel má jiné pořadí)
            calib_df = calib_df[['CHNL', 'Ra', 'K', 'Th']]
            
            # Read samples data - názvy vzorků jsou v hlavičce sloupců
            samples_sheet = excel_file.parse('Vzorky')
            sample_names = samples_sheet.columns[1:].tolist()  # Column headers kromě prvního
            
            # Live times jsou v řádku kde první sloupec == 'ELIVE'
            elive_row = samples_sheet[samples_sheet.iloc[:, 0] == 'ELIVE']
            if not elive_row.empty:
                sample_live_times = elive_row.iloc[0, 1:].values.astype(float).tolist()
            else:
                # Fallback - hledej řádek s indexem 2 (třetí řádek)
                sample_live_times = samples_sheet.iloc[2, 1:].values.astype(float).tolist()
            
            sample_df = pd.read_excel(excel_file, sheet_name='Vzorky', skiprows=skip_rows, header=None)
            sample_df.columns = ['CHNL'] + sample_names
            
            # Odstranit řádky s NaN v CHNL před konverzí
            sample_df = sample_df.dropna(subset=['CHNL'])
            sample_df['CHNL'] = sample_df['CHNL'].astype(int)
            
            # Read background data - detekce všech sloupců pozadí
            bg_sheet = excel_file.parse(pozadi_sheet)
            bg_names = bg_sheet.columns[1:].tolist()  # Všechny sloupce kromě prvního
            
            # Načíst live times pro každé pozadí z ELIVE řádku
            bg_elive_row = bg_sheet[bg_sheet.iloc[:, 0] == 'ELIVE']
            if not bg_elive_row.empty:
                bg_live_times = bg_elive_row.iloc[0, 1:len(bg_names)+1].values.astype(float).tolist()
            else:
                # Fallback - řádek s indexem 2
                bg_live_times = bg_sheet.iloc[2, 1:len(bg_names)+1].values.astype(float).tolist()
            
            bg_df = pd.read_excel(excel_file, sheet_name=pozadi_sheet, skiprows=skip_rows, header=None)
            bg_df.columns = ['CHNL'] + bg_names
            bg_df['CHNL'] = bg_df['CHNL'].astype(int)
            
            # Store data
            data = {
                'calibration': calib_df.to_dict('records'),
                'samples': sample_df.to_dict('records'),
                'background': bg_df.to_dict('records'),
                'sample_names': sample_names,
                'sample_live_times': sample_live_times,
                'bg_names': bg_names,
                'bg_live_times': bg_live_times,
                'parameters': params_dict,
                'filename': filename
            }
            
            # Print to console instead of UI
            print(f"\n=== Excel loaded: {filename} ===")
            print(f"Samples: {len(sample_names)}, Channels: {len(calib_df)}")
            print(f"Backgrounds: {bg_names}")
            
            # Return parameters from Excel
            ref_a0 = float(params_dict.get('ref_a0', 9.6229))
            ref_a1 = float(params_dict.get('ref_a1', 1.3793))
            ref_a2 = float(params_dict.get('ref_a2', 0))
            
            status_msg = html.Div([
                html.Small([
                    html.I(className="fas fa-check-circle text-success me-1"),
                    f"✅ Načteno: {filename}",
                    html.Br(),
                    f"Vzorků: {len(sample_names)}, Pozadí: {len(bg_names)}"
                ], className="text-success")
            ])
            
            return (
                data,
                False,  # Enable analyze button
                ref_a0,  # ref-a0 (hidden)
                ref_a1,  # ref-a1 (hidden)
                ref_a2,  # ref-a2 (hidden)
                ref_a0,  # manual-a0 (visible)
                ref_a1,  # manual-a1 (visible)
                int(params_dict.get('cut_channel', 150)),
                status_msg
            )
            
        except Exception as e:
            print(f"\n!!! ERROR loading Excel: {str(e)} !!!")
            import traceback
            traceback.print_exc()
            
            error_msg = html.Div([
                html.Small([
                    html.I(className="fas fa-exclamation-triangle text-danger me-1"),
                    f"❌ Chyba: {str(e)}"
                ], className="text-danger")
            ])
            
            return None, True, 9.6229, 1.3793, 0, 9.6229, 1.3793, 150, error_msg
    
    
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
    
    
    @app.callback(
        [Output('sample-selector', 'value'),
         Output('status-log', 'children', allow_duplicate=True)],
        Input('sample-selector', 'options'),
        State('excel-data', 'data'),
        prevent_initial_call=True
    )
    def set_default_sample(options, data):
        """Set first sample as default and show info"""
        if not options:
            return None, no_update
        
        selected = options[0]['value']
        
        # Show sample info
        if data and selected:
            idx = data['sample_names'].index(selected)
            live_time = data['sample_live_times'][idx]
            
            status_msg = html.Div([
                html.Small([
                    html.I(className="fas fa-vial text-info me-1"),
                    f"🔬 Vzorek: {selected}",
                    html.Br(),
                    f"Live time: {live_time:.1f} s"
                ], className="text-info")
            ])
            
            return selected, status_msg
        
        return selected, no_update
    
    
    # ==================== CLEAR RESULTS ON SAMPLE CHANGE ====================
    @app.callback(
        Output('sample-results', 'data', allow_duplicate=True),
        Input('sample-selector', 'value'),
        prevent_initial_call=True
    )
    def clear_results_on_sample_change(selected_sample):
        """Clear analysis results when user changes selected sample"""
        return None
    
    
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
