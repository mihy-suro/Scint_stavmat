"""
Reusable Plotly figure builders for spectrum visualization.

This module provides common plotting utilities to eliminate duplication
in visualization callbacks. Functions handle:
- Figure creation with consistent styling
- Sample/fit/component trace addition
- Hover templates with channel->energy conversion
- Layout configuration
- ROI overlays
- Calibration markers
"""

import numpy as np
import plotly.graph_objects as go


def create_spectrum_figure(template='plotly_white'):
    """
    Create base Plotly figure with standard template.
    
    Args:
        template: Plotly template name (default: 'plotly_white')
    
    Returns:
        go.Figure: Empty figure with template applied
    """
    return go.Figure()


def add_sample_trace(fig, channels, counts, energies, name='Naměřené', color='black', width=2):
    """
    Add sample spectrum trace to figure.
    
    Args:
        fig: Plotly Figure object
        channels: Array of channel numbers (X-axis)
        counts: Array of count values (Y-axis)
        energies: Array of energy values (for hover tooltips)
        name: Trace name (default: 'Naměřené')
        color: Line color (default: 'black')
        width: Line width (default: 2)
    """
    fig.add_trace(go.Scatter(
        x=channels,
        y=counts,
        mode='lines',
        line=dict(color=color, width=width, shape='hv'),
        name=name,
        customdata=energies,
        hovertemplate='Kanál: %{x}<br>~%{customdata:.1f} keV<br>Počty: %{y:.0f}<extra></extra>'
    ))


def add_fit_trace(fig, channels, fitted, energies, name='Fit', color='green', width=2):
    """
    Add fitted spectrum trace to figure.
    
    Args:
        fig: Plotly Figure object
        channels: Array of channel numbers (X-axis)
        fitted: Array of fitted count values (Y-axis)
        energies: Array of energy values (for hover tooltips)
        name: Trace name (default: 'Fit')
        color: Line color (default: 'green')
        width: Line width (default: 2)
    """
    if len(fitted) == 0:
        return
    
    fig.add_trace(go.Scatter(
        x=channels,
        y=fitted,
        mode='lines',
        line=dict(color=color, width=width, dash='dot'),
        name=name,
        customdata=energies,
        hovertemplate='Fit: %{y:.0f} počtů<extra></extra>'
    ))


def add_component_trace(fig, channels, component, energies, name, color, opacity=0.6, dash='dashdot', width=1):
    """
    Add individual component trace (Ra/K/Th/BG) to figure.
    
    Args:
        fig: Plotly Figure object
        channels: Array of channel numbers (X-axis)
        component: Array of component count values (Y-axis)
        energies: Array of energy values (for hover tooltips)
        name: Component name (e.g., 'Ra-226', 'K-40')
        color: Line color
        opacity: Line opacity (default: 0.6)
        dash: Line dash style (default: 'dashdot')
        width: Line width (default: 1)
    """
    if len(component) == 0:
        return
    
    fig.add_trace(go.Scatter(
        x=channels,
        y=component,
        mode='lines',
        line=dict(color=color, width=width, dash=dash),
        name=name,
        opacity=opacity,
        customdata=energies,
        hovertemplate=f'{name}: %{{y:.0f}} počtů<extra></extra>'
    ))


def add_roi_components(fig, channels, energies, components, emphasis='Ra/Th'):
    """
    Add all component traces with appropriate emphasis styling.
    
    Args:
        fig: Plotly Figure object
        channels: Array of channel numbers
        energies: Array of energies (for tooltips)
        components: Dict with keys 'Ra', 'K', 'Th', 'BG' containing component arrays
        emphasis: Which components to emphasize ('Ra/Th' or 'K')
    """
    if emphasis == 'Ra/Th':
        # ROI #1: Emphasize Ra and Th
        if 'Ra' in components:
            add_component_trace(fig, channels, components['Ra'], energies, 
                              'Ra-226', 'red', opacity=0.6)
        if 'Th' in components:
            add_component_trace(fig, channels, components['Th'], energies, 
                              'Th-232', 'orange', opacity=0.6)
        if 'K' in components:
            add_component_trace(fig, channels, components['K'], energies, 
                              'K-40', 'blue', opacity=0.3)
    
    elif emphasis == 'K':
        # ROI #2: Emphasize K
        if 'K' in components:
            add_component_trace(fig, channels, components['K'], energies, 
                              'K-40', 'blue', opacity=0.8)
        if 'Ra' in components:
            add_component_trace(fig, channels, components['Ra'], energies, 
                              'Ra-226', 'red', opacity=0.3)
        if 'Th' in components:
            add_component_trace(fig, channels, components['Th'], energies, 
                              'Th-232', 'purple', opacity=0.3)
    
    # Background always faint
    if 'BG' in components:
        add_component_trace(fig, channels, components['BG'], energies, 
                          'Pozadí', 'gray', opacity=0.4, dash='dot')


