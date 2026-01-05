"""
Channel processing utilities - wrappers for channel mapping optimization and rebinning
"""

from scripts.utils import find_optimal_channel_mapping, rebin_channels


def optimize_channel_mapping_wrapper(calib_matrix, sample_spectrum_cps, 
                                     initial_mapping, roi_channels=None,
                                     method='L-BFGS-B', maxiter=1000,
                                     print_diagnostics=True):
    """
    Wrapper for channel mapping optimization with diagnostic output.
    
    Args:
        calib_matrix: Calibration matrix (Ra, K, Th columns)
        sample_spectrum_cps: Sample spectrum in CPS
        initial_mapping: [ch_offset, gain] initial guess
        roi_channels: [min_ch, max_ch] to optimize within ROI (optional)
        method: Optimization method
        maxiter: Maximum iterations
        print_diagnostics: Whether to print diagnostics
        
    Returns:
        tuple: (channel_mapping, opt_result_dict)
    """
    channel_mapping, opt_result = find_optimal_channel_mapping(
        calib_matrix,
        sample_spectrum_cps,
        initial_mapping,
        roi_channels=roi_channels,
        method=method,
        maxiter=maxiter
    )
    
    if print_diagnostics:
        print(f"\n🔧 OPTIMIZATION RESULT:")
        print(f"  Method: {opt_result['method']}")
        print(f"  Iterations: {opt_result['iterations']}")
        print(f"  Final R²: {opt_result['final_r2']:.6f}")
        print(f"  Optimized mapping: ch_offset={channel_mapping[0]:.2f}, gain={channel_mapping[1]:.4f}")
    
    return channel_mapping, opt_result


def rebin_sample_spectrum(channel_mapping, sample_spectrum, n_ref_channels,
                          print_diagnostics=True):
    """
    Rebin sample spectrum to reference detector channels.
    
    Args:
        channel_mapping: [ch_offset, gain]
        sample_spectrum: Original sample spectrum (CPS or counts)
        n_ref_channels: Number of channels in reference detector
        print_diagnostics: Whether to print conservation check
        
    Returns:
        np.ndarray: Rebinned spectrum
    """
    rebinned = rebin_channels(channel_mapping, sample_spectrum, n_ref_channels)
    
    if print_diagnostics:
        original_sum = sample_spectrum.sum()
        rebinned_sum = rebinned.sum()
        conservation_ratio = rebinned_sum / original_sum if original_sum > 0 else 0
        
        print(f"  Rebinning: {len(sample_spectrum)} → {len(rebinned)} channels")
        print(f"  Conservation: {conservation_ratio:.6f} {'✅' if abs(conservation_ratio - 1.0) < 0.01 else '❌'}")
    
    return rebinned
