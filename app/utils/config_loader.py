"""
Config loader - YAML configuration and calibration spectra loading
Extracted from callbacks/data_loading.py
"""

import yaml
import pandas as pd
from pathlib import Path
from scripts.utils import parse_spe_file


def load_yaml_config(detector_name, config_path=None):
    """
    Load detector configuration from YAML file.
    
    Args:
        detector_name: Name of detector in YAML
        config_path: Path to YAML file (auto-detected if None)
        
    Returns:
        dict: Detector configuration
        
    Raises:
        ValueError: If detector not found in config
        FileNotFoundError: If config file doesn't exist
    """
    if config_path is None:
        # Auto-detect: app/config/detectors.yaml (go up from utils/)
        config_path = Path(__file__).parent.parent / 'config' / 'detectors.yaml'
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    if detector_name not in config:
        raise ValueError(f"Detector '{detector_name}' not found in configuration")
    
    return config[detector_name]


def load_calibration_spectra(detector_config, base_path=None):
    """
    Load Ra, K, Th, BG SPE files from detector configuration.
    
    Args:
        detector_config: Detector configuration dict from YAML
        base_path: Base path for SPE files (auto-detected if None)
        
    Returns:
        dict: {
            'ra_spe': parsed SPE data,
            'k_spe': parsed SPE data,
            'th_spe': parsed SPE data,
            'bg_spe': parsed SPE data or None,
            'live_times': {'Ra': float, 'K': float, 'Th': float, 'BG': float},
            'max_channels': int
        }
    """
    if base_path is None:
        # Auto-detect: from app/utils/ go up to project root
        base_path = Path(__file__).parent.parent.parent
    
    calib_spectra = detector_config['calibration_spectra']
    
    # Build paths
    ra_path = base_path / calib_spectra['Ra']
    k_path = base_path / calib_spectra['K']
    th_path = base_path / calib_spectra['Th']
    bg_path_str = calib_spectra.get('BG')
    bg_path = base_path / bg_path_str if bg_path_str else None
    
    # Load SPE files
    with open(ra_path, 'r', encoding='utf-8', errors='ignore') as f:
        ra_spe = parse_spe_file(f.read())
    
    with open(k_path, 'r', encoding='utf-8', errors='ignore') as f:
        k_spe = parse_spe_file(f.read())
    
    with open(th_path, 'r', encoding='utf-8', errors='ignore') as f:
        th_spe = parse_spe_file(f.read())
    
    # Load background if available
    bg_spe = None
    if bg_path and bg_path.exists():
        with open(bg_path, 'r', encoding='utf-8', errors='ignore') as f:
            bg_spe = parse_spe_file(f.read())
    
    # Extract live times
    live_times = {
        'Ra': float(ra_spe.get('ELIVE', 1.0)),
        'K': float(k_spe.get('ELIVE', 1.0)),
        'Th': float(th_spe.get('ELIVE', 1.0)),
        'BG': float(bg_spe.get('ELIVE', 1.0)) if bg_spe else 1.0
    }
    
    # Determine max channels
    max_channels = max(
        len(ra_spe['channels']),
        len(k_spe['channels']),
        len(th_spe['channels'])
    )
    if bg_spe:
        max_channels = max(max_channels, len(bg_spe['channels']))
    
    return {
        'ra_spe': ra_spe,
        'k_spe': k_spe,
        'th_spe': th_spe,
        'bg_spe': bg_spe,
        'live_times': live_times,
        'max_channels': max_channels
    }


def build_calibration_dataframe(spectra_data, detector_config):
    """
    Build calibration DataFrame with normalized Ra, K, Th, BG columns.
    
    Normalization: Ra/K/Th → CPS/Bq (divide by live_time AND activity)
                   BG → CPS only (coefficient will be dimensionless)
    
    Args:
        spectra_data: Dict from load_calibration_spectra()
        detector_config: Detector configuration dict from YAML
        
    Returns:
        pd.DataFrame: Calibration matrix with columns [CHNL, Ra, K, Th, BG]
    """
    ra_spe = spectra_data['ra_spe']
    k_spe = spectra_data['k_spe']
    th_spe = spectra_data['th_spe']
    bg_spe = spectra_data['bg_spe']
    live_times = spectra_data['live_times']
    max_channels = spectra_data['max_channels']
    
    # Get standard activities from config
    standard_activities = detector_config.get('standard_activities', {})
    ra_activity = float(standard_activities.get('Ra', 1001.4))
    k_activity = float(standard_activities.get('K', 21330.0))
    th_activity = float(standard_activities.get('Th', 1020.0))
    
    # Pad channels to max_channels
    ra_channels = ra_spe['channels'][:max_channels] + [0] * (max_channels - len(ra_spe['channels']))
    k_channels = k_spe['channels'][:max_channels] + [0] * (max_channels - len(k_spe['channels']))
    th_channels = th_spe['channels'][:max_channels] + [0] * (max_channels - len(th_spe['channels']))
    bg_channels = (bg_spe['channels'][:max_channels] + [0] * (max_channels - len(bg_spe['channels']))) if bg_spe else [0] * max_channels
    
    # Build DataFrame
    calib_df = pd.DataFrame()
    calib_df['CHNL'] = range(max_channels)
    
    # Normalize to CPS/Bq (counts / live_time / activity)
    calib_df['Ra'] = [c / live_times['Ra'] / ra_activity for c in ra_channels]
    calib_df['K'] = [c / live_times['K'] / k_activity for c in k_channels]
    calib_df['Th'] = [c / live_times['Th'] / th_activity for c in th_channels]
    
    # Background: normalize to CPS only
    calib_df['BG'] = [c / live_times['BG'] for c in bg_channels]
    
    return calib_df