def add_calibration_markers(fig, calib_data, sample_spectrum, display_calib):
    """
    Add vertical markers for calibration peaks.
    
    Args:
        fig: Plotly Figure object
        calib_data: DataFrame with 'Channel' and 'Energy' columns
        sample_spectrum: Array of sample counts (for Y positioning)
        display_calib: Calibration coefficients [a0, a1, a2]
    """
    if calib_data is None or len(calib_data) == 0:
        return
    
    for _, row in calib_data.iterrows():
        channel = row['Channel']
        energy = row['Energy']
        
        # Calculate approximate Y position (max in nearby region)
        nearby_start = max(0, int(channel) - 5)
        nearby_end = min(len(sample_spectrum), int(channel) + 5)
        nearby_counts = sample_spectrum[nearby_start:nearby_end]
        y_pos = np.max(nearby_counts) if len(nearby_counts) > 0 else 0
        
        # Add vertical line
        fig.add_vline(
            x=channel,
            line_dash="dot",
            line_color="red",
            opacity=0.4,
            annotation_text=f"{energy:.0f} keV",
            annotation_position="top"
        )


def add_roi_overlay(fig, roi_range, channels, color='lightblue', name='ROI', opacity=0.1):
    """
    Add shaded ROI region overlay.
    
    Args:
        fig: Plotly Figure object
        roi_range: Tuple (min_channel, max_channel)
        channels: Array of all channels
        color: Fill color (default: 'lightblue')
        name: Trace name (default: 'ROI')
        opacity: Fill opacity (default: 0.1)
    """
    fig.add_vrect(
        x0=roi_range[0],
        x1=roi_range[1],
        fillcolor=color,
        opacity=opacity,
        line_width=0,
        annotation_text=name,
        annotation_position="top left"
    )


def configure_spectrum_layout(fig, title="", xaxis_title="Kanál", yaxis_title="Počty",
                              xaxis_range=None, yaxis_type='log', height=400,
                              show_xticklabels=True, margin=None):
    """
    Configure figure layout with standard spectrum styling.
    
    Args:
        fig: Plotly Figure object
        title: Plot title (default: "")
        xaxis_title: X-axis label (default: "Kanál")
        yaxis_title: Y-axis label (default: "Počty")
        xaxis_range: Tuple (min, max) for X-axis range (default: None = auto)
        yaxis_type: 'log' or 'linear' (default: 'log')
        height: Figure height in pixels (default: 400)
        show_xticklabels: Show X-axis tick labels (default: True)
        margin: Dict with l/r/t/b margins (default: None = auto)
    """
    layout_kwargs = {
        'title': title,
        'xaxis_title': xaxis_title,
        'yaxis_title': yaxis_title,
        'yaxis': dict(type=yaxis_type, tickformat='.0f', automargin=False),
        'xaxis': dict(automargin=False, showticklabels=show_xticklabels),
        'hovermode': 'x unified',
        'template': 'plotly_white',
        'height': height,
        'hoverlabel': dict(align='right', namelength=-1),
        'legend': dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=10)
        )
    }
    
    if xaxis_range is not None:
        layout_kwargs['xaxis']['range'] = xaxis_range
    
    if margin is not None:
        layout_kwargs['margin'] = margin
    else:
        layout_kwargs['margin'] = dict(l=60, r=20, t=60, b=60)
    
    fig.update_layout(**layout_kwargs)


def create_placeholder_figure(title, height=300):
    """
    Create placeholder figure for empty/loading states.
    
    Args:
        title: Title text to display
        height: Figure height in pixels (default: 300)
    
    Returns:
        go.Figure: Empty figure with title
    """
    fig = go.Figure()
    fig.update_layout(
        title=title,
        template='plotly_white',
        height=height
    )
    return fig


def create_error_figure(error_message, height=300):
    """
    Create error figure for exception states.
    
    Args:
        error_message: Error text to display
        height: Figure height in pixels (default: 300)
    
    Returns:
        go.Figure: Empty figure with error title
    """
    fig = go.Figure()
    fig.update_layout(
        title=f"Chyba: {error_message}",
        template='plotly_white',
        height=height
    )
    return fig
