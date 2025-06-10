# database_with_logging.py
import sqlite3
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# --- Database Path Configuration ---
APP_NAME = "KairoApp"
try:
    if os.name == 'win32':
        user_data_dir = Path(os.getenv('APPDATA', Path.home() / 'AppData' / 'Local')) / APP_NAME
    elif os.name == 'darwin':
        user_data_dir = Path.home() / 'Library' / 'Application Support' / APP_NAME
    else:
        user_data_dir = Path(os.getenv('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / APP_NAME
    user_data_dir.mkdir(parents=True, exist_ok=True)
    DATABASE_PATH = user_data_dir / 'kairo_data.db'
    logger.info(f"Database path set to: {DATABASE_PATH}")
except Exception as e:
    # Fallback if standard paths are problematic (e.g., restricted environment)
    user_data_dir = Path.home() / f".{APP_NAME.lower()}_data"
    try:
        user_data_dir.mkdir(parents=True, exist_ok=True)
        DATABASE_PATH = user_data_dir / 'kairo_data.db'
        logger.warning(f"Standard user data directory failed: {e}. Using fallback: {DATABASE_PATH}", exc_info=True)
    except Exception as fallback_e:
        # If even fallback fails, this is critical. Log and perhaps use in-memory or local to script.
        DATABASE_PATH = Path(f"{APP_NAME.lower()}_local_fallback.db")
        logger.critical(f"Fallback user data directory failed: {fallback_e}. Using local script directory: {DATABASE_PATH}", exc_info=True)

# --- End Database Path Configuration ---

_db_connection = None

def get_db_connection():
    global _db_connection
    if _db_connection is None:
        try:
            # Ensure parent directory of DATABASE_PATH exists
            DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _db_connection = sqlite3.connect(DATABASE_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
            _db_connection.row_factory = sqlite3.Row
            logger.info(f"Database connection established to {DATABASE_PATH}")
        except sqlite3.Error as e:
            logger.critical(f"Critical error connecting to database at {DATABASE_PATH}: {e}", exc_info=True)
            raise # Re-raise to signal critical failure to the application
    return _db_connection

def close_db_connection(e=None): # Parameter e is conventional for some contexts like atexit
    global _db_connection
    if _db_connection is not None:
        try:
            _db_connection.close()
            _db_connection = None
            logger.info(f"Database connection to {DATABASE_PATH} closed.")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}", exc_info=True)

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        logger.info(f"Initializing database schema at {DATABASE_PATH}...")

        # Schema definition ( 그대로 유지 - kept as is, assuming it's correct )
        # Each execute should ideally be in its own try-except if granular error reporting is needed
        # For now, one block for schema creation.
        cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, description TEXT, due_datetime TEXT, priority TEXT DEFAULT 'medium', status TEXT DEFAULT 'pending', tags TEXT, course_id TEXT, parent_id TEXT, is_archived BOOLEAN DEFAULT 0, archived_at TEXT, status_change_timestamp TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, scheduled_start TEXT, scheduled_end TEXT );''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, description TEXT,start_datetime TEXT NOT NULL, end_datetime TEXT, location TEXT, attendees TEXT,is_archived BOOLEAN DEFAULT 0, archived_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS courses (course_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, description TEXT,instructor TEXT, schedule TEXT, start_date TEXT, end_date TEXT, is_archived BOOLEAN DEFAULT 0,archived_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS notes (note_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,tags TEXT, linked_item_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS reminders (reminder_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, message TEXT NOT NULL,trigger_time TEXT NOT NULL, item_id TEXT, status TEXT DEFAULT 'pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS conversation_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, sender TEXT NOT NULL,message TEXT NOT NULL, timestamp TEXT DEFAULT CURRENT_TIMESTAMP, parsed_action TEXT,context_flags TEXT);''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS user_settings (user_id TEXT PRIMARY KEY, completed_task_archive_duration INTEGER DEFAULT 30,theme TEXT DEFAULT 'dark', kairo_style TEXT DEFAULT 'professional',notification_preferences TEXT DEFAULT 'all', working_hours_start TEXT DEFAULT '08:00',working_hours_end TEXT DEFAULT '18:00', updated_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS learning_profile (user_id TEXT PRIMARY KEY, productivity_patterns TEXT, task_completion_stats TEXT,preferred_schedule TEXT, learning_style TEXT, knowledge_gaps TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS interaction_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, interaction_type TEXT NOT NULL,interaction_detail TEXT NOT NULL, timestamp TEXT DEFAULT CURRENT_TIMESTAMP, outcome TEXT);''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS knowledge_model (user_id TEXT NOT NULL, topic TEXT NOT NULL, proficiency REAL DEFAULT 0.0,last_reviewed TEXT, next_review TEXT, PRIMARY KEY (user_id, topic));''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(user_id)")
        conn.commit()
        logger.info(f"Database schema initialized/verified successfully at {DATABASE_PATH}")
    except sqlite3.Error as e:
        logger.critical(f"SQLite error during database initialization at {DATABASE_PATH}: {e}", exc_info=True)
        # Depending on app design, might re-raise or try to handle (e.g. backup/restore)
        raise # Critical for app startup
    except Exception as e:
        logger.critical(f"Unexpected error during database initialization at {DATABASE_PATH}: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    # Basic logging for __main__ execution for testing purposes
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
    logger.info(f"Attempting to initialize database directly via __main__ at: {DATABASE_PATH}")

    # Optional: Clean up for testing
    # if os.path.exists(DATABASE_PATH):
    #     try:
    #         os.remove(DATABASE_PATH)
    #         logger.info(f"Removed existing database at {DATABASE_PATH} for fresh __main__ initialization.")
    #     except OSError as e:
    #         logger.error(f"Error removing existing database for test: {e}", exc_info=True)

    init_db()

    conn_test = None
    try:
        conn_test = get_db_connection()
        logger.info(f"Successfully connected to the database via __main__ at {DATABASE_PATH}.")
        test_cursor = conn_test.cursor()
        test_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks';")
        result = test_cursor.fetchone()
        if result: logger.info(f"Table 'tasks' found: {result[0]}")
        else: logger.warning("Table 'tasks' NOT found post-__main__ initialization.")
    except Exception as e:
        logger.error(f"Error during __main__ database test: {e}", exc_info=True)
    finally:
        if conn_test:
            close_db_connection()
            logger.info("Database connection closed after __main__ test.")
    logger.info("If 'Database initialized successfully.' and 'Table 'tasks' found' messages appeared, init_db from __main__ worked.")
