#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
viz_config.py - Konfigurace pro vizualizaci

Obsahuje:
- VizConfig dataclass pro centralizovanou konfiguraci
- Načtení konstant z config.yaml
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional

from .config_loader import (
    get_config, get_elements_dict, get_correction_model,
    get_reference_density, get_relative_uncertainty_nai, get_outlier_threshold
)


@dataclass
class VizConfig:
    """Konfigurace vizualizace."""
    
    # Model korekce
    correction_model: str = field(default_factory=get_correction_model)
    
    # Referenční hustota [g/cm³]
    reference_density: float = field(default_factory=get_reference_density)
    
    # Relativní nejistota NaI měření
    relative_uncertainty_nai: float = field(default_factory=get_relative_uncertainty_nai)
    
    # Práh pro outlier detekci (z-score)
    outlier_threshold: float = field(default_factory=get_outlier_threshold)
    
    # Prvky pro dekonvoluční analýzu
    elements_deconv: Dict[str, Tuple[str, str]] = field(default=None)
    
    # Prvek pro 186 keV analýzu
    element_186: Dict[str, Tuple[str, str]] = field(default=None)
    
    # Metoda NaI pro 186 keV (s en-dash)
    method_186_kev: str = "NaI(Tl) – 186 keV"
    
    # Vizuální nastavení
    marker_size: int = 8
    outlier_marker_size: int = 10
    colorscale: str = "Viridis"
    
    # Rozměry grafu
    figure_height: int = 1600
    figure_width: int = 1200
    
    # Pořadí radionuklidů
    element_order: Tuple[str, ...] = ("K-40", "Th-232", "Ra-226")
    
    def __post_init__(self):
        """Načte prvky z konfigurace pokud nejsou zadány."""
        config = get_config()
        if self.elements_deconv is None:
            self.elements_deconv = get_elements_dict(config, 'deconvolution')
        if self.element_186 is None:
            self.element_186 = get_elements_dict(config, '186_keV')


# Globální instance pro zpětnou kompatibilitu
_default_config: Optional[VizConfig] = None


def get_viz_config() -> VizConfig:
    """Vrátí globální konfiguraci vizualizace."""
    global _default_config
    if _default_config is None:
        _default_config = VizConfig()
    return _default_config


def reset_config():
    """Resetuje globální konfiguraci (pro testování)."""
    global _default_config
    _default_config = None


# Export konstant pro zpětnou kompatibilitu
CORRECTION_MODEL = get_correction_model()
REFERENCE_DENSITY = get_reference_density()
RELATIVE_UNCERTAINTY_NAI = get_relative_uncertainty_nai()
OUTLIER_THRESHOLD = get_outlier_threshold()

# Prvky
_config = get_config()
ELEMENTS_DECONV = get_elements_dict(_config, 'deconvolution')
ELEMENT_186 = get_elements_dict(_config, '186_keV')

# Metoda pro 186 keV (správné kódování s en-dash)
METHOD_186_KEV = "NaI(Tl) – 186 keV"
