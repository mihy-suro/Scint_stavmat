"""
UI builders - reusable components for status messages, alerts, and badges
"""

from dash import html


def create_status_message(message_type, message_lines, icon=None):
    """
    Create a styled status message with icon.
    
    Args:
        message_type: 'success', 'error', 'warning', 'info'
        message_lines: List of strings (one per line) or single string
        icon: FontAwesome icon class (auto-selected if None)
        
    Returns:
        html.Div: Formatted status message
    """
    # Auto-select icon based on type
    if icon is None:
        icon_map = {
            'success': 'fa-check-circle',
            'error': 'fa-exclamation-triangle',
            'warning': 'fa-exclamation-circle',
            'info': 'fa-info-circle'
        }
        icon = icon_map.get(message_type, 'fa-info-circle')
    
    # Map to Bootstrap colors
    color_map = {
        'success': 'text-success',
        'error': 'text-danger',
        'warning': 'text-warning',
        'info': 'text-info'
    }
    color_class = color_map.get(message_type, 'text-muted')
    
    # Handle single string or list
    if isinstance(message_lines, str):
        message_lines = [message_lines]
    
    # Build content with line breaks
    content = []
    for i, line in enumerate(message_lines):
        content.append(line)
        if i < len(message_lines) - 1:
            content.append(html.Br())
    
    return html.Div([
        html.Small([
            html.I(className=f"fas {icon} {color_class} me-1"),
            *content
        ], className=color_class)
    ])


def create_error_alert(error_message, title="Error"):
    """
    Create a Bootstrap alert for errors.
    
    Args:
        error_message: Error text
        title: Alert title
        
    Returns:
        html.Div: Bootstrap alert component
    """
    return html.Div([
        html.Strong(f"{title}: "),
        error_message
    ], className="alert alert-danger", role="alert")


def create_info_badge(text, badge_type='primary'):
    """
    Create a Bootstrap badge.
    
    Args:
        text: Badge text
        badge_type: 'primary', 'secondary', 'success', 'danger', etc.
        
    Returns:
        html.Span: Bootstrap badge
    """
    return html.Span(text, className=f"badge bg-{badge_type}")


def create_loading_message(operation_name="Loading"):
    """
    Create a loading status message with spinner icon.
    
    Args:
        operation_name: Name of operation being performed
        
    Returns:
        html.Div: Loading message
    """
    return create_status_message('info', f"{operation_name}...", icon='fa-spinner fa-spin')
