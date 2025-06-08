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

DATABASE = 'kairo_data.db' # Ensure this matches your file name

# Ollama API Configuration
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.1:8b" # Make sure this model is pulled in your Ollama installation

# --- Custom Exception for API Errors ---
class APIError(Exception):
    """Custom exception for API-specific errors."""
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

# --- Database Functions ---
def get_db():
    """Establishes a database connection or returns the existing one."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row # This makes rows behave like dictionaries
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Closes the database connection at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def setup_database():
    """Initializes the database schema for tasks, events, and courses."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        # Create tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                due_datetime TEXT, -- ISO format:YYYY-MM-DDTHH:MM:SS
                priority TEXT DEFAULT 'medium', -- e.g., low, medium, high
                status TEXT DEFAULT 'pending', -- e.g., pending, in-progress, completed, cancelled
                tags TEXT,        -- comma-separated tags
                course_id TEXT,   -- Optional: Link to a course
                parent_id TEXT,   -- Optional: For sub-tasks/dependencies
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        # Create events table
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        # Create courses table
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        # Create conversation_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                sender TEXT NOT NULL, -- 'user' or 'kairo'
                message TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                parsed_action TEXT -- Store the JSON string of parsed action
            );
        ''')

        db.commit()
        print("Database initialized successfully.")

# Run database initialization on app startup
with app.app_context():
    setup_database()

# --- Helper Functions for Database Operations ---

def generate_unique_id(prefix):
    """Generates a unique ID based on timestamp and a prefix."""
    return f"{prefix}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"

def get_iso_datetime(dt_str):
    """Converts a datetime string to ISO 8601 format, handling various inputs."""
    if not dt_str:
        return None
    try:
        # Try parsing as full ISO format first
        dt_obj = datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt_obj.isoformat()
    except ValueError:
        try:
            # Try parsing as YYYY-MM-DD HH:MM:SS
            dt_obj = datetime.datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            return dt_obj.isoformat()
        except ValueError:
            try:
                # Try parsing as YYYY-MM-DD (assume midnight)
                dt_obj = datetime.datetime.strptime(dt_str, '%Y-%m-%d')
                return dt_obj.isoformat()
            except ValueError:
                return None # Return None if format is unrecognized

def get_iso_date(date_str):
    """Converts a date string to ISO 8601 YYYY-MM-DD format."""
    if not date_str:
        return None
    try:
        date_obj = datetime.datetime.fromisoformat(date_str).date()
        return date_obj.isoformat()
    except ValueError:
        return None

# Task CRUD operations
def add_task_to_db(user_id, title, description=None, due_datetime=None, priority='medium', status='pending', tags=None, course_id=None, parent_id=None):
    db = get_db()
    task_id = generate_unique_id("task")
    current_time = datetime.datetime.now().isoformat()
    due_datetime_iso = get_iso_datetime(due_datetime)
    
    db.execute(
        "INSERT INTO tasks (task_id, user_id, title, description, due_datetime, priority, status, tags, course_id, parent_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (task_id, user_id, title, description, due_datetime_iso, priority, status, tags, course_id, parent_id, current_time, current_time)
    )
    db.commit()
    return get_task_by_id(user_id, task_id) # Return the newly created task object

def get_all_tasks_for_user(user_id):
    db = get_db()
    cursor = db.execute("SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    return [dict(row) for row in cursor.fetchall()]

def get_task_by_id(user_id, task_id):
    db = get_db()
    cursor = db.execute("SELECT * FROM tasks WHERE user_id = ? AND task_id = ?", (user_id, task_id))
    task = cursor.fetchone()
    return dict(task) if task else None

def update_task_in_db(task_id, user_id, updates):
    db = get_db()
    set_clauses = []
    values = []
    
    updates['updated_at'] = datetime.datetime.now().isoformat() # Always update timestamp
    
    for key, value in updates.items():
        if key == 'due_datetime':
            value = get_iso_datetime(value) # Ensure consistent date format
        if key not in ['task_id', 'user_id', 'created_at']: # Prevent updating primary key or immutable fields
            set_clauses.append(f"{key} = ?")
            values.append(value)
    
    if not set_clauses:
        return False # No valid fields to update

    sql = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE user_id = ? AND task_id = ?"
    values.extend([user_id, task_id])
    
    cursor = db.execute(sql, tuple(values))
    db.commit()
    return cursor.rowcount > 0

def delete_task_from_db(task_id, user_id):
    db = get_db()
    cursor = db.execute("DELETE FROM tasks WHERE user_id = ? AND task_id = ?", (user_id, task_id))
    db.commit()
    return cursor.rowcount > 0

# Event CRUD operations
def add_event_to_db(user_id, title, start_datetime, description=None, end_datetime=None, location=None, attendees=None):
    db = get_db()
    event_id = generate_unique_id("event")
    current_time = datetime.datetime.now().isoformat()
    start_datetime_iso = get_iso_datetime(start_datetime)
    end_datetime_iso = get_iso_datetime(end_datetime)

    if not start_datetime_iso:
        raise APIError("Valid start_datetime is required for event.", 400)

    db.execute(
        "INSERT INTO events (event_id, user_id, title, description, start_datetime, end_datetime, location, attendees, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (event_id, user_id, title, description, start_datetime_iso, end_datetime_iso, location, attendees, current_time, current_time)
    )
    db.commit()
    return get_event_by_id(user_id, event_id)

def get_all_events_for_user(user_id):
    db = get_db()
    cursor = db.execute("SELECT * FROM events WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    return [dict(row) for row in cursor.fetchall()]

def get_event_by_id(user_id, event_id):
    db = get_db()
    cursor = db.execute("SELECT * FROM events WHERE user_id = ? AND event_id = ?", (user_id, event_id))
    event = cursor.fetchone()
    return dict(event) if event else None

def update_event_in_db(event_id, user_id, updates):
    db = get_db()
    set_clauses = []
    values = []
    
    updates['updated_at'] = datetime.datetime.now().isoformat()
    
    for key, value in updates.items():
        if key in ['start_datetime', 'end_datetime']:
            value = get_iso_datetime(value) # Ensure consistent date format
        if key not in ['event_id', 'user_id', 'created_at']:
            set_clauses.append(f"{key} = ?")
            values.append(value)
    
    if not set_clauses:
        return False

    sql = f"UPDATE events SET {', '.join(set_clauses)} WHERE user_id = ? AND event_id = ?"
    values.extend([user_id, event_id])
    
    cursor = db.execute(sql, tuple(values))
    db.commit()
    return cursor.rowcount > 0

def delete_event_from_db(event_id, user_id):
    db = get_db()
    cursor = db.execute("DELETE FROM events WHERE user_id = ? AND event_id = ?", (user_id, event_id))
    db.commit()
    return cursor.rowcount > 0

# Course CRUD operations
def add_course_to_db(user_id, name, description=None, instructor=None, schedule=None, start_date=None, end_date=None):
    db = get_db()
    course_id = generate_unique_id("course")
    current_time = datetime.datetime.now().isoformat()
    start_date_iso = get_iso_date(start_date)
    end_date_iso = get_iso_date(end_date)

    db.execute(
        "INSERT INTO courses (course_id, user_id, name, description, instructor, schedule, start_date, end_date, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (course_id, user_id, name, description, instructor, schedule, start_date_iso, end_date_iso, current_time, current_time)
    )
    db.commit()
    return get_course_by_id(user_id, course_id)

def get_all_courses_for_user(user_id):
    db = get_db()
    cursor = db.execute("SELECT * FROM courses WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    return [dict(row) for row in cursor.fetchall()]

def get_course_by_id(user_id, course_id):
    db = get_db()
    cursor = db.execute("SELECT * FROM courses WHERE user_id = ? AND course_id = ?", (user_id, course_id))
    course = cursor.fetchone()
    return dict(course) if course else None

def update_course_in_db(course_id, user_id, updates):
    db = get_db()
    set_clauses = []
    values = []
    
    updates['updated_at'] = datetime.datetime.now().isoformat()
    
    for key, value in updates.items():
        if key in ['start_date', 'end_date']:
            value = get_iso_date(value) # Ensure consistent date format
        if key not in ['course_id', 'user_id', 'created_at']:
            set_clauses.append(f"{key} = ?")
            values.append(value)
    
    if not set_clauses:
        return False

    sql = f"UPDATE courses SET {', '.join(set_clauses)} WHERE user_id = ? AND course_id = ?"
    values.extend([user_id, course_id])
    
    cursor = db.execute(sql, tuple(values))
    db.commit()
    return cursor.rowcount > 0

def delete_course_from_db(course_id, user_id):
    db = get_db()
    cursor = db.execute("DELETE FROM courses WHERE user_id = ? AND course_id = ?", (user_id, course_id))
    db.commit()
    return cursor.rowcount > 0

# --- Ollama AI Integration ---

def get_ollama_response(messages_history):
    """
    Sends messages to Ollama's /api/chat endpoint and returns the AI's content.
    messages_history should be a list of dicts like [{"role": "user", "content": "..."}, ...]
    """
    headers = {'Content-Type': 'application/json'}
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages_history,
        "stream": False # Get a single complete response
    }

    try:
        response = requests.post(OLLAMA_URL, headers=headers, data=json.dumps(payload), timeout=120)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        response_json = response.json()

        if "message" in response_json and "content" in response_json["message"]:
            return response_json["message"]["content"]
        else:
            print(f"Error: Unexpected response format from Ollama: {response_json}")
            return "I apologize, I received an unexpected response format from the AI."

    except requests.exceptions.ConnectionError as e:
        print(f"Error: Could not connect to Ollama server at {OLLAMA_URL}. Is Ollama running? {e}")
        return "I'm sorry, I cannot connect to the AI at the moment. Please ensure Ollama is running."
    except requests.exceptions.Timeout:
        print("Error: Ollama request timed out.")
        return "The AI took too long to respond. Please try again."
    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama API: {e}")
        return f"An error occurred while communicating with the AI: {e}"

def parse_ai_action(user_message, conversation_history_list):
    """
    Uses Ollama to parse user intent and extract structured JSON actions.
    The LLM is prompted to output JSON.
    """
    current_date_str = datetime.date.today().isoformat()
    
    # Define the core system prompt template as a regular string
    system_prompt_template = """
        You are an AI assistant named Kairo for a personal organizer app. Your primary goal is to understand user requests and convert them into structured JSON actions, or provide helpful conversational responses.
        
        **Always output ONLY a single JSON object. Do not include any other text or markdown outside the JSON.**

        **Available Actions (JSON Schema):**

        1.  **Create a Task:**
            ```json
            {{"action": "create_task", "title": "string (required)", "description": "string (optional)", "due_datetime": "YYYY-MM-DDTHH:MM:SS (optional)", "priority": "low|medium|high (optional, default 'medium')", "status": "pending|in-progress|completed|cancelled (optional, default 'pending')", "tags": "comma-separated strings (optional)", "course_id": "string (optional, if related to a course)", "parent_id": "string (optional, for sub-tasks)"}}
            ```
            * **Examples:**
                * "Create a task: buy groceries." -> `{{"action": "create_task", "title": "Buy groceries", "description": null, "due_datetime": null, "priority": "medium", "status": "pending", "tags": null, "course_id": null, "parent_id": null}}`
                * "Remind me to call mom tomorrow at 5 PM." (Assume current date is {current_date}) -> `{{"action": "create_task", "title": "Call mom", "description": null, "due_datetime": "{tomorrow_date}T17:00:00", "priority": "medium", "status": "pending", "tags": null, "course_id": null, "parent_id": null}}`
                * "Add a high priority task to finish project report by next Friday." (Assume next Friday is {next_friday_date}) -> `{{"action": "create_task", "title": "Finish project report", "description": null, "due_datetime": "{next_friday_date}T23:59:59", "priority": "high", "status": "pending", "tags": null, "course_id": null, "parent_id": null}}`

        2.  **Update a Task:**
            ```json
            {{"action": "update_task", "task_id": "string (required, if identifiable)", "title_keywords": "string (optional, keywords to identify task by title if ID not given)", "title": "string (optional)", "description": "string (optional)", "due_datetime": "YYYY-MM-DDTHH:MM:SS (optional)", "priority": "low|medium|high (optional)", "status": "pending|in-progress|completed|cancelled (optional)", "tags": "comma-separated strings (optional)", "course_id": "string (optional)", "parent_id": "string (optional)"}}
            ```
            * **Examples:**
                * "Mark 'buy groceries' as completed." -> `{{"action": "update_task", "title_keywords": "buy groceries", "status": "completed"}}`
                * "Change the due date of task 'project report' to next Monday." (Assume next Monday is {next_monday_date}) -> `{{"action": "update_task", "title_keywords": "project report", "due_datetime": "{next_monday_date}T23:59:59"}}`
                * "Update task_123 to high priority and add 'urgent' tag." -> `{{"action": "update_task", "task_id": "task_123", "priority": "high", "tags": "urgent"}}`

        3.  **Delete a Task:**
            ```json
            {{"action": "delete_task", "task_id": "string (required, if identifiable)", "title_keywords": "string (optional, keywords to identify task by title if ID not given)"}}
            ```
            * **Examples:**
                * "Delete task 'call mom'." -> `{{"action": "delete_task", "title_keywords": "call mom"}}`
                * "Remove task_456." -> `{{"action": "delete_task", "task_id": "task_456"}}`

        4.  **Create an Event:**
            ```json
            {{"action": "create_event", "title": "string (required)", "start_datetime": "YYYY-MM-DDTHH:MM:SS (required)", "description": "string (optional)", "end_datetime": "YYYY-MM-DDTHH:MM:SS (optional)", "location": "string (optional)", "attendees": "comma-separated emails (optional)"}}
            ```
            * **Examples:**
                * "Schedule a meeting for tomorrow at 10 AM for 1 hour about project review." (Assume current date is {current_date}) -> `{{"action": "create_event", "title": "Project Review Meeting", "start_datetime": "{tomorrow_date}T10:00:00", "end_datetime": "{tomorrow_date}T11:00:00", "location": null, "description": "project review", "attendees": null}}`
                * "Add a dentist appointment on 2025-07-15 at 3 PM." -> `{{"action": "create_event", "title": "Dentist Appointment", "start_datetime": "2025-07-15T15:00:00", "description": null, "end_datetime": null, "location": null, "attendees": null}}`

        5.  **Update an Event:**
            ```json
            {{"action": "update_event", "event_id": "string (required, if identifiable)", "title_keywords": "string (optional, keywords to identify event by title if ID not given)", "title": "string (optional)", "description": "string (optional)", "start_datetime": "YYYY-MM-DDTHH:MM:SS (optional)", "end_datetime": "YYYY-MM-DDTHH:MM:SS (optional)", "location": "string (optional)", "attendees": "comma-separated emails (optional)"}}
            ```
            * **Example:** "Reschedule dentist appointment to next Wednesday at 4 PM." (Assume next Wednesday is {next_wednesday_date}) -> `{{"action": "update_event", "title_keywords": "dentist appointment", "start_datetime": "{next_wednesday_date}T16:00:00"}}`

        6.  **Delete an Event:**
            ```json
            {{"action": "delete_event", "event_id": "string (required, if identifiable)", "title_keywords": "string (optional, keywords to identify event by title if ID not given)"}}
            ```
            * **Example:** "Cancel the project review meeting." -> `{{"action": "delete_event", "title_keywords": "project review meeting"}}`

        7.  **Create a Course:**
            ```json
            {{"action": "create_course", "name": "string (required)", "description": "string (optional)", "instructor": "string (optional)", "schedule": "string (optional)", "start_date": "YYYY-MM-DD (optional)", "end_date": "YYYY-MM-DD (optional)"}}
            ```
            * **Example:** "Add my new course: Data Structures, instructor John Doe, starts next month." (Assume next month starts {next_month_start_date}) -> `{{"action": "create_course", "name": "Data Structures", "description": null, "instructor": "John Doe", "schedule": null, "start_date": "{next_month_start_date}", "end_date": null}}`

        8.  **Update a Course:**
            ```json
            {{"action": "update_course", "course_id": "string (required, if identifiable)", "name_keywords": "string (optional, keywords to identify course by name if ID not given)", "name": "string (optional)", "description": "string (optional)", "instructor": "string (optional)", "schedule": "string (optional)", "start_date": "YYYY-MM-DD (optional)", "end_date": "YYYY-MM-DD (optional)"}}
            ```
            * **Example:** "Change Data Structures instructor to Jane Smith." -> `{{"action": "update_course", "name_keywords": "Data Structures", "instructor": "Jane Smith"}}`

        9.  **Delete a Course:**
            ```json
            {{"action": "delete_course", "course_id": "string (required, if identifiable)", "name_keywords": "string (optional, keywords to identify course by name if ID not given)"}}
            ```
            * **Example:** "Remove the course called Linear Algebra." -> `{{"action": "delete_course", "name_keywords": "Linear Algebra"}}`

        10. **Retrieve All (Tasks/Events/Courses - or specific type):**
            ```json
            {{"action": "retrieve_items", "item_type": "tasks|events|courses|all (optional, default 'all')", "status": "pending|in-progress|completed|cancelled|all (optional, for tasks)", "priority": "low|medium|high (optional, for tasks)", "date": "YYYY-MM-DD (optional, for events)", "date_range_start": "YYYY-MM-DD (optional, for events)", "date_range_end": "YYYY-MM-DD (optional, for events)", "keywords": "string (optional, for title/name search)"}}
            ```
            * **Examples:**
                * "List my pending tasks." -> `{{"action": "retrieve_items", "item_type": "tasks", "status": "pending"}}`
                * "Show me all events for next week." (Assume next week is {next_week_start_date} to {next_week_end_date}) -> `{{"action": "retrieve_items", "item_type": "events", "date_range_start": "{next_week_start_date}", "date_range_end": "{next_week_end_date}"}}`
                * "What courses do I have?" -> `{{"action": "retrieve_items", "item_type": "courses"}}`

        11. **General Conversation / No Specific Action:**
            ```json
            {{"action": "respond_conversation", "response_text": "string"}}
            ```
            * **Examples:**
                * "Hello Kairo!" -> `{{"action": "respond_conversation", "response_text": "Hello! How can I assist you today?"}}`
                * "Tell me a joke." -> `{{"action": "respond_conversation", "response_text": "Why don't scientists trust atoms? Because they make up everything!"}}`
                * "What's the weather like?" -> `{{"action": "respond_conversation", "response_text": "I can only help you manage your tasks, events, and courses. I cannot provide weather updates."}}`
                * "How are you?" -> `{{"action": "respond_conversation", "response_text": "I am an AI, so I don't have feelings, but I'm ready to help!"}}`

        **Important Guidelines for Kairo:**
        * Calculate specific YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS dates/datetimes for relative terms (e.g., "today", "tomorrow", "next Monday", "next week", "next month") based on the current date: **{current_date}**.
        * If the user asks to update or delete an item and doesn't provide an ID, assume `title_keywords` or `name_keywords` and fill that field with keywords from their message. If the item type is ambiguous (e.g., "delete the report"), ask for clarification.
        * If a request is ambiguous or requires more information for a structured action, default to `respond_conversation` and ask for clarification, or provide a helpful general response.
        * If the user asks for something completely outside the scope of available actions (e.g., "What's the capital of France?"), use `respond_conversation` and gently remind them of your capabilities regarding tasks, events, and courses.
        * Use the provided `conversation_history_list` to maintain context for follow-up questions.
        * When inferring `title_keywords` or `name_keywords`, be as precise as possible, taking into account the full user message.

        Current Date: {current_date}

        Conversation History:
        {conversation_history_json}

        User Message: "{user_message}"

        Your JSON Action:
    """
    
    # Calculate dynamic dates for examples
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    next_friday = today + datetime.timedelta(days=(4 - today.weekday() + 7) % 7) # Friday is weekday 4
    next_monday = today + datetime.timedelta(days=(0 - today.weekday() + 7) % 7) # Monday is weekday 0
    next_wednesday = today + datetime.timedelta(days=(2 - today.weekday() + 7) % 7) # Wednesday is weekday 2
    
    # Calculate start of next month
    if today.month == 12:
        next_month_start = datetime.date(today.year + 1, 1, 1)
    else:
        next_month_start = datetime.date(today.year, today.month + 1, 1)

    # Calculate next week's start and end dates (Mon-Sun)
    start_of_current_week = today - datetime.timedelta(days=today.weekday())
    next_week_start_date = start_of_current_week + datetime.timedelta(weeks=1)
    next_week_end_date = next_week_start_date + datetime.timedelta(days=6)

    # Format the system prompt template with dynamic dates and history
    formatted_system_prompt = system_prompt_template.format(
        current_date=current_date_str,
        tomorrow_date=tomorrow.isoformat(),
        next_friday_date=next_friday.isoformat(),
        next_monday_date=next_monday.isoformat(),
        next_wednesday_date=next_wednesday.isoformat(),
        next_month_start_date=next_month_start.isoformat(),
        next_week_start_date=next_week_start_date.isoformat(),
        next_week_end_date=next_week_end_date.isoformat(),
        conversation_history_json=json.dumps(conversation_history_list), # Insert JSON string of history
        user_message=user_message
    )

    messages_for_ollama = [
        {"role": "system", "content": formatted_system_prompt},
        {"role": "user", "content": user_message} # The current user message, directly
    ]

    try:
        raw_response = get_ollama_response(messages_for_ollama)
        print(f"Ollama raw action response: {raw_response}")

        # Attempt to clean the response if it contains markdown or extra text outside JSON
        match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if match:
            json_string = match.group(0)
        else:
            json_string = raw_response.strip() # Assume it's just JSON if no markdown
        
        parsed_action = json.loads(json_string)
        return parsed_action
    except json.JSONDecodeError as e:
        print(f"Failed to parse AI action JSON: {raw_response} - Error: {e}")
        raise APIError("Kairo understood your request but generated an invalid action format. Please try rephrasing.", 500)
    except Exception as e:
        print(f"Error in parse_ai_action: {e}")
        raise APIError("Kairo encountered an issue parsing your request into an action. Please try again.", 500)


def process_ai_action(user_id, parsed_action):
    """
    Executes the identified AI action using the backend functions.
    Returns a user-friendly message about the action's success or failure,
    and potentially lists of items if a retrieval action was performed.
    """
    action_type = parsed_action.get('action')
    response_message = "I couldn't understand that action or perform it."
    
    # Initialize lists to return for frontend updates
    tasks_result = []
    events_result = []
    courses_result = []

    try:
        if action_type == "create_task":
            task_obj = add_task_to_db(
                user_id=user_id,
                title=parsed_action.get('title'),
                description=parsed_action.get('description'),
                due_datetime=parsed_action.get('due_datetime'),
                priority=parsed_action.get('priority'),
                status=parsed_action.get('status'),
                tags=parsed_action.get('tags'),
                course_id=parsed_action.get('course_id'),
                parent_id=parsed_action.get('parent_id')
            )
            if task_obj:
                response_message = f"Task '{task_obj['title']}' created successfully (ID: {task_obj['task_id']})."
            else:
                response_message = "Failed to create task."
            tasks_result = get_all_tasks_for_user(user_id) # Refresh list

        elif action_type == "update_task":
            task_id_or_keywords = parsed_action.get('task_id') or parsed_action.get('title_keywords')
            if not task_id_or_keywords:
                response_message = "Please provide a Task ID or keywords from its title to update."
            else:
                target_task = None
                if parsed_action.get('task_id'):
                    target_task = get_task_by_id(user_id, parsed_action['task_id'])
                elif parsed_action.get('title_keywords'):
                    all_tasks = get_all_tasks_for_user(user_id)
                    matching_tasks = [t for t in all_tasks if parsed_action['title_keywords'].lower() in t['title'].lower()]
                    if len(matching_tasks) == 1:
                        target_task = matching_tasks[0]
                    elif len(matching_tasks) > 1:
                        response_message = "Multiple tasks match your description. Please be more specific or provide the Task ID."
                        return response_message, [], [], []
                
                if target_task:
                    updates = {k: v for k, v in parsed_action.items() if k not in ['action', 'task_id', 'title_keywords']}
                    if update_task_in_db(target_task['task_id'], user_id, updates):
                        response_message = f"Task '{target_task['title']}' updated successfully."
                    else:
                        response_message = f"Failed to update task '{target_task['title']}'. No changes applied or task not found."
                else:
                    response_message = "Task not found."
            tasks_result = get_all_tasks_for_user(user_id) # Refresh list

        elif action_type == "delete_task":
            task_id_or_keywords = parsed_action.get('task_id') or parsed_action.get('title_keywords')
            if not task_id_or_keywords:
                response_message = "Please provide a Task ID or keywords from its title to delete."
            else:
                target_task = None
                if parsed_action.get('task_id'):
                    target_task = get_task_by_id(user_id, parsed_action['task_id'])
                elif parsed_action.get('title_keywords'):
                    all_tasks = get_all_tasks_for_user(user_id)
                    matching_tasks = [t for t in all_tasks if parsed_action['title_keywords'].lower() in t['title'].lower()]
                    if len(matching_tasks) == 1:
                        target_task = matching_tasks[0]
                    elif len(matching_tasks) > 1:
                        response_message = "Multiple tasks match your description. Please be more specific or provide the Task ID."
                        return response_message, [], [], []

                if target_task:
                    if delete_task_from_db(target_task['task_id'], user_id):
                        response_message = f"Task '{target_task['title']}' deleted successfully."
                    else:
                        response_message = f"Failed to delete task '{target_task['title']}'. Task not found."
                else:
                    response_message = "Task not found."
            tasks_result = get_all_tasks_for_user(user_id) # Refresh list

        elif action_type == "create_event":
            event_obj = add_event_to_db(
                user_id=user_id,
                title=parsed_action.get('title'),
                start_datetime=parsed_action.get('start_datetime'),
                description=parsed_action.get('description'),
                end_datetime=parsed_action.get('end_datetime'),
                location=parsed_action.get('location'),
                attendees=parsed_action.get('attendees')
            )
            if event_obj:
                response_message = f"Event '{event_obj['title']}' created successfully (ID: {event_obj['event_id']})."
            else:
                response_message = "Failed to create event."
            events_result = get_all_events_for_user(user_id) # Refresh list

        elif action_type == "update_event":
            event_id_or_keywords = parsed_action.get('event_id') or parsed_action.get('title_keywords')
            if not event_id_or_keywords:
                response_message = "Please provide an Event ID or keywords from its title to update."
            else:
                target_event = None
                if parsed_action.get('event_id'):
                    target_event = get_event_by_id(user_id, parsed_action['event_id'])
                elif parsed_action.get('title_keywords'):
                    all_events = get_all_events_for_user(user_id)
                    matching_events = [e for e in all_events if parsed_action['title_keywords'].lower() in e['title'].lower()]
                    if len(matching_events) == 1:
                        target_event = matching_events[0]
                    elif len(matching_events) > 1:
                        response_message = "Multiple events match your description. Please be more specific or provide the Event ID."
                        return response_message, [], [], []

                if target_event:
                    updates = {k: v for k, v in parsed_action.items() if k not in ['action', 'event_id', 'title_keywords']}
                    if update_event_in_db(target_event['event_id'], user_id, updates):
                        response_message = f"Event '{target_event['title']}' updated successfully."
                    else:
                        response_message = f"Failed to update event '{target_event['title']}'. No changes applied or event not found."
                else:
                    response_message = "Event not found."
            events_result = get_all_events_for_user(user_id) # Refresh list

        elif action_type == "delete_event":
            event_id_or_keywords = parsed_action.get('event_id') or parsed_action.get('title_keywords')
            if not event_id_or_keywords:
                response_message = "Please provide an Event ID or keywords from its title to delete."
            else:
                target_event = None
                if parsed_action.get('event_id'):
                    target_event = get_event_by_id(user_id, parsed_action['event_id'])
                elif parsed_action.get('title_keywords'):
                    all_events = get_all_events_for_user(user_id)
                    matching_events = [e for e in all_events if parsed_action['title_keywords'].lower() in e['title'].lower()]
                    if len(matching_events) == 1:
                        target_event = matching_events[0]
                    elif len(matching_events) > 1:
                        response_message = "Multiple events match your description. Please be more specific or provide the Event ID."
                        return response_message, [], [], []

                if target_event:
                    if delete_event_from_db(target_event['event_id'], user_id):
                        response_message = f"Event '{target_event['title']}' deleted successfully."
                    else:
                        response_message = f"Failed to delete event '{target_event['title']}'. Event not found."
                else:
                    response_message = "Event not found."
            events_result = get_all_events_for_user(user_id) # Refresh list

        elif action_type == "create_course":
            course_obj = add_course_to_db(
                user_id=user_id,
                name=parsed_action.get('name'),
                description=parsed_action.get('description'),
                instructor=parsed_action.get('instructor'),
                schedule=parsed_action.get('schedule'),
                start_date=parsed_action.get('start_date'),
                end_date=parsed_action.get('end_date')
            )
            if course_obj:
                response_message = f"Course '{course_obj['name']}' created successfully (ID: {course_obj['course_id']})."
            else:
                response_message = "Failed to create course."
            courses_result = get_all_courses_for_user(user_id) # Refresh list

        elif action_type == "update_course":
            course_id_or_keywords = parsed_action.get('course_id') or parsed_action.get('name_keywords')
            if not course_id_or_keywords:
                response_message = "Please provide a Course ID or keywords from its name to update."
            else:
                target_course = None
                if parsed_action.get('course_id'):
                    target_course = get_course_by_id(user_id, parsed_action['course_id'])
                elif parsed_action.get('name_keywords'):
                    all_courses = get_all_courses_for_user(user_id)
                    matching_courses = [c for c in all_courses if parsed_action['name_keywords'].lower() in c['name'].lower()]
                    if len(matching_courses) == 1:
                        target_course = matching_courses[0]
                    elif len(matching_courses) > 1:
                        response_message = "Multiple courses match your description. Please be more specific or provide the Course ID."
                        return response_message, [], [], []
                
                if target_course:
                    updates = {k: v for k, v in parsed_action.items() if k not in ['action', 'course_id', 'name_keywords']}
                    if update_course_in_db(target_course['course_id'], user_id, updates):
                        response_message = f"Course '{target_course['name']}' updated successfully."
                    else:
                        response_message = f"Failed to update course '{target_course['name']}'. No changes applied or course not found."
                else:
                    response_message = "Course not found."
            courses_result = get_all_courses_for_user(user_id) # Refresh list

        elif action_type == "delete_course":
            course_id_or_keywords = parsed_action.get('course_id') or parsed_action.get('name_keywords')
            if not course_id_or_keywords:
                response_message = "Please provide a Course ID or keywords from its name to delete."
            else:
                target_course = None
                if parsed_action.get('course_id'):
                    target_course = get_course_by_id(user_id, parsed_action['course_id'])
                elif parsed_action.get('name_keywords'):
                    all_courses = get_all_courses_for_user(user_id)
                    matching_courses = [c for c in all_courses if parsed_action['name_keywords'].lower() in c['name'].lower()]
                    if len(matching_courses) == 1:
                        target_course = matching_courses[0]
                    elif len(matching_courses) > 1:
                        response_message = "Multiple courses match your description. Please be more specific or provide the Course ID."
                        return response_message, [], [], []

                if target_course:
                    if delete_course_from_db(target_course['course_id'], user_id):
                        response_message = f"Course '{target_course['name']}' deleted successfully."
                    else:
                        response_message = f"Failed to delete course '{target_course['name']}'. Course not found."
                else:
                    response_message = "Course not found."
            courses_result = get_all_courses_for_user(user_id) # Refresh list

        elif action_type == "retrieve_items":
            item_type = parsed_action.get('item_type', 'all')
            response_items_summary = [] # For the AI's conversational response
            
            if item_type == 'tasks' or item_type == 'all':
                tasks_result = get_all_tasks_for_user(user_id)
                # Apply filters here if needed based on parsed_action (status, priority, date_range, keywords)
                # For simplicity, returning all tasks for now, filtering logic can be added here
                if tasks_result:
                    response_items_summary.append("Tasks:")
                    for t in tasks_result:
                        status_text = f" ({t['status']})" if t['status'] != 'pending' else ''
                        due_text = f" (Due: {t['due_datetime'].split('T')[0]})" if t['due_datetime'] else ''
                        response_items_summary.append(f"- {t['title']}{due_text}{status_text}")
                else:
                    response_items_summary.append("No tasks found.")

            if item_type == 'events' or item_type == 'all':
                events_result = get_all_events_for_user(user_id)
                # Apply filters here if needed (date, date_range, keywords)
                if events_result:
                    response_items_summary.append("Events:")
                    for e in events_result:
                        start_date_text = e['start_datetime'].split('T')[0] if e['start_datetime'] else 'N/A'
                        response_items_summary.append(f"- {e['title']} (Starts: {start_date_text})")
                else:
                    response_items_summary.append("No events found.")

            if item_type == 'courses' or item_type == 'all':
                courses_result = get_all_courses_for_user(user_id)
                # Apply filters here if needed (keywords, instructor)
                if courses_result:
                    response_items_summary.append("Courses:")
                    for c in courses_result:
                        response_items_summary.append(f"- {c['name']} (Instructor: {c['instructor'] or 'N/A'})")
                else:
                    response_items_summary.append("No courses found.")

            response_message = "\n".join(response_items_summary)
            if not response_message:
                response_message = "I couldn't find any items matching your criteria."

        elif action_type == "respond_conversation":
            response_message = parsed_action.get('response_text', "I'm not sure how to respond to that.")
        
        else:
            response_message = "I'm not sure how to process that request. Can you try rephrasing or asking for a task, event, or course related action?"

    except APIError as e:
        response_message = f"Error: {e.message}"
    except Exception as e:
        print(f"Unexpected error in process_ai_action: {e}")
        response_message = "An internal error occurred while processing your request. Please try again."

    return response_message, tasks_result, events_result, courses_result

# --- Flask Routes ---

@app.route('/')
def home():
    return jsonify({"message": "KairoSync AI Assistant Backend. Access API endpoints like /tasks, /events, /courses, /chat."})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message')
    user_id = data.get('user_id')
    kairo_style = data.get('kairo_style', 'friendly')

    if not user_message or not user_id:
        raise APIError("User ID and message are required.", 400)

    db = get_db()
    # Fetch recent conversation history from DB
    cursor = db.execute(
        "SELECT sender, message, parsed_action FROM conversation_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10",
        (user_id,) # Limit to last 10 entries for context
    )
    # Reconstruct messages list for Ollama, keeping roles
    conversation_history_list = []
    for row in cursor.fetchall():
        conversation_history_list.append({"role": row['sender'], "content": row['message']})
        # Optionally, you could also add the AI's parsed_action to the history if it helps context for the LLM
        # if row['parsed_action']:
        #     try:
        #         parsed_action_from_history = json.loads(row['parsed_action'])
        #         conversation_history_list.append({"role": "assistant", "content": f"Action taken: {parsed_action_from_history.get('action')}"})
        #     except:
        #         pass


    ai_response_message = ""
    tasks_data = []
    events_data = []
    courses_data = []
    parsed_action = None # Initialize parsed_action to None

    try:
        # Attempt to parse action directly from the prompt
        # Send the full history including current message for action parsing
        parsed_action = parse_ai_action(user_message, conversation_history_list)
        
        # If an action is parsed, get a confirmation message from process_ai_action
        ai_response_message, tasks_data, events_data, courses_data = process_ai_action(user_id, parsed_action)

    except APIError as e:
        ai_response_message = f"Error processing request: {e.message}"
    except Exception as e:
        print(f"Error during AI interaction: {e}")
        ai_response_message = "I encountered an unexpected error while processing your request. Please try again."

    # Apply Kairo style formatting to the final response message
    if kairo_style == 'professional':
        ai_response_message = f"Acknowledged. {ai_response_message}"
    elif kairo_style == 'friendly':
        ai_response_message = f"Hey there! {ai_response_message}"
    elif kairo_style == 'concise':
        ai_response_message = f"Kairo: {ai_response_message}"
    elif kairo_style == 'casual':
        ai_response_message = f"Sup! {ai_response_message}"
    # Default is no prefix

    # Log user and Kairo responses (and parsed action)
    # Only log user message once it's processed and before Kairo responds
    # The actual message that was sent to Kairo for processing was part of `conversation_history_list`
    # Here we log the user's initial message and Kairo's final response for the conversation history table.
    db.execute(
        "INSERT INTO conversation_history (user_id, sender, message, parsed_action) VALUES (?, ?, ?, ?)",
        (user_id, 'user', user_message, None) 
    )
    db.execute(
        "INSERT INTO conversation_history (user_id, sender, message, parsed_action) VALUES (?, ?, ?, ?)",
        (user_id, 'kairo', ai_response_message, json.dumps(parsed_action) if parsed_action else None)
    )
    db.commit()

    return jsonify({
        "response": ai_response_message,
        "tasks": tasks_data,
        "events": events_data,
        "courses": courses_data,
        "parsed_action": parsed_action # Send parsed_action back to frontend for potential debugging
    })

# --- API Endpoints for Frontend CRUD (Direct Operations) ---

@app.route('/tasks', methods=['GET'])
def get_tasks_route():
    user_id = request.args.get('user_id')
    if not user_id:
        raise APIError("User ID is required.", 400)
    tasks = get_all_tasks_for_user(user_id)
    return jsonify({"tasks": tasks})

@app.route('/tasks', methods=['POST'])
def add_task_route():
    data = request.get_json()
    user_id = data.get('user_id')
    title = data.get('title')
    if not user_id or not title:
        raise APIError("User ID and task title are required.", 400)
    
    task = add_task_to_db(
        user_id=user_id,
        title=title,
        description=data.get('description'),
        due_datetime=data.get('due_datetime'),
        priority=data.get('priority'),
        status=data.get('status'),
        tags=data.get('tags'),
        course_id=data.get('course_id'),
        parent_id=data.get('parent_id')
    )
    return jsonify({"message": "Task added successfully", "task": task}), 201

@app.route('/tasks/<task_id>', methods=['PUT'])
def update_task_route(task_id):
    data = request.get_json()
    user_id = request.args.get('user_id') 
    if not user_id:
        raise APIError("User ID is required.", 400)
    
    if update_task_in_db(task_id, user_id, data):
        return jsonify({"message": "Task updated successfully"})
    else:
        return jsonify({"error": "Task not found or no changes made."}), 404

@app.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task_route(task_id):
    user_id = request.args.get('user_id') 
    if not user_id:
        raise APIError("User ID is required.", 400)
    
    if delete_task_from_db(task_id, user_id):
        return jsonify({"message": "Task deleted successfully"})
    else:
        return jsonify({"error": "Task not found."}), 404

@app.route('/events', methods=['GET'])
def get_events_route():
    user_id = request.args.get('user_id')
    if not user_id:
        raise APIError("User ID is required.", 400)
    events = get_all_events_for_user(user_id)
    return jsonify({"events": events})

@app.route('/events', methods=['POST'])
def add_event_route():
    data = request.get_json()
    user_id = data.get('user_id')
    title = data.get('title')
    start_datetime = data.get('start_datetime')
    if not user_id or not title or not start_datetime:
        raise APIError("User ID, event title, and start date/time are required.", 400)
    
    event = add_event_to_db(
        user_id=user_id,
        title=title,
        description=data.get('description'),
        start_datetime=start_datetime,
        end_datetime=data.get('end_datetime'),
        location=data.get('location'),
        attendees=data.get('attendees')
    )
    return jsonify({"message": "Event added successfully", "event": event}), 201

@app.route('/events/<event_id>', methods=['PUT'])
def update_event_route(event_id):
    data = request.get_json()
    user_id = request.args.get('user_id')
    if not user_id:
        raise APIError("User ID is required.", 400)
    
    if update_event_in_db(event_id, user_id, data):
        return jsonify({"message": "Event updated successfully"})
    else:
        return jsonify({"error": "Event not found or no changes made."}), 404

@app.route('/events/<event_id>', methods=['DELETE'])
def delete_event_route(event_id):
    user_id = request.args.get('user_id')
    if not user_id:
        raise APIError("User ID is required.", 400)
    
    if delete_event_from_db(event_id, user_id):
        return jsonify({"message": "Event deleted successfully"})
    else:
        return jsonify({"error": "Event not found."}), 404

@app.route('/courses', methods=['GET'])
def get_courses_route():
    user_id = request.args.get('user_id')
    if not user_id:
        raise APIError("User ID is required.", 400)
    courses = get_all_courses_for_user(user_id)
    return jsonify({"courses": courses})

@app.route('/courses', methods=['POST'])
def add_course_route():
    data = request.get_json()
    user_id = data.get('user_id')
    name = data.get('name')
    if not user_id or not name:
        raise APIError("User ID and course name are required.", 400)
    
    course = add_course_to_db(
        user_id=user_id,
        name=name,
        description=data.get('description'),
        instructor=data.get('instructor'),
        schedule=data.get('schedule'),
        start_date=data.get('start_date'),
        end_date=data.get('end_date')
    )
    return jsonify({"message": "Course added successfully", "course": course}), 201

@app.route('/courses/<course_id>', methods=['PUT'])
def update_course_route(course_id):
    data = request.get_json()
    user_id = request.args.get('user_id')
    if not user_id:
        raise APIError("User ID is required.", 400)
    
    if update_course_in_db(course_id, user_id, data):
        return jsonify({"message": "Course updated successfully"})
    else:
        return jsonify({"error": "Course not found or no changes made."}), 404

@app.route('/courses/<course_id>', methods=['DELETE'])
def delete_course_route(course_id):
    user_id = request.args.get('user_id')
    if not user_id:
        raise APIError("User ID is required.", 400)
    
    if delete_course_from_db(course_id, user_id):
        return jsonify({"message": "Course deleted successfully"})
    else:
        return jsonify({"error": "Course not found."}), 404

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
def internal_server_error(error):
    # Log the full traceback for debugging server-side issues
    app.logger.error(f"Internal Server Error: {error}", exc_info=True)
    return jsonify({"error": "Internal Server Error"}), 500


if __name__ == '__main__':
    # When running directly, ensure database is set up
    with app.app_context():
        setup_database() # This will create or update tables on start
    app.run(debug=True, port=5000) # debug=True will restart server on code changes and show more info
