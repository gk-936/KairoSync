# settings_service.py
import database
import datetime
import json # For notification_preferences if stored as JSON

class SettingsService:
    DEFAULT_SETTINGS = {
        "completed_task_archive_duration": 30,
        "theme": "dark",
        "kairo_style": "professional",
        "notification_preferences": {"email": True, "in_app": True}, # Example structure
        "working_hours_start": "09:00",
        "working_hours_end": "17:00",
        "user_id": None # This will be set when creating new
    }

    @staticmethod
    def get_user_settings(user_id):
        db = database.get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
        settings_row = cursor.fetchone()

        if settings_row:
            settings = dict(settings_row)
            # Deserialize JSON fields if necessary
            if 'notification_preferences' in settings and isinstance(settings['notification_preferences'], str):
                try:
                    settings['notification_preferences'] = json.loads(settings['notification_preferences'])
                except json.JSONDecodeError:
                    # Fallback to default if JSON is corrupted or not as expected
                    settings['notification_preferences'] = SettingsService.DEFAULT_SETTINGS['notification_preferences']
            return settings
        else:
            # Return a copy of default settings with the current user_id
            defaults_with_id = SettingsService.DEFAULT_SETTINGS.copy()
            defaults_with_id["user_id"] = user_id
            return defaults_with_id

    @staticmethod
    def update_user_settings(user_id, settings_data_dict):
        db = database.get_db_connection()
        cursor = db.cursor()

        # Ensure user_id is part of the settings data, primarily for INSERT
        settings_data_dict["user_id"] = user_id
        settings_data_dict["updated_at"] = datetime.datetime.now().isoformat()

        # Serialize complex types like notification_preferences to JSON string for DB
        if 'notification_preferences' in settings_data_dict and \
           isinstance(settings_data_dict['notification_preferences'], dict):
            settings_data_dict['notification_preferences'] = json.dumps(settings_data_dict['notification_preferences'])


        # Check if settings for user_id exist to decide between INSERT and UPDATE
        cursor.execute("SELECT user_id FROM user_settings WHERE user_id = ?", (user_id,))
        existing_user = cursor.fetchone()

        try:
            if existing_user:
                # UPDATE existing settings
                set_clause = ", ".join([f"{key} = ?" for key in settings_data_dict if key != "user_id"])
                values = [settings_data_dict[key] for key in settings_data_dict if key != "user_id"]
                values.append(user_id) # For the WHERE clause

                query = f"UPDATE user_settings SET {set_clause} WHERE user_id = ?"
                cursor.execute(query, tuple(values))
            else:
                # INSERT new settings
                # Ensure all default fields are present if inserting for the first time
                # This helps maintain a consistent table structure if some fields are optional in settings_data_dict

                # Start with a full set of default values
                final_insert_data = SettingsService.DEFAULT_SETTINGS.copy()
                final_insert_data.update(settings_data_dict) # Override defaults with provided values

                # Ensure user_id is correctly set from the argument
                final_insert_data["user_id"] = user_id
                final_insert_data["updated_at"] = settings_data_dict["updated_at"] # Use the already set timestamp

                # Re-serialize notification_preferences if it was part of final_insert_data and is a dict
                if 'notification_preferences' in final_insert_data and \
                   isinstance(final_insert_data['notification_preferences'], dict):
                    final_insert_data['notification_preferences'] = json.dumps(final_insert_data['notification_preferences'])


                columns = ", ".join(final_insert_data.keys())
                placeholders = ", ".join(["?"] * len(final_insert_data))
                values = list(final_insert_data.values())

                query = f"INSERT INTO user_settings ({columns}) VALUES ({placeholders})"
                cursor.execute(query, tuple(values))

            db.commit()
            return True
        except Exception as e:
            print(f"Error updating/inserting user settings: {e}")
            db.rollback() # Rollback on error
            return False
