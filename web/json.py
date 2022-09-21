from datetime import datetime

def datetime_to_json(obj):
    """json.dumps default function to use to json from datetime conversion"""
    if isinstance(obj, datetime):
        return { '_isoformat': obj.isoformat() }
    raise TypeError('...')

def json_to_datetime(obj):
    """json.loads object_hook function from json to datetime conversion"""
    _isoformat = obj.get('_isoformat')
    if _isoformat is not None:
        return datetime.fromisoformat(_isoformat)
    return obj