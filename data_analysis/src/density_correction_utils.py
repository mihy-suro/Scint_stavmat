"""
Utility funkce pro korekci sampoabsorpce v NaI(Tl) měřeních na základě hustoty vzorku

Implementuje různé korekční modely a optimalizační procedury pro nalezení
optimálních korekčních faktorů minimalizací rozdílů mezi HPGe a NaI(Tl) měřeními.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize, curve_fit
from scipy import stats
from sklearn.model_selection import KFold
from typing import Dict, Tuple, Callable, Optional


# ============================================================
# KOREKČNÍ MODELY
# ============================================================

def exponential_model(A: np.ndarray, density: np.ndarray, b: float) -> np.ndarray:
    """
    Exponenciální korekce: A_corrected = A * exp(b * ρ)
    
    Parameters:
    -----------
    A : array
        Naměřená aktivita
    density : array
        Hustota vzorku [g/cm³]
    b : float
        Korekční koeficient (očekáváme b > 0, protože kompenzujeme ztráty)
    """
    return A * np.exp(b * density)


def linear_model(A: np.ndarray, density: np.ndarray, b: float) -> np.ndarray:
    """
    Lineární korekce: A_corrected = A * (1 + b * ρ)
    """
    return A * (1 + b * density)


def power_model(A: np.ndarray, density: np.ndarray, b: float) -> np.ndarray:
    """
    Mocninná korekce: A_corrected = A * ρ^b
    """
    # Ochrana proti nule/záporným hodnotám
    safe_density = np.maximum(density, 0.1)
    return A * np.power(safe_density, b)


def quadratic_centered_model(A: np.ndarray, density: np.ndarray, params: np.ndarray, rho_ref: float = 1.0) -> np.ndarray:
    """
    Kvadratická korekce centrovaná kolem referenční hustoty:
    A_corrected = A * [1 + b*(ρ - ρ_ref) + c*(ρ - ρ_ref)²]
    
    Tento model umožňuje asymetrickou korekci:
    - Pro nízké hustoty (ρ < ρ_ref): Může kompenzovat nadhodnocení NaI(Tl)
    - Pro vysoké hustoty (ρ > ρ_ref): Může kompenzovat podhodnocení NaI(Tl)
    
    Parameters:
    -----------
    A : array
        Naměřená aktivita
    density : array
        Hustota vzorku [g/cm³]
    params : array
        Korekční koeficienty [b, c]
    rho_ref : float
        Referenční hustota [g/cm³], typicky 1.0 (voda)
    """
    b = params[0]
    c = params[1] if len(params) > 1 else 0.0
    delta_rho = density - rho_ref
    return A * (1 + b * delta_rho + c * delta_rho**2)


def scaled_exponential_model(A: np.ndarray, density: np.ndarray, params: np.ndarray, rho_ref: float = 1.0) -> np.ndarray:
    """
    Škálovaná exponenciální korekce:
    A_corrected = a * A * exp(b * (ρ - ρ_ref))
    
    Kombinuje:
    - Lineární škálování (a): opravuje systematický bias/sklon
    - Exponenciální korekce (b): opravuje závislost na hustotě (samoabsorpce)
    
    Parameters:
    -----------
    A : array
        Naměřená aktivita
    density : array
        Hustota vzorku [g/cm³]
    params : array
        Korekční koeficienty [a, b]
        a = škálovací faktor (a > 1: NaI podhodnocuje, a < 1: NaI nadhodnocuje)
        b = koeficient samoabsorpce (b > 0: vyšší hustota → vyšší korekce)
    rho_ref : float
        Referenční hustota [g/cm³]
    """
    a = params[0]
    b = params[1] if len(params) > 1 else 0.0
    delta_rho = density - rho_ref
    return a * A * np.exp(b * delta_rho)


def scaled_exponential_quadratic_model(A: np.ndarray, density: np.ndarray, params: np.ndarray, rho_ref: float = 1.0) -> np.ndarray:
    """
    Škálovaná exponenciální korekce s kvadratickým členem:
    A_corrected = a * A * exp(b * (ρ - ρ_ref) + c * (ρ - ρ_ref)²)
    
    Kombinuje:
    - Lineární škálování (a): opravuje systematický bias/sklon
    - Exponenciální korekce (b): opravuje lineární závislost na hustotě
    - Kvadratický člen (c): opravuje nelinearitu při vysokých hustotách
    
    Parameters:
    -----------
    A : array
        Naměřená aktivita
    density : array
        Hustota vzorku [g/cm³]
    params : array
        Korekční koeficienty [a, b, c]
        a = škálovací faktor (a > 1: NaI podhodnocuje)
        b = lineární koeficient samoabsorpce
        c = kvadratický koeficient (c > 0: silnější korekce při vysokých hustotách)
    rho_ref : float
        Referenční hustota [g/cm³]
    """
    a = params[0]
    b = params[1] if len(params) > 1 else 0.0
    c = params[2] if len(params) > 2 else 0.0
    delta_rho = density - rho_ref
    return a * A * np.exp(b * delta_rho + c * delta_rho**2)


# Slovník dostupných modelů
CORRECTION_MODELS: Dict[str, Callable] = {
    'exponential': exponential_model,
    'linear': linear_model,
    'power': power_model,
    'quadratic_centered': quadratic_centered_model,
    'scaled_exponential': scaled_exponential_model,
    'scaled_exponential_quadratic': scaled_exponential_quadratic_model
}


# ============================================================
# OPTIMALIZAČNÍ FUNKCE
# ============================================================

def fit_correction_factor(
    A_hpge: np.ndarray,
    A_nai: np.ndarray,
    density: np.ndarray,
    U_hpge: np.ndarray,
    U_nai: np.ndarray,
    model: str = 'exponential',
    rho_ref: float = 1.0
) -> Dict:
    """
    Najde optimální korekční faktor minimalizací rozdílů mezi HPGe a NaI(Tl).
    
    Parameters:
    -----------
    A_hpge : array
        Aktivita měřená HPGe (referenční)
    A_nai : array
        Aktivita měřená NaI(Tl) (ke korekci)
    density : array
        Hustota vzorků [g/cm³]
    U_hpge, U_nai : array
        Nejistoty měření
    model : str
        Typ korekčního modelu ('exponential', 'linear', 'power', 'quadratic_centered')
    rho_ref : float
        Referenční hustota [g/cm³] pro centered modely
    
    Returns:
    --------
    dict : Slovník s výsledky fitu
    """
    if model not in CORRECTION_MODELS:
        raise ValueError(f"Neznámý model: {model}. Dostupné: {list(CORRECTION_MODELS.keys())}")
    
    correction_func = CORRECTION_MODELS[model]
    
    # Odstranění NaN hodnot
    mask = ~(np.isnan(A_hpge) | np.isnan(A_nai) | np.isnan(density))
    A_hpge_clean = A_hpge[mask]
    A_nai_clean = A_nai[mask]
    density_clean = density[mask]
    U_hpge_clean = U_hpge[mask]
    U_nai_clean = U_nai[mask]
    
    if len(A_hpge_clean) < 3:
        return {
            'b': 0.0,
            'b_uncertainty': 0.0,
            'R2_before': 0.0,
            'R2_after': 0.0,
            'RMSE_before': 0.0,
            'RMSE_after': 0.0,
            'chi2_before': 0.0,
            'chi2_after': 0.0,
            'success': False,
            'message': 'Nedostatek dat pro fit'
        }
    
    # Výpočet metrik před korekcí
    R2_before = calculate_r2(A_hpge_clean, A_nai_clean)
    RMSE_before = calculate_rmse(A_hpge_clean, A_nai_clean)
    chi2_before = calculate_chi2(A_hpge_clean, A_nai_clean, U_hpge_clean, U_nai_clean)
    
    # Definice cost funkce (weighted least squares)
    def cost_function(params):
        if model == 'quadratic_centered':
            A_corrected = quadratic_centered_model(A_nai_clean, density_clean, params, rho_ref)
        elif model == 'scaled_exponential':
            A_corrected = scaled_exponential_model(A_nai_clean, density_clean, params, rho_ref)
        elif model == 'scaled_exponential_quadratic':
            A_corrected = scaled_exponential_quadratic_model(A_nai_clean, density_clean, params, rho_ref)
        elif model == 'exponential':
            A_corrected = exponential_model(A_nai_clean, density_clean, params[0])
        elif model == 'linear':
            A_corrected = linear_model(A_nai_clean, density_clean, params[0])
        elif model == 'power':
            A_corrected = power_model(A_nai_clean, density_clean, params[0])
        else:
            A_corrected = A_nai_clean
        
        weights = 1.0 / (U_hpge_clean**2 + U_nai_clean**2)
        residuals = (A_hpge_clean - A_corrected)**2
        return np.sum(residuals * weights)
    
    # Optimalizace
    # Inicializační hodnoty závisí na modelu
    if model == 'scaled_exponential':
        # Odhad počátečního 'a' z poměru průměrů
        a0 = np.mean(A_hpge_clean) / np.mean(A_nai_clean) if np.mean(A_nai_clean) > 0 else 1.0
        x0 = [a0, 0.1]  # [a, b]
        bounds = [(0.1, 10.0), (-2.0, 2.0)]
    elif model == 'scaled_exponential_quadratic':
        # Odhad počátečního 'a' z poměru průměrů
        a0 = np.mean(A_hpge_clean) / np.mean(A_nai_clean) if np.mean(A_nai_clean) > 0 else 1.0
        x0 = [a0, 0.1, 0.0]  # [a, b, c]
        bounds = [(0.1, 10.0), (-2.0, 2.0), (-1.0, 1.0)]
    elif model == 'quadratic_centered':
        x0 = [0.0, 0.0]  # [b, c]
        bounds = [(-2.0, 2.0), (-2.0, 2.0)]
    elif model == 'exponential':
        x0 = [0.1]  # Malá pozitivní hodnota
        bounds = [(-2.0, 2.0)]
    elif model == 'linear':
        x0 = [0.0]
        bounds = [(-2.0, 2.0)]
    else:  # power
        x0 = [0.1]
        bounds = [(-1.0, 1.0)]
    
    result = minimize(
        cost_function,
        x0=x0,
        method='L-BFGS-B',
        bounds=bounds
    )
    
    params_opt = result.x
    
    # Aplikace korekce
    if model == 'quadratic_centered':
        A_nai_corrected = quadratic_centered_model(A_nai_clean, density_clean, params_opt, rho_ref)
    elif model == 'scaled_exponential':
        A_nai_corrected = scaled_exponential_model(A_nai_clean, density_clean, params_opt, rho_ref)
    elif model == 'scaled_exponential_quadratic':
        A_nai_corrected = scaled_exponential_quadratic_model(A_nai_clean, density_clean, params_opt, rho_ref)
    elif model == 'exponential':
        A_nai_corrected = exponential_model(A_nai_clean, density_clean, params_opt[0])
    elif model == 'linear':
        A_nai_corrected = linear_model(A_nai_clean, density_clean, params_opt[0])
    elif model == 'power':
        A_nai_corrected = power_model(A_nai_clean, density_clean, params_opt[0])
    else:
        A_nai_corrected = A_nai_clean
    
    # Výpočet metrik po korekci
    R2_after = calculate_r2(A_hpge_clean, A_nai_corrected)
    RMSE_after = calculate_rmse(A_hpge_clean, A_nai_corrected)
    chi2_after = calculate_chi2(A_hpge_clean, A_nai_corrected, U_hpge_clean, U_nai_clean)
    
    # Odhad nejistoty parametrů
    param_uncertainties = [estimate_parameter_uncertainty(
        cost_function, params_opt[i] if len(params_opt) > i else 0, chi2_after, len(A_hpge_clean)
    ) for i in range(len(params_opt))]
    
    # Sestavení výsledku podle modelu
    result_dict = {
        'params': params_opt,
        'R2_before': R2_before,
        'R2_after': R2_after,
        'RMSE_before': RMSE_before,
        'RMSE_after': RMSE_after,
        'chi2_before': chi2_before,
        'chi2_after': chi2_after,
        'n_samples': len(A_hpge_clean),
        'success': result.success,
        'message': result.message if hasattr(result, 'message') else 'OK'
    }
    
    if model == 'scaled_exponential':
        result_dict['a'] = params_opt[0]
        result_dict['b'] = params_opt[1]
        result_dict['a_uncertainty'] = param_uncertainties[0] if len(param_uncertainties) > 0 else 0.05
        result_dict['b_uncertainty'] = param_uncertainties[1] if len(param_uncertainties) > 1 else 0.05
    elif model == 'scaled_exponential_quadratic':
        result_dict['a'] = params_opt[0]
        result_dict['b'] = params_opt[1]
        result_dict['c'] = params_opt[2] if len(params_opt) > 2 else 0.0
        result_dict['a_uncertainty'] = param_uncertainties[0] if len(param_uncertainties) > 0 else 0.05
        result_dict['b_uncertainty'] = param_uncertainties[1] if len(param_uncertainties) > 1 else 0.05
        result_dict['c_uncertainty'] = param_uncertainties[2] if len(param_uncertainties) > 2 else 0.05
    elif model == 'quadratic_centered':
        result_dict['b'] = params_opt[0]
        result_dict['c'] = params_opt[1] if len(params_opt) > 1 else 0.0
        result_dict['b_uncertainty'] = param_uncertainties[0] if len(param_uncertainties) > 0 else 0.05
        result_dict['c_uncertainty'] = param_uncertainties[1] if len(param_uncertainties) > 1 else 0.05
    else:
        result_dict['b'] = params_opt[0]
        result_dict['b_uncertainty'] = param_uncertainties[0] if len(param_uncertainties) > 0 else 0.05
    
    return result_dict


def estimate_parameter_uncertainty(cost_func: Callable, b_opt: float, chi2_min: float, n_samples: int) -> float:
    """
    Odhadne nejistotu parametru b pomocí delta chi² metody.
    
    Hledá b hodnoty kde chi² = chi²_min + 1 (68% confidence interval)
    """
    try:
        # Grid search kolem optima
        b_range = np.linspace(b_opt - 0.5, b_opt + 0.5, 50)
        chi2_values = np.array([cost_func([b]) for b in b_range])
        
        # Najít kde chi² překročí threshold
        threshold = chi2_min + 1.0
        above_threshold = chi2_values > threshold
        
        if np.any(above_threshold) and np.any(~above_threshold):
            # Odhadnout šířku
            uncertainty = np.std(b_range[~above_threshold])
            if np.isnan(uncertainty) or uncertainty <= 0:
                return 0.05  # Default
            return max(uncertainty, 0.01)  # Minimální nejistota
        else:
            # Jednoduchý odhad z rozsahu hledání
            return 0.05  # Default
    except:
        return 0.05  # Default fallback


# ============================================================
# METRIKY
# ============================================================

def calculate_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Koeficient determinace R²"""
    ss_res = np.sum((y_true - y_pred)**2)
    ss_tot = np.sum((y_true - np.mean(y_true))**2)
    return 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0


