import uuid
import datetime
import dateutil.parser
import logging

logger = logging.getLogger(__name__)

class Task:
    @staticmethod
    def create(user_id, title, description=None, due_datetime=None, priority='medium', status='pending', depends_on_task_id=None): # Added depends_on_task_id
        if not user_id or not title:
            logger.error("Task.create: user_id and title are required.")
            raise ValueError("User ID and Title are required for task creation.")

        return {
            'task_id': f"task_{uuid.uuid4().hex}",
            'user_id': user_id,
            'title': title,
            'description': description,
            'due_datetime': Models.parse_datetime(due_datetime),
            'priority': priority,
            'status': status,
            'depends_on_task_id': depends_on_task_id, # Added
            'created_at': datetime.datetime.now().isoformat(),
            'updated_at': datetime.datetime.now().isoformat()
        }

class Event:
    @staticmethod
    def create(user_id, title, start_datetime, description=None, end_datetime=None, location=None, attendees=None):
        if not user_id or not title or not start_datetime:
            logger.error("Event.create: user_id, title, and start_datetime are required.")
            raise ValueError("User ID, Title, and Start Datetime are required for event creation.")

        return {
            'event_id': f"event_{uuid.uuid4().hex}",
            'user_id': user_id,
            'title': title,
            'description': description,
            'start_datetime': Models.parse_datetime(start_datetime),
            'end_datetime': Models.parse_datetime(end_datetime),
            'location': location,
            'attendees': attendees if attendees is not None else [],
            'created_at': datetime.datetime.now().isoformat(),
            'updated_at': datetime.datetime.now().isoformat()
        }

class Models:
    @staticmethod
    def parse_datetime(dt_str):
        if not dt_str:
            return None
        try:
            if isinstance(dt_str, str):
                # Try ISO standard parsing first, which is more strict
                parsed_dt = datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                return parsed_dt.isoformat()
            elif isinstance(dt_str, (datetime.datetime, datetime.date)):
                return dt_str.isoformat()
            else: # Fallback for other string formats if necessary, though ISO is preferred
                logger.warning(f"Parsing non-standard or non-ISO datetime string: {dt_str}")
                return dateutil.parser.parse(dt_str).isoformat()
        except ValueError as e:
            logger.warning(f"Could not parse datetime string '{dt_str}' as ISO or other known format: {e}")
            # Fallback to general parser for common non-ISO date strings if direct ISO fails
            try:
                return dateutil.parser.parse(dt_str).isoformat()
            except Exception as final_e:
                logger.error(f"Final attempt to parse datetime string '{dt_str}' failed: {final_e}", exc_info=True)
                return None
        except Exception as e:
            logger.error(f"Unexpected error parsing datetime string '{dt_str}': {e}", exc_info=True)
            return None

    @staticmethod
    def validate_task(data):
        if not isinstance(data, dict):
            logger.error(f"validate_task: input data is not a dict: {type(data)}")
            raise ValueError("Invalid input: Task data must be a dictionary.")
        if not data.get('title'):
            logger.warning("validate_task: Task title is missing.")
            raise ValueError("Task title is required")

        priority = data.get('priority')
        if priority is not None and priority not in ['low', 'medium', 'high']:
            logger.warning(f"validate_task: Invalid priority value '{priority}'.")
            raise ValueError(f"Invalid priority value: {priority}. Must be one of 'low', 'medium', 'high'.")

        # depends_on_task_id is passed through; actual existence check would be in service or DB layer.
        return data

    @staticmethod
    def validate_event(data):
        if not isinstance(data, dict):
            logger.error(f"validate_event: input data is not a dict: {type(data)}")
            raise ValueError("Invalid input: Event data must be a dictionary.")
        if not data.get('title'):
            logger.warning("validate_event: Event title is missing.")
            raise ValueError("Event title is required")
        if not data.get('start_datetime'):
            logger.warning("validate_event: Event start_datetime is missing.")
            raise ValueError("Start datetime is required")

        for dt_key in ['start_datetime', 'end_datetime']:
            dt_val = data.get(dt_key)
            if dt_val and isinstance(dt_val, str):
                parsed_dt_val = Models.parse_datetime(dt_val) # Use the enhanced parser
                if parsed_dt_val is None:
                    logger.warning(f"validate_event: Invalid datetime format for {dt_key}: '{dt_val}'.")
                    raise ValueError(f"Invalid datetime format for {dt_key}. Use ISO 8601 format or a parsable date/time string.")
                data[dt_key] = parsed_dt_val # Store the standardized ISO string
        return data
