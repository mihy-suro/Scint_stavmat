# Architektura kalibrace - Store-based synchronization

## Koncept

### Referencní kalibrace (ref_calib)
- **Zdroj**: Excel list Parametry → sloupce `ref_a0`, `ref_a1`, `ref_a2`
- **Vlastnosti**: Fixní, nikdy se nemění během běhu aplikace
- **Viditelnost**: Skryté inputy v UI (`ref-a0`, `ref-a1`, `ref-a2`)
- **Účel**: Cílová energetická škála pro rebinning, společná pro všechny vzorky

### Vzorková kalibrace (sample_calib)
- **Zdroj**: Uživatelsky editovatelná
- **Vlastnosti**: Dynamická, mění se při:
  - Načtení Excel (default z Parametry nebo sample_a0/a1 pokud existují)
  - Manuální editaci polí
  - Manuální kalibraci (fit peaků)
  - Optimalizaci
- **Viditelnost**: Viditelné inputy (`manual-a0`, `manual-a1`, `manual-a2`)
- **Účel**: Energetická škála aktuálního vzorku, použitá pro rebinning

## Store-based synchronization

### dcc.Store('current-sample-calib')
```python
dcc.Store(id='current-sample-calib', data={'a0': 9.6229, 'a1': 1.3793, 'a2': 0})
```

### Sync callback
```python
@app.callback(
    Output('current-sample-calib', 'data'),
    [Input('manual-a0', 'value'), Input('manual-a1', 'value'), Input('manual-a2', 'value')]
)
def sync_sample_calibration(a0, a1, a2):
    """Automaticky synchronizuje UI pole → store při jakékoliv změně"""
    return {'a0': a0, 'a1': a1, 'a2': a2 or 0}
```

## Použití v callbackech

### 1. calibration.py - Vizualizace kalibrační křivky
```python
@app.callback(
    Output('calibration-fit-plot', 'figure'),
    [...],
    Input('current-sample-calib', 'data')  # Čtení ze store
)
def plot_calibration_fit(calib_data, current_sample_calib):
    a0 = current_sample_calib.get('a0', 9.6229)
    a1 = current_sample_calib.get('a1', 1.3793)
    # ... použití pro vykreslení
```

### 2. analysis.py - Hlavní analýza
```python
@app.callback(
    [...],
    State('current-sample-calib', 'data')  # Čtení ze store
)
def run_analysis(..., current_sample_calib, ...):
    # Referencní kalibrace (fixní)
    ref_calib = [ref_a0, ref_a1, ref_a2]
    
    # Vzorková kalibrace ze store (aktuální UI hodnoty)
    initial_sample_calib = [
        current_sample_calib.get('a0', 9.6229),
        current_sample_calib.get('a1', 1.3793),
        current_sample_calib.get('a2', 0)
    ]
    
    if is_optimizing:
        bounds = [(5, 15), (1.35, 1.45), (0, 1e-5)]
        sample_calib = find_optimal_calibration(
            ref_calib,
            initial_sample_calib,  # START Z AKTUÁLNÍCH UI HODNOT
            X, y,
            bounds[:len(initial_sample_calib)],  # Slice bounds
            method='L-BFGS-B'
        )
    else:
        sample_calib = initial_sample_calib
```

### 3. visualization.py - Raw spektrum
```python
@app.callback(
    Output('spectrum-plot', 'figure'),
    [...],
    State('current-sample-calib', 'data')  # Čtení ze store
)
def update_plot(..., current_sample_calib):
    # Pro raw spektrum (před analýzou)
    sample_calib = [
        current_sample_calib.get('a0', 9.6229),
        current_sample_calib.get('a1', 1.3793),
        current_sample_calib.get('a2', 0)
    ]
    energies = [calculate_energy(ch, sample_calib) for ch in channels]
```

## Workflow

1. **Načtení Excel**:
   - `parse_excel()` nastaví `ref-a0/a1/a2` (skryté) a `manual-a0/a1` (viditelné)
   - Sync callback automaticky aktualizuje store

2. **Manuální editace**:
   - Uživatel změní `manual-a0` nebo `manual-a1`
   - Sync callback automaticky aktualizuje store
   - `plot_calibration_fit()` se přepočítá s novými hodnotami

3. **Manuální kalibrace**:
   - Uživatel klikne energii + peak v grafu
   - `calculate_and_apply_calibration()` fitne peak→channel data
   - Vrátí nové hodnoty do `manual-a0`, `manual-a1`
   - Sync callback automaticky aktualizuje store

4. **Optimalizace**:
   - `run_analysis()` přečte aktuální hodnoty ze store
   - Použije je jako `initial_sample_calib` pro optimalizaci
   - Optimalizace vrátí nové hodnoty do `manual-a0`, `manual-a1`
   - Sync callback automaticky aktualizuje store

## Výhody

1. **Single source of truth**: UI pole jsou jediný zdroj pravdy
2. **Automatická synchronizace**: Žádné ruční propojování callbacků
3. **Respektování uživatelských edits**: Optimalizace vždy startuje z aktuálních hodnot
4. **Opravuje bounds error**: Správné slicing `bounds[:len(initial_sample_calib)]`
5. **Konzistentní workflow**: Všechny cesty (Excel, manual edit, manual fit, optimize) fungují stejně

## Opravené chyby

### Původní problém
```python
# ❌ ŠPATNĚ - používalo ref_calib jako start
sample_calib = find_optimal_calibration(
    ref_calib,
    ref_calib,  # START Z FIXNÍ KALIBRACE - ignoruje UI edits!
    X, y,
    bounds,  # 2 bounds pro 3 parametry → ERROR
    method='L-BFGS-B'
)
```

### Opraveno
```python
# ✅ SPRÁVNĚ - používá aktuální UI hodnoty ze store
initial_sample_calib = [store['a0'], store['a1'], store['a2']]
sample_calib = find_optimal_calibration(
    ref_calib,
    initial_sample_calib,  # START Z AKTUÁLNÍCH UI HODNOT
    X, y,
    bounds[:len(initial_sample_calib)],  # Slice bounds
    method='L-BFGS-B'
)
```
