# routes.py
import datetime
from flask import request, jsonify

from database import get_db
from services import TaskService, EventService, ReportService, LearningService
from scheduling_service import SchedulingService  # Assuming this exists
from kairo_ai import get_kairo_response, parse_ai_action  # Assuming these exist
from adaptive_learning import AdaptiveLearner  # Assuming this exists


def configure_routes(app):
    @app.route('/tasks', methods=['POST'])
    def create_task():
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({"error": "User ID required"}), 400

        try:
            task = TaskService.create_task(user_id, data)
            return jsonify({"task": task}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/tasks', methods=['GET'])
    def get_tasks():
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"error": "User ID required"}), 400

        tasks = TaskService.get_all_tasks(user_id)
        return jsonify({"tasks": tasks})

    @app.route('/tasks/complete/<task_id>', methods=['POST'])
    def complete_task(task_id):
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({"error": "User ID required"}), 400

        task = TaskService.complete_task(task_id, user_id)
        if task:
            return jsonify({"task": dict(task)})
        return jsonify({"error": "Task not found"}), 404

    @app.route('/events', methods=['POST'])
    def create_event():
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({"error": "User ID required"}), 400

        try:
            event = EventService.create_event(user_id, data)
            return jsonify({"event": event}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/events', methods=['GET'])
    def get_events():
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"error": "User ID required"}), 400

        events = EventService.get_all_events(user_id)
        return jsonify({"events": events})

    @app.route('/daily-summary', methods=['GET'])
    def daily_summary():
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"error": "User ID required"}), 400
        summary = ReportService.generate_daily_summary(user_id)
        return jsonify({"summary": summary})

    @app.route('/chat', methods=['POST'])
    def chat():
        data = request.get_json()
        user_message = data.get('message')
        user_id = data.get('user_id')

        if not user_message or not user_id:
            return jsonify({"error": "Missing parameters"}), 400

        # Get conversation history
        db = get_db()
        history = db.execute(
            "SELECT sender, message, context_flags FROM conversation_history "
            "WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10",
            (user_id,)
        ).fetchall()

        # Get AI response
        ai_response = get_kairo_response(user_id, user_message, [dict(h) for h in history])
        action = parse_ai_action(ai_response)

        # Process different action types
        if action.get('action') == 'create_task':
            try:
                task = TaskService.create_task(user_id, action.get('parameters', {}))
                return jsonify({
                    "response": "Task created successfully",
                    "task": task
                })
            except Exception as e:
                return jsonify({
                    "response": f"Couldn't create task: {str(e)}"
                }), 400

        # Log conversation
        db.execute(
            "INSERT INTO conversation_history (user_id, sender, message) "
            "VALUES (?, ?, ?)",
            (user_id, 'user', user_message)
        )
        db.execute(
            "INSERT INTO conversation_history (user_id, sender, message) "
            "VALUES (?, ?, ?)",
            (user_id, 'kairo', ai_response)
        )
        db.commit()

        return jsonify({"response": ai_response})

    # Adaptive learning routes
    @app.route('/adaptive/profile', methods=['GET'])
    def get_learning_profile():
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"error": "User ID required"}), 400

        learner = AdaptiveLearner(user_id)
        return jsonify(learner.profile)

    @app.route('/adaptive/suggestions', methods=['GET'])
    def get_adaptive_suggestions():
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"error": "User ID required"}), 400

        learner = AdaptiveLearner(user_id)
        return jsonify({"suggestions": learner.generate_adaptive_suggestions()})

    @app.route('/tasks/schedule-multiple', methods=['POST'])
    def schedule_multiple_tasks():
        data = request.get_json()
        user_id = data.get('user_id')
        tasks = data.get('tasks', [])
        strategy = data.get('strategy', 'priority_based')

        if not user_id or not tasks:
            return jsonify({"error": "User ID and tasks are required"}), 400

        try:
            scheduler = SchedulingService(user_id)
            scheduled_tasks = scheduler.schedule_multiple_tasks(tasks, strategy)
            return jsonify({"scheduled_tasks": scheduled_tasks})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/learning/session', methods=['POST'])
    def create_learning_session():
        data = request.get_json()
        user_id = data.get('user_id')
        topic = data.get('topic')
        resources = data.get('resources', [])

        if not user_id or not topic:
            return jsonify({"error": "User ID and topic required"}), 400

        service = LearningService()
        event, note = service.create_learning_session(user_id, topic, resources)
        return jsonify({"event": event, "note": note})

    @app.route('/learning/content', methods=['GET'])
    def get_learning_content():
        user_id = request.args.get('user_id')
        topic = request.args.get('topic')

        if not user_id or not topic:
            return jsonify({"error": "User ID and topic required"}), 400

        service = LearningService()
        content = service.generate_personalized_content(user_id, topic)
        return jsonify({"content": content})

    @app.route('/settings', methods=['GET'])
    def get_settings():
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"error": "User ID required"}), 400

        db = get_db()
        settings = db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        if settings:
            return jsonify(dict(settings))
        else:
            # Return default settings
            return jsonify({
                "user_id": user_id,
                "completed_task_archive_duration": 30,
                "theme": "dark",
                "kairo_style": "professional",
                "notification_preferences": "all",
                "working_hours_start": "08:00",
                "working_hours_end": "18:00"
            })

    @app.route('/settings', methods=['POST'])
    def update_settings():
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({"error": "User ID required"}), 400

        db = get_db()
        current_time = datetime.datetime.now().isoformat()

        # Check if settings exist
        existing = db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        if existing:
            # Update existing settings
            set_clauses = []
            values = []
            for key in data:
                if key != 'user_id':
                    set_clauses.append(f"{key} = ?")
                    values.append(data[key])

            if set_clauses:
                sql = f"UPDATE user_settings SET {', '.join(set_clauses)}, updated_at = ? WHERE user_id = ?"
                values.extend([current_time, user_id])
                db.execute(sql, values)
        else:
            # Insert new settings
            db.execute(
                "INSERT INTO user_settings (user_id, completed_task_archive_duration, "
                "theme, kairo_style, notification_preferences, working_hours_start, "
                "working_hours_end, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    data.get('completed_task_archive_duration', 30),
                    data.get('theme', 'dark'),
                    data.get('kairo_style', 'professional'),
                    data.get('notification_preferences', 'all'),
                    data.get('working_hours_start', '08:00'),
                    data.get('working_hours_end', '18:00'),
                    current_time
                )
            )

        db.commit()
        return jsonify({"message": "Settings updated successfully"})

    @app.route('/voice-command', methods=['POST'])
    def voice_command():
        # In production: Integrate with speech-to-text service
        # For demo: Use placeholder transcript
        transcript = "Schedule meeting with team tomorrow at 2 PM"

        # Process as regular chat
        return chat({
            'user_id': request.form.get('user_id'),
            'message': transcript
        })