"""
SPE file handler - Upload, decode, parse, and merge SPE files
Extracted from callbacks/data_loading.py
"""

import base64
import os
from scripts.utils import parse_spe_file


def decode_spe_upload(content, filename):
    """
    Decode uploaded SPE file from Dash Upload component.
    
    Args:
        content: Base64 encoded content from dcc.Upload
        filename: Original filename
        
    Returns:
        dict: Parsed SPE data from parse_spe_file()
        
    Raises:
        ValueError: If content cannot be decoded
    """
    # Decode base64
    content_type, content_string = content.split(',')
    decoded_bytes = base64.b64decode(content_string)
    
    # Try multiple encodings
    decoded = None
    for encoding in ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']:
        try:
            decoded = decoded_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    
    # Fallback to latin1 with error handling
    if decoded is None:
        decoded = decoded_bytes.decode('latin1', errors='ignore')
    
    # Parse SPE format
    spe_data = parse_spe_file(decoded)
    
    return spe_data


def get_sample_id_from_filename(filename):
    """
    Extract sample ID from filename (remove extension).
    
    Args:
        filename: Original filename with extension
        
    Returns:
        str: Sample ID (filename without extension)
    """
    return os.path.splitext(filename)[0]


def is_background_file(sample_id):
    """
    Check if sample ID indicates a background file.
    
    Args:
        sample_id: Sample identifier
        
    Returns:
        bool: True if this is a background file
    """
    return sample_id.startswith('BG:') or sample_id.startswith('BG_')


def clean_background_from_samples(excel_data):
    """
    Remove any background entries from sample_names list.
    
    Args:
        excel_data: Data structure to clean (modified in-place)
        
    Returns:
        int: Number of background entries removed
    """
    if 'sample_names' not in excel_data:
        return 0
    
    bg_indices = [i for i, name in enumerate(excel_data['sample_names']) if is_background_file(name)]
    
    if bg_indices:
        print(f"🧹 Cleaning {len(bg_indices)} background entries from sample_names")
        for idx in reversed(bg_indices):  # Remove from end to preserve indices
            del excel_data['sample_names'][idx]
            if idx < len(excel_data.get('sample_live_times', [])):
                del excel_data['sample_live_times'][idx]
    
    return len(bg_indices)


def merge_spe_into_dataframe(excel_data, sample_id, spe_data):
    """
    Merge parsed SPE data into excel_data samples structure.
    
    Args:
        excel_data: Existing data structure (modified in-place)
        sample_id: Sample identifier
        spe_data: Parsed SPE data dict with 'channels' and 'ELIVE'
        
    Returns:
        bool: True if successful, False if error
    """
    try:
        # Add to sample lists
        excel_data['sample_names'].append(sample_id)
        excel_data['sample_live_times'].append(spe_data['ELIVE'])
        
        channels = spe_data['channels']
        
        # Initialize samples structure if empty
        if not excel_data.get('samples') or len(excel_data['samples']) == 0:
            for ch_num, count in enumerate(channels):
                excel_data['samples'].append({'CHNL': ch_num, sample_id: count})
            return True
        
        # Defensive check: ensure samples is a list
        if not isinstance(excel_data['samples'], list):
            # Structure corrupted, reinitialize
            excel_data['samples'] = []
            for i, c in enumerate(channels):
                excel_data['samples'].append({'CHNL': i, sample_id: c})
            return True
        
        # Add to existing structure
        for ch_num, count in enumerate(channels):
            # Extend structure if needed
            if ch_num >= len(excel_data['samples']):
                # Create new row with CHNL and zeros for existing samples
                new_row = {'CHNL': ch_num}
                for existing_sample in excel_data['sample_names'][:-1]:  # Exclude current one
                    new_row[existing_sample] = 0
                new_row[sample_id] = count
                excel_data['samples'].append(new_row)
            else:
                # Row exists - verify it's a dict and add count
                if not isinstance(excel_data['samples'][ch_num], dict):
                    excel_data['samples'][ch_num] = {'CHNL': ch_num}
                excel_data['samples'][ch_num][sample_id] = count
        
        return True
        
    except Exception as e:
        print(f"Error merging SPE for {sample_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_multiple_spe_files(contents_list, filenames_list, excel_data):
    """
    Load multiple uploaded SPE files into excel_data structure.
    
    Args:
        contents_list: List of base64 contents from dcc.Upload
        filenames_list: List of filenames
        excel_data: Existing data structure (modified in-place)
        
    Returns:
        tuple: (loaded_samples, errors)
            loaded_samples: List of successfully loaded sample IDs
            errors: List of error messages
    """
    # Handle single file
    if not isinstance(contents_list, list):
        contents_list = [contents_list]
        filenames_list = [filenames_list]
    
    # Clean background entries first
    clean_background_from_samples(excel_data)
    
    loaded_samples = []
    errors = []
    
    for content, filename in zip(contents_list, filenames_list):
        try:
            # Decode and parse
            spe_data = decode_spe_upload(content, filename)
            
            # Get sample ID
            sample_id = get_sample_id_from_filename(filename)
            
            # Skip background files
            if is_background_file(sample_id):
                print(f"Skipping background file in sample upload: {filename}")
                continue
            
            # Merge into excel_data
            success = merge_spe_into_dataframe(excel_data, sample_id, spe_data)
            
            if success:
                loaded_samples.append(sample_id)
            else:
                errors.append(f"{filename}: Failed to merge into data structure")
                
        except Exception as e:
            errors.append(f"{filename}: {str(e)}")
            print(f"Error loading {filename}: {e}")
            import traceback
            traceback.print_exc()
    
    return loaded_samples, errors


def validate_excel_data_structure(excel_data):
    """
    Validate that excel_data has required structure.
    
    Args:
        excel_data: Data structure to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not isinstance(excel_data, dict):
        return False, "excel_data must be a dictionary"
    
    required_keys = ['calibration', 'samples', 'sample_names', 'sample_live_times', 'parameters']
    for key in required_keys:
        if key not in excel_data:
            return False, f"Missing required key: {key}"
    
    if not isinstance(excel_data['sample_names'], list):
        return False, "sample_names must be a list"
    
    if not isinstance(excel_data['sample_live_times'], list):
        return False, "sample_live_times must be a list"
    
    if len(excel_data['sample_names']) != len(excel_data['sample_live_times']):
        return False, "sample_names and sample_live_times must have same length"
    
    return True, None
