# new_services.py (with LearningService refactor)
import datetime
import json
import database
from models import Task, Event, Models
from utils import format_timestamp, generate_id
from adaptive_learning import AdaptiveLearner

class TaskService: # Unchanged from previous correct version
    @staticmethod
    def create_task(user_id, data):
        validated = Models.validate_task(data)
        task_data = Task.create(
            user_id=user_id,
            title=validated['title'],
            description=validated.get('description'),
            due_datetime=validated.get('due_datetime'),
            priority=validated.get('priority', 'medium')
        )
        db = database.get_db_connection()
        db.execute(
            "INSERT INTO tasks (task_id, user_id, title, description, due_datetime, priority, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (task_data['task_id'], user_id, task_data['title'], task_data['description'],
             task_data['due_datetime'], task_data['priority'], task_data['status'])
        )
        db.commit()
        return task_data

    @staticmethod
    def get_all_tasks(user_id):
        db = database.get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND (is_archived = 0 OR is_archived IS NULL) ORDER BY created_at DESC",
            (user_id,)
        )
        tasks = cursor.fetchall()
        return [dict(task) for task in tasks]

    @staticmethod
    def complete_task(task_id, user_id):
        db = database.get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM tasks WHERE task_id = ? AND user_id = ?",
            (task_id, user_id)
        )
        task = cursor.fetchone()
        if not task: return None
        completed_at = datetime.datetime.now().isoformat()
        db.execute(
            "UPDATE tasks SET status = 'completed', status_change_timestamp = ? "
            "WHERE task_id = ?",
            (completed_at, task_id)
        )
        db.commit()
        learner = AdaptiveLearner(user_id)
        detail = json.dumps({"task_id": task_id, "title": task['title'], "completed_at": completed_at})
        learner.log_interaction("task_completion", detail, "success")
        cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        updated_task = cursor.fetchone()
        return dict(updated_task) if updated_task else None

class EventService: # Unchanged from previous correct version
    @staticmethod
    def create_event(user_id, data):
        validated = Models.validate_event(data)
        event_data = Event.create(
            user_id=user_id,
            title=validated['title'],
            start_datetime=validated['start_datetime'],
            description=validated.get('description'),
            end_datetime=validated.get('end_datetime'),
            location=validated.get('location'),
            attendees=validated.get('attendees')
        )
        db = database.get_db_connection()
        db.execute(
            "INSERT INTO events (event_id, user_id, title, description, start_datetime, end_datetime, location, attendees) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event_data['event_id'], user_id, event_data['title'], event_data['description'],
             event_data['start_datetime'], event_data['end_datetime'], event_data['location'],
             json.dumps(event_data.get('attendees')) if event_data.get('attendees') is not None else None)
        )
        db.commit()
        return event_data

    @staticmethod
    def get_all_events(user_id):
        db = database.get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM events WHERE user_id = ? AND (is_archived = 0 OR is_archived IS NULL) ORDER BY start_datetime DESC",
            (user_id,)
        )
        events = cursor.fetchall()
        event_list = []
        for event_row in events:
            event_dict = dict(event_row)
            if event_dict.get('attendees') and isinstance(event_dict['attendees'], str):
                try: event_dict['attendees'] = json.loads(event_dict['attendees'])
                except json.JSONDecodeError: event_dict['attendees'] = []
            event_list.append(event_dict)
        return event_list

