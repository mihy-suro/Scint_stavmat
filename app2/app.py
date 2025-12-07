"""
Dash aplikace pro sekvenční analýzu scintilačních spekter
Verze 2 - zjednodušená pro jednotlivé vzorky
"""

import dash
import dash_bootstrap_components as dbc
from layout import create_layout
from callbacks import register_all_callbacks

# Initialize Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True,
    title="Gamma Spektroskopie - Analýza vzorků"
)

# Set up the layout
app.layout = create_layout()

# Register all callbacks
register_all_callbacks(app)

# Run the server
if __name__ == "__main__":
    app.run(debug=True, port=8051)