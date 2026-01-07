"""
Generalized high-level plotting components for ROI analysis.

This module provides complete plot generation functions that eliminate
duplication between roi1/roi2 and residuals plots by parameterizing
the differences (ROI number, component emphasis).
"""

import numpy as np
import plotly.graph_objects as go
from .plot_builders import (
    create_spectrum_figure,
    add_sample_trace,
    add_fit_trace,
    add_roi_components,
    configure_spectrum_layout,
    create_placeholder_figure,
    create_error_figure
)


def calculate_display_energy(channels, calib):
    """
    Calculate energy values from channels using calibration.
    
    Args:
        channels: Array of channel numbers
        calib: List [a0, a1, a2] calibration coefficients
    
    Returns:
        Array of energy values
    """
    a0, a1, a2 = calib
    return a0 + a1 * channels + a2 * channels**2


def create_roi_plot(results, roi_num, roi_range, ref_calib, emphasis='Ra/Th'):
    """
    Create generalized ROI plot (works for both ROI #1 and ROI #2).
    
    Args:
        results: Analysis results dict
        roi_num: ROI number (1 or 2)
        roi_range: Current ROI range [min, max] from slider
        ref_calib: Reference calibration [a0, a1, a2] for tooltips
        emphasis: Which components to emphasize ('Ra/Th' or 'K')
    
    Returns:
        go.Figure: ROI plot with sample, fit, and components
    """
    roi_label = f"ROI #{roi_num}"
    roi_name = "Ra/Th" if roi_num == 1 else "K-40"
    
    # Show placeholder if no results yet
    if results is None:
        return create_placeholder_figure(f"{roi_label}: {roi_name} (čeká na analýzu)", height=300)
    
    # Check if ROI data is available
    roi_info = results.get('roi_info', {})
    fitted_key = f'roi{roi_num}_fitted'
    components_key = f'roi{roi_num}_components_data'
    range_key = f'roi{roi_num}_range'
    
    if not roi_info.get('enabled') or not roi_info.get(fitted_key):
        return create_placeholder_figure(f"{roi_label}: {roi_name} (žádná ROI data)", height=300)
    
    try:
        # Extract data - use ROI-specific rebinned spectrum if available
        # This handles the case where each ROI has its own channel mapping
        roi_rebinned_key = f'roi{roi_num}_sample_rebinned'
        if roi_info.get(roi_rebinned_key):
            # Use ROI-specific rebinned spectrum (new behavior with separate mappings)
            sample_rebinned = np.array(roi_info.get(roi_rebinned_key))
        else:
            # Fallback to global rebinned spectrum (backward compatibility)
            sample_rebinned = np.array(results['sample_rebinned'])
        n_channels = len(sample_rebinned)
        
        roi_fitted = np.array(roi_info.get(fitted_key, []))
        components = roi_info.get(components_key, {})
        
        # CHANNEL-CENTRIC: X-axis is channels
        channels = np.arange(n_channels)
        energies = calculate_display_energy(channels, ref_calib)
        
        # Use current slider value for display range (dynamic zoom)
        # But data (fitted values) are from analysis
        roi_range_actual = roi_range if roi_range else roi_info[range_key]
        mask = (channels >= roi_range_actual[0]) & (channels <= roi_range_actual[1])
        
        # Create figure
        fig = create_spectrum_figure()
        
        # Add sample data
        add_sample_trace(fig, channels[mask], sample_rebinned[mask], energies[mask])
        
        # Add fitted spectrum
        add_fit_trace(fig, channels[mask], roi_fitted[mask], energies[mask])
        
        # Add components with appropriate emphasis
        # Filter out 'mask' key which is metadata, not a component
        component_keys = [k for k in components.keys() if k != 'mask']
        masked_components = {k: np.array(components[k])[mask] for k in component_keys}
        add_roi_components(fig, channels[mask], energies[mask], masked_components, emphasis=emphasis)
        
        # Configure layout
        configure_spectrum_layout(
            fig,
            title="",
            xaxis_title="",
            yaxis_title="Počty",
            xaxis_range=roi_range_actual,
            yaxis_type='linear',
            height=300,
            show_xticklabels=False,
            margin=dict(l=60, r=20, t=40, b=30)
        )
        
        return fig
        
    except Exception as e:
        return create_error_figure(str(e), height=300)


