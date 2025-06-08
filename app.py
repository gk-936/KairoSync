import sqlite3
import json
import datetime
import os
import re
import requests
from flask import Flask, request, jsonify, g
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

DATABASE = 'kairo_data.db'

# --- Custom Exception for API Errors ---
class APIError(Exception):
    """Custom exception for API-specific errors."""
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

# --- Database Setup ---
def get_db():
    """Establishes a database connection or returns the existing one."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def setup_database():
    """Initializes the database schema for tasks, events, and courses."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # Tasks Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                due_date TEXT, -- Storing as TEXT in ISO format (YYYY-MM-DDTHH:MM:SS)
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'pending',
                tags TEXT,
                course_id TEXT,
                parent_id TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        # Add Indexes for tasks
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks (due_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks (priority);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_course_id ON tasks (course_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_parent_id ON tasks (parent_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks (created_at);")

        # Events Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                start_datetime TEXT NOT NULL, -- ISO format
                end_datetime TEXT,     -- ISO format
                location TEXT,
                attendees TEXT,        -- comma-separated emails
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_user_id ON events (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_start_datetime ON events (start_datetime);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_created_at ON events (created_at);")

        # Courses Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                course_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                instructor TEXT,
                schedule TEXT,      -- e.g., "Mon,Wed,Fri 09:00-10:00"
                start_date TEXT,    -- YYYY-MM-DD
                end_date TEXT,      -- YYYY-MM-DD
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_user_id ON courses (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_start_date ON courses (start_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_created_at ON courses (created_at);")

        # Conversation History Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                sender TEXT NOT NULL, -- 'user' or 'kairo'
                message TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                parsed_action TEXT -- Store the JSON string of parsed action
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversation_history_user_id ON conversation_history (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversation_history_timestamp ON conversation_history (timestamp);")

        db.commit()
        print("Database initialized successfully with tables and indexes.")

def init_db(): # Renamed from init_db to avoid conflict with flask command if any, and to be explicit.
    """Initializes the database if it hasn't been already for this app context."""
    # This function can be called explicitly at app start.
    # setup_database() will use app.app_context()
    setup_database()

init_db() # Call it to ensure DB is set up when module is loaded.

# --- Helper Functions ---
def get_iso_datetime(dt_str):
    if not dt_str:
        return None

    # Attempt to parse as YYYY-MM-DD first and foremost for this test
    try:
        # Try parsing as YYYY-MM-DD first to ensure correct end-of-day conversion
        dt_obj = datetime.datetime.strptime(dt_str, '%Y-%m-%d')
        return dt_obj.replace(hour=23, minute=59, second=59).isoformat()
    except ValueError:
        # If not YYYY-MM-DD, try other formats
        try:
            # Try parsing as full ISO format (handles 'Z' by removing it, assumes naive or UTC)
            return datetime.datetime.fromisoformat(dt_str.replace('Z', '')).isoformat()
        except ValueError:
            try:
                # Try parsing as YYYY-MM-DD HH:MM:SS
                return datetime.datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S').isoformat()
            except ValueError:
                return None # Return None if all formats fail

def get_iso_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.datetime.fromisoformat(date_str.replace('Z', '')).date().isoformat()
    except ValueError:
        try:
            return datetime.datetime.strptime(date_str, '%Y-%m-%d').date().isoformat()
        except ValueError:
            return None # Or raise APIError(f"Invalid date format: {date_str}", 400)

def generate_unique_id(prefix="item"):
    #This helper function was missing in the previous app.py, adding it here.
    #It was defined in test_app.py, but should be part of app.py for consistency if used by app logic (e.g. AI creating tasks)
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

# OLLAMA_MODEL needs to be defined, assuming it's an environment variable or a fixed value.
# For now, let's hardcode a placeholder if it's not in os.environ for broader compatibility.
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama2")


def save_task_to_db(task):
    conn = get_db()
    cursor = conn.cursor()
    # The task['due_date'] should already be normalized by the calling route/function (e.g., add_task_route or process_ai_action)
    # before this function is called.
    try:
        cursor.execute(
            "INSERT INTO tasks (task_id, user_id, title, description, due_date, priority, status, created_at, updated_at, tags, course_id, parent_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (task['task_id'], task['user_id'], task['title'], task.get('description'), task.get('due_date'), task.get('priority', 'medium'), task.get('status', 'pending'), task['created_at'], task['updated_at'], task.get('tags'), task.get('course_id'), task.get('parent_id'))
        )
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise APIError(f"Database error: {e}", 500)
    return task

def get_tasks_from_db(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE user_id = ?", (user_id,))
    tasks = [dict(row) for row in cursor.fetchall()]
    return tasks

def get_task_by_id_from_db(task_id, user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    if user_id:
        cursor.execute("SELECT * FROM tasks WHERE task_id = ? AND user_id = ?", (task_id, user_id))
    else: # Allow fetching by task_id only, internal use or admin? Carefully consider.
        cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    task_data = cursor.fetchone()
    return dict(task_data) if task_data else None

def update_task_in_db(task_id, user_id, updates):
    conn = get_db()
    cursor = conn.cursor()
    fields_to_update = []
    values = []
    allowed_fields = ["title", "description", "due_date", "priority", "status", "tags", "course_id", "parent_id"]

    for key, value in updates.items():
        if key not in allowed_fields:
            continue
        if key == 'due_date':
            if value:
                original_value = value
                value = get_iso_datetime(value)
                if not value:
                    raise APIError(f"Invalid due_date format for '{original_value}'. Please use YYYY-MM-DDTHH:MM:SS, YYYY-MM-DD HH:MM:SS, or YYYY-MM-DD.", 400)
            else: # Allow setting due_date to null
                value = None
        elif key == 'priority':
            allowed_priorities = ['low', 'medium', 'high']
            if value is not None and value not in allowed_priorities: # Allow None to skip update for this field
                raise APIError(f"Invalid priority value '{value}'. Allowed values are: {', '.join(allowed_priorities)}.", 400)
        elif key == 'status':
            allowed_statuses = ['pending', 'in-progress', 'completed', 'cancelled']
            if value is not None and value not in allowed_statuses: # Allow None to skip update
                raise APIError(f"Invalid status value '{value}'. Allowed values are: {', '.join(allowed_statuses)}.", 400)

        # Only add to update if value is not None, or if it's a field that can be set to NULL (like due_date, description)
        if value is not None or key in ['description', 'due_date', 'tags', 'course_id', 'parent_id']:
            fields_to_update.append(f"{key} = ?")
            values.append(value)

    if not fields_to_update:
        return 0 # No valid fields to update or all values were None for non-nullable fields

    fields_to_update.append("updated_at = ?")
    values.append(datetime.datetime.now().isoformat())
    values.append(user_id) # For WHERE clause
    values.append(task_id) # For WHERE clause

    sql = f"UPDATE tasks SET {', '.join(fields_to_update)} WHERE user_id = ? AND task_id = ?"
    try:
        cursor.execute(sql, tuple(values))
        conn.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        conn.rollback()
        raise APIError(f"Database error: {e}", 500)

def delete_task_from_db(user_id, task_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM tasks WHERE user_id = ? AND task_id = ?", (user_id, task_id))
        conn.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        conn.rollback()
        raise APIError(f"Database error: {e}", 500)

# Event CRUD DB Functions
def add_event_to_db(user_id, title, start_datetime, description=None, end_datetime=None, location=None, attendees=None):
    db = get_db()
    cursor = db.cursor()
    event_id = generate_unique_id("event")
    current_time = datetime.datetime.now().isoformat()

    original_start_datetime = start_datetime
    start_datetime_iso = get_iso_datetime(start_datetime)
    if not start_datetime_iso:
        raise APIError(f"Invalid start_datetime format for '{original_start_datetime}'. Required.", 400)

    end_datetime_iso = None
    if end_datetime:
        original_end_datetime = end_datetime
        end_datetime_iso = get_iso_datetime(end_datetime)
        if not end_datetime_iso:
            raise APIError(f"Invalid end_datetime format for '{original_end_datetime}'.", 400)
        if start_datetime_iso and end_datetime_iso < start_datetime_iso: # Ensure end is after start
            raise APIError(f"End datetime '{end_datetime}' cannot be before start datetime '{start_datetime}'.", 400)

    try:
        cursor.execute(
            "INSERT INTO events (event_id, user_id, title, description, start_datetime, end_datetime, location, attendees, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, user_id, title, description, start_datetime_iso, end_datetime_iso, location, attendees, current_time, current_time)
        )
        db.commit()
    except sqlite3.Error as e:
        db.rollback()
        raise APIError(f"Database error: {e}", 500)
    return get_event_by_id(user_id, event_id) # Return the full event object

def get_all_events_for_user(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM events WHERE user_id = ? ORDER BY start_datetime DESC", (user_id,))
    events = [dict(row) for row in cursor.fetchall()]
    return events

def get_event_by_id(user_id, event_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM events WHERE user_id = ? AND event_id = ?", (user_id, event_id))
    event = cursor.fetchone()
    return dict(event) if event else None

def _get_event_by_id_internal(event_id): # Internal helper, e.g. if AI needs to check existence without user context
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM events WHERE event_id = ?", (event_id,))
    event = cursor.fetchone()
    return dict(event) if event else None

def update_event_in_db(event_id, user_id, updates):
    db = get_db()
    cursor = db.cursor()
    fields_to_update = []
    values = []
    allowed_fields = ["title", "description", "start_datetime", "end_datetime", "location", "attendees"]

    has_valid_update = False
    for key, value in updates.items():
        if key in allowed_fields:
            if key in ['start_datetime', 'end_datetime']:
                if value: # Allow clearing the datetime by passing None/null
                    original_value = value
                    value = get_iso_datetime(value)
                    if not value:
                        raise APIError(f"Invalid {key} format for '{original_value}'.", 400)
            # For other fields, if value is None, it means clear the field (set to NULL)
            # If value is provided, it's an update.
            fields_to_update.append(f"{key} = ?")
            values.append(value)
            has_valid_update = True # Mark that there's a field to update

    if not has_valid_update: # No valid fields were passed in `updates`
        return 0

    # Validate start/end datetime consistency if both are being updated or one is updated and the other exists
    updated_start_datetime = updates.get('start_datetime')
    updated_end_datetime = updates.get('end_datetime')

    if updated_start_datetime or updated_end_datetime:
        current_event_data = get_event_by_id(user_id, event_id)
        sdt_to_check = get_iso_datetime(updated_start_datetime) if updated_start_datetime else current_event_data.get('start_datetime')
        edt_to_check = get_iso_datetime(updated_end_datetime) if updated_end_datetime else current_event_data.get('end_datetime')
        if sdt_to_check and edt_to_check and edt_to_check < sdt_to_check:
            raise APIError("End datetime cannot be before start datetime.", 400)


    fields_to_update.append("updated_at = ?")
    values.append(datetime.datetime.now().isoformat())
    values.append(user_id) # For WHERE user_id = ?
    values.append(event_id) # For WHERE event_id = ?

    sql = f"UPDATE events SET {', '.join(fields_to_update)} WHERE user_id = ? AND event_id = ?"
    try:
        cursor.execute(sql, tuple(values))
        db.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        db.rollback()
        raise APIError(f"Database error: {e}", 500)

def delete_event_from_db(event_id, user_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM events WHERE user_id = ? AND event_id = ?", (user_id, event_id))
        conn.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        conn.rollback()
        raise APIError(f"Database error: {e}", 500)

# Course CRUD operations
def add_course_to_db(user_id, name, description=None, instructor=None, schedule=None, start_date=None, end_date=None):
    db = get_db()
    cursor = db.cursor()
    course_id = generate_unique_id("course")
    current_time = datetime.datetime.now().isoformat()

    start_date_iso = None
    if start_date:
        original_start_date = start_date
        start_date_iso = get_iso_date(start_date)
        if not start_date_iso:
            raise APIError(f"Invalid start_date format for '{original_start_date}'. Please use YYYY-MM-DD.", 400)

    end_date_iso = None
    if end_date:
        original_end_date = end_date
        end_date_iso = get_iso_date(end_date)
        if not end_date_iso:
            raise APIError(f"Invalid end_date format for '{original_end_date}'. Please use YYYY-MM-DD.", 400)
        if start_date_iso and end_date_iso < start_date_iso: # Ensure end is after start
            raise APIError(f"End date '{end_date}' cannot be before start date '{start_date}'.", 400)

    try:
        cursor.execute(
            "INSERT INTO courses (course_id, user_id, name, description, instructor, schedule, start_date, end_date, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (course_id, user_id, name, description, instructor, schedule, start_date_iso, end_date_iso, current_time, current_time)
        )
        db.commit()
    except sqlite3.Error as e:
        db.rollback()
        raise APIError(f"Database error: {e}", 500)
    return get_course_by_id(user_id, course_id)

def get_all_courses_for_user(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM courses WHERE user_id = ?", (user_id,))
    courses = [dict(row) for row in cursor.fetchall()]
    return courses

def get_course_by_id(user_id, course_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM courses WHERE user_id = ? AND course_id = ?", (user_id, course_id))
    course = cursor.fetchone()
    return dict(course) if course else None

def _get_course_by_id_internal(course_id): # Internal helper
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM courses WHERE course_id = ?", (course_id,))
    course = cursor.fetchone()
    return dict(course) if course else None

def update_course_in_db(course_id, user_id, updates):
    db = get_db()
    cursor = db.cursor()
    fields_to_update = []
    values = []
    allowed_fields = ["name", "description", "instructor", "schedule", "start_date", "end_date"]

    has_valid_update_field = False
    for key, value in updates.items():
        if key in allowed_fields:
            if key in ['start_date', 'end_date']:
                if value: # Allow clearing date by passing None/null
                    original_value = value
                    value = get_iso_date(value)
                    if not value:
                        raise APIError(f"Invalid {key} format for '{original_value}'. Please use YYYY-MM-DD.", 400)
            fields_to_update.append(f"{key} = ?")
            values.append(value)
            has_valid_update_field = True


    if not has_valid_update_field:
        return 0

    # Validate start/end date consistency
    updated_start_date = updates.get('start_date')
    updated_end_date = updates.get('end_date')
    if updated_start_date or updated_end_date:
        current_course_data = get_course_by_id(user_id, course_id)
        sdt_to_check = get_iso_date(updated_start_date) if updated_start_date else current_course_data.get('start_date')
        edt_to_check = get_iso_date(updated_end_date) if updated_end_date else current_course_data.get('end_date')
        if sdt_to_check and edt_to_check and edt_to_check < sdt_to_check:
            raise APIError("End date cannot be before start date.", 400)

    fields_to_update.append("updated_at = ?")
    values.append(datetime.datetime.now().isoformat())

    sql = f"UPDATE courses SET {', '.join(fields_to_update)} WHERE user_id = ? AND course_id = ?"
    values.extend([user_id, course_id]) # Add user_id and course_id for the WHERE clause

    try:
        cursor.execute(sql, tuple(values))
        db.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        db.rollback()
        raise APIError(f"Database error: {e}", 500)

def delete_course_from_db(course_id, user_id):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM courses WHERE user_id = ? AND course_id = ?", (user_id, course_id))
        db.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        db.rollback()
        raise APIError(f"Database error: {e}", 500)

# --- Ollama AI Integration ---
OLLAMA_MODEL_API_URL = os.environ.get("OLLAMA_MODEL_API_URL", "http://localhost:11434/api/chat")

def get_ollama_response(messages_history):
    """
    Sends messages to Ollama's /api/chat endpoint and returns the AI's content.
    messages_history should be a list of dicts like [{"role": "user", "content": "..."}, ...]
    """
    headers = {'Content-Type': 'application/json'}
    payload = {
        "model": OLLAMA_MODEL, # Ensure OLLAMA_MODEL is defined (e.g., from os.environ or hardcoded)
        "messages": messages_history,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_MODEL_API_URL, headers=headers, data=json.dumps(payload), timeout=120)
        response.raise_for_status()
        response_json = response.json()

        if "message" in response_json and "content" in response_json["message"]:
            return response_json["message"]["content"]
        else:
            app.logger.error(f"Unexpected response format from Ollama: {response_json}")
            raise APIError("AI response format error.", 500)

    except requests.exceptions.ConnectionError as e:
        app.logger.error(f"Could not connect to Ollama server at {OLLAMA_MODEL_API_URL}: {e}")
        raise APIError("Cannot connect to AI service.", 503) # Service Unavailable
    except requests.exceptions.Timeout:
        app.logger.error("Ollama request timed out.")
        raise APIError("AI service timeout.", 504) # Gateway Timeout
    except requests.exceptions.RequestException as e: # Catch other request-related errors
        app.logger.error(f"Error calling Ollama API: {e}")
        raise APIError(f"AI service communication error: {e}", 500)

def parse_ai_action(user_message, conversation_history_list):
    """
    Uses Ollama to parse user intent and extract structured JSON actions.
    The LLM is prompted to output JSON.
    """
    current_date_str = datetime.date.today().isoformat()

    system_prompt_template = """
You are Kairo, an AI assistant for a personal organizer app. Your goal is to convert user requests into structured JSON actions or provide conversational responses.
Your response **must be only a single, valid JSON object** and nothing else. Do not include any explanatory text, markdown formatting, or anything outside of this single JSON object.

**Available Actions (JSON Schema):**

1.  **Create a Task:**
    ```json
    {{"action": "create_task", "title": "string (required)", "description": "string (optional)", "due_date": "YYYY-MM-DDTHH:MM:SS (optional, if only date is given, time defaults to 23:59:59 of that day)", "priority": "low|medium|high (optional, default 'medium')", "status": "pending|in-progress|completed|cancelled (optional, default 'pending')", "tags": "comma-separated strings (optional)", "course_id": "string (optional, if related to a course)", "parent_id": "string (optional, for sub-tasks)"}}
    ```
    * **Examples:**
        * "Create a task: buy groceries." -> `{{"action": "create_task", "title": "Buy groceries"}}`
        * "Remind me to call mom tomorrow at 5 PM." (Current date: {current_date}) -> `{{"action": "create_task", "title": "Call mom", "due_date": "{tomorrow_date}T17:00:00"}}`
        * "Add a high priority task to finish project report by next Friday." (Current date: {current_date}, next Friday: {next_friday_date}) -> `{{"action": "create_task", "title": "Finish project report", "due_date": "{next_friday_date}T23:59:59", "priority": "high"}}`

2.  **Update a Task:**
    ```json
    {{"action": "update_task", "task_id": "string (optional, if known)", "title_keywords": "string (optional, to identify task by title if ID not given)", "title": "string (optional, new title)", "description": "string (optional)", "due_date": "YYYY-MM-DDTHH:MM:SS (optional, if only date is given, time defaults to 23:59:59)", "priority": "low|medium|high (optional)", "status": "pending|in-progress|completed|cancelled (optional)", "tags": "comma-separated strings (optional, replaces existing)", "course_id": "string (optional)", "parent_id": "string (optional)"}}
    ```
    * **Examples:**
        * "Mark 'buy groceries' as completed." -> `{{"action": "update_task", "title_keywords": "buy groceries", "status": "completed"}}`
        * "Change the due date of task 'project report' to next Monday." (Current date: {current_date}, next Monday: {next_monday_date}) -> `{{"action": "update_task", "title_keywords": "project report", "due_date": "{next_monday_date}T23:59:59"}}`
        * "Update task_123 to high priority and add 'urgent, important' tags." -> `{{"action": "update_task", "task_id": "task_123", "priority": "high", "tags": "urgent, important"}}`

3.  **Delete a Task:**
    ```json
    {{"action": "delete_task", "task_id": "string (optional, if known)", "title_keywords": "string (optional, to identify task by title if ID not given)"}}
    ```
    * **Examples:**
        * "Delete task 'call mom'." -> `{{"action": "delete_task", "title_keywords": "call mom"}}`
        * "Remove task_456." -> `{{"action": "delete_task", "task_id": "task_456"}}`

4.  **Create an Event:**
    ```json
    {{"action": "create_event", "title": "string (required)", "start_datetime": "YYYY-MM-DDTHH:MM:SS (required)", "description": "string (optional)", "end_datetime": "YYYY-MM-DDTHH:MM:SS (optional)", "location": "string (optional)", "attendees": "comma-separated emails (optional)"}}
    ```
    * **Examples:**
        * "Schedule a meeting for tomorrow at 10 AM for 1 hour about project review." (Current date: {current_date}) -> `{{"action": "create_event", "title": "Project Review Meeting", "start_datetime": "{tomorrow_date}T10:00:00", "end_datetime": "{tomorrow_date}T11:00:00", "description": "project review"}}`
        * "Add a dentist appointment on 2025-07-15 at 3 PM." -> `{{"action": "create_event", "title": "Dentist Appointment", "start_datetime": "2025-07-15T15:00:00"}}`

5.  **Update an Event:**
    ```json
    {{"action": "update_event", "event_id": "string (optional, if known)", "title_keywords": "string (optional, to identify event by title if ID not given)", "title": "string (optional, new title)", "description": "string (optional)", "start_datetime": "YYYY-MM-DDTHH:MM:SS (optional)", "end_datetime": "YYYY-MM-DDTHH:MM:SS (optional)", "location": "string (optional)", "attendees": "comma-separated emails (optional)"}}
    ```
    * **Example:** "Reschedule dentist appointment to next Wednesday at 4 PM." (Current date: {current_date}, next Wednesday: {next_wednesday_date}) -> `{{"action": "update_event", "title_keywords": "dentist appointment", "start_datetime": "{next_wednesday_date}T16:00:00"}}`

6.  **Delete an Event:**
    ```json
    {{"action": "delete_event", "event_id": "string (optional, if known)", "title_keywords": "string (optional, to identify event by title if ID not given)"}}
    ```
    * **Example:** "Cancel the project review meeting." -> `{{"action": "delete_event", "title_keywords": "project review meeting"}}`

7.  **Create a Course:**
    ```json
    {{"action": "create_course", "name": "string (required)", "description": "string (optional)", "instructor": "string (optional)", "schedule": "string (optional)", "start_date": "YYYY-MM-DD (optional)", "end_date": "YYYY-MM-DD (optional)"}}
    ```
    * **Example:** "Add my new course: Data Structures, instructor John Doe, starts next month." (Current date: {current_date}, next month starts: {next_month_start_date}) -> `{{"action": "create_course", "name": "Data Structures", "instructor": "John Doe", "start_date": "{next_month_start_date}"}}`

8.  **Update a Course:**
    ```json
    {{"action": "update_course", "course_id": "string (optional, if known)", "name_keywords": "string (optional, to identify course by name if ID not given)", "name": "string (optional, new name)", "description": "string (optional)", "instructor": "string (optional)", "schedule": "string (optional)", "start_date": "YYYY-MM-DD (optional)", "end_date": "YYYY-MM-DD (optional)"}}
    ```
    * **Example:** "Change Data Structures instructor to Jane Smith." -> `{{"action": "update_course", "name_keywords": "Data Structures", "instructor": "Jane Smith"}}`

9.  **Delete a Course:**
    ```json
    {{"action": "delete_course", "course_id": "string (optional, if known)", "name_keywords": "string (optional, to identify course by name if ID not given)"}}
    ```
    * **Example:** "Remove the course called Linear Algebra." -> `{{"action": "delete_course", "name_keywords": "Linear Algebra"}}`

10. **Retrieve Items (Tasks, Events, Courses):**
    ```json
    {{"action": "retrieve_items", "item_type": "tasks|events|courses|all (optional, default 'all')", "status": "pending|in-progress|completed|cancelled|all (optional, for tasks)", "priority": "low|medium|high (optional, for tasks)", "date": "YYYY-MM-DD (optional, for events on a specific day)", "date_range_start": "YYYY-MM-DD (optional, for events in a range)", "date_range_end": "YYYY-MM-DD (optional, for events in a range)", "keywords": "string (optional, for title/name search)"}}
    ```
    * **Examples:**
        * "List my pending tasks." -> `{{"action": "retrieve_items", "item_type": "tasks", "status": "pending"}}`
        * "Show me all events for next week." (Current date: {current_date}, next week: {next_week_start_date} to {next_week_end_date}) -> `{{"action": "retrieve_items", "item_type": "events", "date_range_start": "{next_week_start_date}", "date_range_end": "{next_week_end_date}"}}`
        * "What courses do I have?" -> `{{"action": "retrieve_items", "item_type": "courses"}}`

11. **General Conversation / No Specific Action:**
    ```json
    {{"action": "respond_conversation", "response_text": "string (your conversational reply)"}}
    ```
    * **Use this if the user's query does not map to any of the above actions or if more information is needed.**
    * **Examples:**
        * "Hello Kairo!" -> `{{"action": "respond_conversation", "response_text": "Hello! How can I assist you today?"}}`
        * "Tell me a joke." -> `{{"action": "respond_conversation", "response_text": "Why don't scientists trust atoms? Because they make up everything!"}}`
        * "What's the weather like?" -> `{{"action": "respond_conversation", "response_text": "I can help you manage your tasks, events, and courses. I'm unable to provide weather updates."}}`

        **Important Guidelines:**
        * **Date & Time:** Accurately calculate dates/datetimes for relative terms (e.g., "today", "tomorrow", "next Monday", "next week", "next month") based on the **Current Date: {current_date}**. For due_datetime or start_datetime, if only a date is provided, assume end-of-day (23:59:59) for tasks or a sensible default time for events if not specified.
        * **Identification:** If the user asks to update or delete an item and doesn't provide an ID, use `title_keywords` (for tasks/events) or `name_keywords` (for courses) and fill that field with keywords from their message. If the item type is ambiguous (e.g., "delete the report"), ask for clarification.
        * **Ambiguity:** If a request is ambiguous or requires more information for a structured action, default to `respond_conversation` and ask for clarification, or provide a helpful general response.
        * **Out of Scope:** For requests unrelated to tasks, events, or courses, use `respond_conversation` to gently guide the user.
        * **Context:** Use `Conversation History` for context in follow-up questions.
        * **Keywords:** When inferring keywords, be precise.

        Current Date: {current_date}

        Conversation History (most recent first):
        {conversation_history_json}

        User Message: "{user_message}"

        Your JSON Action:
    """

    # Calculate dynamic dates for examples
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    next_friday = today + datetime.timedelta(days=(4 - today.weekday() + 7) % 7)
    next_monday = today + datetime.timedelta(days=(0 - today.weekday() + 7) % 7)
    next_wednesday = today + datetime.timedelta(days=(2 - today.weekday() + 7) % 7)

    if today.month == 12:
        next_month_start = datetime.date(today.year + 1, 1, 1)
    else:
        next_month_start = datetime.date(today.year, today.month + 1, 1)

    start_of_current_week = today - datetime.timedelta(days=today.weekday())
    next_week_start_date = start_of_current_week + datetime.timedelta(weeks=1)
    next_week_end_date = next_week_start_date + datetime.timedelta(days=6)

    formatted_system_prompt = system_prompt_template.format(
        current_date=current_date_str,
        tomorrow_date=tomorrow.isoformat(),
        next_friday_date=next_friday.isoformat(),
        next_monday_date=next_monday.isoformat(),
        next_wednesday_date=next_wednesday.isoformat(),
        next_month_start_date=next_month_start.isoformat(),
        next_week_start_date=next_week_start_date.isoformat(),
        next_week_end_date=next_week_end_date.isoformat(),
        conversation_history_json=json.dumps(conversation_history_list),
        user_message=user_message
    )

    messages_for_ollama = [
        {"role": "system", "content": formatted_system_prompt},
        {"role": "user", "content": user_message}
    ]

    try:
        raw_response = get_ollama_response(messages_for_ollama)
        match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if match:
            json_string = match.group(0)
        else:
            # Fallback if no clear JSON block is found, try to clean common issues
            json_string = raw_response.strip().replace("```json", "").replace("```", "").strip()

        parsed_action = json.loads(json_string)
        return parsed_action
    except json.JSONDecodeError as e:
        app.logger.error(f"Failed to parse AI action JSON. Raw response: '{raw_response}'. Error: {e}")
        # Try to provide a more specific error if the cleaned string is short/empty
        if not json_string or len(json_string) < 2: # e.g. empty or just "{"
             raise APIError(f"Kairo's response was empty or not valid JSON. Raw: '{raw_response}'", 500)
        raise APIError(f"Kairo understood your request but had trouble formatting its response. Please try rephrasing. (Details: {e}) Raw: '{raw_response}'", 500)
    except Exception as e: # Catch other exceptions from get_ollama_response or parsing
        app.logger.error(f"Error in parse_ai_action: {e}", exc_info=True)
        raise APIError("Kairo encountered an issue parsing your request into an action. Please try again.", 500)


def process_ai_action(user_id, parsed_action):
    if not parsed_action or not isinstance(parsed_action, dict):
        raise APIError("Invalid action format received from AI.", 500)

    action_type = parsed_action.get('action')
    tasks_result, events_result, courses_result = [], [], []
    response_message = ""

    if not action_type:
        response_message = parsed_action.get('response_text', "I couldn't understand the specific action. Please rephrase.")
        return response_message, [], [], []

    try:
        if action_type == "create_task":
            if not parsed_action.get('title'): raise APIError("Task title is required.", 400)
            due_date_str = parsed_action.get('due_date')
            due_date_iso = get_iso_datetime(due_date_str) if due_date_str else None
            if due_date_str and not due_date_iso: raise APIError(f"Invalid due_date format: {due_date_str}.", 400)

            task_data = {
                "user_id": user_id, "title": parsed_action.get('title'),
                "description": parsed_action.get('description'), "due_date": due_date_iso,
                "priority": parsed_action.get('priority', 'medium'), "status": parsed_action.get('status', 'pending'),
                "tags": parsed_action.get('tags'), "course_id": parsed_action.get('course_id'),
                "parent_id": parsed_action.get('parent_id'), "task_id": generate_unique_id("task"),
                "created_at": datetime.datetime.now().isoformat(), "updated_at": datetime.datetime.now().isoformat()
            }
            if task_data['priority'] not in ['low', 'medium', 'high']: raise APIError("Invalid priority.", 400)
            if task_data['status'] not in ['pending', 'in-progress', 'completed', 'cancelled']: raise APIError("Invalid status.", 400)

            task_obj = save_task_to_db(task_data)
            response_message = f"Task '{task_obj['title']}' created (ID: {task_obj['task_id']})."
            tasks_result = get_tasks_from_db(user_id)

        elif action_type in ["update_task", "delete_task"]:
            task_id = parsed_action.get('task_id')
            title_keywords = parsed_action.get('title_keywords')
            if not task_id and not title_keywords: raise APIError("Task ID or title keywords required.", 400)

            target_task = None
            if task_id:
                target_task = get_task_by_id_from_db(task_id, user_id)
            else: # title_keywords
                all_user_tasks = get_tasks_from_db(user_id)
                matching_tasks = [t for t in all_user_tasks if title_keywords.lower() in t['title'].lower()]
                if not matching_tasks: raise APIError(f"No task found with keywords '{title_keywords}'.", 404)
                if len(matching_tasks) > 1:
                    ids = ", ".join([t['task_id'] for t in matching_tasks[:3]])
                    raise APIError(f"Multiple tasks match '{title_keywords}'. Use Task ID. Matches: {ids}", 400)
                target_task = matching_tasks[0]

            if not target_task: raise APIError("Task not found.", 404)

            if action_type == "update_task":
                updates = {k: v for k, v in parsed_action.items() if k not in ['action', 'task_id', 'title_keywords', 'user_id'] and v is not None}
                if not updates: raise APIError("No update information provided.", 400)
                # due_date validation for update is handled by update_task_in_db
                if update_task_in_db(target_task['task_id'], user_id, updates):
                    response_message = f"Task '{target_task['title']}' updated."
                else:
                    response_message = f"Task '{target_task['title']}' not updated (no changes or issue)."
            elif action_type == "delete_task":
                if delete_task_from_db(user_id, target_task['task_id']):
                    response_message = f"Task '{target_task['title']}' deleted."
                else: raise APIError(f"Failed to delete task '{target_task['title']}'.", 500)
            tasks_result = get_tasks_from_db(user_id)

        elif action_type == "create_event":
            if not parsed_action.get('title') or not parsed_action.get('start_datetime'):
                raise APIError("Event title and start_datetime are required.", 400)
            event_obj = add_event_to_db(user_id=user_id, **{k:v for k,v in parsed_action.items() if k not in ['action', 'user_id']})
            response_message = f"Event '{event_obj['title']}' created (ID: {event_obj['event_id']})."
            events_result = get_all_events_for_user(user_id)

        elif action_type in ["update_event", "delete_event"]:
            event_id = parsed_action.get('event_id')
            title_keywords = parsed_action.get('title_keywords')
            if not event_id and not title_keywords: raise APIError("Event ID or title keywords required.", 400)

            target_event = None
            if event_id: target_event = get_event_by_id(user_id, event_id)
            else:
                all_user_events = get_all_events_for_user(user_id)
                matching_events = [e for e in all_user_events if title_keywords.lower() in e['title'].lower()]
                if not matching_events: raise APIError(f"No event found with keywords '{title_keywords}'.", 404)
                if len(matching_events) > 1:
                    ids = ", ".join([e['event_id'] for e in matching_events[:3]])
                    raise APIError(f"Multiple events match '{title_keywords}'. Use Event ID. Matches: {ids}", 400)
                target_event = matching_events[0]

            if not target_event: raise APIError("Event not found.", 404)

            if action_type == "update_event":
                updates = {k:v for k,v in parsed_action.items() if k not in ['action', 'event_id', 'title_keywords', 'user_id'] and v is not None}
                if not updates: raise APIError("No update info for event.", 400)
                if update_event_in_db(target_event['event_id'], user_id, updates):
                    response_message = f"Event '{target_event['title']}' updated."
                else: response_message = f"Event '{target_event['title']}' not updated."
            elif action_type == "delete_event":
                if delete_event_from_db(target_event['event_id'], user_id):
                    response_message = f"Event '{target_event['title']}' deleted."
                else: raise APIError(f"Failed to delete event '{target_event['title']}'.", 500)
            events_result = get_all_events_for_user(user_id)

        elif action_type == "create_course":
            if not parsed_action.get('name'): raise APIError("Course name required.", 400)
            course_obj = add_course_to_db(user_id=user_id, **{k:v for k,v in parsed_action.items() if k not in ['action', 'user_id']})
            response_message = f"Course '{course_obj['name']}' created (ID: {course_obj['course_id']})."
            courses_result = get_all_courses_for_user(user_id)

        elif action_type in ["update_course", "delete_course"]:
            course_id = parsed_action.get('course_id')
            name_keywords = parsed_action.get('name_keywords')
            if not course_id and not name_keywords: raise APIError("Course ID or name keywords required.", 400)

            target_course = None
            if course_id: target_course = get_course_by_id(user_id, course_id)
            else:
                all_user_courses = get_all_courses_for_user(user_id)
                matching_courses = [c for c in all_user_courses if name_keywords.lower() in c['name'].lower()]
                if not matching_courses: raise APIError(f"No course with keywords '{name_keywords}'.", 404)
                if len(matching_courses) > 1:
                    ids = ", ".join([c['course_id'] for c in matching_courses[:3]])
                    raise APIError(f"Multiple courses match '{name_keywords}'. Use ID. Matches: {ids}", 400)
                target_course = matching_courses[0]

            if not target_course: raise APIError("Course not found.", 404)

            if action_type == "update_course":
                updates = {k:v for k,v in parsed_action.items() if k not in ['action', 'course_id', 'name_keywords', 'user_id'] and v is not None}
                if not updates: raise APIError("No update info for course.", 400)
                if update_course_in_db(target_course['course_id'], user_id, updates):
                    response_message = f"Course '{target_course['name']}' updated."
                else: response_message = f"Course '{target_course['name']}' not updated."
            elif action_type == "delete_course":
                if delete_course_from_db(target_course['course_id'], user_id):
                    response_message = f"Course '{target_course['name']}' deleted."
                else: raise APIError(f"Failed to delete course '{target_course['name']}'.", 500)
            courses_result = get_all_courses_for_user(user_id)

        elif action_type == "retrieve_items":
            item_type = parsed_action.get('item_type', 'all')
            summaries = []
            if item_type == 'tasks' or item_type == 'all':
                tasks_result = get_tasks_from_db(user_id)
                if tasks_result: summaries.append(f"Tasks ({len(tasks_result)}): " + ", ".join([t['title'] for t in tasks_result[:5]])) # show first 5
                else: summaries.append("No tasks found.")
            if item_type == 'events' or item_type == 'all':
                events_result = get_all_events_for_user(user_id)
                if events_result: summaries.append(f"Events ({len(events_result)}): " + ", ".join([e['title'] for e in events_result[:5]]))
                else: summaries.append("No events found.")
            if item_type == 'courses' or item_type == 'all':
                courses_result = get_all_courses_for_user(user_id)
                if courses_result: summaries.append(f"Courses ({len(courses_result)}): " + ", ".join([c['name'] for c in courses_result[:5]]))
                else: summaries.append("No courses found.")
            response_message = "\n".join(summaries) if summaries else "No items found matching your criteria."

        elif action_type == "respond_conversation":
            response_message = parsed_action.get('response_text', "I'm not sure how to respond to that.")

        else:
            raise APIError(f"Unknown action type: {action_type}", 400)

    except APIError as e_api: # Catch APIErrors raised by DB functions or validation
        app.logger.warning(f"APIError in process_ai_action: {e_api.message} (Status: {e_api.status_code}) - Action: {action_type}")
        response_message = e_api.message # Use the error message from APIError
        # Depending on desired behavior, you might want to re-raise or handle differently
    except Exception as e_unexpected: # Catch any other unexpected errors
        app.logger.error(f"Unexpected error in process_ai_action for action '{action_type}': {e_unexpected}", exc_info=True)
        response_message = "An internal server error occurred while processing your request."
        # Re-raise to be caught by global error handler, ensuring a 500 response
        if not isinstance(e_unexpected, APIError): # Should not happen if APIError is caught above
             raise e_unexpected

    return response_message, tasks_result, events_result, courses_result

# --- API Routes ---

@app.route('/')
def home():
    return jsonify({"message": "KairoSync AI Assistant Backend. Access API endpoints like /tasks, /events, /courses, /chat."})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data: raise APIError("Request body must be JSON.", 400)

    user_id = data.get('user_id')
    user_message = data.get('message')
    kairo_style = data.get('kairo_style', 'friendly')

    if not user_id: raise APIError("User ID is required.", 400)
    if not user_message: raise APIError("Message is required.", 400)

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT sender, message FROM conversation_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10", (user_id,)
    )
    conversation_history_list = [{"role": row['sender'], "content": row['message']} for row in cursor.fetchall()]
    conversation_history_list.reverse()

    ai_response_message = ""
    tasks_data, events_data, courses_data = [], [], []
    parsed_action_for_log = None
    error_occurred = False # Flag to check if error was handled by APIError block

    try:
        parsed_action_for_log = parse_ai_action(user_message, conversation_history_list)
        ai_response_message, tasks_data, events_data, courses_data = process_ai_action(user_id, parsed_action_for_log)
    except APIError as e:
        error_occurred = True
        ai_response_message = e.message
        # Status code from APIError will be used by handle_api_error if this is re-raised,
        # but here we are packaging it into a 200 response's JSON body for the chat.
        # For the /chat endpoint, we typically want to return a 200 OK with the error message in the response body.
        # The HTTP status code of the /chat response itself might remain 200.
        # If we want /chat to return specific error codes (4xx, 5xx), we'd re-raise e here.
        app.logger.warning(f"APIError in chat (handled for user response): {e.message} (Status: {e.status_code})")
        # To ensure the correct status code is sent to the client for API errors from chat:
        # return jsonify({"error": e.message, "parsed_action": parsed_action_for_log}), e.status_code
        # However, the current structure logs it and returns 200 with the message in "response".
        # Let's keep it consistent with current structure first.
        parsed_action_for_log = parsed_action_for_log or {"action": "error", "error_details": e.message}
    except Exception as e_unhandled:
        error_occurred = True
        app.logger.error(f"Unexpected error in chat endpoint: {e_unhandled}", exc_info=True)
        ai_response_message = "I encountered an unexpected internal error. Please try again later."
        parsed_action_for_log = {"action": "error", "error_details": str(e_unhandled)}
        # For truly unexpected errors, it's good practice for the endpoint to return a 500.
        # This requires re-raising or returning a specific Flask error response.
        # For now, this will also be wrapped in a 200 OK for the chat.
        # raise APIError(ai_response_message, 500) # Option to convert to standard API error response

    # Apply Kairo style (moved after error handling to ensure message is set)
    base_response = ai_response_message
    if kairo_style == 'professional' and not error_occurred : base_response = f"Acknowledged. {ai_response_message}"
    elif kairo_style == 'friendly' and not error_occurred: base_response = f"Hey there! {ai_response_message}"
    # Concise style might not add prefix for errors or already concise messages
    elif kairo_style == 'concise' and not error_occurred and len(ai_response_message) > 20: base_response = f"Kairo: {ai_response_message}"
    elif kairo_style == 'casual' and not error_occurred: base_response = f"Sup! {ai_response_message}"
    ai_response_message = base_response

    # Log conversation
    current_time = datetime.datetime.now().isoformat()
    try:
        cursor.execute(
            "INSERT INTO conversation_history (user_id, sender, message, timestamp, parsed_action) VALUES (?, ?, ?, ?, ?)",
            (user_id, 'user', user_message, current_time, None)
        )
        # Ensure parsed_action_for_log is a dict before attempting json.dumps
        action_log_str = json.dumps(parsed_action_for_log) if isinstance(parsed_action_for_log, dict) else str(parsed_action_for_log)
        cursor.execute(
            "INSERT INTO conversation_history (user_id, sender, message, timestamp, parsed_action) VALUES (?, ?, ?, ?, ?)",
            (user_id, 'kairo', ai_response_message, datetime.datetime.now().isoformat(),action_log_str)
        )
        db.commit()
    except Exception as e_log:
        app.logger.error(f"Error logging conversation to database: {e_log}", exc_info=True)

    # If an APIError was caught and we want the /chat endpoint to reflect its status code:
    # if isinstance(e, APIError): return jsonify({"response": ai_response_message, "parsed_action": parsed_action_for_log}), e.status_code

    return jsonify({
        "response": ai_response_message,
        "tasks": tasks_data,
        "events": events_data,
        "courses": courses_data, # Ensure this is 'courses_data' not 'courses_result'
        "parsed_action": parsed_action_for_log
    })

# --- API Endpoints for Frontend CRUD (Direct Operations) ---

@app.route('/tasks', methods=['GET'])
def get_tasks_route():
    user_id = request.args.get('user_id')
    if not user_id: raise APIError("User ID is required.", 400)
    tasks = get_tasks_from_db(user_id)
    return jsonify(tasks)

@app.route('/tasks', methods=['POST'])
def add_task_route():
    data = request.get_json()
    if not data: raise APIError("Request body must be JSON.", 400)

    user_id = data.get('user_id')
    title = data.get('title')

    if not user_id: raise APIError("User ID is required.", 400)
    if not title: raise APIError("Task title is required.", 400)

    priority = data.get('priority', 'medium')
    status = data.get('status', 'pending')
    if priority not in ['low', 'medium', 'high']:
        raise APIError(f"Invalid priority: {priority}.", 400)
    if status not in ['pending', 'in-progress', 'completed', 'cancelled']:
        raise APIError(f"Invalid status: {status}.", 400)

    due_date_str = data.get('due_date')
    due_date_iso = None
    if due_date_str:
        due_date_iso = get_iso_datetime(due_date_str)
        if not due_date_iso:
            raise APIError(f"Invalid due_date format for '{due_date_str}'. Use ISO compatible (YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, etc.).", 400)

    task_data = {
        "task_id": generate_unique_id("task"),
        "user_id": user_id, "title": title,
        "description": data.get('description'), "due_date": due_date_iso, # Use normalized date
        "priority": priority, "status": status,
        "tags": data.get("tags"), "course_id": data.get("course_id"), "parent_id": data.get("parent_id"),
        "created_at": datetime.datetime.now().isoformat(), "updated_at": datetime.datetime.now().isoformat()
    }
    created_task = save_task_to_db(task_data)
    return jsonify(created_task), 201

@app.route('/tasks/<task_id>', methods=['GET'])
def get_task_route(task_id):
    user_id = request.args.get('user_id')
    if not user_id: raise APIError("User ID is required.", 400)
    task = get_task_by_id_from_db(task_id, user_id)
    if task: return jsonify(task)
    else: raise APIError("Task not found.", 404)

@app.route('/tasks/<task_id>', methods=['PUT'])
def update_task_route(task_id):
    data = request.get_json()
    if not data: raise APIError("Request body must be JSON.", 400)
    user_id = request.args.get('user_id')
    if not user_id: raise APIError("User ID is required as query parameter.", 400)

    if not get_task_by_id_from_db(task_id, user_id):
        raise APIError("Task not found or access denied.", 404) # Checks ownership

    # Validations for fields if they are present in data
    if 'priority' in data and data['priority'] is not None and data['priority'] not in ['low', 'medium', 'high']:
        raise APIError(f"Invalid priority: {data['priority']}.", 400)
    if 'status' in data and data['status'] is not None and data['status'] not in ['pending', 'in-progress', 'completed', 'cancelled']:
        raise APIError(f"Invalid status: {data['status']}.", 400)
    if 'due_date' in data and data['due_date'] is not None:
        if not get_iso_datetime(data['due_date']):
             raise APIError(f"Invalid due_date format for '{data['due_date']}'.", 400)

    rows_affected = update_task_in_db(task_id, user_id, data)
    updated_task = get_task_by_id_from_db(task_id, user_id) # Fetch regardless of rows_affected to get current state
    if not updated_task: raise APIError("Task not found after update attempt (possibly deleted concurrently).", 404)

    if rows_affected > 0:
        return jsonify({"message": "Task updated successfully", "task": updated_task})
    else: # No rows affected, means no changes applied or data was same
        return jsonify({"message": "Task update processed, but no changes were made or task already in desired state.", "task": updated_task}), 200


@app.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task_route(task_id):
    user_id = request.args.get('user_id')
    if not user_id: raise APIError("User ID is required as query parameter.", 400)

    if not get_task_by_id_from_db(task_id, user_id): # Check existence and ownership
        raise APIError("Task not found or access denied.", 404)

    if delete_task_from_db(user_id, task_id):
        return jsonify({"message": "Task deleted successfully"})
    else:
        # This case should be rare if the above check passed, implies a race condition or unexpected DB error
        raise APIError("Task deletion failed. It might have been already deleted or an error occurred.", 500)


@app.route('/events', methods=['GET'])
def get_events_route():
    user_id = request.args.get('user_id')
    if not user_id: raise APIError("User ID is required.", 400)
    events = get_all_events_for_user(user_id)
    return jsonify(events)

@app.route('/events', methods=['POST'])
def add_event_route():
    data = request.get_json()
    if not data: raise APIError("Request body must be JSON.", 400)

    user_id = data.get('user_id')
    title = data.get('title')
    start_datetime_str = data.get('start_datetime')

    if not user_id: raise APIError("User ID is required.", 400)
    if not title: raise APIError("Event title is required.", 400)
    if not start_datetime_str: raise APIError("Event start_datetime is required.", 400)

    # Date validation is handled by add_event_to_db, which calls get_iso_datetime
    event = add_event_to_db(
        user_id=user_id, title=title, start_datetime=start_datetime_str,
        description=data.get('description'), end_datetime=data.get('end_datetime'),
        location=data.get('location'), attendees=data.get('attendees')
    )
    return jsonify({"message": "Event added successfully", "event": event}), 201

@app.route('/events/<event_id>', methods=['GET'])
def get_event_route(event_id):
    user_id = request.args.get('user_id')
    if not user_id: raise APIError("User ID is required.", 400)
    event = get_event_by_id(user_id, event_id)
    if event: return jsonify(event)
    else: raise APIError("Event not found.", 404)

@app.route('/events/<event_id>', methods=['PUT'])
def update_event_route(event_id):
    data = request.get_json()
    if not data: raise APIError("Request body must be JSON.", 400)
    user_id = request.args.get('user_id')
    if not user_id: raise APIError("User ID is required as query parameter.", 400)

    if not get_event_by_id(user_id, event_id): # Check existence and ownership
        raise APIError("Event not found or access denied.", 404)

    # Date validation for start/end is handled by update_event_in_db
    rows_affected = update_event_in_db(event_id, user_id, data)
    updated_event = get_event_by_id(user_id, event_id)
    if not updated_event: raise APIError("Event not found after update attempt.", 404)

    if rows_affected > 0:
        return jsonify({"message": "Event updated successfully", "event": updated_event})
    else:
        return jsonify({"message": "Event update processed, but no changes made or already in desired state.", "event": updated_event}), 200


@app.route('/events/<event_id>', methods=['DELETE'])
def delete_event_route(event_id):
    user_id = request.args.get('user_id')
    if not user_id: raise APIError("User ID is required as query parameter.", 400)

    if not get_event_by_id(user_id, event_id): # Check existence and ownership
        raise APIError("Event not found or access denied.", 404)

    if delete_event_from_db(event_id, user_id):
        return jsonify({"message": "Event deleted successfully"})
    else:
        raise APIError("Event deletion failed.", 500)


@app.route('/courses', methods=['GET'])
def get_courses_route():
    user_id = request.args.get('user_id')
    if not user_id: raise APIError("User ID is required.", 400)
    courses = get_all_courses_for_user(user_id)
    return jsonify(courses)

@app.route('/courses', methods=['POST'])
def add_course_route():
    data = request.get_json()
    if not data: raise APIError("Request body must be JSON.", 400)

    user_id = data.get('user_id')
    name = data.get('name')

    if not user_id: raise APIError("User ID is required.", 400)
    if not name: raise APIError("Course name is required.", 400)

    # Date validation is handled by add_course_to_db
    course = add_course_to_db(
        user_id=user_id, name=name, description=data.get('description'),
        instructor=data.get('instructor'), schedule=data.get('schedule'),
        start_date=data.get('start_date'), end_date=data.get('end_date')
    )
    return jsonify({"message": "Course added successfully", "course": course}), 201

@app.route('/courses/<course_id>', methods=['GET'])
def get_course_route(course_id):
    user_id = request.args.get('user_id')
    if not user_id: raise APIError("User ID is required.", 400)
    course = get_course_by_id(user_id, course_id)
    if course: return jsonify(course)
    else: raise APIError("Course not found.", 404)

@app.route('/courses/<course_id>', methods=['PUT'])
def update_course_route(course_id):
    data = request.get_json()
    if not data: raise APIError("Request body must be JSON.", 400)
    user_id = request.args.get('user_id')
    if not user_id: raise APIError("User ID is required as query parameter.", 400)

    if not get_course_by_id(user_id, course_id): # Check existence and ownership
        raise APIError("Course not found or access denied.", 404)

    # Date validation handled by update_course_in_db
    rows_affected = update_course_in_db(course_id, user_id, data)
    updated_course = get_course_by_id(user_id, course_id)
    if not updated_course: raise APIError("Course not found after update attempt.", 404)

    if rows_affected > 0:
        return jsonify({"message": "Course updated successfully", "course": updated_course})
    else:
        return jsonify({"message": "Course update processed, but no changes made or already in desired state.", "course": updated_course}), 200

@app.route('/courses/<course_id>', methods=['DELETE'])
def delete_course_route(course_id):
    user_id = request.args.get('user_id')
    if not user_id: raise APIError("User ID is required as query parameter.", 400)

    if not get_course_by_id(user_id, course_id): # Check existence and ownership
        raise APIError("Course not found or access denied.", 404)

    if delete_course_from_db(course_id, user_id):
        return jsonify({"message": "Course deleted successfully"})
    else:
        raise APIError("Course deletion failed.", 500) # Changed from 404 to 500


# --- General Error Handlers ---
@app.errorhandler(APIError)
def handle_api_error(error):
    response = jsonify({"error": error.message})
    response.status_code = error.status_code
    return response

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not Found"}), 404

@app.errorhandler(500)
def internal_server_error(error): # Parameter name 'error' is conventional
    app.logger.error(f"Internal Server Error: {error}", exc_info=True)
    return jsonify({"error": "An internal server error occurred."}), 500

if __name__ == '__main__':
    init_db() # Ensure DB is initialized
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
