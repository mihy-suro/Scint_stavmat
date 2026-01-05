"""
Layout komponenty pro Dash aplikaci
Jednoduchý UI pro sekvenční analýzu vzorků
"""

import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table
def create_samples_tab_layout():
    """Vytvoří layout pro tab analýzy vzorků"""
    
    samples_layout = dbc.Container([
        # Stores for internal state
        dcc.Store(id='current-sample-calib', data={'a0': 9.6229, 'a1': 1.3793, 'a2': 0}),
        dcc.Store(id='excel-data'),
        dcc.Store(id='sample-results'),
        dcc.Store(id='peak-calibration-data'),
        dcc.Store(id='accumulated-results', data=[]),
        dcc.Store(id='loading-state', data=False),
        dcc.Download(id='download-results'),
        
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
                            value='NaI(Tl)',
                            placeholder="Vyberte detektor...",
                            className="mb-2"
                        ),
                    ])
                ], className="mb-3"),
                
                # Sample upload card
                dbc.Card([
                    dbc.CardHeader("📁 Vzorky"),
                    dbc.CardBody([
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
                        html.Div(id='spe-status', className="mt-2 small"),
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
                                    html.Th("E (keV)", style={'width': '35%'}),
                                    html.Th("CH", style={'width': '65%'})
                                ])
                            ]),
                            html.Tbody([
                                html.Tr([
                                    html.Td(dbc.Button("238", id='select-e-238', size="sm", color="light", 
                                                      className="w-100", style={'textAlign': 'left'})),
                                    html.Td([
                                        html.Span(id='peak-ch-238', children="-", className="ms-2"),
                                        dbc.Button("×", id='reset-peak-238', size="sm", color="link", 
                                                  className="p-0 ms-2 text-danger", style={'fontSize': '14px'})
                                    ])
                                ], id='row-238', style={'cursor': 'pointer'}),
                                html.Tr([
                                    html.Td(dbc.Button("295", id='select-e-295', size="sm", color="light",
                                                      className="w-100", style={'textAlign': 'left'})),
                                    html.Td([
                                        html.Span(id='peak-ch-295', children="-", className="ms-2"),
                                        dbc.Button("×", id='reset-peak-295', size="sm", color="link", 
                                                  className="p-0 ms-2 text-danger", style={'fontSize': '14px'})
                                    ])
                                ], id='row-295'),
                                html.Tr([
                                    html.Td(dbc.Button("352", id='select-e-352', size="sm", color="light",
                                                      className="w-100", style={'textAlign': 'left'})),
                                    html.Td([
                                        html.Span(id='peak-ch-352', children="-", className="ms-2"),
                                        dbc.Button("×", id='reset-peak-352', size="sm", color="link", 
                                                  className="p-0 ms-2 text-danger", style={'fontSize': '14px'})
                                    ])
                                ], id='row-352'),
                                html.Tr([
                                    html.Td(dbc.Button("609", id='select-e-609', size="sm", color="light",
                                                      className="w-100", style={'textAlign': 'left'})),
                                    html.Td([
                                        html.Span(id='peak-ch-609', children="-", className="ms-2"),
                                        dbc.Button("×", id='reset-peak-609', size="sm", color="link", 
                                                  className="p-0 ms-2 text-danger", style={'fontSize': '14px'})
                                    ])
                                ], id='row-609'),
                                html.Tr([
                                    html.Td(dbc.Button("1461", id='select-e-1461', size="sm", color="light",
                                                      className="w-100", style={'textAlign': 'left'})),
                                    html.Td([
                                        html.Span(id='peak-ch-1461', children="-", className="ms-2"),
                                        dbc.Button("×", id='reset-peak-1461', size="sm", color="link", 
                                                  className="p-0 ms-2 text-danger", style={'fontSize': '14px'})
                                    ])
                                ], id='row-1461'),
                                html.Tr([
                                    html.Td(dbc.Button("1764", id='select-e-1764', size="sm", color="light",
                                                      className="w-100", style={'textAlign': 'left'})),
                                    html.Td([
                                        html.Span(id='peak-ch-1764', children="-", className="ms-2"),
                                        dbc.Button("×", id='reset-peak-1764', size="sm", color="link", 
                                                  className="p-0 ms-2 text-danger", style={'fontSize': '14px'})
                                    ])
                                ], id='row-1764'),
                                html.Tr([
                                    html.Td(dbc.Button("2614", id='select-e-2614', size="sm", color="light",
                                                      className="w-100", style={'textAlign': 'left'})),
                                    html.Td([
                                        html.Span(id='peak-ch-2614', children="-", className="ms-2"),
                                        dbc.Button("×", id='reset-peak-2614', size="sm", color="link", 
                                                  className="p-0 ms-2 text-danger", style={'fontSize': '14px'})
                                    ])
                                ], id='row-2614'),
                            ])
                        ], size="sm", bordered=True, className="mb-2"),
                        
                        dbc.Row([
                            dbc.Col([
                                dbc.Button(
                                    "Vypočítat",
                                    id='calculate-calibration',
                                    color='success',
                                    size='sm',
                                    className='w-100 mt-2',
                                    disabled=True
                                ),
                            ], width=6),
                            dbc.Col([
                                dbc.Button(
                                    "Reset vše",
                                    id='reset-all-peaks',
                                    color='warning',
                                    size='sm',
                                    className='w-100 mt-2',
                                    outline=True
                                ),
                            ], width=6),
                        ]),
                    ])
                ], className="mb-3"),
                
            ], width=2),
            
            # Middle panel - graphs
            dbc.Col([
                # Full spectrum (top)
                dbc.Card([
                    dbc.CardHeader(id='spectrum-plot-full-header', children="📊 Celé spektrum"),
                    dbc.CardBody([
                        dcc.Loading(
                            id="loading-graph-full",
                            type="default",
                            children=dcc.Graph(id='spectrum-plot-full', style={'height': '300px'})
                        )
                    ])
                ], className="mb-3"),
                
                # ROI plots (side by side)
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Ra/Th ROI"),
                            dbc.CardBody([
                                dcc.Graph(id='spectrum-plot-roi1', style={'height': '300px'}),
                                dcc.Graph(id='residuals-plot-roi1', style={'height': '120px'})
                            ])
                        ])
                    ], width=6),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("K ROI"),
                            dbc.CardBody([
                                dcc.Graph(id='spectrum-plot-roi2', style={'height': '300px'}),
                                dcc.Graph(id='residuals-plot-roi2', style={'height': '120px'})
                            ])
                        ])  
                    ], width=6),
                ], className="mb-3"),
                
                # Calibration graph (moved from left panel)
                dbc.Card([
                    dbc.CardHeader("📈 Energetická kalibrace"),
                    dbc.CardBody([
                        dcc.Graph(id='calibration-fit-plot', config={'displayModeBar': False}, style={'height': '250px'})
                    ], className="p-2")
                ], className="mb-3"),
                
                # Status window
                dbc.Card([
                    dbc.CardHeader("📢 Status"),
                    dbc.CardBody([
                        html.Div(id='status-log', children=[
                            html.Small("Připraveno...", className="text-muted")
                        ], style={
                            'height': '80px',
                            'overflowY': 'auto',
                            'fontSize': '12px',
                            'backgroundColor': '#f8f9fa',
                            'padding': '8px',
                            'borderRadius': '4px'
                        })
                    ], className="p-2")
                ]),
            ], width=7),
            
            # Right panel - analysis controls, results and status
            dbc.Col([
                # Analysis controls
                dbc.Card([
                    dbc.CardHeader("🎯 Optimalizace energetické kalibrace"),
                    dbc.CardBody([
                        # Optimization and regression on one row
                        dbc.Row([
                            dbc.Col([
                                dbc.Checklist(
                                    id='optimize-calibration',
                                    options=[{"label": " Optimalizovat", "value": "optimize"}],
                                    value=["optimize"],
                                    switch=True,
                                )
                            ], width=4),
                            dbc.Col([
                                dcc.Dropdown(
                                    id='regression-method',
                                    options=[
                                        {"label": "OLS", "value": "OLS"},
                                        {"label": "NNLS", "value": "NNLS"},
                                    ],
                                    value="OLS",
                                    clearable=False,
                                    placeholder="Regrese",
                                    style={'fontSize': '13px'}
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Checklist(
                                    id='use-background',
                                    options=[{"label": " Použít pozadí", "value": "use"}],
                                    value=[],
                                    switch=True,
                                    className="mt-1"
                                )
                            ], width=3),
                            dbc.Col([
                                dcc.Dropdown(
                                    id='optimization-method',
                                    options=[
                                        {'label': 'L-BFGS-B', 'value': 'L-BFGS-B'},
                                        {'label': 'Powell', 'value': 'Powell'},
                                        {'label': 'Nelder-Mead', 'value': 'Nelder-Mead'},
                                    ],
                                    value='L-BFGS-B',
                                    clearable=False,
                                    placeholder="Optimalizace",
                                    style={'fontSize': '13px'}
                                )
                            ], width=3),
                        ], className="mb-2"),
                        
                        # Hidden max-iterations field (value from config)
                        dbc.Input(id='max-iterations', type='hidden', value=1000),
                        
                        # Dual ROI analysis card
                        dbc.Card([
                            dbc.CardHeader("🎯 Definice ROI (kanály)"),
                            dbc.CardBody([
                                # Region 1: Ra/Th - RangeSlider IN CHANNELS
                                html.Label("Ra/Th ROI:", className="fw-bold small mb-1"),
                                dcc.RangeSlider(
                                    id='roi1-range-slider',
                                    min=0,
                                    max=2047,
                                    step=1,
                                    value=[138, 573],
                                    marks={
                                        0: '0',
                                        200: '200',
                                        400: '400',
                                        600: '600',
                                        800: '800',
                                        1000: '1000',
                                        1200: '1200',
                                        1400: '1400',
                                        1600: '1600',
                                        1800: '1800',
                                        2000: '2000'
                                    },
                                    tooltip={"placement": "bottom", "always_visible": True},
                                    allowCross=False,
                                    className="mb-3"
                                ),
                                
                                # Region 2: K-40 - RangeSlider IN CHANNELS
                                html.Label("K ROI:", className="fw-bold small mb-1"),
                                dcc.RangeSlider(
                                    id='roi2-range-slider',
                                    min=0,
                                    max=2047,
                                    step=1,
                                    value=[504, 1182],
                                    marks={
                                        0: '0',
                                        200: '200',
                                        400: '400',
                                        600: '600',
                                        800: '800',
                                        1000: '1000',
                                        1200: '1200',
                                        1400: '1400',
                                        1600: '1600',
                                        1800: '1800',
                                        2000: '2000'
                                    },
                                    tooltip={"placement": "bottom", "always_visible": True},
                                    allowCross=False,
                                    className="mb-2"
                                ),
                            ], className="p-2")
                        ], className="mb-3", color="info", outline=True),
                        
                        # Hidden stores for ROI ranges (now in CHANNELS)
                        dcc.Store(id='roi1-range', data=[138, 573]),
                        dcc.Store(id='roi2-range', data=[504, 1182]),
                        
                        # Analysis status/warning display
                        html.Div(id='analysis-status', className="mt-3"),
                        
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
                        
                        # Navigation buttons
                        dbc.Row([
                            dbc.Col([
                                dbc.Button(
                                    [html.I(className="fas fa-backward me-2"), "Předchozí"],
                                    id='previous-sample-button',
                                    color='info',
                                    size='sm',
                                    className='w-100',
                                    disabled=True,
                                    outline=True
                                ),
                            ], width=6),
                            dbc.Col([
                                dbc.Button(
                                    [html.I(className="fas fa-forward me-2"), "Další"],
                                    id='next-sample-button',
                                    color='info',
                                    size='sm',
                                    className='w-100',
                                    disabled=True,
                                    outline=True
                                ),
                            ], width=6),
                        ], className='mt-2'),
                    ])
                ], className="mb-3"),
                
                # Accumulated results table
                dbc.Card([
                    dbc.CardHeader([
                        "📊 Výsledky",
                        dbc.ButtonGroup([
                            dbc.Button(
                                html.I(className="fas fa-trash"),
                                id='delete-selected-rows',
                                color='danger',
                                size='sm',
                                title='Smazat vybrané řádky',
                                className='me-1'
                            ),
                            dbc.Button(
                                html.I(className="fas fa-download"),
                                id='export-results',
                                color='success',
                                size='sm',
                                title='Export výsledků'
                            ),
                        ], className='float-end'),
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
                                {'name': 'Index', 'id': 'Index'},
                                {'name': 'Index σ', 'id': 'Index_err'},
                            ],
                            data=[],
                            row_selectable='multi',
                            selected_rows=[],
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
            ], width=3),
        ]),
        
        # Download components
        dcc.Download(id="download-csv"),
        
    ], fluid=True)
    
    return samples_layout


def create_layout():
    """Vytvoří hlavní layout aplikace s tabs"""
    
    layout = dbc.Container([
        # Global shared stores
        dcc.Store(id='shared-detector', data=None),  # Synchronize detector between tabs
        
        # Header
        dbc.Row([
            dbc.Col([
                html.H2("☢️ Analýza scintilačních spekter CeBr₃ & NaI(Tl)", 
                       className="text-center mt-3 mb-3"),
            ])
        ]),
        
        # Content - single tab layout
        create_samples_tab_layout(),
        
    ], fluid=True)
    
    return layout