def create_residuals_plot(results, roi_num, roi_range, ref_calib, relayout_data=None):
    """
    Create generalized residuals plot (works for both ROI #1 and ROI #2).
    
    Shows relative residuals: (observed - fitted) / observed
    
    Args:
        results: Analysis results dict
        roi_num: ROI number (1 or 2)
        roi_range: Current ROI range [min, max] from slider
        ref_calib: Reference calibration [a0, a1, a2] for tooltips
        relayout_data: Optional relayout data from spectrum plot for zoom sync
    
    Returns:
        go.Figure: Relative residuals plot
    """
    roi_label = f"ROI #{roi_num}"
    
    # Default empty figure
    empty_fig = create_spectrum_figure()
    empty_fig.update_layout(
        template='plotly_white',
        height=120,
        margin=dict(l=60, r=20, t=10, b=30),
        xaxis_title="",
        yaxis_title="Rel. res."
    )
    
    # Show placeholder if no results yet
    if results is None:
        return empty_fig
    
    # Check if ROI data is available
    roi_info = results.get('roi_info', {})
    fitted_key = f'roi{roi_num}_fitted'
    range_key = f'roi{roi_num}_range'
    
    if not roi_info.get('enabled') or not roi_info.get(fitted_key):
        return empty_fig
    
    try:
        # Extract data - use ROI-specific rebinned spectrum if available
        roi_rebinned_key = f'roi{roi_num}_sample_rebinned'
        if roi_info.get(roi_rebinned_key):
            # Use ROI-specific rebinned spectrum (new behavior with separate mappings)
            sample_rebinned = np.array(roi_info.get(roi_rebinned_key))
        else:
            # Fallback to global rebinned spectrum (backward compatibility)
            sample_rebinned = np.array(results['sample_rebinned'])
        n_channels = len(sample_rebinned)
        
        roi_fitted = np.array(roi_info.get(fitted_key, []))
        
        if len(roi_fitted) == 0:
            return empty_fig
        
        # CHANNEL-CENTRIC: X-axis is channels
        channels = np.arange(n_channels)
        energies = calculate_display_energy(channels, ref_calib)
        
        # Use current slider value for display range
        roi_range_actual = roi_range if roi_range else roi_info[range_key]
        mask = (channels >= roi_range_actual[0]) & (channels <= roi_range_actual[1])
        
        # Calculate relative residuals: (observed - fitted) / observed
        with np.errstate(divide='ignore', invalid='ignore'):
            rel_residuals = (sample_rebinned - roi_fitted) / sample_rebinned
            rel_residuals[~np.isfinite(rel_residuals)] = 0
        
        # Create figure
        fig = create_spectrum_figure()
        
        # Add residuals trace (markers, not lines)
        fig.add_trace(go.Scatter(
            x=channels[mask],
            y=rel_residuals[mask],
            mode='markers',
            marker=dict(size=3, color='blue'),
            name='Relativní residua',
            customdata=energies[mask],
            hovertemplate='Ch: %{x}<br>~%{customdata:.1f} keV<br>%{y:.3f}<extra></extra>'
        ))
        
        # Add zero line
        fig.add_hline(
            y=0,
            line_dash="dash",
            line_color="gray",
            line_width=1
        )
        
        # Sync x-axis range with main plot (CHANNEL range), fallback to ROI range
        xaxis_range = None
        if relayout_data and 'xaxis.range[0]' in relayout_data:
            xaxis_range = [relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']]
        elif relayout_data and 'xaxis.range' in relayout_data:
            xaxis_range = relayout_data['xaxis.range']
        else:
            xaxis_range = roi_range_actual  # Default to ROI range to prevent offset
        
        # Calculate symmetric y-range to align with ROI graph
        y_abs_max = np.max(np.abs(rel_residuals[mask]))
        y_range = [-y_abs_max * 1.1, y_abs_max * 1.1]  # Symmetric around zero
        
        # Configure layout
        fig.update_layout(
            template='plotly_white',
            height=120,
            margin=dict(l=60, r=20, t=10, b=30),
            xaxis_title="",
            yaxis_title="Rel. res.",
            yaxis=dict(tickformat='.3f', range=y_range, automargin=False),
            xaxis=dict(range=xaxis_range, automargin=False),
            showlegend=False,
            hovermode='x',
            hoverlabel=dict(align='right', namelength=-1)
        )
        
        return fig
        
    except Exception as e:
        return empty_fig
