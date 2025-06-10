# services.py
import datetime
import json
from database import get_db
from models import Task, Event, Models  # Assuming Models, Task, Event exist
from utils import format_timestamp, generate_id, parse_flexible_datetime  # Assuming these exist
from adaptive_learning import AdaptiveLearner  # Assuming this exists


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

        db = get_db()
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
        db = get_db()
        tasks = db.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND is_archived = 0 ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return [dict(task) for task in tasks]

    @staticmethod
    def complete_task(task_id, user_id):
        db = get_db()
        task = db.execute(
            "SELECT * FROM tasks WHERE task_id = ? AND user_id = ?",
            (task_id, user_id)
        ).fetchone()

        if not task:
            return None

        completed_at = datetime.datetime.now().isoformat()
        db.execute(
            "UPDATE tasks SET status = 'completed', status_change_timestamp = ? "
            "WHERE task_id = ?",
            (completed_at, task_id)
        )
        db.commit()

        # Log adaptive learning interaction
        learner = AdaptiveLearner(user_id)
        detail = json.dumps({
            "task_id": task_id,
            "title": task['title'],
            "completed_at": completed_at
        })
        learner.log_interaction("task_completion", detail, "success")
        learner.analyze_task_performance()

        return db.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()


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

        db = get_db()
        db.execute(
            "INSERT INTO events (event_id, user_id, title, description, start_datetime, end_datetime, location, attendees) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event_data['event_id'], user_id, event_data['title'], event_data['description'],
             event_data['start_datetime'], event_data['end_datetime'], event_data['location'], event_data['attendees'])
        )
        db.commit()
        return event_data

    @staticmethod
    def get_all_events(user_id):
        db = get_db()
        events = db.execute(
            "SELECT * FROM events WHERE user_id = ? ORDER BY start_datetime DESC",
            (user_id,)
        ).fetchall()
        return [dict(event) for event in events]


class LearningService:
    def create_learning_session(self, user_id, topic, resources):
        # Create learning session event
        event_service = EventService()
        optimal_time = AdaptiveLearner(user_id).optimize_schedule(2)  # Assuming this method exists
        event = event_service.create_event(
            user_id,
            {
                "title": f"Learning Session: {topic}",
                "start_datetime": optimal_time,
                "end_datetime": (
                            datetime.datetime.fromisoformat(optimal_time) + datetime.timedelta(hours=2)).isoformat()
            }
        )

        # Create related materials
        note = {
            "title": f"{topic} Study Notes",
            "content": f"Resources: {', '.join(resources)}",
            "tags": "learning," + topic
        }
        db = get_db()
        note_id = generate_id("note")  # Assuming generate_id exists
        db.execute(
            "INSERT INTO notes (note_id, user_id, title, content, tags) "
            "VALUES (?, ?, ?, ?, ?)",
            (note_id, user_id, note['title'], note['content'], note['tags'])
        )
        db.commit()

        # Log learning interaction
        learner = AdaptiveLearner(user_id)  # Assuming AdaptiveLearner exists
        detail = json.dumps({
            "topic": topic,
            "resources": resources,
            "interaction_type": "learning"
        })
        learner.log_interaction("learning", detail, "scheduled")

        return event, {"note_id": note_id, **note}

    def generate_personalized_content(self, user_id, topic):
        learner = AdaptiveLearner(user_id)  # Assuming AdaptiveLearner exists
        style = learner.profile['learning_style']
        proficiency = learner.get_knowledge_proficiency(topic)

        content = ""
        if style == "visual":
            content = f"Here are visual resources for {topic}:\n\n- Diagrams\n- Infographics\n- Video tutorials"
        elif style == "auditory":
            content = f"Here are auditory resources for {topic}:\n\n- Podcasts\n- Lectures\n- Discussions"
        else:
            content = f"Here are hands-on resources for {topic}:\n\n- Practice exercises\n- Projects\n- Experiments"

        # Adjust difficulty based on proficiency
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
        db = get_db()
        today = datetime.date.today().isoformat()

        # Get today's events
        events = db.execute(
            "SELECT title, start_datetime FROM events "
            "WHERE user_id = ? AND date(start_datetime) = ? "
            "ORDER BY start_datetime",
            (user_id, today)
        ).fetchall()

        # Get pending tasks
        tasks = db.execute(
            "SELECT title, priority FROM tasks "
            "WHERE user_id = ? AND status != 'completed' AND is_archived = 0 "
            "ORDER BY due_datetime",
            (user_id,)
        ).fetchall()

        # Format summary
        summary = "Good morning. I'm Kairo. Here's your daily briefing:\n\n"

        if events:
            summary += "📅 Today's Schedule:\n"
            for event in events:
                start_time = format_timestamp(event['start_datetime'], '%H:%M')
                summary += f"- {start_time}: {event['title']}\n"
            summary += "\n"

        if tasks:
            summary += "📝 Your Tasks:\n"
            for task in tasks:
                summary += f"- {task['title']} ({task['priority']} priority)\n"

        summary += "\nWould you like me to schedule focus time for your high-priority tasks?"
        return summary