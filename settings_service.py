# settings_service_with_logging.py
import database
import datetime
import json
import logging

logger = logging.getLogger(__name__)

class SettingsService:
    DEFAULT_SETTINGS = {
        "completed_task_archive_duration": 30,
        "theme": "dark",
        "kairo_style": "professional",
        "notification_preferences": {"email": True, "in_app": True},
        "working_hours_start": "09:00",
        "working_hours_end": "17:00",
        "user_id": None
    }

    @staticmethod
    def get_user_settings(user_id):
        try:
            db = database.get_db_connection()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
            settings_row = cursor.fetchone()

            if settings_row:
                settings = dict(settings_row)
                if 'notification_preferences' in settings and isinstance(settings['notification_preferences'], str):
                    try:
                        settings['notification_preferences'] = json.loads(settings['notification_preferences'])
                    except json.JSONDecodeError as je:
                        logger.warning(f"Corrupted JSON in notification_preferences for user {user_id}: {str(je)}. Falling back to default.")
                        settings['notification_preferences'] = SettingsService.DEFAULT_SETTINGS['notification_preferences']
                return settings
            else:
                logger.info(f"No settings found for user {user_id}, returning defaults.")
                defaults_with_id = SettingsService.DEFAULT_SETTINGS.copy()
                defaults_with_id["user_id"] = user_id
                return defaults_with_id
        except Exception as e:
            logger.error(f"Database error in get_user_settings for user {user_id}: {str(e)}", exc_info=True)
            # Return defaults on any error to ensure app continues with a valid settings structure
            defaults_with_id_on_error = SettingsService.DEFAULT_SETTINGS.copy()
            defaults_with_id_on_error["user_id"] = user_id
            return defaults_with_id_on_error


    @staticmethod
    def update_user_settings(user_id, settings_data_dict):
        try:
            db = database.get_db_connection()
            cursor = db.cursor()
            settings_data_dict["user_id"] = user_id # Ensure user_id is present
            settings_data_dict["updated_at"] = datetime.datetime.now().isoformat()

            if 'notification_preferences' in settings_data_dict and \
               isinstance(settings_data_dict['notification_preferences'], dict):
                settings_data_dict['notification_preferences'] = json.dumps(settings_data_dict['notification_preferences'])

            cursor.execute("SELECT user_id FROM user_settings WHERE user_id = ?", (user_id,))
            existing_user = cursor.fetchone()

            if existing_user:
                set_clause_parts = []
                values = []
                for key, value in settings_data_dict.items():
                    if key != "user_id": # user_id is for WHERE clause, not SET
                        set_clause_parts.append(f"{key} = ?")
                        values.append(value)
                values.append(user_id) # For WHERE user_id = ?

                if not set_clause_parts: # Should not happen if updated_at is always set
                    logger.warning(f"No fields to update for user {user_id} in update_user_settings.")
                    return True # Or False, depending on desired behavior for no-op update

                set_clause = ", ".join(set_clause_parts)
                query = f"UPDATE user_settings SET {set_clause} WHERE user_id = ?"
                cursor.execute(query, tuple(values))
                logger.info(f"Settings updated for user {user_id}.")
            else:
                final_insert_data = SettingsService.DEFAULT_SETTINGS.copy()
                final_insert_data.update(settings_data_dict)
                final_insert_data["user_id"] = user_id # Ensure it's the correct user_id
                final_insert_data["updated_at"] = settings_data_dict["updated_at"]
                if 'notification_preferences' in final_insert_data and \
                   isinstance(final_insert_data['notification_preferences'], dict):
                    final_insert_data['notification_preferences'] = json.dumps(final_insert_data['notification_preferences'])

                columns = ", ".join(final_insert_data.keys())
                placeholders = ", ".join(["?"] * len(final_insert_data))
                values = list(final_insert_data.values())
                query = f"INSERT INTO user_settings ({columns}) VALUES ({placeholders})"
                cursor.execute(query, tuple(values))
                logger.info(f"Settings inserted for new user {user_id}.")

            db.commit()
            return True
        except Exception as e:
            logger.error(f"Database error in update_user_settings for user {user_id}: {str(e)}", exc_info=True)
            try:
                db.rollback()
            except Exception as rb_e: # If rollback itself fails (e.g., connection closed)
                logger.error(f"Rollback failed in update_user_settings for user {user_id}: {str(rb_e)}", exc_info=True)
            return False
