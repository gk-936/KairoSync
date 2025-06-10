import datetime
import json
from collections import defaultdict
import database # Changed
from utils import format_timestamp, generate_id # Removed parse_flexible_datetime as it's not used
from adaptive_learning import AdaptiveLearner

class SchedulingService:
    def __init__(self, user_id):
        self.user_id = user_id
        self.db = database.get_db_connection() # Changed
        self.learner = AdaptiveLearner(user_id) # Assuming AdaptiveLearner is independent of Flask

    def schedule_multiple_tasks(self, tasks_list_of_dicts, strategy="priority_based"):
        """
        Schedule multiple tasks at once with intelligent allocation.
        tasks_list_of_dicts: A list of task dictionaries. Each dict should have at least 'title',
                             and optionally 'priority', 'duration' (in minutes), and 'task_id'.
        Strategies:
          - priority_based: Schedule high priority first
        """
        if not tasks_list_of_dicts:
            return []

        existing_events = self.get_upcoming_events()
        scheduled_tasks_output = []

        working_hours = self.get_working_hours()
        peak_hours = [] # Default
        if hasattr(self.learner, 'profile') and self.learner.profile and \
           'productivity_patterns' in self.learner.profile and \
           isinstance(self.learner.profile['productivity_patterns'], dict):
            peak_hours = self.learner.profile['productivity_patterns'].get('peak_hours', [])

        processed_tasks = []
        for task_dict in tasks_list_of_dicts:
            current_task = task_dict.copy()
            if 'duration' not in current_task or not current_task['duration']:
                current_task['duration'] = self.estimate_task_duration(current_task)
            processed_tasks.append(current_task)

        # Currently, only priority_based is implemented for simplicity
        if strategy == "priority_based":
            scheduled_tasks_output = self._priority_based_scheduling_logic(processed_tasks, existing_events, working_hours, peak_hours)
        else:
            # Fallback to priority_based if other strategies aren't implemented
            scheduled_tasks_output = self._priority_based_scheduling_logic(processed_tasks, existing_events, working_hours, peak_hours)

        final_scheduled_info = []
        for task_info in scheduled_tasks_output:
            if 'task_id' in task_info and task_info.get('scheduled_start') and task_info.get('scheduled_end'):
                 updated_task_info = self.update_task_schedule_in_db(
                    task_info['task_id'],
                    task_info.get('scheduled_start'),
                    task_info.get('scheduled_end')
                )
                 if updated_task_info:
                    final_scheduled_info.append(updated_task_info)
            else:
                print(f"Skipping task update for {task_info.get('title')} due to missing ID or schedule times.")

        return final_scheduled_info

    def get_upcoming_events(self):
        now = datetime.datetime.now().isoformat()
        seven_days_later = (datetime.datetime.now() + datetime.timedelta(days=7)).isoformat()
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM events WHERE user_id = ? AND start_datetime BETWEEN ? AND ? "
            "AND (is_archived = 0 OR is_archived IS NULL) ORDER BY start_datetime", # Ensure is_archived is handled
            (self.user_id, now, seven_days_later)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_working_hours(self):
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT working_hours_start, working_hours_end FROM user_settings WHERE user_id = ?",
            (self.user_id,)
        )
        settings = cursor.fetchone()
        if settings and settings['working_hours_start'] and settings['working_hours_end']:
            return {"start": settings['working_hours_start'], "end": settings['working_hours_end']}
        return {"start": "09:00", "end": "17:00"} # Default working hours

    def estimate_task_duration(self, task_dict):
        cursor = self.db.cursor()
        # Using status_change_timestamp as completed_at as per previous discussion
        cursor.execute(
            "SELECT AVG((julianday(status_change_timestamp) - julianday(created_at)) * 24 * 60) AS avg_duration "
            "FROM tasks WHERE user_id = ? AND title LIKE ? AND status = 'completed' AND status_change_timestamp IS NOT NULL AND created_at IS NOT NULL",
            (self.user_id, f"%{task_dict.get('title', 'Default Title')}%") # Use get with default for safety
        )
        result = cursor.fetchone()
        if result and result['avg_duration'] and result['avg_duration'] > 0 :
            return int(result['avg_duration'])
        priority = task_dict.get('priority', 'medium')
        return {'high': 60, 'medium': 90, 'low': 120}.get(priority, 90) # Adjusted defaults

    def _priority_based_scheduling_logic(self, tasks, existing_events, working_hours, peak_hours):
        # Sort tasks by priority: high (0), medium (1), low (2)
        tasks.sort(key=lambda t: {'high': 0, 'medium': 1, 'low': 2}.get(t.get('priority', 'medium'), 1))

        scheduled_list_of_tasks = [] # This will hold task dicts with new schedule info
        current_time_marker = datetime.datetime.now() # Start searching for slots from now

        for task_to_schedule in tasks:
            task_duration = task_to_schedule.get('duration', 60)

            # Find the next available slot
            scheduled_start_time = self._find_next_available_slot(
                current_time_marker,
                task_duration,
                existing_events + scheduled_list_of_tasks, # Commitments include already scheduled tasks from this run
                working_hours,
                peak_hours # peak_hours can be an empty list if not defined
            )

            # Update task dictionary with new schedule information
            task_to_schedule['scheduled_start'] = scheduled_start_time.isoformat()
            task_to_schedule['scheduled_end'] = (scheduled_start_time + datetime.timedelta(minutes=task_duration)).isoformat()

            scheduled_list_of_tasks.append(task_to_schedule)

            # Update current_time_marker to the end of the just-scheduled task for the next iteration
            current_time_marker = scheduled_start_time + datetime.timedelta(minutes=task_duration)

        return scheduled_list_of_tasks

    def _find_next_available_slot(self, search_start_dt, duration_minutes, commitments, working_hours, peak_hours_list):
        current_search_dt = search_start_dt
        wh_start_time = datetime.datetime.strptime(working_hours['start'], "%H:%M").time()
        wh_end_time = datetime.datetime.strptime(working_hours['end'], "%H:%M").time()

        # Limit search to a reasonable future period, e.g., 14 days
        max_search_date = current_search_dt.date() + datetime.timedelta(days=14)

        while current_search_dt.date() <= max_search_date:
            # Adjust to start of working hours if current_search_dt is before them on its current day
            if current_search_dt.time() < wh_start_time:
                current_search_dt = datetime.datetime.combine(current_search_dt.date(), wh_start_time)
            # If current_search_dt is after working hours, move to start of next working day
            elif current_search_dt.time() >= wh_end_time:
                current_search_dt = datetime.datetime.combine(current_search_dt.date() + datetime.timedelta(days=1), wh_start_time)
                continue # Re-check if the new day is within max_search_date

            slot_end_dt = current_search_dt + datetime.timedelta(minutes=duration_minutes)

            # If slot ends after working hours for its day, move to start of next day
            if slot_end_dt.time() > wh_end_time or slot_end_dt.date() > current_search_dt.date():
                current_search_dt = datetime.datetime.combine(current_search_dt.date() + datetime.timedelta(days=1), wh_start_time)
                continue

            # Check for conflicts with existing commitments
            is_conflict = False
            for commitment in commitments:
                commit_start_str = commitment.get('scheduled_start') or commitment.get('start_datetime')
                commit_end_str = commitment.get('scheduled_end') or commitment.get('end_datetime')
                if not commit_start_str or not commit_end_str: continue # Skip if commitment has no time

                commit_start_dt = datetime.datetime.fromisoformat(commit_start_str)
                commit_end_dt = datetime.datetime.fromisoformat(commit_end_str)

                if current_search_dt < commit_end_dt and slot_end_dt > commit_start_dt: # Overlap
                    is_conflict = True
                    current_search_dt = commit_end_dt # Advance search to end of this conflict
                    break

            if not is_conflict:
                return current_search_dt # Found a non-conflicting slot

        # Fallback if no slot found within 14 days (should be rare with proper logic)
        print(f"Warning: Could not find slot for task within 14 days. Defaulting to current time + 1 hour from last attempt: {current_search_dt + datetime.timedelta(hours=1)}")
        return current_search_dt + datetime.timedelta(hours=1)


    def update_task_schedule_in_db(self, task_id, scheduled_start_iso, scheduled_end_iso):
        """Updates the scheduled_start, scheduled_end, and status for an existing task in the DB."""
        try:
            cursor = self.db.cursor()
            cursor.execute(
                "UPDATE tasks SET scheduled_start = ?, scheduled_end = ?, status = ? WHERE task_id = ?",
                (scheduled_start_iso, scheduled_end_iso, 'scheduled', task_id)
            )
            self.db.commit()

            # Fetch and return the updated task to confirm changes
            cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            updated_task_row = cursor.fetchone()
            return dict(updated_task_row) if updated_task_row else None
        except Exception as e:
            print(f"Error updating task schedule in DB for {task_id}: {e}")
            # self.db.rollback() # Consider if rollback is needed here or handled by connection context
            return None

    # Note: Methods like time_optimized_scheduling, balanced_scheduling, find_next_peak_slot,
    # group_tasks_by_type, get_available_slots were significantly simplified or effectively removed
    # to focus on the core priority_based scheduling and its DB interaction.
    # A full implementation of these would require more complex calendar logic.
    # The 'create_scheduled_task' method was also effectively replaced by 'update_task_schedule_in_db'
    # as this service now primarily deals with scheduling *existing* tasks.
