# services_task_deps.py
import datetime
import json
import database
from models import Task, Event, Models
from utils import format_timestamp, generate_id
from adaptive_learning import AdaptiveLearner
import logging

logger = logging.getLogger(__name__)

class ServiceError(Exception):
    """Custom exception for service layer errors."""
    pass

class TaskService:
    @staticmethod
    def create_task(user_id, data):
        try:
            validated_data = Models.validate_task(data)
            # Pass depends_on_task_id from validated_data to Task.create
            task_obj_data = Task.create(
                user_id=user_id,
                title=validated_data['title'],
                description=validated_data.get('description'),
                due_datetime=validated_data.get('due_datetime'),
                priority=validated_data.get('priority', 'medium'),
                depends_on_task_id=validated_data.get('depends_on_task_id') # Added
            )

            if not isinstance(task_obj_data, dict):
                task_data_for_db = task_obj_data.dict() if hasattr(task_obj_data, 'dict') else vars(task_obj_data)
            else:
                task_data_for_db = task_obj_data

            db = database.get_db_connection()
            cursor = db.cursor()
            # Include depends_on_task_id in INSERT statement
            cursor.execute(
                "INSERT INTO tasks (task_id, user_id, title, description, due_datetime, priority, status, depends_on_task_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", # Added one ?
                (task_data_for_db['task_id'], user_id, task_data_for_db['title'],
                 task_data_for_db['description'], task_data_for_db['due_datetime'],
                 task_data_for_db['priority'], task_data_for_db.get('status', 'pending'),
                 task_data_for_db.get('depends_on_task_id')) # Added value
            )
            db.commit()
            logger.info(f"Task created successfully: {task_data_for_db['task_id']} for user {user_id}")
            return task_data_for_db
        except ValueError as ve: # Catch validation errors from Models.validate_task or Task.create
            logger.error(f"Validation error in TaskService.create_task for user {user_id}: {str(ve)}", exc_info=True)
            raise ServiceError(f"Invalid task data: {str(ve)}") from ve
        except Exception as e:
            logger.error(f"Database error in TaskService.create_task for user {user_id}: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def get_all_tasks(user_id): # No change needed here, SELECT * gets the new column
        try:
            db = database.get_db_connection()
            cursor = db.cursor()
            cursor.execute(
                "SELECT * FROM tasks WHERE user_id = ? AND (is_archived = 0 OR is_archived IS NULL) ORDER BY created_at DESC",
                (user_id,)
            )
            tasks = cursor.fetchall()
            return [dict(task) for task in tasks]
        except Exception as e:
            logger.error(f"Database error in TaskService.get_all_tasks for user {user_id}: {str(e)}", exc_info=True)
            return []

    @staticmethod
    def complete_task(task_id, user_id): # No change needed for depends_on_task_id logic here
        try:
            db = database.get_db_connection()
            cursor = db.cursor()
            cursor.execute(
                "SELECT * FROM tasks WHERE task_id = ? AND user_id = ?", (task_id, user_id)
            )
            task = cursor.fetchone()
            if not task:
                logger.warning(f"TaskService.complete_task: Task {task_id} not found for user {user_id}.")
                return None

            completed_at = datetime.datetime.now().isoformat()
            cursor.execute(
                "UPDATE tasks SET status = 'completed', status_change_timestamp = ? WHERE task_id = ?",
                (completed_at, task_id)
            )
            db.commit()

            try:
                learner = AdaptiveLearner(user_id)
                detail = json.dumps({"task_id": task_id, "title": task['title'], "completed_at": completed_at})
                if hasattr(learner, 'log_interaction'): learner.log_interaction("task_completion", detail, "success")
            except Exception as learner_e:
                logger.error(f"AdaptiveLearner error in complete_task for user {user_id}, task {task_id}: {str(learner_e)}", exc_info=True)

            cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            updated_task = cursor.fetchone()
            logger.info(f"Task {task_id} completed for user {user_id}.")
            return dict(updated_task) if updated_task else None
        except Exception as e:
            logger.error(f"Database error in TaskService.complete_task for user {user_id}, task {task_id}: {str(e)}", exc_info=True)
            return None

# EventService, LearningService, ReportService remain unchanged from services_with_logging.py content
# For brevity, only showing TaskService which was modified for this specific step.
# In a real operation, the full file content with other services would be used here.

class EventService:
    @staticmethod
    def create_event(user_id, data):
        try:
            validated_data = Models.validate_event(data)
            event_obj_data = Event.create(user_id=user_id, **validated_data)
            if not isinstance(event_obj_data, dict):
                event_data_for_db = event_obj_data.dict() if hasattr(event_obj_data, 'dict') else vars(event_obj_data)
            else: event_data_for_db = event_obj_data
            db = database.get_db_connection(); cursor = db.cursor()
            cursor.execute(
                "INSERT INTO events (event_id, user_id, title, description, start_datetime, end_datetime, location, attendees) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (event_data_for_db['event_id'], user_id, event_data_for_db['title'], event_data_for_db['description'],
                 event_data_for_db['start_datetime'], event_data_for_db.get('end_datetime'), event_data_for_db.get('location'),
                 json.dumps(event_data_for_db.get('attendees')) if event_data_for_db.get('attendees') is not None else None)
            )
            db.commit(); logger.info(f"Event created: {event_data_for_db['event_id']} for user {user_id}"); return event_data_for_db
        except ValueError as ve: logger.error(f"Validation error in EventService.create_event: {str(ve)}", exc_info=True); raise ServiceError(f"Invalid event data: {str(ve)}") from ve
        except Exception as e: logger.error(f"Database error in EventService.create_event for user {user_id}: {str(e)}", exc_info=True); return None

    @staticmethod
    def get_all_events(user_id):
        try:
            db = database.get_db_connection(); cursor = db.cursor()
            cursor.execute("SELECT * FROM events WHERE user_id = ? AND (is_archived = 0 OR is_archived IS NULL) ORDER BY start_datetime DESC",(user_id,))
            events = cursor.fetchall(); event_list = []
            for event_row in events:
                event_dict = dict(event_row)
                if event_dict.get('attendees') and isinstance(event_dict['attendees'], str):
                    try: event_dict['attendees'] = json.loads(event_dict['attendees'])
                    except json.JSONDecodeError: event_dict['attendees'] = []
                event_list.append(event_dict)
            return event_list
        except Exception as e: logger.error(f"Database error in EventService.get_all_events for user {user_id}: {str(e)}", exc_info=True); return []

