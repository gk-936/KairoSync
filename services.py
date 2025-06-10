# new_services.py
import datetime
import json
import database # Changed from "from database import get_db"
from models import Task, Event, Models
from utils import format_timestamp, generate_id # parse_flexible_datetime removed as it's not used here
from adaptive_learning import AdaptiveLearner

class TaskService:
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

        db = database.get_db_connection() # Changed
        # Assuming db.execute is a direct method on the connection object
        # For sqlite3, this is true. For other DBAPIs, a cursor might be needed first.
        # The original code used db.execute directly, so we maintain that pattern.
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
        db = database.get_db_connection() # Changed
        cursor = db.cursor() # Use a cursor for fetching
        cursor.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND is_archived = 0 ORDER BY created_at DESC",
            (user_id,)
        )
        tasks = cursor.fetchall() # Fetch all from cursor
        return [dict(task) for task in tasks]

    @staticmethod
    def complete_task(task_id, user_id):
        db = database.get_db_connection() # Changed
        cursor = db.cursor() # Use a cursor
        cursor.execute(
            "SELECT * FROM tasks WHERE task_id = ? AND user_id = ?",
            (task_id, user_id)
        )
        task = cursor.fetchone() # Fetch one

        if not task:
            return None

        completed_at = datetime.datetime.now().isoformat()
        # Direct execute on connection for non-query statements is fine for sqlite3
        db.execute(
            "UPDATE tasks SET status = 'completed', status_change_timestamp = ? "
            "WHERE task_id = ?",
            (completed_at, task_id)
        )
        db.commit()

        learner = AdaptiveLearner(user_id)
        detail = json.dumps({
            "task_id": task_id,
            "title": task['title'], # task is a Row object, access by index or key
            "completed_at": completed_at
        })
        learner.log_interaction("task_completion", detail, "success")

        # Fetch the updated task to return it
        cursor.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        )
        updated_task = cursor.fetchone()
        return dict(updated_task) if updated_task else None


class EventService:
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

        db = database.get_db_connection() # Changed
        db.execute(
            "INSERT INTO events (event_id, user_id, title, description, start_datetime, end_datetime, location, attendees) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event_data['event_id'], user_id, event_data['title'], event_data['description'],
             event_data['start_datetime'], event_data['end_datetime'], event_data['location'],
             json.dumps(event_data.get('attendees')) if event_data.get('attendees') is not None else None) # Store as JSON
        )
        db.commit()
        return event_data

    @staticmethod
    def get_all_events(user_id):
        db = database.get_db_connection() # Changed
        cursor = db.cursor() # Use a cursor
        cursor.execute(
            "SELECT * FROM events WHERE user_id = ? AND is_archived = 0 ORDER BY start_datetime DESC", # Assuming is_archived field
            (user_id,)
        )
        events = cursor.fetchall() # Fetch all
        event_list = []
        for event_row in events:
            event_dict = dict(event_row)
            if event_dict.get('attendees') and isinstance(event_dict['attendees'], str):
                try:
                    event_dict['attendees'] = json.loads(event_dict['attendees'])
                except json.JSONDecodeError:
                    event_dict['attendees'] = [] # Default to empty list on error
            event_list.append(event_dict)
        return event_list


class LearningService:
    def create_learning_session(self, user_id, topic, resources):
        event_service = EventService()
        # Simplified optimal_time for now, AdaptiveLearner might be complex
        optimal_time = (datetime.datetime.now() + datetime.timedelta(days=1)).isoformat()

        event_dict_data = {
            "title": f"Learning Session: {topic}",
            "start_datetime": optimal_time,
            "end_datetime": (datetime.datetime.fromisoformat(optimal_time) + datetime.timedelta(hours=2)).isoformat()
        }
        event = event_service.create_event(user_id, event_dict_data)

        note = {
            "title": f"{topic} Study Notes",
            "content": f"Resources: {', '.join(resources if isinstance(resources, list) else [str(resources)])}",
            "tags": "learning," + topic
        }
        db = database.get_db_connection() # Changed
        note_id = generate_id("note")
        db.execute(
            "INSERT INTO notes (note_id, user_id, title, content, tags) "
            "VALUES (?, ?, ?, ?, ?)",
            (note_id, user_id, note['title'], note['content'], note['tags'])
        )
        db.commit()

        learner = AdaptiveLearner(user_id)
        detail = json.dumps({
            "topic": topic,
            "resources": resources,
            "interaction_type": "learning"
        })
        learner.log_interaction("learning", detail, "scheduled")

        return event, {"note_id": note_id, **note}

    def generate_personalized_content(self, user_id, topic):
        learner = AdaptiveLearner(user_id)
        style = learner.profile.get('learning_style', 'visual')
        proficiency = learner.get_knowledge_proficiency(topic) if hasattr(learner, 'get_knowledge_proficiency') else 0.1

        content = ""
        if style == "visual":
            content = f"Here are visual resources for {topic}:\n\n- Diagrams\n- Infographics\n- Video tutorials"
        elif style == "auditory":
            content = f"Here are auditory resources for {topic}:\n\n- Podcasts\n- Lectures\n- Discussions"
        else:
            content = f"Here are hands-on resources for {topic}:\n\n- Practice exercises\n- Projects\n- Experiments"

        if proficiency < 0.3:
            content += "\n\nStarting with beginner materials..."
        elif proficiency < 0.7:
            content += "\n\nFocusing on intermediate concepts..."
        else:
            content += "\n\nChallenging advanced topics..."
        return content


class ReportService:
    @staticmethod
    def generate_daily_summary(user_id):
        db = database.get_db_connection() # Changed
        today = datetime.date.today().isoformat()
        cursor = db.cursor()

        cursor.execute(
            "SELECT title, start_datetime FROM events "
            "WHERE user_id = ? AND date(start_datetime) = ? "
            "ORDER BY start_datetime",
            (user_id, today)
        )
        events = cursor.fetchall()

        cursor.execute(
            "SELECT title, priority FROM tasks "
            "WHERE user_id = ? AND status != 'completed' AND is_archived = 0 "
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
        else:
            summary += "📅 No events scheduled for today.\n\n"


        if tasks:
            summary += "📝 Your Tasks:\n"
            for task_row in tasks:
                task = dict(task_row)
                summary += f"- {task['title']} ({task.get('priority','medium')} priority)\n"
            summary += "\n"
        else:
            summary += "📝 No pending tasks. Well done!\n\n"

        summary += "\nWould you like me to schedule focus time for your high-priority tasks?"
        return summary
