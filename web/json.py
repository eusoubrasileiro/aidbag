from datetime import datetime
from pathlib import Path 
import sys 

def datetime_to_json(obj, verbose=False):
    """json.dumps default function to use to json from datetime conversion"""
    if isinstance(obj, datetime):
        return { '_isoformat': obj.isoformat() }
    else:
        if verbose:
            print(f"object of type {type(obj)} converted to '' in JSON file", file=sys.stderr) 
        return ''        

def json_to_datetime(obj):
    """json.loads object_hook function from json to datetime conversion"""
    _isoformat = obj.get('_isoformat')
    if _isoformat is not None:
        return datetime.fromisoformat(_isoformat)
    return obj

def path_to_json(obj, verbose=False):
    """json.dumps default function to use to json from datetime conversion"""
    if isinstance(obj, Path):
        return { '_pathlibpath': str(obj.absolute()) }
    else:
        if verbose:
            print(f"object of type {type(obj)} converted to '' in JSON file", file=sys.stderr) 
        return ''        

def json_to_path(obj):
    """json.loads object_hook function from json to datetime conversion"""
    _pathlibpath = obj.get('_pathlibpath')
    if _pathlibpath is not None:
        return Path(_pathlibpath)
    return obj

