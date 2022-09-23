from datetime import datetime
import sys 

def datetime_to_json(obj):
    """json.dumps default function to use to json from datetime conversion"""
    if isinstance(obj, datetime):
        return { '_isoformat': obj.isoformat() }
    else:
        print(f"object of type {type(obj)} converted to '' in JSON file", file=sys.stderr) 
        return ''        

def json_to_datetime(obj):
    """json.loads object_hook function from json to datetime conversion"""
    _isoformat = obj.get('_isoformat')
    if _isoformat is not None:
        return datetime.fromisoformat(_isoformat)
    return obj