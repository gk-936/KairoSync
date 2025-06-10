import datetime
import json
from collections import defaultdict
from database import get_db
from utils import format_timestamp, generate_id
from adaptive_learning import AdaptiveLearner

class SchedulingService:
    def __init__(self, user_id):
        self.user_id = user_id
        self.db = get_db()
        self.learner = AdaptiveLearner(user_id)
    
    def schedule_multiple_tasks(self, tasks, strategy="priority_based"):
        """
        Schedule multiple tasks at once with intelligent allocation
        Strategies: 
          - priority_based: Schedule high priority first
          - time_optimized: Group similar tasks and schedule together
          - balanced: Distribute tasks throughout available time
        """
        # Get existing commitments
        existing_events = self.get_upcoming_events()
        scheduled_tasks = []
        
        # Get user preferences
        working_hours = self.get_working_hours()
        peak_hours = self.learner.profile['productivity_patterns'].get('peak_hours', [])
        
        # Preprocess tasks
        for task in tasks:
            if 'duration' not in task:
                task['duration'] = self.estimate_task_duration(task)
        
        # Apply scheduling strategy
        if strategy == "priority_based":
            scheduled_tasks = self.priority_based_scheduling(tasks, existing_events, working_hours, peak_hours)
        elif strategy == "time_optimized":
            scheduled_tasks = self.time_optimized_scheduling(tasks, existing_events, working_hours)
        elif strategy == "balanced":
            scheduled_tasks = self.balanced_scheduling(tasks, existing_events, working_hours)
        else:
            scheduled_tasks = self.default_scheduling(tasks, existing_events, working_hours)
        
        # Save scheduled tasks
        for task in scheduled_tasks:
            self.create_scheduled_task(task)
        
        return scheduled_tasks
    
    def get_upcoming_events(self):
        """Get events for the next 7 days"""
        now = datetime.datetime.now().isoformat()
        seven_days_later = (datetime.datetime.now() + datetime.timedelta(days=7)).isoformat()
        
        cursor = self.db.execute(
            "SELECT * FROM events WHERE user_id = ? AND start_datetime BETWEEN ? AND ? "
            "AND is_archived = 0 ORDER BY start_datetime",
            (self.user_id, now, seven_days_later)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_working_hours(self):
        """Get user's preferred working hours"""
        cursor = self.db.execute(
            "SELECT working_hours_start, working_hours_end FROM user_settings WHERE user_id = ?",
            (self.user_id,)
        )
        settings = cursor.fetchone()
        if settings:
            return {
                "start": settings['working_hours_start'],
                "end": settings['working_hours_end']
            }
        return {"start": "08:00", "end": "18:00"}  # Default
    
    def estimate_task_duration(self, task):
        """Estimate task duration based on historical data"""
        # Get average duration for similar tasks
        cursor = self.db.execute(
            "SELECT AVG((julianday(completed_at) - julianday(created_at)) * 24 * 60) AS avg_duration "
            "FROM tasks WHERE user_id = ? AND title LIKE ? AND completed_at IS NOT NULL",
            (self.user_id, f"%{task['title']}%")
        )
        result = cursor.fetchone()
        
        if result and result['avg_duration']:
            return result['avg_duration']
        
        # Fallback to priority-based estimates
        priority = task.get('priority', 'medium')
        return {
            'high': 60,    # 1 hour for high priority tasks
            'medium': 120,  # 2 hours for medium priority
            'low': 240      # 4 hours for low priority
        }.get(priority, 120)
    
    def priority_based_scheduling(self, tasks, existing_events, working_hours, peak_hours):
        """Schedule high-priority tasks first during peak hours"""
        # Sort tasks by priority (high to low)
        tasks.sort(key=lambda t: {'high': 0, 'medium': 1, 'low': 2}.get(t.get('priority', 'medium'), 1))
        
        scheduled = []
        current_time = datetime.datetime.now()
        
        for task in tasks:
            # Find next available peak hour slot
            scheduled_time = self.find_next_peak_slot(
                task['duration'], 
                existing_events + scheduled,
                working_hours,
                peak_hours,
                current_time
            )
            
            task['scheduled_start'] = scheduled_time.isoformat()
            task['scheduled_end'] = (scheduled_time + datetime.timedelta(minutes=task['duration'])).isoformat()
            scheduled.append(task)
            current_time = scheduled_time + datetime.timedelta(minutes=task['duration'])
        
        return scheduled
    
    def find_next_peak_slot(self, duration, commitments, working_hours, peak_hours, start_from):
        """Find the next available time slot during peak hours"""
        # Convert to datetime objects
        work_start = datetime.datetime.strptime(working_hours['start'], '%H:%M').time()
        work_end = datetime.datetime.strptime(working_hours['end'], '%H:%M').time()
        
        # Check next 7 days
        for day in range(7):
            current_date = start_from.date() + datetime.timedelta(days=day)
            
            # Get all peak hours for this day
            for hour in peak_hours:
                slot_start = datetime.datetime.combine(current_date, datetime.time(hour, 0))
                slot_end = slot_start + datetime.timedelta(minutes=duration)
                
                # Skip if outside working hours
                if slot_start.time() < work_start or slot_end.time() > work_end:
                    continue
                
                # Check conflicts with existing commitments
                if not self.has_conflict(slot_start, slot_end, commitments):
                    return slot_start
        
        # If no peak slots found, find any available slot
        return self.find_any_slot(duration, commitments, working_hours, start_from)
    
    def time_optimized_scheduling(self, tasks, existing_events, working_hours):
        """Group similar tasks and schedule together to minimize context switching"""
        # Group tasks by type (based on title keywords)
        task_groups = self.group_tasks_by_type(tasks)
        scheduled = []
        
        current_time = datetime.datetime.now()
        
        for group, group_tasks in task_groups.items():
            # Calculate total duration for group
            group_duration = sum(t['duration'] for t in group_tasks)
            
            # Find time slot for the entire group
            slot_start = self.find_available_slot(
                group_duration, 
                existing_events + scheduled,
                working_hours,
                current_time
            )
            
            # Schedule each task in the group sequentially
            for task in group_tasks:
                task['scheduled_start'] = slot_start.isoformat()
                slot_end = slot_start + datetime.timedelta(minutes=task['duration'])
                task['scheduled_end'] = slot_end.isoformat()
                scheduled.append(task)
                slot_start = slot_end
            
            current_time = slot_end
        
        return scheduled
    
    def group_tasks_by_type(self, tasks):
        """Group tasks by similarity"""
        groups = defaultdict(list)
        
        for task in tasks:
            # Simple grouping by first keyword in title
            first_word = task['title'].split()[0].lower()
            groups[first_word].append(task)
        
        return groups
    
    def balanced_scheduling(self, tasks, existing_events, working_hours):
        """Distribute tasks evenly across available time"""
        scheduled = []
        total_duration = sum(t['duration'] for t in tasks)
        
        # Get available time slots
        available_slots = self.get_available_slots(
            existing_events, 
            working_hours,
            datetime.datetime.now(),
            datetime.timedelta(days=7)
        )
        
        # Distribute tasks across slots
        for slot in available_slots:
            slot_duration = (slot['end'] - slot['start']).total_seconds() / 60
            
            while tasks and slot_duration > 0:
                task = tasks[0]
                
                if task['duration'] <= slot_duration:
                    # Task fits in current slot
                    task['scheduled_start'] = slot['start'].isoformat()
                    task['scheduled_end'] = (slot['start'] + datetime.timedelta(minutes=task['duration'])).isoformat()
                    scheduled.append(task)
                    
                    # Update slot
                    slot['start'] += datetime.timedelta(minutes=task['duration'])
                    slot_duration -= task['duration']
                    tasks.pop(0)
                else:
                    # Task doesn't fit, move to next slot
                    break
        
        # Handle any remaining tasks
        if tasks:
            # Try to schedule remaining tasks in any available slots
            for task in tasks:
                slot_start = self.find_available_slot(
                    task['duration'],
                    existing_events + scheduled,
                    working_hours,
                    datetime.datetime.now()
                )
                task['scheduled_start'] = slot_start.isoformat()
                task['scheduled_end'] = (slot_start + datetime.timedelta(minutes=task['duration'])).isoformat()
                scheduled.append(task)
        
        return scheduled
    
    def get_available_slots(self, events, working_hours, start_from, period):
        """Get all available time slots within working hours"""
        slots = []
        end_time = start_from + period
        
        # Convert working hours to time objects
        work_start_time = datetime.datetime.strptime(working_hours['start'], '%H:%M').time()
        work_end_time = datetime.datetime.strptime(working_hours['end'], '%H:%M').time()
        
        # Create daily slots
        current_day = start_from.date()
        while current_day <= end_time.date():
            day_start = datetime.datetime.combine(current_day, work_start_time)
            day_end = datetime.datetime.combine(current_day, work_end_time)
            
            # Initialize with full day slot
            slots.append({'start': day_start, 'end': day_end})
            current_day += datetime.timedelta(days=1)
        
        # Cut out existing events
        for event in events:
            event_start = datetime.datetime.fromisoformat(event['start_datetime'])
            event_end = datetime.datetime.fromisoformat(event['end_datetime']) if event['end_datetime'] else event_start + datetime.timedelta(hours=1)
            
            for slot in slots[:]:
                if event_start < slot['end'] and event_end > slot['start']:
                    # Event overlaps with slot
                    if event_start > slot['start'] and event_end < slot['end']:
                        # Event is inside slot - split slot
                        new_slot = {'start': event_end, 'end': slot['end']}
                        slot['end'] = event_start
                        slots.append(new_slot)
                    elif event_start <= slot['start']:
                        slot['start'] = max(slot['start'], event_end)
                    else:
                        slot['end'] = min(slot['end'], event_start)
        
        # Remove zero-duration slots
        slots = [s for s in slots if s['end'] > s['start']]
        
        return slots
    
    def create_scheduled_task(self, task):
        """Save scheduled task to database"""
        # Add scheduled times to task
        task['scheduled_start'] = task.get('scheduled_start')
        task['scheduled_end'] = task.get('scheduled_end')
        
        # Create or update task
        if 'task_id' in task:
            # Update existing task
            self.db.execute(
                "UPDATE tasks SET scheduled_start = ?, scheduled_end = ? WHERE task_id = ?",
                (task['scheduled_start'], task['scheduled_end'], task['task_id'])
            )
        else:
            # Create new task
            task_id = generate_id("task")
            self.db.execute(
                "INSERT INTO tasks (task_id, user_id, title, description, due_datetime, "
                "priority, status, scheduled_start, scheduled_end) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (task_id, self.user_id, task['title'], task.get('description'),
                 task.get('due_datetime'), task.get('priority', 'medium'), 
                 'scheduled', task['scheduled_start'], task['scheduled_end'])
            )
            task['task_id'] = task_id
        
        self.db.commit()
        return task
    
    def has_conflict(self, start, end, commitments):
        """Check if time slot conflicts with existing commitments"""
        for item in commitments:
            item_start = datetime.datetime.fromisoformat(item.get('scheduled_start', item.get('start_datetime')))
            item_end = datetime.datetime.fromisoformat(item.get('scheduled_end', item.get('end_datetime', item_start + datetime.timedelta(hours=1))))
            
            if start < item_end and end > item_start:
                return True
        return False