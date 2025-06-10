# scheduling_service_with_logging.py
import datetime
import json
from collections import defaultdict
import database
from utils import format_timestamp, generate_id
from adaptive_learning import AdaptiveLearner
import logging

logger = logging.getLogger(__name__)

class SchedulingServiceError(Exception):
    """Custom exception for scheduling service errors."""
    pass

class SchedulingService:
    def __init__(self, user_id):
        self.user_id = user_id
        try:
            self.db = database.get_db_connection()
        except Exception as e:
            logger.critical(f"SchedulingService critical: Failed to get DB connection for user {user_id}. Error: {e}", exc_info=True)
            # This service cannot function without a DB. Re-raise or handle gracefully.
            raise SchedulingServiceError(f"Could not initialize database for SchedulingService: {e}") from e

        try:
            self.learner = AdaptiveLearner(user_id)
        except Exception as e:
            logger.error(f"SchedulingService: Failed to initialize AdaptiveLearner for user {user_id}. Error: {e}", exc_info=True)
            # Depending on how critical AdaptiveLearner is, you might want to raise an error
            # or allow the service to continue with degraded functionality.
            # For now, we'll let it proceed but log the error.
            self.learner = None # Or a dummy learner object

    def schedule_multiple_tasks(self, tasks_list_of_dicts, strategy="priority_based"):
        if not tasks_list_of_dicts:
            logger.info(f"User {self.user_id}: No tasks provided for scheduling.")
            return []
        logger.info(f"User {self.user_id}: Starting schedule_multiple_tasks with strategy '{strategy}' for {len(tasks_list_of_dicts)} tasks.")
        try:
            existing_events = self.get_upcoming_events()
            working_hours = self.get_working_hours()
            peak_hours = []
            if self.learner and hasattr(self.learner, 'profile') and self.learner.profile and \
               'productivity_patterns' in self.learner.profile and \
               isinstance(self.learner.profile['productivity_patterns'], dict):
                peak_hours = self.learner.profile['productivity_patterns'].get('peak_hours', [])

            processed_tasks = []
            for task_dict in tasks_list_of_dicts:
                current_task = task_dict.copy()
                if 'duration' not in current_task or not current_task['duration']:
                    current_task['duration'] = self.estimate_task_duration(current_task)
                processed_tasks.append(current_task)

            scheduled_tasks_output = []
            if strategy == "priority_based":
                scheduled_tasks_output = self._priority_based_scheduling_logic(processed_tasks, existing_events, working_hours, peak_hours)
            else:
                logger.warning(f"User {self.user_id}: Strategy '{strategy}' not fully implemented, defaulting to priority_based.")
                scheduled_tasks_output = self._priority_based_scheduling_logic(processed_tasks, existing_events, working_hours, peak_hours)

            final_scheduled_info = []
            for task_info in scheduled_tasks_output:
                if 'task_id' in task_info and task_info.get('scheduled_start') and task_info.get('scheduled_end'):
                     updated_task_info = self.update_task_schedule_in_db(
                        task_info['task_id'], task_info.get('scheduled_start'), task_info.get('scheduled_end'))
                     if updated_task_info: final_scheduled_info.append(updated_task_info)
                else: logger.warning(f"User {self.user_id}: Skipping task update for '{task_info.get('title')}' due to missing ID or schedule times.")

            logger.info(f"User {self.user_id}: Successfully scheduled/updated {len(final_scheduled_info)} tasks.")
            return final_scheduled_info
        except Exception as e:
            logger.error(f"User {self.user_id}: Error in schedule_multiple_tasks: {str(e)}", exc_info=True)
            return None # Indicate failure to the caller

    def get_upcoming_events(self):
        try:
            now = datetime.datetime.now().isoformat()
            seven_days_later = (datetime.datetime.now() + datetime.timedelta(days=7)).isoformat()
            cursor = self.db.cursor()
            cursor.execute(
                "SELECT * FROM events WHERE user_id = ? AND start_datetime BETWEEN ? AND ? AND (is_archived = 0 OR is_archived IS NULL) ORDER BY start_datetime",
                (self.user_id, now, seven_days_later))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"User {self.user_id}: DB error in get_upcoming_events: {str(e)}", exc_info=True)
            return []

    def get_working_hours(self):
        try:
            cursor = self.db.cursor()
            cursor.execute("SELECT working_hours_start, working_hours_end FROM user_settings WHERE user_id = ?", (self.user_id,))
            settings = cursor.fetchone()
            if settings and settings['working_hours_start'] and settings['working_hours_end']:
                return {"start": settings['working_hours_start'], "end": settings['working_hours_end']}
            logger.info(f"User {self.user_id}: No specific working hours found, using defaults.")
            return {"start": "09:00", "end": "17:00"}
        except Exception as e:
            logger.error(f"User {self.user_id}: DB error in get_working_hours: {str(e)}", exc_info=True)
            return {"start": "09:00", "end": "17:00"} # Fallback to default

    def estimate_task_duration(self, task_dict):
        try:
            cursor = self.db.cursor()
            title_like = f"%{task_dict.get('title', '###')}%" # Avoid empty LIKE clause
            cursor.execute(
                "SELECT AVG((julianday(status_change_timestamp) - julianday(created_at)) * 24 * 60) AS avg_duration "
                "FROM tasks WHERE user_id = ? AND title LIKE ? AND status = 'completed' AND status_change_timestamp IS NOT NULL AND created_at IS NOT NULL",
                (self.user_id, title_like))
            result = cursor.fetchone()
            if result and result['avg_duration'] and result['avg_duration'] > 0 : return int(result['avg_duration'])
        except Exception as e:
            logger.error(f"User {self.user_id}: DB error estimating duration for task '{task_dict.get('title')}': {str(e)}", exc_info=True)
        priority = task_dict.get('priority', 'medium')
        return {'high': 60, 'medium': 90, 'low': 120}.get(priority, 90)

    def _priority_based_scheduling_logic(self, tasks, existing_events, working_hours, peak_hours):
        try:
            tasks.sort(key=lambda t: {'high': 0, 'medium': 1, 'low': 2}.get(t.get('priority', 'medium'), 1))
            scheduled_list_of_tasks = []
            current_time_marker = datetime.datetime.now()
            for task_to_schedule in tasks:
                task_duration = task_to_schedule.get('duration', 60)
                scheduled_start_time = self._find_next_available_slot(current_time_marker, task_duration, existing_events + scheduled_list_of_tasks, working_hours, peak_hours)
                task_to_schedule['scheduled_start'] = scheduled_start_time.isoformat()
                task_to_schedule['scheduled_end'] = (scheduled_start_time + datetime.timedelta(minutes=task_duration)).isoformat()
                scheduled_list_of_tasks.append(task_to_schedule)
                current_time_marker = scheduled_start_time + datetime.timedelta(minutes=task_duration)
            return scheduled_list_of_tasks
        except Exception as e:
            logger.error(f"User {self.user_id}: Error in _priority_based_scheduling_logic: {str(e)}", exc_info=True)
            return tasks # Return original tasks to indicate failure to schedule properly

    def _find_next_available_slot(self, search_start_dt, duration_minutes, commitments, working_hours, peak_hours_list):
        try:
            current_search_dt = search_start_dt
            wh_start_time = datetime.datetime.strptime(working_hours['start'], "%H:%M").time()
            wh_end_time = datetime.datetime.strptime(working_hours['end'], "%H:%M").time()
            max_search_date = current_search_dt.date() + datetime.timedelta(days=14) # Limit search depth

            while current_search_dt.date() <= max_search_date:
                if current_search_dt.time() < wh_start_time: current_search_dt = datetime.datetime.combine(current_search_dt.date(), wh_start_time)
                elif current_search_dt.time() >= wh_end_time: current_search_dt = datetime.datetime.combine(current_search_dt.date() + datetime.timedelta(days=1), wh_start_time); continue
                slot_end_dt = current_search_dt + datetime.timedelta(minutes=duration_minutes)
                if slot_end_dt.time() > wh_end_time or slot_end_dt.date() > current_search_dt.date(): current_search_dt = datetime.datetime.combine(current_search_dt.date() + datetime.timedelta(days=1), wh_start_time); continue
                is_conflict = False
                for commitment in commitments:
                    commit_start_str = commitment.get('scheduled_start') or commitment.get('start_datetime'); commit_end_str = commitment.get('scheduled_end') or commitment.get('end_datetime')
                    if not commit_start_str or not commit_end_str: continue
                    commit_start_dt = datetime.datetime.fromisoformat(commit_start_str); commit_end_dt = datetime.datetime.fromisoformat(commit_end_str)
                    if current_search_dt < commit_end_dt and slot_end_dt > commit_start_dt: is_conflict = True; current_search_dt = commit_end_dt; break
                if not is_conflict: return current_search_dt

            logger.warning(f"User {self.user_id}: Could not find slot within 14 days for duration {duration_minutes} min. Defaulting to {search_start_dt + datetime.timedelta(hours=1)}")
            return search_start_dt + datetime.timedelta(hours=1) # Fallback
        except Exception as e:
            logger.error(f"User {self.user_id}: Error in _find_next_available_slot: {str(e)}", exc_info=True)
            return search_start_dt + datetime.timedelta(hours=1) # Fallback on error

    def update_task_schedule_in_db(self, task_id, scheduled_start_iso, scheduled_end_iso):
        try:
            cursor = self.db.cursor()
            cursor.execute("UPDATE tasks SET scheduled_start = ?, scheduled_end = ?, status = ? WHERE task_id = ?", (scheduled_start_iso, scheduled_end_iso, 'scheduled', task_id))
            self.db.commit()
            cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            updated_task_row = cursor.fetchone()
            logger.info(f"User {self.user_id}: Task {task_id} schedule updated in DB.")
            return dict(updated_task_row) if updated_task_row else None
        except Exception as e:
            logger.error(f"User {self.user_id}: DB error updating task schedule for {task_id}: {str(e)}", exc_info=True)
            # self.db.rollback() # Usually handled by connection context or if autocommit is off
            return None
