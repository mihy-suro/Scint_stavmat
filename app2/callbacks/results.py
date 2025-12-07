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
            ols_res = results['results_ols']
            nnls_res = results['results_nnls']
            bg_names = results.get('bg_names', [])
            
            # Extract values from nested structure
            ols_coeff = ols_res['Coefficients']
            ols_stderr = ols_res['Std Errors']
            nnls_coeff = nnls_res['Coefficients']
            nnls_stderr = nnls_res['Std Errors']
            
            # Print detailed stats to console
            print(f"\n{'='*60}")
            print(f"Vzorek: {results['sample_name']}")
            print(f"Kalibrace: {results['calib_method']}")
            print(f"{'='*60}")
            print("\nOLS výsledky:")
            print("  Radioaktivita:")
            print(f"    Ra-226: {ols_coeff['Ra']:.4f} Bq  (σ: {ols_stderr['Ra']:.4f})")
            print(f"    K-40:   {ols_coeff['K']:.4f} Bq  (σ: {ols_stderr['K']:.4f})")
            print(f"    Th-232: {ols_coeff['Th']:.4f} Bq  (σ: {ols_stderr['Th']:.4f})")
            print("\n  Pozadí (koeficienty, očekáváno ~1.0):")
            for bg in bg_names:
                print(f"    {bg}: {ols_coeff[bg]:.4f}  (σ: {ols_stderr[bg]:.4f})")
            print(f"\n  R² = {ols_res['R^2']:.6f}")
            print(f"  Adjusted R² = {ols_res['Adjusted R^2']:.6f}")
            
            print("\nNNLS výsledky:")
            print("  Radioaktivita:")
            print(f"    Ra-226: {nnls_coeff['Ra']:.4f} Bq  (σ: {nnls_stderr['Ra']:.4f})")
            print(f"    K-40:   {nnls_coeff['K']:.4f} Bq  (σ: {nnls_stderr['K']:.4f})")
            print(f"    Th-232: {nnls_coeff['Th']:.4f} Bq  (σ: {nnls_stderr['Th']:.4f})")
            print("\n  Pozadí (koeficienty, očekáváno ~1.0):")
            for bg in bg_names:
                print(f"    {bg}: {nnls_coeff[bg]:.4f}  (σ: {nnls_stderr[bg]:.4f})")
            print(f"\n  R² = {nnls_res['R^2']:.6f}")
            print(f"  Adjusted R² = {nnls_res['Adjusted R^2']:.6f}")
            print(f"{'='*60}\n")
            
            # Create compact vertical table (only Ra, K, Th activities)
            table_data = [
                {
                    'Radionuklid': 'Ra-226',
                    'OLS (Bq)': f"{ols_coeff['Ra']:.3f}",
                    'OLS σ': f"{ols_stderr['Ra']:.3f}",
                    'NNLS (Bq)': f"{nnls_coeff['Ra']:.3f}",
                    'NNLS σ': f"{nnls_stderr['Ra']:.3f}",
                },
                {
                    'Radionuklid': 'K-40',
                    'OLS (Bq)': f"{ols_coeff['K']:.3f}",
                    'OLS σ': f"{ols_stderr['K']:.3f}",
                    'NNLS (Bq)': f"{nnls_coeff['K']:.3f}",
                    'NNLS σ': f"{nnls_stderr['K']:.3f}",
                },
                {
                    'Radionuklid': 'Th-232',
                    'OLS (Bq)': f"{ols_coeff['Th']:.3f}",
                    'OLS σ': f"{ols_stderr['Th']:.3f}",
                    'NNLS (Bq)': f"{nnls_coeff['Th']:.3f}",
                    'NNLS σ': f"{nnls_stderr['Th']:.3f}",
                }
            ]
            
            columns = [
                {"name": "Radionuklid", "id": "Radionuklid"},
                {"name": "OLS (Bq)", "id": "OLS (Bq)"},
                {"name": "σ", "id": "OLS σ"},
                {"name": "NNLS (Bq)", "id": "NNLS (Bq)"},
                {"name": "σ", "id": "NNLS σ"},
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
