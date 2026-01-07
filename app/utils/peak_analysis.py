"""
Peak analysis utilities for Ra-226 186 keV photopeak analysis.

Provides an alternative, regression-independent method for calculating
Ra-226 activity based on net peak area comparison.
"""

import numpy as np
from scipy.ndimage import uniform_filter1d


def smooth_spectrum(spectrum, window=5):
    """
    Smooth spectrum using a moving average filter.
    
    Args:
        spectrum: Array of counts per channel
        window: Window size for smoothing (should be odd)
        
    Returns:
        Smoothed spectrum array
    """
    if window < 1:
        return spectrum
    return uniform_filter1d(spectrum.astype(float), size=window, mode='nearest')


def find_peak_in_roi(spectrum, center_ch, search_width=10, smooth_window=5):
    """
    Find the peak (maximum) in a region around the expected position.
    
    Args:
        spectrum: Array of counts per channel
        center_ch: Expected center channel (from energy calibration)
        search_width: Number of channels to search on each side
        smooth_window: Window for smoothing before peak search
        
    Returns:
        tuple: (peak_channel, peak_value) or (None, None) if not found
    """
    n_channels = len(spectrum)
    
    # Define search region
    search_min = max(0, int(center_ch - search_width))
    search_max = min(n_channels - 1, int(center_ch + search_width))
    
    if search_min >= search_max:
        return None, None
    
    # Smooth spectrum for peak finding
    smoothed = smooth_spectrum(spectrum, smooth_window)
    
    # Find maximum in search region
    search_region = smoothed[search_min:search_max + 1]
    local_max_idx = np.argmax(search_region)
    peak_channel = search_min + local_max_idx
    peak_value = spectrum[peak_channel]
    
    return peak_channel, peak_value


def calculate_linear_background(spectrum, roi_min, roi_max, bg_margin=5):
    """
    Calculate linear background (continuum) under a peak.
    
    Uses average of counts in margin regions at each end of the ROI
    to define a linear interpolation.
    
    Args:
        spectrum: Array of counts per channel
        roi_min: Left edge of ROI
        roi_max: Right edge of ROI
        bg_margin: Number of channels to average on each side
        
    Returns:
        tuple: (background_array, left_avg, right_avg)
               background_array has same length as ROI
    """
    n_channels = len(spectrum)
    
    # Ensure bounds are valid
    roi_min = max(0, int(roi_min))
    roi_max = min(n_channels - 1, int(roi_max))
    
    # Calculate average on left side
    left_start = max(0, roi_min)
    left_end = min(roi_min + bg_margin, roi_max)
    left_avg = np.mean(spectrum[left_start:left_end]) if left_end > left_start else 0
    
    # Calculate average on right side
    right_start = max(roi_min, roi_max - bg_margin)
    right_end = min(n_channels, roi_max + 1)
    right_avg = np.mean(spectrum[right_start:right_end]) if right_end > right_start else 0
    
    # Linear interpolation
    roi_length = roi_max - roi_min + 1
    if roi_length <= 0:
        return np.array([]), left_avg, right_avg
    
    background = np.linspace(left_avg, right_avg, roi_length)
    
    return background, left_avg, right_avg


def calculate_net_area(spectrum, peak_ch, roi_half_width=15, bg_margin=5):
    """
    Calculate net peak area after background subtraction.
    
    Args:
        spectrum: Array of counts per channel
        peak_ch: Channel of peak maximum
        roi_half_width: Half-width of integration region
        bg_margin: Channels for background estimation at edges
        
    Returns:
        dict: {
            'net_area': Net counts after background subtraction,
            'gross_area': Total counts in ROI,
            'background_area': Background counts in ROI,
            'uncertainty': Statistical uncertainty (sqrt of gross + background),
            'roi_min': Left edge of ROI,
            'roi_max': Right edge of ROI,
            'bg_left': Background level at left edge,
            'bg_right': Background level at right edge
        }
    """
    if peak_ch is None:
        return None
    
    n_channels = len(spectrum)
    
    # Define ROI
    roi_min = max(0, int(peak_ch - roi_half_width))
    roi_max = min(n_channels - 1, int(peak_ch + roi_half_width))
    
    # Get ROI spectrum
    roi_spectrum = spectrum[roi_min:roi_max + 1]
    
    # Calculate background
    background, bg_left, bg_right = calculate_linear_background(
        spectrum, roi_min, roi_max, bg_margin
    )
    
    # Calculate areas
    gross_area = np.sum(roi_spectrum)
    background_area = np.sum(background)
    net_area = gross_area - background_area
    
    # Uncertainty: sqrt(N_gross + N_background) for counting statistics
    # Background contributes twice to uncertainty (subtraction)
    uncertainty = np.sqrt(gross_area + background_area)
    
    return {
        'net_area': net_area,
        'gross_area': gross_area,
        'background_area': background_area,
        'uncertainty': uncertainty,
        'roi_min': roi_min,
        'roi_max': roi_max,
        'bg_left': bg_left,
        'bg_right': bg_right
    }