def load_detector_configuration(detector_name, config_path=None, base_path=None):
    """
    Complete detector configuration loading pipeline.
    
    Args:
        detector_name: Name of detector
        config_path: Path to YAML config (auto-detected if None)
        base_path: Base path for SPE files (auto-detected if None)
        
    Returns:
        dict: Complete configuration with:
            - excel_data: Data structure for callbacks
            - enable_analysis: Boolean
            - display_calib: [a0, a1, a2]
            - manual_calib: [a0, a1]
            - roi_ranges: [roi1_range, roi2_range]
            - status_msg: HTML status message
    """
    # Load YAML
    detector_config = load_yaml_config(detector_name, config_path)
    
    # Load spectra
    spectra_data = load_calibration_spectra(detector_config, base_path)
    
    # Build calibration DataFrame
    calib_df = build_calibration_dataframe(spectra_data, detector_config)
    
    # Extract configuration parameters
    channel_mapping = detector_config.get('channel_mapping', {'ref_a0': 0.0, 'ref_a1': 1.0})
    ref_ch_a0 = float(channel_mapping['ref_a0'])
    ref_ch_a1 = float(channel_mapping['ref_a1'])
    
    display_calib = detector_config.get('display_calibration', {'a0': 9.6229, 'a1': 1.3793, 'a2': 0.0})
    display_a0 = float(display_calib['a0'])
    display_a1 = float(display_calib['a1'])
    display_a2 = float(display_calib.get('a2', 0.0))
    
    roi_ranges = detector_config.get('roi_ranges', {'roi1': [138, 573], 'roi2': [504, 1182]})
    roi1_range = roi_ranges.get('roi1', [138, 573])
    roi2_range = roi_ranges.get('roi2', [504, 1182])
    
    # Get activities
    standard_activities = detector_config.get('standard_activities', {})
    ra_activity = float(standard_activities.get('Ra', 1001.4))
    k_activity = float(standard_activities.get('K', 21330.0))
    th_activity = float(standard_activities.get('Th', 1020.0))
    
    # Build data structure
    excel_data = {
        'calibration': calib_df.to_dict('records'),
        'samples': [],
        'sample_names': [],
        'sample_live_times': [],
        'parameters': {
            'ref_ch_a0': ref_ch_a0,
            'ref_ch_a1': ref_ch_a1,
            'display_a0': display_a0,
            'display_a1': display_a1,
            'display_a2': display_a2,
            'Ra_activity': ra_activity,
            'K_activity': k_activity,
            'Th_activity': th_activity,
            'Ra_live_time': spectra_data['live_times']['Ra'],
            'K_live_time': spectra_data['live_times']['K'],
            'Th_live_time': spectra_data['live_times']['Th'],
            'BG_live_time': spectra_data['live_times']['BG'],
            'has_background': spectra_data['bg_spe'] is not None
        },
        'detector_name': detector_name
    }
    
    # Calculate approximate keV for display
    roi1_kev_min = display_a0 + display_a1 * roi1_range[0]
    roi1_kev_max = display_a0 + display_a1 * roi1_range[1]
    roi2_kev_min = display_a0 + display_a1 * roi2_range[0]
    roi2_kev_max = display_a0 + display_a1 * roi2_range[1]
    
    # Build status message (will need to import html from Dash in calling code)
    status_info = {
        'detector_name': detector_name,
        'num_channels': spectra_data['max_channels'],
        'has_bg': spectra_data['bg_spe'] is not None,
        'activities': {'Ra': ra_activity, 'K': k_activity, 'Th': th_activity},
        'roi1': {'range': roi1_range, 'kev': (roi1_kev_min, roi1_kev_max)},
        'roi2': {'range': roi2_range, 'kev': (roi2_kev_min, roi2_kev_max)}
    }
    
    return {
        'excel_data': excel_data,
        'enable_analysis': True,  # Will be disabled until sample loaded
        'display_calib': [display_a0, display_a1, display_a2],
        'manual_calib': [display_a0, display_a1],
        'roi_ranges': [roi1_range, roi2_range],
        'status_info': status_info
    }