def calculate_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Root Mean Square Error"""
    return np.sqrt(np.mean((y_true - y_pred)**2))


def calculate_chi2(y_true: np.ndarray, y_pred: np.ndarray, u_true: np.ndarray, u_pred: np.ndarray) -> float:
    """Redukované chi²"""
    sigma_total = np.sqrt(u_true**2 + u_pred**2)
    chi2 = np.sum(((y_true - y_pred) / sigma_total)**2)
    n = len(y_true)
    return chi2 / (n - 1) if n > 1 else 0.0


# ============================================================
# HLAVNÍ FUNKCE PRO OPTIMALIZACI VŠECH PRVKŮ
# ============================================================

def optimize_all_elements(
    df_compare: pd.DataFrame,
    elements_dict: Dict[str, Tuple[str, str]],
    model: str = 'exponential',
    rho_ref: float = 1.0,
    verbose: bool = True
) -> Dict:
    """
    Optimalizuje korekční faktory pro všechny prvky.
    
    Parameters:
    -----------
    df_compare : DataFrame
        Data s HPGe a NaI měřeními (již merged)
    elements_dict : dict
        Slovník {název_prvku: (activity_col, uncertainty_col)}
    model : str
        Typ korekčního modelu
    rho_ref : float
        Referenční hustota [g/cm³] pro centered modely
    verbose : bool
        Zda tisknout průběžné výsledky
    
    Returns:
    --------
    dict : Slovník s výsledky pro každý prvek
    """
    results = {}
    
    # Výpočet hustoty
    weight_col = 'Hmotnost [kg]_HPGe' if 'Hmotnost [kg]_HPGe' in df_compare.columns else 'Hmotnost [kg]'
    volume_col = 'Objem [l]_HPGe' if 'Objem [l]_HPGe' in df_compare.columns else 'Objem [l]'
    density = (df_compare[weight_col] / df_compare[volume_col]).values
    
    if verbose:
        print("\n" + "="*60)
        print("OPTIMALIZACE KOREKČNÍCH FAKTORŮ SAMPOABSORPCE")
        print("="*60)
        print(f"Model: {model}")
        print(f"Počet vzorků: {len(df_compare)}")
        print(f"Rozsah hustot: {density.min():.3f} - {density.max():.3f} g/cm³")
        print("="*60)
    
    for element_name, (activity_col, uncertainty_col) in elements_dict.items():
        hpge_act = f"{activity_col}_HPGe"
        nai_act = f"{activity_col}_NaI"
        hpge_unc = f"{uncertainty_col}_HPGe"
        nai_unc = f"{uncertainty_col}_NaI"
        
        # Extrakce dat
        A_hpge = df_compare[hpge_act].values
        A_nai = df_compare[nai_act].values
        U_hpge = df_compare[hpge_unc].values
        U_nai = df_compare[nai_unc].values
        
        # Fit
        fit_result = fit_correction_factor(
            A_hpge, A_nai, density, U_hpge, U_nai, model=model, rho_ref=rho_ref
        )
        
        results[element_name] = fit_result
        
        if verbose:
            print(f"\n{element_name}:")
            if model == 'scaled_exponential':
                print(f"  a = {fit_result['a']:.4f} ± {fit_result['a_uncertainty']:.4f}")
                print(f"  b = {fit_result['b']:.4f} ± {fit_result['b_uncertainty']:.4f}")
            elif model == 'scaled_exponential_quadratic':
                print(f"  a = {fit_result['a']:.4f} ± {fit_result['a_uncertainty']:.4f}")
                print(f"  b = {fit_result['b']:.4f} ± {fit_result['b_uncertainty']:.4f}")
                print(f"  c = {fit_result['c']:.4f} ± {fit_result['c_uncertainty']:.4f}")
            elif model == 'quadratic_centered':
                print(f"  b = {fit_result['b']:.4f} ± {fit_result['b_uncertainty']:.4f}")
                print(f"  c = {fit_result['c']:.4f} ± {fit_result['c_uncertainty']:.4f}")
            else:
                print(f"  b = {fit_result['b']:.4f} ± {fit_result['b_uncertainty']:.4f}")
            print(f"  R² před:  {fit_result['R2_before']:.4f}")
            print(f"  R² po:    {fit_result['R2_after']:.4f}  " +
                  f"(Δ = {fit_result['R2_after'] - fit_result['R2_before']:+.4f})")
            print(f"  RMSE před: {fit_result['RMSE_before']:.3f} Bq/kg")
            print(f"  RMSE po:   {fit_result['RMSE_after']:.3f} Bq/kg  " +
                  f"({(1 - fit_result['RMSE_after']/fit_result['RMSE_before'])*100:.1f}% redukce)")
            print(f"  χ²/ndf před: {fit_result['chi2_before']:.3f}")
            print(f"  χ²/ndf po:   {fit_result['chi2_after']:.3f}")
    
    if verbose:
        print("\n" + "="*60)
    
    return results


# ============================================================
# APLIKACE KOREKCE
# ============================================================

def apply_correction(
    A_nai: np.ndarray,
    density: np.ndarray,
    b: float,
    model: str = 'exponential',
    c: float = 0.0,
    rho_ref: float = 1.0,
    a: float = 1.0
) -> np.ndarray:
    """
    Aplikuje korekci na NaI(Tl) data.
    
    Parameters:
    -----------
    A_nai : array
        Naměřená aktivita NaI(Tl)
    density : array
        Hustota vzorků [g/cm³]
    b : float
        Korekční koeficient (lineární člen)
    model : str
        Typ korekčního modelu
    c : float
        Kvadratický koeficient (pro quadratic_centered model)
    rho_ref : float
        Referenční hustota [g/cm³] (pro centered modely)
    a : float
        Škálovací faktor (pro scaled_exponential model)
    
    Returns:
    --------
    array : Korigovaná aktivita
    """
    if model not in CORRECTION_MODELS:
        raise ValueError(f"Neznámý model: {model}")
    
    if model == 'scaled_exponential':
        params = np.array([a, b])
        return scaled_exponential_model(A_nai, density, params, rho_ref)
    elif model == 'scaled_exponential_quadratic':
        params = np.array([a, b, c])
        return scaled_exponential_quadratic_model(A_nai, density, params, rho_ref)
    elif model == 'quadratic_centered':
        params = np.array([b, c])
        return quadratic_centered_model(A_nai, density, params, rho_ref)
    else:
        correction_func = CORRECTION_MODELS[model]
        return correction_func(A_nai, density, b)


# ============================================================
# CROSS-VALIDACE (volitelné)
# ============================================================

def cross_validate(
    df_compare: pd.DataFrame,
    element: str,
    activity_col: str,
    uncertainty_col: str,
    model: str = 'exponential',
    k_folds: int = 5
) -> Dict:
    """
    K-fold cross-validace pro ověření robustnosti korekce.
    
    Returns:
    --------
    dict : Průměr a std R² a RMSE přes foldy
    """
    weight_col = 'Hmotnost [kg]_HPGe' if 'Hmotnost [kg]_HPGe' in df_compare.columns else 'Hmotnost [kg]'
    volume_col = 'Objem [l]_HPGe' if 'Objem [l]_HPGe' in df_compare.columns else 'Objem [l]'
    
    hpge_act = f"{activity_col}_HPGe"
    nai_act = f"{activity_col}_NaI"
    hpge_unc = f"{uncertainty_col}_HPGe"
    nai_unc = f"{uncertainty_col}_NaI"
    
    # Připravit data
    df_clean = df_compare.dropna(subset=[hpge_act, nai_act, weight_col, volume_col]).copy()
    df_clean['density'] = df_clean[weight_col] / df_clean[volume_col]
    
    kf = KFold(n_splits=k_folds, shuffle=True, random_state=42)
    
    r2_scores = []
    rmse_scores = []
    
    for train_idx, test_idx in kf.split(df_clean):
        # Train set
        train_data = df_clean.iloc[train_idx]
        A_hpge_train = train_data[hpge_act].values
        A_nai_train = train_data[nai_act].values
        density_train = train_data['density'].values
        U_hpge_train = train_data[hpge_unc].values
        U_nai_train = train_data[nai_unc].values
        
        # Fit na train
        fit_result = fit_correction_factor(
            A_hpge_train, A_nai_train, density_train,
            U_hpge_train, U_nai_train, model=model
        )
        
        # Test na test set
        test_data = df_clean.iloc[test_idx]
        A_hpge_test = test_data[hpge_act].values
        A_nai_test = test_data[nai_act].values
        density_test = test_data['density'].values
        
        A_nai_corrected = apply_correction(A_nai_test, density_test, fit_result['b'], model)
        
        r2 = calculate_r2(A_hpge_test, A_nai_corrected)
        rmse = calculate_rmse(A_hpge_test, A_nai_corrected)
        
        r2_scores.append(r2)
        rmse_scores.append(rmse)
    
    return {
        'R2_mean': np.mean(r2_scores),
        'R2_std': np.std(r2_scores),
        'RMSE_mean': np.mean(rmse_scores),
        'RMSE_std': np.std(rmse_scores)
    }
