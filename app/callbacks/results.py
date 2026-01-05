"""
Results callbacks - display and export results
"""

from .utils import *
from utils import (
    calculate_activity_index,
    calculate_index_uncertainty,
    extract_coefficients_from_results
)


def register_results_callbacks(app):
    """Register results display and export callbacks"""
    
    # ==================== UPDATE ACCUMULATED RESULTS TABLE ====================
    @app.callback(
        Output('accumulated-results-table', 'data'),
        Input('accumulated-results', 'data')
    )
    def update_accumulated_table(accumulated):
        """Update accumulated results table - K always from ROI2"""
        if not accumulated:
            return []
        
        # K always from ROI2 (K ROI)
        k_source_roi = 'roi2'
        
        # Format for display - expect only full results format from run_analysis
        display_data = []
        for entry in accumulated:
            try:
                # Extract coefficients and errors using utility
                ra_val, k_val, th_val, ra_err_val, k_err, th_err_val = extract_coefficients_from_results(
                    entry, k_source_roi=k_source_roi
                )
                
                # Calculate index using utilities
                index = calculate_activity_index(ra_val, th_val, k_val)
                index_err = calculate_index_uncertainty(ra_val, ra_err_val, th_val, th_err_val, k_val, k_err)
                
                display_data.append({
                    'sample_id': entry['sample_name'],
                    'Ra': f"{ra_val:.3f}",
                    'Ra_err': f"{ra_err_val:.3f}",
                    'K': f"{k_val:.3f}",
                    'K_err': f"{k_err:.3f}",
                    'Th': f"{th_val:.3f}",
                    'Th_err': f"{th_err_val:.3f}",
                    'Index': f"{index:.4f}",
                    'Index_err': f"{index_err:.4f}"
                })
            except Exception as e:
                print(f"Warning: Could not format entry: {e}")
                continue
        
        return display_data
    
    
    # ==================== DELETE SELECTED ROWS ====================
    @app.callback(
        Output('accumulated-results', 'data', allow_duplicate=True),
        Output('accumulated-results-table', 'selected_rows'),
        Input('delete-selected-rows', 'n_clicks'),
        State('accumulated-results-table', 'selected_rows'),
        State('accumulated-results', 'data'),
        prevent_initial_call=True
    )
    def delete_selected_rows(n_clicks, selected_rows, accumulated):
        """Delete selected rows from accumulated results"""
        if not n_clicks or not selected_rows or not accumulated:
            raise PreventUpdate
        
        # Remove selected indices (sort descending to preserve indices)
        selected_rows_sorted = sorted(selected_rows, reverse=True)
        updated_accumulated = accumulated.copy()
        
        for idx in selected_rows_sorted:
            if 0 <= idx < len(updated_accumulated):
                deleted_name = updated_accumulated[idx].get('sample_name', 'unknown')
                del updated_accumulated[idx]
                print(f"🗑️ Deleted row: {deleted_name}")
        
        print(f"📊 Remaining results: {len(updated_accumulated)}")
        
        # Clear selection
        return updated_accumulated, []
    
    
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
            # Extract flat data from nested structure
            export_data = []
            for entry in accumulated:
                try:
                    # Extract coefficients and errors using utility (use 'roi2' for export)
                    ra_val, k_val, th_val, ra_err, k_err, th_err = extract_coefficients_from_results(
                        entry, k_source_roi='roi2'
                    )
                    
                    # Calculate index using utilities
                    index = calculate_activity_index(ra_val, th_val, k_val)
                    index_err = calculate_index_uncertainty(ra_val, ra_err, th_val, th_err, k_val, k_err)
                    
                    export_data.append({
                        'sample_name': entry['sample_name'],
                        'Ra': ra_val,
                        'Ra_err': ra_err,
                        'K': k_val,
                        'K_err': k_err,
                        'Th': th_val,
                        'Th_err': th_err,
                        'Index': index,
                        'Index_err': index_err
                    })
                except Exception as e:
                    print(f"Warning: Could not export entry: {e}")
                    continue
            
            # Create DataFrame
            df = pd.DataFrame(export_data)
            
            # Export to Excel
            wb = Workbook()
            ws = wb.active
            ws.title = "Results"
            
            # Write header
            header = ['sample_name', 'Ra', 'Ra_err', 'K', 'K_err', 'Th', 'Th_err', 'Index', 'Index_err']
            ws.append(header)
            
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