def energy_to_channel(energy_keV, display_calib):
    """
    Convert energy in keV to channel number.
    
    Args:
        energy_keV: Energy in keV
        display_calib: [a0, a1, a2] calibration coefficients
                       E = a0 + a1*ch + a2*ch^2
        
    Returns:
        Channel number (float)
    """
    a0, a1, a2 = display_calib[0], display_calib[1], display_calib[2] if len(display_calib) > 2 else 0
    
    if a2 != 0:
        # Quadratic: solve a2*ch^2 + a1*ch + (a0 - E) = 0
        discriminant = a1**2 - 4*a2*(a0 - energy_keV)
        if discriminant < 0:
            return None
        ch = (-a1 + np.sqrt(discriminant)) / (2*a2)
    else:
        # Linear: ch = (E - a0) / a1
        if a1 == 0:
            return None
        ch = (energy_keV - a0) / a1
    
    return ch


def calculate_ra226_from_186kev_peak(sample_cps, energy_calib, config=None, 
                                     manual_roi=None, sample_live_time=None,
                                     precalib_net_cps_per_bq=None, 
                                     interference_factor=None):
    """
    Calculate Ra-226 activity from 186 keV photopeak using pre-calibrated cps/Bq value.
    
    Method:
    1. Calculate net peak area for sample in CPS
    2. Use pre-calibrated net_cps_per_bq (from calibrate_186_peak.py)
    3. Activity = net_cps_sample / net_cps_per_bq × interference_factor
    
    Args:
        sample_cps: Sample spectrum in CPS (counts per second per channel)
        energy_calib: [a0, a1, a2] energy calibration for channel conversion
        config: Optional dict with parameters (bg_margin, etc.)
        manual_roi: [left_ch, right_ch] for ROI boundaries
        sample_live_time: Sample live time in seconds (for uncertainty calculation)
        precalib_net_cps_per_bq: Pre-calibrated net CPS/Bq for 186 keV peak (from config)
        interference_factor: U-235 interference correction factor (default from config or 0.575)
    
    Returns:
        dict with activity, uncertainty, net areas, etc.
    """
    # Default configuration
    if config is None:
        config = {}
    
    ra_186_energy = config.get('ra_186_energy', 186.0)
    bg_margin = config.get('bg_margin', 5)
    
    # Use provided interference factor or get from config
    if interference_factor is None:
        interference_factor = config.get('ra_186_correction', 0.575)
    
    # Get pre-calibrated value from config if not provided directly
    if precalib_net_cps_per_bq is None:
        precalib_net_cps_per_bq = config.get('precalib_net_cps_per_bq')
    
    if precalib_net_cps_per_bq is None or precalib_net_cps_per_bq <= 0:
        print(f"[Peak Analysis] ERROR: Pre-calibrated net_cps_per_bq not provided!")
        print(f"  Run calibrate_186_peak.py to generate calibration value.")
        return None
    
    # Ensure sample spectrum is numpy array
    sample_cps = np.array(sample_cps, dtype=float)
    
    print(f"\\n{'='*60}")
    print(f"PEAK ANALYSIS: Ra-226 @ 186 keV (pre-calibrated method)")
    print(f"{'='*60}")
    print(f"Sample spectrum: {len(sample_cps)} channels (cps)")
    print(f"Pre-calibrated net_cps_per_bq: {precalib_net_cps_per_bq:.6f}")
    print(f"Interference factor: {interference_factor}")
    
    # Determine ROI boundaries
    if manual_roi is not None and len(manual_roi) == 2:
        roi_min, roi_max = int(manual_roi[0]), int(manual_roi[1])
        print(f"Using MANUAL ROI: channels {roi_min}-{roi_max}")
    else:
        # Auto-detect from energy
        center_ch = energy_to_channel(ra_186_energy, energy_calib)
        if center_ch is None or center_ch < 0:
            print(f"[Peak Analysis] Could not convert {ra_186_energy} keV to channel")
            return None
        roi_half_width = config.get('roi_half_width', 15)
        roi_min = int(max(0, center_ch - roi_half_width))
        roi_max = int(min(len(sample_cps) - 1, center_ch + roi_half_width))
        print(f"Auto ROI from {ra_186_energy} keV: channels {roi_min}-{roi_max}")
    
    # Validate ROI bounds
    roi_min = max(0, roi_min)
    roi_max = min(len(sample_cps) - 1, roi_max)
    
    if roi_max - roi_min < 10:
        print(f"[Peak Analysis] ROI too small: {roi_max - roi_min} channels")
        return None
    
    # Extract sample spectrum in ROI
    sample_roi = sample_cps[roi_min:roi_max + 1]
    
    # Calculate linear background for SAMPLE (in cps)
    bg_left_sample = np.mean(sample_roi[:bg_margin]) if len(sample_roi) >= bg_margin else sample_roi[0]
    bg_right_sample = np.mean(sample_roi[-bg_margin:]) if len(sample_roi) >= bg_margin else sample_roi[-1]
    bg_sample = np.linspace(bg_left_sample, bg_right_sample, len(sample_roi))
    
    # Calculate gross and net areas for sample
    gross_sample_cps = np.sum(sample_roi)
    bg_sample_cps = np.sum(bg_sample)
    net_sample_cps = gross_sample_cps - bg_sample_cps
    
    print(f"\\n→ Sample ROI: gross={gross_sample_cps:.4f}, bg={bg_sample_cps:.4f}, net={net_sample_cps:.4f} cps")
    
    # Check for valid net area
    if net_sample_cps <= 0:
        print(f"[Peak Analysis] Sample net area <= 0")
        return None
    
    # Calculate raw activity: A = net_cps_sample / net_cps_per_bq
    activity_raw = net_sample_cps / precalib_net_cps_per_bq
    
    # Apply interference correction factor
    activity = activity_raw * interference_factor
    
    # Estimate uncertainty using proper Poisson statistics
    if sample_live_time is not None and sample_live_time > 0:
        # Convert CPS to counts for uncertainty calculation
        gross_counts_sample = gross_sample_cps * sample_live_time
        bg_counts_sample = bg_sample_cps * sample_live_time
        net_counts_sample = net_sample_cps * sample_live_time
        
        # Uncertainty on net counts: σ(net) = √(gross + bg)
        sigma_net_counts = np.sqrt(gross_counts_sample + bg_counts_sample)
        
        # Relative uncertainty on sample net area
        rel_unc_sample = sigma_net_counts / net_counts_sample if net_counts_sample > 0 else 1
        
        # Calibration uncertainty (~2%)
        rel_unc_calib = 0.02
        
        # Combined relative uncertainty
        rel_uncertainty = np.sqrt(rel_unc_sample**2 + rel_unc_calib**2)
        uncertainty = activity * rel_uncertainty
        
        print(f"\\n→ Uncertainty calculation:")
        print(f"   Gross counts: {gross_counts_sample:.0f}, BG counts: {bg_counts_sample:.0f}")
        print(f"   Net counts: {net_counts_sample:.0f} ± {sigma_net_counts:.0f}")
        print(f"   Relative uncertainty: {rel_uncertainty*100:.1f}%")
    else:
        uncertainty = activity * 0.1  # 10% default
        print(f"\\n→ Uncertainty: using default 10% (live_time not provided)")
    
    # Find peak position for display
    sample_peak_ch = roi_min + np.argmax(sample_roi)
    
    print(f"\\n→ Raw activity (cps / cps/Bq): {activity_raw:.2f} Bq")
    print(f"→ Interference factor: {interference_factor}")
    print(f"→ Final Ra-226 activity: {activity:.2f} ± {uncertainty:.2f} Bq")
    print(f"{'='*60}\\n")
    
    return {
        'activity': activity,
        'activity_raw': activity_raw,
        'uncertainty': uncertainty,
        'net_cps_sample': net_sample_cps,
        'net_cps_per_bq_calib': precalib_net_cps_per_bq,
        'gross_cps_sample': gross_sample_cps,
        'peak_channel_sample': sample_peak_ch,
        'roi_range': [roi_min, roi_max],
        'bg_left': bg_left_sample,
        'bg_right': bg_right_sample,
        'correction_factor': interference_factor,
        'method': 'peak_186keV_precalibrated'
    }