class LearningService: # Refactored as per subtask
    def create_learning_session(self, user_id, topic, resources, start_datetime_str): # Added start_datetime_str
        event_service = EventService()

        try:
            # Validate and use the provided start_datetime_str
            start_dt_obj = datetime.datetime.fromisoformat(start_datetime_str)
            end_dt_obj = start_dt_obj + datetime.timedelta(hours=2) # Default 2-hour session
        except ValueError:
            # Fallback if provided string is invalid - e.g., log error and use a default
            print(f"Invalid start_datetime_str: {start_datetime_str}. Using default for event.")
            start_dt_obj = datetime.datetime.now() + datetime.timedelta(days=1)
            start_dt_obj = start_dt_obj.replace(hour=10, minute=0, second=0, microsecond=0)
            end_dt_obj = start_dt_obj + datetime.timedelta(hours=2)

        event_dict_data = {
            "title": f"Learning Session: {topic}",
            "start_datetime": start_dt_obj.isoformat(),
            "end_datetime": end_dt_obj.isoformat()
        }
        event = event_service.create_event(user_id, event_dict_data)

        note = {
            "title": f"{topic} Study Notes",
            "content": f"Resources: {', '.join(resources if isinstance(resources, list) else [str(resources)])}",
            "tags": "learning," + topic # Ensure topic is a string
        }
        db = database.get_db_connection()
        note_id = generate_id("note")
        db.execute(
            "INSERT INTO notes (note_id, user_id, title, content, tags) "
            "VALUES (?, ?, ?, ?, ?)",
            (note_id, user_id, note['title'], note['content'], note['tags'])
        )
        db.commit()

        learner = AdaptiveLearner(user_id) # Assuming AdaptiveLearner exists and is usable
        detail = json.dumps({
            "topic": topic,
            "resources": resources,
            "interaction_type": "learning_session_creation" # More specific
        })
        # Ensure log_interaction method exists and handles these parameters
        if hasattr(learner, 'log_interaction'):
            learner.log_interaction("learning_session", detail, "created")

        return event, {"note_id": note_id, **note}

    def generate_personalized_content(self, user_id, topic):
        learner = AdaptiveLearner(user_id)
        # Ensure learner.profile and learning_style exist, or provide defaults
        style = "visual" # Default style
        if hasattr(learner, 'profile') and learner.profile and 'learning_style' in learner.profile:
            style = learner.profile.get('learning_style', 'visual')

        # Simplified proficiency part
        content = ""
        if style == "visual":
            content = f"Visual learning resources for {topic}:\n- Diagrams\n- Infographics\n- Video tutorials"
        elif style == "auditory":
            content = f"Auditory learning resources for {topic}:\n- Podcasts\n- Lectures\n- Audio discussions"
        else: # Default to hands-on/text or mixed
            content = f"General resources for {topic}:\n- Practice exercises\n- Projects\n- In-depth readings"

        content += "\n\nStarting with general materials..." # Simplified proficiency adjustment
        return content

class ReportService: # Unchanged from previous correct version
    @staticmethod
    def generate_daily_summary(user_id):
        db = database.get_db_connection()
        today = datetime.date.today().isoformat()
        cursor = db.cursor()
        cursor.execute(
            "SELECT title, start_datetime FROM events "
            "WHERE user_id = ? AND date(start_datetime) = ? "
            "AND (is_archived = 0 OR is_archived IS NULL) ORDER BY start_datetime",
            (user_id, today)
        )
        events = cursor.fetchall()
        cursor.execute(
            "SELECT title, priority FROM tasks "
            "WHERE user_id = ? AND status != 'completed' AND (is_archived = 0 OR is_archived IS NULL) "
            "ORDER BY due_datetime",
            (user_id,)
        )
        tasks = cursor.fetchall()
        summary = "Good morning. I'm Kairo. Here's your daily briefing:\n\n"
        if events:
            summary += "📅 Today's Schedule:\n"
            for event_row in events:
                event = dict(event_row)
                start_time = format_timestamp(event['start_datetime'], '%H:%M') if event.get('start_datetime') else "N/A"
                summary += f"- {start_time}: {event['title']}\n"
            summary += "\n"
        else: summary += "📅 No events scheduled for today.\n\n"
        if tasks:
            summary += "📝 Your Tasks:\n"
            for task_row in tasks:
                task = dict(task_row)
                summary += f"- {task['title']} ({task.get('priority','medium')} priority)\n"
            summary += "\n"
        else: summary += "📝 No pending tasks. Well done!\n\n"
        summary += "\nWould you like me to schedule focus time for your high-priority tasks?"
        return summary
