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
        dcc.Store(id='accumulated-results', data=[]),  # Accumulated results for batch
        dcc.Store(id='batch-queue', data={'remaining': [], 'current_index': 0, 'total': 0, 'processing': False}),  # Batch processing queue
        dcc.Store(id='batch-trigger', data=0),  # Trigger to process next sample (increments)
        dcc.Store(id='batch-counter', data=0),  # Atomic counter for batch recursion
        dcc.Store(id='loading-state', data=False),
        dcc.Download(id='download-results'),  # Results export
        
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
                # Detector selection card
                dbc.Card([
                    dbc.CardHeader("🔬 Detektor"),
                    dbc.CardBody([
                        html.Label("Typ detektoru:", className="fw-bold small mb-2"),
                        dcc.Dropdown(
                            id='detector-selector',
                            options=[
                                {'label': 'CeBr₃', 'value': 'CeBr3'},
                                {'label': 'NaI(Tl)', 'value': 'NaI(Tl)'}
                            ],
                            placeholder="Vyberte detektor...",
                            className="mb-2"
                        ),
                    ])
                ], className="mb-3"),
                
                # Sample upload card
                dbc.Card([
                    dbc.CardHeader("📁 Vzorky"),
                    dbc.CardBody([
                        # SPE upload
                        html.Label("Nahrát SPE soubory:", className="fw-bold small mb-2"),
                        dcc.Upload(
                            id='upload-spe',
                            children=html.Div([
                                html.I(className="fas fa-file-upload me-2"),
                                'Vybrat spektra (.spe)'
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
                            multiple=True
                        ),
                        
                        # SPE status badge
                        html.Div(id='spe-status', className="mt-2 small"),
                        
                        # Sample selector
                        html.Hr(className="my-3"),
                        html.Label("Vybrat vzorek:", className="fw-bold small mb-2"),
                        dcc.Dropdown(
                            id='sample-selector',
                            options=[],
                            placeholder="Vyberte vzorek...",
                            className="mb-2"
                        ),
                    ])
                ], className="mb-3"),
                
                # Energy calibration card
                dbc.Card([
                    dbc.CardHeader("⚡ Energetická kalibrace"),
                    dbc.CardBody([
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
                            className='w-100'
                        ),
                        
                        # Hidden ref calibration fields for internal use (fixed from Excel)
                        html.Div([
                            dbc.Input(id='ref-a0', type="hidden", value=9.6229),
                            dbc.Input(id='ref-a1', type="hidden", value=1.3793),
                            dbc.Input(id='ref-a2', type="hidden", value=0),
                        ], style={'display': 'none'}),
                    ])
                ], className="mb-3"),
                
                # Manual peak calibration card
                dbc.Card([
                    dbc.CardHeader("📋 Manuální kalibrace"),
                    dbc.CardBody([
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
                    ])
                ], className="mb-3"),
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
                
                # Residuals plot (hidden initially)
                dbc.Card([
                    dbc.CardHeader("📉 Residua (Naměřeno - Fit)"),
                    dbc.CardBody([
                        dcc.Graph(id='residuals-plot', style={'height': '250px'})
                    ])
                ], className="mb-3", id='residuals-card', style={'display': 'none'}),
                
                # Calibration plot
                dbc.Card([
                    dbc.CardHeader("📈 Kalibrace: Kanál → Energie"),
                    dbc.CardBody([
                        dcc.Graph(id='calibration-fit-plot', style={'height': '300px'})
                    ])
                ], className="mb-3"),
            ], width=7),
            
            # Right panel - analysis controls, results and status
            dbc.Col([
                # Analysis controls
                dbc.Card([
                    dbc.CardHeader("🎯 Analýza"),
                    dbc.CardBody([
                        # Spectrum range selection
                        html.Label("Rozsah spektra (kanály):", className="fw-bold small mb-2"),
                        dcc.RangeSlider(
                            id='cut-channel-range',
                            min=0,
                            max=2048,
                            step=10,
                            value=[0, 2048],
                            marks={
                                0: '0',
                                500: '500',
                                1000: '1000',
                                1500: '1500',
                                2048: '2048'
                            },
                            tooltip={"placement": "bottom", "always_visible": True},
                            allowCross=False,
                            className="mb-3"
                        ),
                        
                        html.Hr(className="my-2"),
                        
                        # Optimization toggle
                        dbc.Checklist(
                            id='optimize-calibration',
                            options=[{"label": " Optimalizovat", "value": "optimize"}],
                            value=["optimize"],
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
                        
                        html.Hr(),
                        
                        # Regression method selection
                        html.Label("Regresní metoda:", className="fw-bold mt-2 small"),
                        dbc.RadioItems(
                            id='regression-method',
                            options=[
                                {"label": " OLS (Ordinary Least Squares)", "value": "OLS"},
                                {"label": " NNLS (Non-Negative Least Squares)", "value": "NNLS"},
                            ],
                            value="OLS",
                            className="mb-3 small"
                        ),
                        
                        # Analyze button with loading
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
                            ],
                            parent_className='w-100'
                        ),
                        
                        # Batch processing button
                        dbc.Button(
                            [html.I(className="fas fa-layer-group me-2"), "Analyzovat vše (dávka)"],
                            id='run-batch-analysis',
                            color='info',
                            size='sm',
                            className='w-100 mt-2',
                            disabled=True,
                            outline=True
                        ),
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
                        
                        # Confirm result button
                        html.Hr(className="my-3"),
                        dbc.Button(
                            [html.I(className="fas fa-check-circle me-2"), "Potvrdit výsledek"],
                            id='confirm-result-button',
                            color='primary',
                            size='sm',
                            className="w-100",
                            disabled=True
                        ),
                    ])
                ], className="mb-3"),
                
                # Accumulated results table
                dbc.Card([
                    dbc.CardHeader([
                        "📊 Kumulativní výsledky",
                        dbc.Button(
                            html.I(className="fas fa-download"),
                            id='export-results',
                            color='success',
                            size='sm',
                            className='float-end',
                            title='Export výsledků'
                        ),
                    ]),
                    dbc.CardBody([
                        dash_table.DataTable(
                            id='accumulated-results-table',
                            columns=[
                                {'name': 'ID vzorku', 'id': 'sample_id'},
                                {'name': 'Ra (Bq)', 'id': 'Ra'},
                                {'name': 'Ra σ (Bq)', 'id': 'Ra_err'},
                                {'name': 'K (Bq)', 'id': 'K'},
                                {'name': 'K σ (Bq)', 'id': 'K_err'},
                                {'name': 'Th (Bq)', 'id': 'Th'},
                                {'name': 'Th σ (Bq)', 'id': 'Th_err'},
                                {'name': 'R²', 'id': 'R2'},
                                {'name': 'Metoda', 'id': 'method'},
                            ],
                            data=[],
                            style_table={'overflowX': 'auto'},
                            style_cell={'textAlign': 'center', 'padding': '6px', 'fontSize': '11px'},
                            style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold', 'fontSize': '11px'},
                            style_data_conditional=[
                                {
                                    'if': {'column_id': 'sample_id'},
                                    'fontWeight': 'bold',
                                    'textAlign': 'left'
                                }
                            ],
                            page_size=10,
                        ),
                    ])
                ], className="mb-3"),
                
                # Status window
                dbc.Card([
                    dbc.CardHeader("📢 Status"),
                    dbc.CardBody([
                        # Progress bar for batch processing
                        html.Div([
                            html.Small(id='batch-progress-label', children="", className="text-muted mb-1"),
                            dbc.Progress(
                                id='batch-progress',
                                value=0,
                                striped=True,
                                animated=True,
                                className="mb-2",
                                style={'height': '25px'}
                            ),
                        ], id='batch-progress-container', style={'display': 'none'}),
                        
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
                ]),
            ], width=3),
        ]),
        
        # Download component
        dcc.Download(id="download-csv"),
        
    ], fluid=True)
    
    return layout
