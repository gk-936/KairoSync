# new_database.py
import sqlite3
import os

DATABASE_PATH = 'kairo_data.db'
_db_connection = None

def get_db_connection():
    global _db_connection
    if _db_connection is None:
        _db_connection = sqlite3.connect(DATABASE_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        _db_connection.row_factory = sqlite3.Row
    return _db_connection

def close_db_connection(e=None):
    global _db_connection
    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            due_datetime TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            tags TEXT,
            course_id TEXT,
            parent_id TEXT,
            is_archived BOOLEAN DEFAULT 0,
            archived_at TEXT,
            status_change_timestamp TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            scheduled_start TEXT,
            scheduled_end TEXT
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            start_datetime TEXT NOT NULL,
            end_datetime TEXT,
            location TEXT,
            attendees TEXT,
            is_archived BOOLEAN DEFAULT 0,
            archived_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            course_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            instructor TEXT,
            schedule TEXT,
            start_date TEXT,
            end_date TEXT,
            is_archived BOOLEAN DEFAULT 0,
            archived_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            note_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT,
            linked_item_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            reminder_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            message TEXT NOT NULL,
            trigger_time TEXT NOT NULL,
            item_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            parsed_action TEXT,
            context_flags TEXT
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY,
            completed_task_archive_duration INTEGER DEFAULT 30,
            theme TEXT DEFAULT 'dark',
            kairo_style TEXT DEFAULT 'professional',
            notification_preferences TEXT DEFAULT 'all',
            working_hours_start TEXT DEFAULT '08:00',
            working_hours_end TEXT DEFAULT '18:00',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # Adaptive learning tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_profile (
            user_id TEXT PRIMARY KEY,
            productivity_patterns TEXT,
            task_completion_stats TEXT,
            preferred_schedule TEXT,
            learning_style TEXT,
            knowledge_gaps TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interaction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            interaction_type TEXT NOT NULL,
            interaction_detail TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            outcome TEXT
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_model (
            user_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            proficiency REAL DEFAULT 0.0,
            last_reviewed TEXT,
            next_review TEXT,
            PRIMARY KEY (user_id, topic)
        );
    ''')

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(user_id)")

    conn.commit()
    print("Database initialized successfully.")

if __name__ == '__main__':
    # For testing purposes, you can run this script directly
    # to initialize the database.
    print(f"Creating/Initializing database at: {os.path.abspath(DATABASE_PATH)}")
    init_db()
    print("Database schema should be up to date.")
    # Example of closing the connection if you were testing get_db_connection
    # conn = get_db_connection()
    # print(conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall())
    # close_db_connection()
