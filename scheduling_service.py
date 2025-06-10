# scheduling_service_detailed_feedback_v2.py
import datetime
import json
from collections import defaultdict, deque
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
        self.tasks_map_for_run = {} # Initialize here
        self.scheduled_tasks_map_with_times = {} # Initialize here
        try:
            self.db = database.get_db_connection()
        except Exception as e:
            logger.critical(f"SchedulingService critical: Failed to get DB connection for user {user_id}. Error: {e}", exc_info=True)
            raise SchedulingServiceError(f"Could not initialize database for SchedulingService: {e}") from e

        try:
            self.learner = AdaptiveLearner(user_id)
        except Exception as e:
            logger.error(f"SchedulingService: Failed to initialize AdaptiveLearner for user {user_id}. Error: {e}", exc_info=True)
            self.learner = None

    def _get_tasks_in_topological_order(self, tasks_list_of_dicts):
        # tasks_map_for_sort is now self.tasks_map_for_run, populated in schedule_multiple_tasks
        if not tasks_list_of_dicts:
            return {'ordered_ids': [], 'cyclical_task_ids': [], 'unprocessed_ids': []}

        adj = defaultdict(list)
        in_degree = defaultdict(int)
        task_ids_set = set(self.tasks_map_for_run.keys())

        for task_id in task_ids_set:
            _ = in_degree[task_id] # Ensure all tasks are in in_degree

        for task_id, task_dict in self.tasks_map_for_run.items():
            depends_on = task_dict.get('depends_on_task_id')
            if depends_on and depends_on in task_ids_set:
                adj[depends_on].append(task_id)
                in_degree[task_id] += 1

        queue = deque([tid for tid in task_ids_set if in_degree[tid] == 0])
        topological_order_ids = []

        processed_count = 0
        while queue:
            u = queue.popleft()
            topological_order_ids.append(u)
            processed_count +=1
            for v_neighbor in adj[u]:
                in_degree[v_neighbor] -= 1
                if in_degree[v_neighbor] == 0:
                    queue.append(v_neighbor)

        cyclical_task_ids = []
        unprocessed_ids = [] # For tasks not part of a cycle but still not processed (e.g. disconnected components if logic changes)

        if processed_count != len(task_ids_set):
            logger.error(f"User {self.user_id}: Cycle detected or tasks unorderable. Sorted: {processed_count}/{len(task_ids_set)}.")
            for task_id in task_ids_set:
                if task_id not in topological_order_ids:
                    cyclical_task_ids.append(task_id)

        logger.info(f"User {self.user_id}: Topological sort - Ordered: {len(topological_order_ids)}, Cyclical: {len(cyclical_task_ids)}")
        return {'ordered_ids': topological_order_ids, 'cyclical_task_ids': cyclical_task_ids, 'unprocessed_ids': unprocessed_ids}

    def schedule_multiple_tasks(self, tasks_to_schedule_dicts, strategy="priority_based"):
        detailed_outcome = {'scheduled_tasks': [], 'unscheduled_tasks_info': []}
        if not tasks_to_schedule_dicts:
            logger.info(f"User {self.user_id}: No tasks provided for scheduling.")
            return detailed_outcome

        logger.info(f"User {self.user_id}: Starting schedule_multiple_tasks with strategy '{strategy}' for {len(tasks_to_schedule_dicts)} tasks.")

        self.tasks_map_for_run = {task['task_id']: task for task in tasks_to_schedule_dicts if 'task_id' in task}
        self.scheduled_tasks_map_with_times = {} # Reset for this run

        try:
            topo_sort_result = self._get_tasks_in_topological_order(tasks_to_schedule_dicts) # Pass original list

            unorderable_ids = set(topo_sort_result['cyclical_task_ids']) | set(topo_sort_result['unprocessed_ids'])
            for task_id in unorderable_ids:
                detailed_outcome['unscheduled_tasks_info'].append({
                    'task_id': task_id,
                    'task_title': self.tasks_map_for_run.get(task_id, {}).get('title', 'Unknown Title'),
                    'reason': 'Dependency cycle or unorderable'
                })

            ordered_tasks_for_strategy_input = [self.tasks_map_for_run[tid] for tid in topo_sort_result['ordered_ids'] if tid in self.tasks_map_for_run and tid not in unorderable_ids]

            if not ordered_tasks_for_strategy_input and not unorderable_ids: # No tasks to schedule and no errors from topo sort
                 logger.warning(f"User {self.user_id}: No tasks available for strategy input after topological sort and filtering.")
                 # Add all tasks as unscheduled if they weren't caught by cycle detection but didn't make it to ordered list
                 if not detailed_outcome['unscheduled_tasks_info']: # If no specific reason yet
                    for task_id in self.tasks_map_for_run:
                        if task_id not in orderable_task_ids: # Check against the set of orderable IDs from topo_sort_result
                             detailed_outcome['unscheduled_tasks_info'].append({
                                'task_id': task_id,
                                'task_title': self.tasks_map_for_run[task_id].get('title', 'Unknown Title'),
                                'reason': 'Not processed by topological sort (unknown reason)'
                            })
                 return detailed_outcome

            existing_events = self.get_upcoming_events()
            working_hours = self.get_working_hours()
            peak_hours = []
            if self.learner and hasattr(self.learner, 'profile') and self.learner.profile and \
               'productivity_patterns' in self.learner.profile and \
               isinstance(self.learner.profile['productivity_patterns'], dict):
                peak_hours = self.learner.profile['productivity_patterns'].get('peak_hours', [])

            processed_tasks_for_strategy = []
            for task_dict in ordered_tasks_for_strategy_input:
                current_task = task_dict.copy()
                if 'duration' not in current_task or not current_task['duration']:
                    current_task['duration'] = self.estimate_task_duration(current_task)
                processed_tasks_for_strategy.append(current_task)

            strategy_result = {'scheduled_in_strategy': [], 'not_scheduled_in_strategy': []}
            if strategy == "priority_based":
                strategy_result = self._priority_based_scheduling_logic(
                    processed_tasks_for_strategy, self.scheduled_tasks_map_with_times,
                    existing_events, working_hours, peak_hours
                )
            else:
                logger.warning(f"User {self.user_id}: Strategy '{strategy}' not fully implemented, defaulting to priority_based.")
                strategy_result = self._priority_based_scheduling_logic(processed_tasks_for_strategy, self.scheduled_tasks_map_with_times, existing_events, working_hours, peak_hours)

            for task_info_with_schedule in strategy_result['scheduled_in_strategy']:
                updated_task_db_info = self.update_task_schedule_in_db(
                    task_info_with_schedule['task_id'],
                    task_info_with_schedule.get('scheduled_start'),
                    task_info_with_schedule.get('scheduled_end')
                )
                if updated_task_db_info: detailed_outcome['scheduled_tasks'].append(updated_task_db_info)
                else: detailed_outcome['unscheduled_tasks_info'].append({'task_id': task_info_with_schedule['task_id'],'task_title': task_info_with_schedule.get('title', 'Unknown Title'),'reason': 'DB update failed post-scheduling'})

            for unscheduled_item in strategy_result['not_scheduled_in_strategy']: # Already has task_id, task_title, reason
                detailed_outcome['unscheduled_tasks_info'].append(unscheduled_item)

            logger.info(f"User {self.user_id}: Scheduling outcome - Scheduled: {len(detailed_outcome['scheduled_tasks'])}, Unscheduled: {len(detailed_outcome['unscheduled_tasks_info'])}.")
        except Exception as e:
            logger.error(f"User {self.user_id}: Critical error in schedule_multiple_tasks: {str(e)}", exc_info=True)
            for task_id in self.tasks_map_for_run: # Mark all tasks as unscheduled due to global error
                if not any(info['task_id'] == task_id for info in detailed_outcome['unscheduled_tasks_info']): # Avoid duplicates
                    detailed_outcome['unscheduled_tasks_info'].append({'task_id': task_id,'task_title': self.tasks_map_for_run[task_id].get('title', 'Unknown Title'),'reason': f'Critical scheduling error: {str(e)}'})
        return detailed_outcome

    def _priority_based_scheduling_logic(self, topologically_ordered_tasks, scheduled_tasks_map_accumulator, existing_events, working_hours, peak_hours):
        locally_scheduled_tasks = []
        locally_unscheduled_tasks_info = []
        current_time_marker = datetime.datetime.now()

        for task_to_schedule in topologically_ordered_tasks:
            task_id = task_to_schedule['task_id']
            task_duration = task_to_schedule.get('duration', 60)
            parent_id = task_to_schedule.get('depends_on_task_id')
            parent_title = self.tasks_map_for_run.get(parent_id, {}).get('title', parent_id if parent_id else "N/A")

            min_start_time_due_to_dependency = datetime.datetime.now() # Can't start before now

            if parent_id:
                if parent_id in scheduled_tasks_map_accumulator:
                    parent_task_end_str = scheduled_tasks_map_accumulator[parent_id].get('scheduled_end')
                    if parent_task_end_str:
                        try: parent_end_dt = datetime.datetime.fromisoformat(parent_task_end_str)
                        min_start_time_due_to_dependency = max(min_start_time_due_to_dependency, parent_end_dt)
                        except ValueError as ve:
                            logger.error(f"Task {task_id}: Could not parse parent task '{parent_title}' ({parent_id}) end time '{parent_task_end_str}': {ve}", exc_info=True)
                            locally_unscheduled_tasks_info.append({'task_id': task_id, 'task_title': task_to_schedule.get('title'), 'reason': f"Parent task '{parent_title}' has invalid end time."}); continue
                    else:
                        logger.warning(f"Task {task_id}: Parent task '{parent_title}' ({parent_id}) is in map but has no end time.")
                        locally_unscheduled_tasks_info.append({'task_id': task_id, 'task_title': task_to_schedule.get('title'), 'reason': f"Parent task '{parent_title}' missing scheduled end time."}); continue
                else:
                    # This task is in the topologically_ordered_list, so its parent (if part of the batch) should have been processed.
                    # If parent_id is not in scheduled_tasks_map_accumulator, it means the parent itself couldn't be scheduled.
                    logger.warning(f"Task {task_id}: Dependency '{parent_title}' ({parent_id}) not successfully scheduled. Cannot schedule this task.")
                    locally_unscheduled_tasks_info.append({'task_id': task_id, 'task_title': task_to_schedule.get('title'), 'reason': f"Parent task '{parent_title}' could not be scheduled."}); continue

            effective_search_start_time = max(current_time_marker, min_start_time_due_to_dependency)
            scheduled_start_time = self._find_next_available_slot(effective_search_start_time, task_duration, existing_events + locally_scheduled_tasks, working_hours, peak_hours)

            if scheduled_start_time is None:
                logger.warning(f"Task {task_id} ('{task_to_schedule.get('title')}') could not find an available slot after {effective_search_start_time}.")
                locally_unscheduled_tasks_info.append({'task_id': task_id, 'task_title': task_to_schedule.get('title'), 'reason': 'No available slot found.'}); continue

            task_to_schedule['scheduled_start'] = scheduled_start_time.isoformat()
            task_to_schedule['scheduled_end'] = (scheduled_start_time + datetime.timedelta(minutes=task_duration)).isoformat()

            scheduled_tasks_map_accumulator[task_id] = task_to_schedule
            locally_scheduled_tasks.append(task_to_schedule)
            # current_time_marker = scheduled_start_time + datetime.timedelta(minutes=task_duration)
            # The current_time_marker should not just jump to the end of the last scheduled task,
            # as the next task in topological order might have an earlier min_start_time due to its own (lack of) dependencies
            # The effective_search_start_time for the next task will correctly use max(current_time_marker, its_own_dependency_end_time)
            # However, to prevent all tasks from trying to schedule from "now", we should advance current_time_marker
            # if the new task is scheduled later than the current marker.
            if scheduled_start_time + datetime.timedelta(minutes=task_duration) > current_time_marker:
                 current_time_marker = scheduled_start_time + datetime.timedelta(minutes=task_duration)

        return {'scheduled_in_strategy': locally_scheduled_tasks, 'not_scheduled_in_strategy': locally_unscheduled_tasks_info}

    def _find_next_available_slot(self, search_start_dt, duration_minutes, commitments, working_hours, peak_hours_list):
        try:
            current_search_dt = search_start_dt
            wh_start_time = datetime.datetime.strptime(working_hours['start'], "%H:%M").time()
            wh_end_time = datetime.datetime.strptime(working_hours['end'], "%H:%M").time()
            max_search_date = current_search_dt.date() + datetime.timedelta(days=14)
            while current_search_dt.date() <= max_search_date:
                if current_search_dt.time() < wh_start_time: current_search_dt = datetime.datetime.combine(current_search_dt.date(), wh_start_time)
                elif current_search_dt.time() >= wh_end_time: current_search_dt = datetime.datetime.combine(current_search_dt.date() + datetime.timedelta(days=1), wh_start_time); continue
                slot_end_dt = current_search_dt + datetime.timedelta(minutes=duration_minutes)
                if slot_end_dt.time() > wh_end_time or (slot_end_dt.date() > current_search_dt.date() and slot_end_dt.time() != datetime.time.min): current_search_dt = datetime.datetime.combine(current_search_dt.date() + datetime.timedelta(days=1), wh_start_time); continue
                is_conflict = False
                for commitment in commitments:
                    commit_start_str = commitment.get('scheduled_start') or commitment.get('start_datetime'); commit_end_str = commitment.get('scheduled_end') or commitment.get('end_datetime')
                    if not commit_start_str or not commit_end_str: continue
                    try: commit_start_dt = datetime.datetime.fromisoformat(commit_start_str); commit_end_dt = datetime.datetime.fromisoformat(commit_end_str)
                    except ValueError: logger.warning(f"Invalid datetime format in commitment: {commitment}", exc_info=True); continue
                    if current_search_dt < commit_end_dt and slot_end_dt > commit_start_dt: is_conflict = True; current_search_dt = commit_end_dt; break
                if not is_conflict: return current_search_dt
            logger.warning(f"User {self.user_id}: Could not find slot within 14 days for duration {duration_minutes} min from {search_start_dt}.")
            return None
        except Exception as e: logger.error(f"User {self.user_id}: Error in _find_next_available_slot: {str(e)}", exc_info=True); return None

    def get_upcoming_events(self):
        try:
            now = datetime.datetime.now().isoformat(); seven_days_later = (datetime.datetime.now() + datetime.timedelta(days=7)).isoformat()
            cursor = self.db.cursor(); cursor.execute("SELECT * FROM events WHERE user_id = ? AND start_datetime BETWEEN ? AND ? AND (is_archived = 0 OR is_archived IS NULL) ORDER BY start_datetime",(self.user_id, now, seven_days_later))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e: logger.error(f"User {self.user_id}: DB error in get_upcoming_events: {str(e)}", exc_info=True); return []
    def get_working_hours(self):
        try:
            cursor = self.db.cursor(); cursor.execute("SELECT working_hours_start, working_hours_end FROM user_settings WHERE user_id = ?", (self.user_id,))
            settings = cursor.fetchone()
            if settings and settings['working_hours_start'] and settings['working_hours_end']: return {"start": settings['working_hours_start'], "end": settings['working_hours_end']}
            logger.info(f"User {self.user_id}: No specific working hours found, using defaults.")
            return {"start": "09:00", "end": "17:00"}
        except Exception as e: logger.error(f"User {self.user_id}: DB error in get_working_hours: {str(e)}", exc_info=True); return {"start": "09:00", "end": "17:00"}
    def estimate_task_duration(self, task_dict):
        try:
            cursor = self.db.cursor(); title_like = f"%{task_dict.get('title', '###')}%"
            cursor.execute("SELECT AVG((julianday(status_change_timestamp) - julianday(created_at)) * 24 * 60) AS avg_duration FROM tasks WHERE user_id = ? AND title LIKE ? AND status = 'completed' AND status_change_timestamp IS NOT NULL AND created_at IS NOT NULL",(self.user_id, title_like))
            result = cursor.fetchone()
            if result and result['avg_duration'] and result['avg_duration'] > 0 : return int(result['avg_duration'])
        except Exception as e: logger.error(f"User {self.user_id}: DB error estimating duration for task '{task_dict.get('title')}': {str(e)}", exc_info=True)
        priority = task_dict.get('priority', 'medium'); return {'high': 60, 'medium': 90, 'low': 120}.get(priority, 90)
    def update_task_schedule_in_db(self, task_id, scheduled_start_iso, scheduled_end_iso):
        try:
            cursor = self.db.cursor()
            cursor.execute("UPDATE tasks SET scheduled_start = ?, scheduled_end = ?, status = ? WHERE task_id = ?", (scheduled_start_iso, scheduled_end_iso, 'scheduled', task_id))
            self.db.commit(); cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)); updated_task_row = cursor.fetchone()
            logger.info(f"User {self.user_id}: Task {task_id} schedule updated in DB.")
            return dict(updated_task_row) if updated_task_row else None
        except Exception as e: logger.error(f"User {self.user_id}: DB error updating task schedule for {task_id}: {str(e)}", exc_info=True); return None