class LearningService:
    def create_learning_session(self, user_id, topic, resources, start_datetime_str):
        try:
            event_service = EventService()
            start_dt_obj = datetime.datetime.fromisoformat(start_datetime_str)
            end_dt_obj = start_dt_obj + datetime.timedelta(hours=2)
            event_dict_data = {"title": f"Learning Session: {topic}", "start_datetime": start_dt_obj.isoformat(), "end_datetime": end_dt_obj.isoformat()}
            created_event = event_service.create_event(user_id, event_dict_data)
            if not created_event: raise ServiceError(f"Failed to create event for learning session for topic '{topic}'.")
            note_content_str = f"Resources: {', '.join(resources if isinstance(resources, list) else [str(resources)])}"
            note = {"title": f"{topic} Study Notes", "content": note_content_str, "tags": "learning," + topic}
            db = database.get_db_connection(); cursor = db.cursor(); note_id = generate_id("note")
            cursor.execute("INSERT INTO notes (note_id, user_id, title, content, tags) VALUES (?, ?, ?, ?, ?)",(note_id, user_id, note['title'], note['content'], note['tags']))
            db.commit(); full_note_details = {"note_id": note_id, **note}
            logger.info(f"Learning session created for topic '{topic}', user {user_id}. Event: {created_event['event_id']}, Note: {note_id}")
            try:
                learner = AdaptiveLearner(user_id)
                detail = json.dumps({"topic": topic, "resources": resources, "event_id": created_event['event_id'], "note_id": note_id})
                if hasattr(learner, 'log_interaction'): learner.log_interaction("learning_session_created", detail, "success")
            except Exception as learner_e: logger.error(f"AdaptiveLearner error in create_learning_session for user {user_id}, topic {topic}: {str(learner_e)}", exc_info=True)
            return created_event, full_note_details
        except ValueError as ve: logger.error(f"Date/time format error for user {user_id}, topic {topic}: {str(ve)}", exc_info=True); raise ServiceError(f"Invalid start date/time format.")
        except Exception as e: logger.error(f"Error in LearningService.create_learning_session for user {user_id}, topic {topic}: {str(e)}", exc_info=True); raise ServiceError(f"Could not create session: {str(e)}")

    def generate_personalized_content(self, user_id, topic):
        try:
            learner = AdaptiveLearner(user_id); style = "visual"
            if hasattr(learner, 'profile') and learner.profile and 'learning_style' in learner.profile: style = learner.profile.get('learning_style', 'visual')
            content = "";
            if style == "visual": content = f"Visual resources for {topic}:\n- Diagrams\n- Infographics\n- Video tutorials"
            elif style == "auditory": content = f"Auditory resources for {topic}:\n- Podcasts\n- Lectures\n- Audio discussions"
            else: content = f"General resources for {topic}:\n- Practice exercises\n- Projects\n- In-depth readings"
            content += "\n\nStarting with general materials..."
            return content
        except Exception as e: logger.error(f"Error in LearningService.generate_personalized_content for user {user_id}, topic {topic}: {str(e)}", exc_info=True); return "Sorry, error generating content."

class ReportService:
    @staticmethod
    def generate_daily_summary(user_id):
        try:
            db = database.get_db_connection(); today = datetime.date.today().isoformat(); cursor = db.cursor()
            cursor.execute("SELECT title, start_datetime FROM events WHERE user_id = ? AND date(start_datetime) = ? AND (is_archived = 0 OR is_archived IS NULL) ORDER BY start_datetime",(user_id, today))
            events = cursor.fetchall()
            cursor.execute("SELECT title, priority FROM tasks WHERE user_id = ? AND status != 'completed' AND (is_archived = 0 OR is_archived IS NULL) ORDER BY due_datetime",(user_id,))
            tasks = cursor.fetchall()
            summary = "Good morning. I'm Kairo. Here's your daily briefing:\n\n";
            if events:
                summary += "📅 Today's Schedule:\n"
                for event_row in events: event = dict(event_row); start_time = format_timestamp(event['start_datetime'], '%H:%M') if event.get('start_datetime') else "N/A"; summary += f"- {start_time}: {event['title']}\n"
                summary += "\n"
            else: summary += "📅 No events scheduled for today.\n\n"
            if tasks:
                summary += "📝 Your Tasks:\n"
                for task_row in tasks: task = dict(task_row); summary += f"- {task['title']} ({task.get('priority','medium')} priority)\n"
                summary += "\n"
            else: summary += "📝 No pending tasks. Well done!\n\n"
            summary += "\nWould you like me to schedule focus time for your high-priority tasks?"
            return summary
        except Exception as e: logger.error(f"Database error in ReportService.generate_daily_summary for user {user_id}: {str(e)}", exc_info=True); return "Sorry, couldn't generate daily summary."
