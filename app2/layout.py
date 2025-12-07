"""
Layout komponenty pro Dash aplikaci
Jednoduchý UI pro sekvenční analýzu vzorků
"""

import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table


def create_layout():
    """Vytvoří layout aplikace"""
    
    layout = dbc.Container([
        # Stores for internal state
        dcc.Store(id='current-sample-calib', data={'a0': 9.6229, 'a1': 1.3793, 'a2': 0}),
        dcc.Store(id='excel-data'),
        dcc.Store(id='sample-results'),
        dcc.Store(id='peak-calibration-data'),
        dcc.Store(id='optimization-progress', data={'iteration': 0, 'r2': 0, 'coeffs': [], 'running': False}),
        
        # Interval for live progress updates
        dcc.Interval(id='progress-interval', interval=500, disabled=True),
        
        # Header
        dbc.Row([
            dbc.Col([
                html.H2("☢️ Analýza scintilačních spekter", className="text-center mt-3 mb-2"),
                html.P("Sekvenční dekonvoluce gamma spekter - CeBr₃ & NaI(Tl)", 
                       className="text-center text-muted mb-4"),
            ])
        ]),
        
        # Main content
        dbc.Row([
            # Left sidebar - controls (narrower)
            dbc.Col([
                # Upload card
                dbc.Card([
                    dbc.CardHeader("📁 Data"),
                    dbc.CardBody([
                        dcc.Upload(
                            id='upload-excel',
                            children=html.Div([
                                html.I(className="fas fa-upload me-2"),
                                'Excel'
                            ]),
                            style={
                                'width': '100%',
                                'height': '45px',
                                'lineHeight': '45px',
                                'borderWidth': '2px',
                                'borderStyle': 'dashed',
                                'borderRadius': '5px',
                                'textAlign': 'center',
                                'cursor': 'pointer',
                                'borderColor': '#0d6efd'
                            },
                            multiple=False
                        ),
                    ])
                ], className="mb-3"),
                
                # Settings card
                dbc.Card([
                    dbc.CardHeader("⚙️ Nastavení"),
                    dbc.CardBody([
                        # Sample selector
                        html.Label("Vzorek:", className="fw-bold small"),
                        dcc.Dropdown(
                            id='sample-selector',
                            options=[],
                            placeholder="Vyberte vzorek...",
                            className="mb-3"
                        ),
                        
                        html.Hr(),
                        
        # Sample calibration (visible)
        html.Label("Kalibrace vzorku:", className="fw-bold mt-2 small"),
        
        # Polynomial degree selection
        dbc.RadioItems(
            id='polynomial-degree',
            options=[
                {"label": " Lineární (E = a₀ + a₁·CH)", "value": "linear"},
                {"label": " Kvadratická (E = a₀ + a₁·CH + a₂·CH²)", "value": "quadratic"},
            ],
            value="linear",
            className="mb-2 small"
        ),
        
        dbc.InputGroup([
            dbc.InputGroupText("a₀", style={"width": "50px"}),
            dbc.Input(id='manual-a0', type="number", value=9.6229, step=0.0001, size="sm"),
            dbc.InputGroupText("keV", style={"fontSize": "11px"}),
        ], className="mb-2", size="sm"),
        
        dbc.InputGroup([
            dbc.InputGroupText("a₁", style={"width": "50px"}),
            dbc.Input(id='manual-a1', type="number", value=1.3793, step=0.0001, size="sm"),
            dbc.InputGroupText("keV/CH", style={"fontSize": "11px"}),
        ], className="mb-2", size="sm"),
        
        # Quadratic coefficient (conditional)
        html.Div([
            dbc.InputGroup([
                dbc.InputGroupText("a₂", style={"width": "50px"}),
                dbc.Input(id='manual-a2', type="number", value=0, step=0.000001, size="sm"),
                dbc.InputGroupText("keV/CH²", style={"fontSize": "11px"}),
            ], className="mb-2", size="sm"),
        ], id='a2-input-container', style={'display': 'none'}),
        
        dbc.Button(
            [html.I(className="fas fa-undo me-1"), "Reset"],
            id='reset-calibration',
            color='secondary',
            size='sm',
            outline=True,
            className='w-100 mb-3'
        ),
        
        # Hidden ref calibration fields for internal use (fixed from Excel)
        html.Div([
            dbc.Input(id='ref-a0', type="hidden", value=9.6229),
            dbc.Input(id='ref-a1', type="hidden", value=1.3793),
            dbc.Input(id='ref-a2', type="hidden", value=0),
        ], style={'display': 'none'}),
        
        html.Hr(),
        
        # Cut channel (left side)
        html.Label("Vynulovat prvních N kanálů:", className="fw-bold mt-2 small"),
        dcc.Slider(
            id='cut-channel',
            min=0,
            max=500,
            step=10,
            value=150,
            marks={0: '0', 150: '150', 300: '300', 500: '500'},
            tooltip={"placement": "bottom", "always_visible": True}
        ),
        
        # Cut channel (right side)
        html.Label("Omezit na prvních M kanálů:", className="fw-bold mt-3 small"),
        dcc.Slider(
            id='cut-channel-right',
            min=1500,
            max=2048,
            step=50,
            value=2048,
            marks={1500: '1500', 1750: '1750', 2000: '2000', 2048: '2048'},
            tooltip={"placement": "bottom", "always_visible": True}
        ),
                        
                        html.Hr(),
                        
                        # Manual peak calibration
                        html.Label("Manuální kalibrace:", className="fw-bold mt-2 small"),
                        html.P("1) Klikni energii, 2) Klikni pík, 3) Potvrď", className="small text-muted mb-2"),
                        
                        dbc.Table([
                            html.Thead([
                                html.Tr([
                                    html.Th("E (keV)", style={'width': '40%'}),
                                    html.Th("CH", style={'width': '60%'})
                                ])
                            ]),
                            html.Tbody([
                                html.Tr([
                                    html.Td(dbc.Button("238", id='select-e-238', size="sm", color="light", 
                                                      className="w-100", style={'textAlign': 'left'})),
                                    html.Td(html.Span(id='peak-ch-238', children="-", className="ms-2"))
                                ], id='row-238', style={'cursor': 'pointer'}),
                                html.Tr([
                                    html.Td(dbc.Button("295", id='select-e-295', size="sm", color="light",
                                                      className="w-100", style={'textAlign': 'left'})),
                                    html.Td(html.Span(id='peak-ch-295', children="-", className="ms-2"))
                                ], id='row-295'),
                                html.Tr([
                                    html.Td(dbc.Button("352", id='select-e-352', size="sm", color="light",
                                                      className="w-100", style={'textAlign': 'left'})),
                                    html.Td(html.Span(id='peak-ch-352', children="-", className="ms-2"))
                                ], id='row-352'),
                                html.Tr([
                                    html.Td(dbc.Button("609", id='select-e-609', size="sm", color="light",
                                                      className="w-100", style={'textAlign': 'left'})),
                                    html.Td(html.Span(id='peak-ch-609', children="-", className="ms-2"))
                                ], id='row-609'),
                                html.Tr([
                                    html.Td(dbc.Button("1461", id='select-e-1461', size="sm", color="light",
                                                      className="w-100", style={'textAlign': 'left'})),
                                    html.Td(html.Span(id='peak-ch-1461', children="-", className="ms-2"))
                                ], id='row-1461'),
                            ])
                        ], size="sm", bordered=True, className="mb-2"),
                        
                        dbc.Button(
                            "Vypočítat",
                            id='calculate-calibration',
                            color='success',
                            size='sm',
                            className='w-100 mt-2',
                            disabled=True
                        ),
                        
                        html.Hr(),
                        
                        # Optimization toggle
                        dbc.Checklist(
                            id='optimize-calibration',
                            options=[{"label": " Optimalizovat", "value": "optimize"}],
                            value=[],
                            switch=True,
                            className="mb-2"
                        ),
                        
                        # Optimization settings (collapsible)
                        dbc.Collapse([
                            dbc.Card([
                                dbc.CardBody([
                                    html.Label("Metoda:", className="fw-bold small mb-1"),
                                    dcc.Dropdown(
                                        id='optimization-method',
                                        options=[
                                            {'label': 'L-BFGS-B (doporučeno)', 'value': 'L-BFGS-B'},
                                            {'label': 'Powell', 'value': 'Powell'},
                                            {'label': 'Nelder-Mead', 'value': 'Nelder-Mead'},
                                        ],
                                        value='L-BFGS-B',
                                        clearable=False,
                                        className="mb-2"
                                    ),
                                    
                                    html.Label("Max. iterací:", className="fw-bold small mb-1"),
                                    dbc.Input(
                                        id='max-iterations',
                                        type='number',
                                        min=50,
                                        max=5000,
                                        step=50,
                                        value=1000,
                                        size='sm',
                                        className="mb-2"
                                    ),
                                ], className="p-2")
                            ], className="mb-2", color="light", outline=True)
                        ], id='optimization-settings-collapse', is_open=False),
                        
                        # Include background toggle
                        dbc.Checklist(
                            id='include-background',
                            options=[{"label": " Zahrnout pozadí do fitu", "value": "include"}],
                            value=["include"],
                            switch=True,
                            className="mb-3"
                        ),
                        
                        html.Hr(),
                        
                        # Analyze button
                        dcc.Loading(
                            id="loading-analysis",
                            type="default",
                            children=[
                                dbc.Button(
                                    [html.I(className="fas fa-play me-2"), "Analyzovat"],
                                    id='run-analysis',
                                    color='primary',
                                    size='lg',
                                    className='w-100 mt-3',
                                    disabled=True
                                ),
                            ]
                        ),
                    ])
                ])
            ], width=2),
            
            # Middle panel - graphs
            dbc.Col([
                # Graph
                dbc.Card([
                    dbc.CardHeader("📊 Spektrum a fit"),
                    dbc.CardBody([
                        dcc.Loading(
                            id="loading-graph",
                            type="default",
                            children=dcc.Graph(id='spectrum-plot', style={'height': '450px'})
                        )
                    ])
                ], className="mb-3"),
                
                # Calibration plot
                dbc.Card([
                    dbc.CardHeader("📈 Kalibrace: Kanál → Energie"),
                    dbc.CardBody([
                        dcc.Graph(id='calibration-fit-plot', style={'height': '300px'})
                    ])
                ], className="mb-3"),
            ], width=7),
            
            # Right panel - results and status
            dbc.Col([
                # Status window
                dbc.Card([
                    dbc.CardHeader("📢 Status"),
                    dbc.CardBody([
                        html.Div(id='status-log', children=[
                            html.Small("Připraveno...", className="text-muted")
                        ], style={
                            'height': '120px',
                            'overflowY': 'auto',
                            'fontSize': '12px',
                            'backgroundColor': '#f8f9fa',
                            'padding': '8px',
                            'borderRadius': '4px'
                        })
                    ])
                ], className="mb-3"),
                
                # Results table
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("📊 Výsledky"),
                        dbc.Button(
                            html.I(className="fas fa-download"),
                            id='export-csv',
                            color='success',
                            size='sm',
                            className='float-end',
                            title='Export CSV'
                        ),
                    ]),
                    dbc.CardBody([
                        dash_table.DataTable(
                            id='results-table',
                            columns=[],
                            data=[],
                            style_table={'overflowX': 'auto'},
                            style_cell={'textAlign': 'center', 'padding': '8px', 'fontSize': '13px'},
                            style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold', 'fontSize': '12px'},
                            style_data_conditional=[
                                {
                                    'if': {'column_id': 'Radionuklid'},
                                    'fontWeight': 'bold',
                                    'textAlign': 'left'
                                }
                            ]
                        ),
                    ])
                ], style={'height': '100%'})
            ], width=3),
        ]),
        
        # Download component
        dcc.Download(id="download-csv"),
        
    ], fluid=True)
    
    return layout
