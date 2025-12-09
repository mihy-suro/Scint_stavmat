"""
Results callbacks - display and export results
"""

from .utils import *


def register_results_callbacks(app):
    """Register results display and export callbacks"""
    
    # ==================== UPDATE RESULTS TABLE ====================
    @app.callback(
        [Output('results-table', 'data'),
         Output('results-table', 'columns')],
        Input('sample-results', 'data')
    )
    def update_results_table(results):
        """Update compact results table"""
        if results is None:
            return [], []
        
        try:
            # Get single method results
            res = results['results']
            regression_method = results.get('regression_method', 'OLS')
            bg_names = results.get('bg_names', [])
            
            # Extract values from nested structure
            coeff = res['Coefficients']
            stderr = res['Std Errors']
            
            # Print detailed stats to console
            print(f"\n{'='*60}")
            print(f"Vzorek: {results['sample_name']}")
            print(f"Kalibrace: {results['calib_method']}")
            print(f"Metoda: {regression_method}")
            print(f"{'='*60}")
            print(f"\n{regression_method} výsledky:")
            print("  Radioaktivita:")
            print(f"    Ra-226: {coeff['Ra']:.4f} Bq  (σ: {stderr['Ra']:.4f})")
            print(f"    K-40:   {coeff['K']:.4f} Bq  (σ: {stderr['K']:.4f})")
            print(f"    Th-232: {coeff['Th']:.4f} Bq  (σ: {stderr['Th']:.4f})")
            print("\n  Pozadí (koeficienty, očekáváno ~1.0):")
            for bg in bg_names:
                print(f"    {bg}: {coeff[bg]:.4f}  (σ: {stderr[bg]:.4f})")
            print(f"\n  R² = {res['R^2']:.6f}")
            print(f"  Adjusted R² = {res['Adjusted R^2']:.6f}")
            print(f"{'='*60}\n")
            
            # Create compact vertical table (only Ra, K, Th activities)
            table_data = [
                {
                    'Radionuklid': 'Ra-226',
                    f'{regression_method} (Bq)': f"{coeff['Ra']:.3f}",
                    'σ': f"{stderr['Ra']:.3f}",
                },
                {
                    'Radionuklid': 'K-40',
                    f'{regression_method} (Bq)': f"{coeff['K']:.3f}",
                    'σ': f"{stderr['K']:.3f}",
                },
                {
                    'Radionuklid': 'Th-232',
                    f'{regression_method} (Bq)': f"{coeff['Th']:.3f}",
                    'σ': f"{stderr['Th']:.3f}",
                }
            ]
            
            columns = [
                {"name": "Radionuklid", "id": "Radionuklid"},
                {"name": f"{regression_method} (Bq)", "id": f"{regression_method} (Bq)"},
                {"name": "σ", "id": "σ"},
            ]
            
            return table_data, columns
            
            return table_data, columns
        
        except Exception as e:
            print(f"\n!!! ERROR updating results table: {str(e)} !!!")
            import traceback
            traceback.print_exc()
            return [], []
    
    
    # ==================== EXPORT CSV ====================
    @app.callback(
        Output("download-csv", "data"),
        Input("export-csv", "n_clicks"),
        State('results-table', 'data'),
        State('sample-results', 'data'),
        prevent_initial_call=True
    )
    def export_csv(n_clicks, table_data, results):
        """Export results to CSV"""
        if table_data and results:
            df = pd.DataFrame(table_data)
            filename = f"results_{results['sample_name']}.csv"
            return dict(content=df.to_csv(index=False), filename=filename)
        raise PreventUpdate
    
    
    # ==================== ENABLE CONFIRM BUTTON ====================
    @app.callback(
        Output('confirm-result-button', 'disabled'),
        Input('sample-results', 'data')
    )
    def enable_confirm_button(results):
        """Enable confirm button when analysis is complete"""
        return results is None
    
    
    # ==================== CONFIRM AND SAVE RESULT ====================
    @app.callback(
        [Output('accumulated-results', 'data'),
         Output('status-log', 'children', allow_duplicate=True)],
        Input('confirm-result-button', 'n_clicks'),
        [State('sample-results', 'data'),
         State('accumulated-results', 'data')],
        prevent_initial_call=True
    )
    def confirm_result(n_clicks, current_result, accumulated):
        """Save current result to accumulated results"""
        if not current_result:
            raise PreventUpdate
        
        from datetime import datetime
        
        try:
            # Extract data
            sample_name = current_result['sample_name']
            res = current_result['results']
            regression_method = current_result.get('regression_method', 'OLS')
            calib = current_result.get('sample_calib', [0, 0, 0])
            
            coeff = res['Coefficients']
            stderr = res['Std Errors']
            
            # Create result entry
            result_entry = {
                'sample_id': sample_name,
                'Ra': round(coeff['Ra'], 3),
                'Ra_err': round(stderr['Ra'], 3),
                'K': round(coeff['K'], 3),
                'K_err': round(stderr['K'], 3),
                'Th': round(coeff['Th'], 3),
                'Th_err': round(stderr['Th'], 3),
                'R2': round(res['R^2'], 4),
                'method': regression_method,
                'calib_a0': round(calib[0], 4),
                'calib_a1': round(calib[1], 4),
                'calib_a2': round(calib[2], 6),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Add to accumulated
            accumulated.append(result_entry)
            
            print(f"\n✅ Výsledek potvrzen: {sample_name}")
            print(f"   Ra={coeff['Ra']:.3f}, K={coeff['K']:.3f}, Th={coeff['Th']:.3f} Bq")
            
            status_msg = html.Div([
                html.Small([
                    html.I(className="fas fa-save text-success me-1"),
                    f"✅ Uloženo: {sample_name}",
                    html.Br(),
                    f"Celkem výsledků: {len(accumulated)}"
                ], className="text-success")
            ])
            
            return accumulated, status_msg
            
        except Exception as e:
            print(f"\n!!! ERROR confirming result: {str(e)} !!!")
            import traceback
            traceback.print_exc()
            raise PreventUpdate
    
    
    # ==================== UPDATE ACCUMULATED RESULTS TABLE ====================
    @app.callback(
        Output('accumulated-results-table', 'data'),
        Input('accumulated-results', 'data')
    )
    def update_accumulated_table(accumulated):
        """Update accumulated results table"""
        if not accumulated:
            return []
        
        # Format for display (keep only display columns)
        display_data = []
        for entry in accumulated:
            # Handle both old format (dict with sample_id) and new format (full results dict)
            if 'sample_id' in entry:
                # Old format - direct use
                display_data.append({
                    'sample_id': entry['sample_id'],
                    'Ra': entry['Ra'],
                    'Ra_err': entry['Ra_err'],
                    'K': entry['K'],
                    'K_err': entry['K_err'],
                    'Th': entry['Th'],
                    'Th_err': entry['Th_err'],
                    'R2': entry['R2'],
                    'method': entry['method']
                })
            else:
                # New format - extract from results dict
                res = entry['results']
                coeff = res['Coefficients']
                stderr = res['Std Errors']
                display_data.append({
                    'sample_id': entry['sample_name'],
                    'Ra': f"{coeff['Ra']:.3f}",
                    'Ra_err': f"{stderr['Ra']:.3f}",
                    'K': f"{coeff['K']:.3f}",
                    'K_err': f"{stderr['K']:.3f}",
                    'Th': f"{coeff['Th']:.3f}",
                    'Th_err': f"{stderr['Th']:.3f}",
                    'R2': f"{res['R^2']:.4f}",
                    'method': entry['regression_method']
                })
        
        return display_data
    
    
    # ==================== EXPORT ACCUMULATED RESULTS ====================
    @app.callback(
        Output("download-results", "data"),
        Input("export-results", "n_clicks"),
        State('accumulated-results', 'data'),
        prevent_initial_call=True
    )
    def export_accumulated_results(n_clicks, accumulated):
        """Export all accumulated results to Excel/CSV"""
        if not accumulated:
            raise PreventUpdate
        
        from datetime import datetime
        import io
        from openpyxl import Workbook
        
        try:
            # Create DataFrame
            df = pd.DataFrame(accumulated)
            
            # Reorder columns for readability
            column_order = [
                'sample_id', 'Ra', 'Ra_err', 'K', 'K_err', 'Th', 'Th_err',
                'R2', 'method', 'calib_a0', 'calib_a1', 'calib_a2', 'timestamp'
            ]
            df = df[column_order]
            
            # Export to Excel
            wb = Workbook()
            ws = wb.active
            ws.title = "Results"
            
            # Write header
            ws.append(column_order)
            
            # Write data
            for idx, row in df.iterrows():
                ws.append(list(row))
            
            # Save to BytesIO
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"accumulated_results_{timestamp}.xlsx"
            
            print(f"\n📊 Exported {len(accumulated)} results to {filename}")
            
            return dcc.send_bytes(output.read(), filename)
            
        except Exception as e:
            print(f"\n!!! ERROR exporting results: {str(e)} !!!")
            import traceback
            traceback.print_exc()
            raise PreventUpdate

