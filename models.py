import uuid
import datetime
import dateutil.parser

class Task:
    @staticmethod
    def create(user_id, title, description=None, due_datetime=None, priority='medium', status='pending'):
        return {
            'task_id': f"task_{uuid.uuid4().hex}",
            'user_id': user_id,
            'title': title,
            'description': description,
            'due_datetime': Models.parse_datetime(due_datetime),
            'priority': priority,
            'status': status,
            'created_at': datetime.datetime.now().isoformat(),
            'updated_at': datetime.datetime.now().isoformat()
        }

class Event:
    @staticmethod
    def create(user_id, title, start_datetime, description=None, end_datetime=None, location=None, attendees=None):
        return {
            'event_id': f"event_{uuid.uuid4().hex}",
            'user_id': user_id,
            'title': title,
            'description': description,
            'start_datetime': Models.parse_datetime(start_datetime),
            'end_datetime': Models.parse_datetime(end_datetime),
            'location': location,
            'attendees': attendees,
            'created_at': datetime.datetime.now().isoformat(),
            'updated_at': datetime.datetime.now().isoformat()
        }

class Models:
    @staticmethod
    def parse_datetime(dt_str):
        if not dt_str:
            return None
        try:
            return dateutil.parser.parse(dt_str).isoformat()
        except:
            return None
    
    @staticmethod
    def validate_task(data):
        if not data.get('title'):
            raise ValueError("Task title is required")
        if data.get('priority') not in ['low', 'medium', 'high', None]:
            raise ValueError("Invalid priority value")
        return data
    
    @staticmethod
    def validate_event(data):
        if not data.get('title'):
            raise ValueError("Event title is required")
        if not data.get('start_datetime'):
            raise ValueError("Start datetime is required")
        return data