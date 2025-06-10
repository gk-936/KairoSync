# new_database_user_dir.py
import sqlite3
import os
from pathlib import Path # Added

# --- Database Path Configuration ---
APP_NAME = "KairoApp"
try:
    # Standard app data directory per OS
    if os.name == 'win32': # Windows
        user_data_dir = Path(os.getenv('APPDATA', Path.home() / 'AppData' / 'Local')) / APP_NAME
    elif os.name == 'darwin': # macOS
        user_data_dir = Path.home() / 'Library' / 'Application Support' / APP_NAME
    else: # Linux and other Unix-like
        user_data_dir = Path(os.getenv('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / APP_NAME
except Exception:
    # Fallback if standard paths are problematic (e.g., restricted environment)
    user_data_dir = Path.home() / f".{APP_NAME.lower()}_data" # e.g., ~/.kairoapp_data

user_data_dir.mkdir(parents=True, exist_ok=True) # Ensure directory exists
DATABASE_PATH = user_data_dir / 'kairo_data.db'
# print(f"Database path set to: {DATABASE_PATH}") # For debugging
# --- End Database Path Configuration ---

_db_connection = None

def get_db_connection():
    global _db_connection
    if _db_connection is None:
        try:
            # Ensure parent directory of DATABASE_PATH exists, as it's now in user_data_dir
            # This check is redundant if user_data_dir.mkdir is successful above, but good for safety.
            DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _db_connection = sqlite3.connect(DATABASE_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
            _db_connection.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            print(f"Error connecting to database at {DATABASE_PATH}: {e}")
            # In a GUI app, you might want to show this error to the user
            # For now, re-raising allows the app to halt if DB is critical
            raise
    return _db_connection

def close_db_connection(e=None):
    global _db_connection
    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None

def init_db():
    # No need to pass app or config, DATABASE_PATH is now globally defined and user-specific
    conn = get_db_connection() # This will create the DB file if it doesn't exist in the new path
    cursor = conn.cursor()

    # Schema definition ( 그대로 유지 )
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, description TEXT,
            due_datetime TEXT, priority TEXT DEFAULT 'medium', status TEXT DEFAULT 'pending',
            tags TEXT, course_id TEXT, parent_id TEXT, is_archived BOOLEAN DEFAULT 0,
            archived_at TEXT, status_change_timestamp TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP, scheduled_start TEXT, scheduled_end TEXT
        );''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, description TEXT,
            start_datetime TEXT NOT NULL, end_datetime TEXT, location TEXT, attendees TEXT,
            is_archived BOOLEAN DEFAULT 0, archived_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            course_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, description TEXT,
            instructor TEXT, schedule TEXT, start_date TEXT, end_date TEXT, is_archived BOOLEAN DEFAULT 0,
            archived_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            note_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
            tags TEXT, linked_item_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            reminder_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, message TEXT NOT NULL,
            trigger_time TEXT NOT NULL, item_id TEXT, status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, sender TEXT NOT NULL,
            message TEXT NOT NULL, timestamp TEXT DEFAULT CURRENT_TIMESTAMP, parsed_action TEXT,
            context_flags TEXT
        );''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY, completed_task_archive_duration INTEGER DEFAULT 30,
            theme TEXT DEFAULT 'dark', kairo_style TEXT DEFAULT 'professional',
            notification_preferences TEXT DEFAULT 'all', working_hours_start TEXT DEFAULT '08:00',
            working_hours_end TEXT DEFAULT '18:00', updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_profile (
            user_id TEXT PRIMARY KEY, productivity_patterns TEXT, task_completion_stats TEXT,
            preferred_schedule TEXT, learning_style TEXT, knowledge_gaps TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interaction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, interaction_type TEXT NOT NULL,
            interaction_detail TEXT NOT NULL, timestamp TEXT DEFAULT CURRENT_TIMESTAMP, outcome TEXT
        );''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_model (
            user_id TEXT NOT NULL, topic TEXT NOT NULL, proficiency REAL DEFAULT 0.0,
            last_reviewed TEXT, next_review TEXT, PRIMARY KEY (user_id, topic)
        );''')

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(user_id)")

    conn.commit()
    # print(f"Database initialized successfully at {DATABASE_PATH}") # For debugging

if __name__ == '__main__':
    print(f"Attempting to initialize database at: {DATABASE_PATH}")
    # To ensure a clean test, you might want to manually delete the DB file
    # if os.path.exists(DATABASE_PATH):
    #     os.remove(DATABASE_PATH)
    #     print(f"Removed existing database at {DATABASE_PATH} for fresh initialization.")
    init_db()

    # Test connection and basic operation
    conn_test = None
    try:
        conn_test = get_db_connection()
        print(f"Successfully connected to the database at {DATABASE_PATH}.")
        test_cursor = conn_test.cursor()
        test_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks';")
        result = test_cursor.fetchone()
        if result: print(f"Table 'tasks' found: {result[0]}")
        else: print("Table 'tasks' NOT found post-initialization.")
    except Exception as e:
        print(f"Error during database test: {e}")
    finally:
        if conn_test: # Ensure close_db_connection uses the global _db_connection
            close_db_connection()
            print("Database connection closed after test.")
    print("If 'Database initialized successfully.' and 'Table 'tasks' found' messages appeared, init_db worked.")
