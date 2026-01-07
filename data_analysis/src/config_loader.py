"""
config_loader.py - Načítání centrální konfigurace

Poskytuje funkce pro načtení konfigurace z config.yaml
a převod na struktury používané ve skriptech.
"""

from pathlib import Path
from typing import Dict, Any, Tuple
import yaml


def load_config(config_path: Path = None) -> Dict[str, Any]:
    """
    Načte konfiguraci z YAML souboru.
    
    Parameters:
    -----------
    config_path : Path, optional
        Cesta ke konfiguračnímu souboru. Pokud není zadána,
        použije se config.yaml ve stejném adresáři.
    
    Returns:
    --------
    dict : Slovník s konfigurací
    """
    if config_path is None:
        # config.yaml is in parent directory (data_analysis/) not in src/
        config_path = Path(__file__).parent.parent / "config.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config


def get_elements_dict(config: Dict[str, Any], element_type: str = 'deconvolution') -> Dict[str, Tuple[str, str]]:
    """
    Převede konfiguraci prvků na formát používaný ve skriptech.
    
    Parameters:
    -----------
    config : dict
        Načtená konfigurace
    element_type : str
        'deconvolution' nebo '186_keV'
    
    Returns:
    --------
    dict : {element_name: (activity_col, uncertainty_col)}
    """
    elements_config = config.get('elements', {}).get(element_type, {})
    
    result = {}
    for element_name, cols in elements_config.items():
        result[element_name] = (cols['activity_col'], cols['uncertainty_col'])
    
    return result


# Singleton pro konfiguraci - načte se jen jednou
_config_cache = None


def get_config() -> Dict[str, Any]:
    """
    Vrátí konfiguraci (cache-ovanou).
    """
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache


# Pomocné funkce pro snadný přístup
def get_correction_model() -> str:
    """Vrátí název korekčního modelu."""
    return get_config()['correction']['model']


def get_reference_density() -> float:
    """Vrátí referenční hustotu."""
    return get_config()['correction']['reference_density']


def get_outlier_threshold() -> float:
    """Vrátí práh pro identifikaci outlierů."""
    return get_config()['outliers']['threshold']


def get_relative_uncertainty_nai() -> float:
    """Vrátí relativní nejistotu NaI(Tl)."""
    return get_config()['uncertainty']['relative_nai']


def get_input_files() -> Dict[str, str]:
    """Vrátí konfiguraci vstupních souborů."""
    return get_config()['input']


def get_output_dir() -> str:
    """Vrátí výstupní adresář."""
    return get_config()['output']['directory']
