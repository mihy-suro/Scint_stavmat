"""
Data manipulation helpers - common patterns for unpacking and validating data
"""

import pandas as pd
import numpy as np


def unpack_excel_data(excel_data):
    """
    Unpack excel_data dict into DataFrames and metadata.
    
    Args:
        excel_data: Dictionary with calibration, samples, parameters
        
    Returns:
        tuple: (calib_df, sample_df, parameters_dict)
    """
    calib_df = pd.DataFrame(excel_data['calibration'])
    sample_df = pd.DataFrame(excel_data['samples'])
    parameters = excel_data.get('parameters', {})
    
    return calib_df, sample_df, parameters


def get_sample_data(sample_name, excel_data):
    """
    Extract sample spectrum and metadata from excel_data.
    
    Args:
        sample_name: Name of the sample
        excel_data: Dictionary with sample data
        
    Returns:
        tuple: (spectrum, live_time, sample_idx)
    """
    sample_df = pd.DataFrame(excel_data['samples'])
    sample_idx = excel_data['sample_names'].index(sample_name)
    sample_live_time = excel_data['sample_live_times'][sample_idx]
    
    # Get spectrum (in counts)
    sample_spectrum = sample_df[sample_name].values
    
    return sample_spectrum, sample_live_time, sample_idx


def validate_roi_ranges(roi1_range, roi2_range):
    """
    Validate that ROI ranges are properly defined.
    
    Args:
        roi1_range: [min, max] for ROI1
        roi2_range: [min, max] for ROI2
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not roi1_range or not roi2_range:
        return False
    
    if None in roi1_range or None in roi2_range:
        return False
    
    # Check that ranges are valid (min < max)
    if roi1_range[0] >= roi1_range[1] or roi2_range[0] >= roi2_range[1]:
        return False
    
    return True


def safe_dict_get(data_dict, *keys, default=None):
    """
    Safely navigate nested dictionary keys.
    
    Args:
        data_dict: Dictionary to navigate
        *keys: Sequence of keys to access
        default: Default value if key path doesn't exist
        
    Returns:
        Value at key path or default
        
    Example:
        safe_dict_get(results, 'roi_info', 'roi1_range', default=[])
    """
    result = data_dict
    for key in keys:
        if isinstance(result, dict) and key in result:
            result = result[key]
        else:
            return default
    return result


def has_background_data(excel_data):
    """Check if excel_data contains background spectrum."""
    calib_df = pd.DataFrame(excel_data.get('calibration', {}))
    return 'BG' in calib_df.columns


def create_channel_mask(roi_channels, n_channels):
    """Create boolean mask for channels within channel range.
    
    This is the CHANNEL-CENTRIC version - much simpler than energy-based masking!
    
    Args:
        roi_channels: [ch_min, ch_max] - channel range
        n_channels: Total number of channels in spectrum
    
    Returns:
        mask: Boolean array of shape (n_channels,)
    """
    channels = np.arange(n_channels)
    mask = (channels >= roi_channels[0]) & (channels <= roi_channels[1])
    return mask
