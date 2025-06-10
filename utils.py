import uuid
import datetime

import dateutil

def generate_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"

def format_timestamp(dt_str, format='%H:%M'):
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.datetime.fromisoformat(dt_str)
        return dt.strftime(format)
    except:
        return "Invalid date"

def parse_flexible_datetime(dt_str):
    """Parse various datetime formats including natural language"""
    if not dt_str:
        return None
    try:
        return dateutil.parser.parse(dt_str).isoformat()
    except:
        return None