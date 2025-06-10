# main_app.py
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, Text
import database
from user_service import UserService
from services import TaskService, EventService, ReportService, LearningService
from settings_service import SettingsService
from scheduling_service import SchedulingService
import kairo_ai
import os
import datetime
import json
import logging
from pathlib import Path

# --- App Name and Logging Configuration ---
APP_NAME = "KairoApp"
try:
    if os.name == 'win32': log_dir_base = Path(os.getenv('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif os.name == 'darwin': log_dir_base = Path.home() / 'Library' / 'Logs'
    else: log_dir_base = Path(os.getenv('XDG_STATE_HOME', Path.home() / '.local' / 'state'))
    LOG_DIR = log_dir_base / APP_NAME / "logs"; LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE_PATH = LOG_DIR / 'kairo_app.log'
except Exception as e_log_setup:
    LOG_DIR = Path.home() / f".{APP_NAME.lower()}_logs"; LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE_PATH = LOG_DIR / 'kairo_app.log'
    print(f"Error setting up standard log directory: {e_log_setup}. Using fallback: {LOG_FILE_PATH}")
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s', filename=LOG_FILE_PATH, filemode='a')
logging.info("KairoApp started")
# --- End Logging Configuration ---
try:
    from tkcalendar import DateEntry; TKCALENDAR_AVAILABLE = True; logging.info("tkcalendar imported successfully.")
except ImportError:
    TKCALENDAR_AVAILABLE = False; logging.warning("tkcalendar not found, falling back to ttk.Entry for dates."); print("tkcalendar not found, falling back to ttk.Entry for dates.")

# --- UI Constants ---
BASE_PADDING={'padx':8,'pady':4};INPUT_PADDING={'padx':5,'pady':5};FRAME_PADDING={'padx':10,'pady':5};LABELFRAME_PADDING=(10,5)
APP_FONT_FAMILY="Arial";APP_FONT_SIZE=10;APP_FONT=(APP_FONT_FAMILY,APP_FONT_SIZE);TITLE_FONT_SIZE=12;TITLE_FONT=(APP_FONT_FAMILY,TITLE_FONT_SIZE,"bold")
TEXT_FONT=(APP_FONT_FAMILY,APP_FONT_SIZE);ENTRY_FONT=(APP_FONT_FAMILY,APP_FONT_SIZE);BG_COLOR="#FAFAFA";TEXT_COLOR="#212121"
BORDER_COLOR="#E0E0E0";HIGHLIGHT_THICKNESS=0;BORDER_WIDTH=0

class BaseView(ttk.Frame):
    def __init__(self, parent, user_id, app=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs); self.user_id=user_id; self.app=app; self.logger=logging.getLogger(self.__class__.__name__)

class DashboardView(BaseView): # Unchanged
    def __init__(self, parent, user_id, app=None):
        super().__init__(parent, user_id, app=app); top_frame=ttk.Frame(self); top_frame.pack(fill=tk.X,padx=FRAME_PADDING['padx'],pady=(FRAME_PADDING['pady'],0))
        self.refresh_button=ttk.Button(top_frame,text="Refresh Dashboard",command=self.load_dashboard_data); self.refresh_button.pack(side=tk.LEFT,**BASE_PADDING)
        self.summary_text=Text(self,wrap=tk.WORD,state=tk.DISABLED,height=20,font=TEXT_FONT,relief=tk.FLAT,highlightthickness=HIGHLIGHT_THICKNESS,borderwidth=BORDER_WIDTH,padx=5,pady=5,bg=BG_COLOR,fg=TEXT_COLOR)
        self.summary_text.pack(fill=tk.BOTH,expand=True,**FRAME_PADDING); self.load_dashboard_data()
    def load_dashboard_data(self):
        self.summary_text.config(state=tk.NORMAL);self.summary_text.delete("1.0",tk.END)
        try: self.summary_text.insert(tk.END,ReportService.generate_daily_summary(self.user_id))
        except Exception as e: error_msg=f"Error loading dashboard: {str(e)}";self.summary_text.insert(tk.END,error_msg);self.logger.error(f"UI Error in DashboardView.load_dashboard_data: {str(e)}",exc_info=True);messagebox.showerror("Operation Failed",f"Failed to load dashboard: {str(e)}",parent=self)
        finally: self.summary_text.config(state=tk.DISABLED)

class TaskView(BaseView): # Unchanged
    def __init__(self, parent, user_id, app=None):
        super().__init__(parent, user_id, app=app)
        self.tasks_map = {}
        new_task_frame = ttk.LabelFrame(self, text="New Task", padding=LABELFRAME_PADDING); new_task_frame.pack(fill="x", **FRAME_PADDING)
        self.entries = {}
        ttk.Label(new_task_frame, text="Title:").grid(row=0, column=0, sticky="w", **INPUT_PADDING)
        self.entries["title"] = ttk.Entry(new_task_frame, width=40); self.entries["title"].grid(row=0, column=1, sticky="ew", **INPUT_PADDING)
        ttk.Label(new_task_frame, text="Description:").grid(row=1, column=0, sticky="w", **INPUT_PADDING)
        self.entries["description"] = ttk.Entry(new_task_frame, width=40); self.entries["description"].grid(row=1, column=1, sticky="ew", **INPUT_PADDING)
        ttk.Label(new_task_frame, text="Due Date:").grid(row=2, column=0, sticky="w", **INPUT_PADDING)
        if TKCALENDAR_AVAILABLE:
            self.entries["due_date"] = DateEntry(new_task_frame, width=18, date_pattern='yyyy-mm-dd', font=ENTRY_FONT, locale='en_US'); self.entries["due_date"].grid(row=2, column=1, sticky="ew", **INPUT_PADDING)
            ttk.Label(new_task_frame, text="Time (HH:MM opt.):").grid(row=2, column=2, sticky="w", **INPUT_PADDING)
            self.entries["due_time"] = ttk.Entry(new_task_frame, width=10, font=ENTRY_FONT); self.entries["due_time"].grid(row=2, column=3, sticky="w", **INPUT_PADDING)
            self.entries["due_time"].insert(0, (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%H:%M"))
        else:
            self.entries["due_date_str"] = ttk.Entry(new_task_frame, width=40); self.entries["due_date_str"].grid(row=2, column=1, columnspan=3, sticky="ew", **INPUT_PADDING)
            self.entries["due_date_str"].insert(0, (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M"))
        ttk.Label(new_task_frame, text="Priority:").grid(row=3, column=0, sticky="w", **INPUT_PADDING)
        self.entries["priority_var"] = tk.StringVar(value="medium"); priority_options = ["low", "medium", "high"]
        priority_menu = ttk.OptionMenu(new_task_frame, self.entries["priority_var"], priority_options[1], *priority_options); priority_menu.grid(row=3, column=1, columnspan=3, sticky="ew", **INPUT_PADDING)
        new_task_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(new_task_frame, text="Add Task", command=self.add_task).grid(row=4, column=0, columnspan=4, pady=BASE_PADDING['pady']*2)
        tasks_frame = ttk.LabelFrame(self, text="Tasks", padding=LABELFRAME_PADDING); tasks_frame.pack(fill="both", expand=True, **FRAME_PADDING)
        columns = ("id", "title", "due_date", "priority", "status", "scheduled_start", "scheduled_end")
        self.tree = ttk.Treeview(tasks_frame, columns=columns, show="headings", selectmode='extended')
        for col in columns: self.tree.heading(col, text=col.replace("_"," ").title()); self.tree.column(col, width=50 if col=="id" else (180 if col=="title" else (110 if "schedule" in col or "date" in col else 80)), stretch=(col!="id"))
        self.tree.pack(fill="both", expand=True, side="left", **BASE_PADDING)
        scrollbar = ttk.Scrollbar(tasks_frame, orient="vertical", command=self.tree.yview); self.tree.configure(yscrollcommand=scrollbar.set); scrollbar.pack(side="right", fill="y")
        buttons_frame = ttk.Frame(self); buttons_frame.pack(fill='x', **FRAME_PADDING)
        ttk.Button(buttons_frame, text="Refresh Tasks", command=self.load_tasks).pack(side="left", **BASE_PADDING)
        ttk.Button(buttons_frame, text="Mark Complete", command=self.complete_task).pack(side="left", **BASE_PADDING)
        ttk.Button(buttons_frame, text="Smart Schedule Tasks", command=self.open_scheduler_dialog).pack(side="left", **BASE_PADDING)
    def _format_dt_display(self,s): return datetime.datetime.fromisoformat(s).strftime("%Y-%m-%d %H:%M") if s and isinstance(s,str) else "N/A"
    def load_tasks(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.tasks_map.clear()
        try:
            tasks_from_service = TaskService.get_all_tasks(self.user_id)
            if tasks_from_service:
                for task_dict in tasks_from_service:
                    self.tasks_map[task_dict['task_id']] = task_dict
                    display_values = (task_dict.get('task_id','N/A')[:8], task_dict.get('title','N/A'), self._format_dt_display(task_dict.get('due_datetime')), task_dict.get('priority','N/A'), task_dict.get('status','N/A'), self._format_dt_display(task_dict.get('scheduled_start')), self._format_dt_display(task_dict.get('scheduled_end')))
                    self.tree.insert("","end", iid=task_dict['task_id'], values=display_values)
            else: self.tree.insert("", "end", values=("", "No tasks found.", "", "", "", "", ""))
        except Exception as e: self.logger.error(f"UI Error in TaskView.load_tasks: {str(e)}", exc_info=True); messagebox.showerror("Error Loading Tasks",f"Failed to load tasks: {e}", parent=self)
    def add_task(self):
        try:
            title = self.entries["title"].get(); description = self.entries["description"].get(); priority = self.entries["priority_var"].get(); due_datetime_iso = None
            if TKCALENDAR_AVAILABLE:
                date_val = self.entries["due_date"].get_date(); time_str = self.entries["due_time"].get()
                if time_str:
                    try: time_obj = datetime.datetime.strptime(time_str, "%H:%M").time(); due_datetime_iso = datetime.datetime.combine(date_val, time_obj).isoformat()
                    except ValueError: messagebox.showerror("Error", "Invalid time format. Use HH:MM.", parent=self); return
                else: due_datetime_iso = date_val.isoformat()
            else:
                due_date_str_val = self.entries["due_date_str"].get()
                if due_date_str_val:
                    try: due_datetime_iso = datetime.datetime.strptime(due_date_str_val, "%Y-%m-%d %H:%M").isoformat()
                    except ValueError:
                        try: due_datetime_iso = datetime.datetime.strptime(due_date_str_val, "%Y-%m-%d").date().isoformat()
                        except ValueError: messagebox.showerror("Error","Invalid date. Use YYYY-MM-DD HH:MM or YYYY-MM-DD.", parent=self); return
            if not title: messagebox.showerror("Error","Title required.", parent=self); return
            task_data = {"title":title, "description":description, "priority":priority};
            if due_datetime_iso: task_data["due_datetime"] = due_datetime_iso
            created_task = TaskService.create_task(self.user_id,task_data)
            if created_task: messagebox.showinfo("Success","Task added.", parent=self); self.load_tasks()
            else: messagebox.showerror("Error Adding Task", "Failed to create task (service returned None).", parent=self)
            self.entries["title"].delete(0,tk.END); self.entries["description"].delete(0,tk.END)
            if TKCALENDAR_AVAILABLE: self.entries["due_time"].delete(0,tk.END); self.entries["due_time"].insert(0, (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%H:%M"))
        except Exception as e: self.logger.error(f"UI Error in TaskView.add_task: {str(e)}", exc_info=True); messagebox.showerror("Error Adding Task",f"Failed: {e}", parent=self)
    def complete_task(self):
        try:
            selected_iids = self.tree.selection()
            if not selected_iids: messagebox.showerror("Error","No task selected.", parent=self); return
            completed_count = 0
            for item_iid in selected_iids:
                full_task_id = item_iid
                if not full_task_id or full_task_id not in self.tasks_map: self.logger.warning(f"TaskView.complete_task: Invalid task_id {full_task_id} from selection, or not in tasks_map."); continue
                completed = TaskService.complete_task(full_task_id,self.user_id)
                if completed: completed_count += 1
                else: self.logger.warning(f"TaskView.complete_task: Failed to complete task {full_task_id} via service.")
            if completed_count > 0: messagebox.showinfo("Success",f"{completed_count} task(s) marked as complete.", parent=self)
            if completed_count < len(selected_iids): messagebox.showwarning("Partial Success", f"{len(selected_iids) - completed_count} task(s) could not be completed.", parent=self)
            self.load_tasks()
        except Exception as e: self.logger.error(f"UI Error in TaskView.complete_task: {str(e)}", exc_info=True); messagebox.showerror("Error Completing Task",f"Failed: {e}", parent=self)
    def open_scheduler_dialog(self):
        try:
            self.scheduler_dialog = tk.Toplevel(self.master); self.scheduler_dialog.title("Smart Scheduler"); self.scheduler_dialog.geometry("350x150"); self.scheduler_dialog.transient(self.master); self.scheduler_dialog.grab_set()
            dialog_frame = ttk.Frame(self.scheduler_dialog, padding=FRAME_PADDING); dialog_frame.pack(expand=True, fill=tk.BOTH)
            ttk.Label(dialog_frame, text="Select Scheduling Strategy:").pack(pady=BASE_PADDING['pady']*2)
            self.schedule_strategy_var = tk.StringVar(value="priority_based"); strategies = ["priority_based", "time_optimized", "balanced"]
            strategy_combo = ttk.Combobox(dialog_frame, textvariable=self.schedule_strategy_var, values=strategies, state="readonly"); strategy_combo.pack(pady=BASE_PADDING['pady']); strategy_combo.set("priority_based")
            ttk.Button(dialog_frame, text="Schedule Selected Tasks", command=self.execute_scheduling).pack(pady=BASE_PADDING['pady']*2)
        except Exception as e: self.logger.error(f"UI Error in TaskView.open_scheduler_dialog: {str(e)}", exc_info=True); messagebox.showerror("Error", f"Could not open scheduler: {e}", parent=self)
    def execute_scheduling(self):
        try:
            strategy = self.schedule_strategy_var.get()
            if not strategy: messagebox.showerror("Error", "Please select a strategy.", parent=self.scheduler_dialog); return
            selected_task_ids = self.tree.selection()
            if not selected_task_ids: messagebox.showinfo("No Tasks Selected", "Please select one or more tasks from the list to schedule.", parent=self.scheduler_dialog); return
            selected_tasks_list = [self.tasks_map[tid] for tid in selected_task_ids if tid in self.tasks_map]
            if not selected_tasks_list: messagebox.showwarning("Tasks Not Found", "Could not retrieve details for selected tasks. Please refresh and try again.", parent=self.scheduler_dialog); return
            scheduler = SchedulingService(self.user_id); scheduled_info = scheduler.schedule_multiple_tasks(selected_tasks_list, strategy)
            if scheduled_info is not None: messagebox.showinfo("Success", f"{len(scheduled_info) if scheduled_info else 0} selected tasks have been scheduled/rescheduled.", parent=self.scheduler_dialog)
            else: messagebox.showwarning("Scheduling", "Scheduling service failed or no tasks were scheduled.", parent=self.scheduler_dialog)
            self.load_tasks()
            if hasattr(self, 'scheduler_dialog') and self.scheduler_dialog.winfo_exists(): self.scheduler_dialog.destroy()
        except Exception as e: self.logger.error(f"UI Error in TaskView.execute_scheduling: {str(e)}", exc_info=True); messagebox.showerror("Scheduling Error", f"Failed to schedule tasks: {e}", parent=self.scheduler_dialog if hasattr(self, 'scheduler_dialog') else self)

class EventView(BaseView): # Unchanged
    def __init__(self, parent, user_id, app=None):
        super().__init__(parent, user_id, app=app)
        new_event_frame = ttk.LabelFrame(self, text="New Event", padding=LABELFRAME_PADDING); new_event_frame.pack(fill="x", **FRAME_PADDING)
        self.entries = {}
        form_fields = {"title": {"label": "Title:", "row": 0, "widget": ttk.Entry},"description": {"label": "Description:", "row": 1, "widget": Text, "height": 3},"start_date": {"label": "Start Date:", "row": 2, "widget": DateEntry if TKCALENDAR_AVAILABLE else ttk.Entry, "pattern": "yyyy-mm-dd"},"start_time": {"label": "Start Time (HH:MM):", "row": 2, "widget": ttk.Entry, "width": 10},"end_date": {"label": "End Date:", "row": 3, "widget": DateEntry if TKCALENDAR_AVAILABLE else ttk.Entry, "pattern": "yyyy-mm-dd"},"end_time": {"label": "End Time (HH:MM):", "row": 3, "widget": ttk.Entry, "width": 10},"location": {"label": "Location:", "row": 4, "widget": ttk.Entry},"attendees": {"label": "Attendees (comma-sep):", "row": 5, "widget": ttk.Entry}}
        for key, field in form_fields.items():
            ttk.Label(new_event_frame,text=field["label"]).grid(row=field["row"],column=0 if "time" not in key else 2, sticky="w" if "time" not in key else "e", **INPUT_PADDING)
            if field["widget"] == Text: entry = Text(new_event_frame,width=40,height=field["height"],font=TEXT_FONT,relief=tk.SOLID, borderwidth=1)
            elif field["widget"] == DateEntry: entry = DateEntry(new_event_frame,width=18 if "time" in key else 12, date_pattern=field["pattern"],font=ENTRY_FONT, locale='en_US')
            else: entry = ttk.Entry(new_event_frame,width=field.get("width", 40))
            entry.grid(row=field["row"],column=1 if "time" not in key else 3, sticky="ew", **INPUT_PADDING); self.entries[key] = entry
        now = datetime.datetime.now()
        if TKCALENDAR_AVAILABLE: self.entries["start_date"].set_date(now + datetime.timedelta(hours=1)); self.entries["end_date"].set_date(now + datetime.timedelta(hours=2))
        else: self.entries["start_date"].insert(0, (now + datetime.timedelta(hours=1)).strftime("%Y-%m-%d")); self.entries["end_date"].insert(0, (now + datetime.timedelta(hours=2)).strftime("%Y-%m-%d"))
        self.entries["start_time"].insert(0, (now + datetime.timedelta(hours=1)).strftime("%H:%M")); self.entries["end_time"].insert(0, (now + datetime.timedelta(hours=2)).strftime("%H:%M"))
        new_event_frame.grid_columnconfigure(1, weight=1); new_event_frame.grid_columnconfigure(3, weight=1)
        ttk.Button(new_event_frame,text="Add Event",command=self.add_event).grid(row=len(form_fields),column=0,columnspan=4,pady=BASE_PADDING['pady']*2)
        events_frame=ttk.LabelFrame(self,text="Events", padding=LABELFRAME_PADDING); events_frame.pack(fill="both",expand=True,**FRAME_PADDING)
        cols=("id","title","start_datetime","end_datetime","location"); self.event_tree=ttk.Treeview(events_frame,columns=cols,show="headings")
        for c in cols: self.event_tree.heading(c,text=c.replace("_"," ").title()); self.event_tree.column(c,width=120 if c not in ["id","title"] else (50 if c=="id" else 200),stretch=(c!="id"))
        self.event_tree.pack(fill="both",expand=True,side="left", **BASE_PADDING)
        scroll=ttk.Scrollbar(events_frame,orient="vertical",command=self.event_tree.yview); self.event_tree.configure(yscrollcommand=scroll.set); scroll.pack(side="right",fill="y")
        ttk.Button(self,text="Refresh Events",command=self.load_events).pack(pady=BASE_PADDING['pady']*2)
    def _fmt_dt(self,s): return datetime.datetime.fromisoformat(s).strftime("%Y-%m-%d %H:%M") if s and isinstance(s,str) else "N/A"
    def load_events(self):
        for i in self.event_tree.get_children(): self.event_tree.delete(i)
        try:
            for e_item in EventService.get_all_events(self.user_id): self.event_tree.insert("","end",values=(e_item.get('event_id','N/A')[:8],e_item.get('title','N/A'),self._fmt_dt(e_item.get('start_datetime')),self._fmt_dt(e_item.get('end_datetime')),e_item.get('location','N/A')))
        except Exception as ex: self.logger.error(f"UI Error in EventView.load_events: {str(ex)}", exc_info=True); messagebox.showerror("Error Loading Events",f"Failed: {ex}", parent=self)
    def add_event(self):
        try:
            title = self.entries["title"].get(); desc = self.entries["description"].get("1.0", tk.END).strip(); loc = self.entries["location"].get(); attendees_str = self.entries["attendees"].get(); attendees = [a.strip() for a in attendees_str.split(',') if a.strip()] if attendees_str else []
            start_time_str = self.entries["start_time"].get(); end_time_str = self.entries["end_time"].get()
            if TKCALENDAR_AVAILABLE: start_date_obj = self.entries["start_date"].get_date(); end_date_obj = self.entries["end_date"].get_date()
            else:
                try: start_date_obj = datetime.datetime.strptime(self.entries["start_date"].get(), "%Y-%m-%d").date(); end_date_obj = datetime.datetime.strptime(self.entries["end_date"].get(), "%Y-%m-%d").date() if self.entries["end_date"].get() else None
                except ValueError: messagebox.showerror("Error", "Invalid Date format. Use YYYY-MM-DD.", parent=self); return
            if not title or not start_date_obj or not start_time_str : messagebox.showerror("Error","Title, Start Date, and Start Time required.", parent=self); return
            start_time_obj = datetime.datetime.strptime(start_time_str, "%H:%M").time(); start_datetime = datetime.datetime.combine(start_date_obj, start_time_obj)
            event_data = {"title":title, "description":desc, "location":loc, "attendees":attendees, "start_datetime": start_datetime.isoformat()}
            if end_date_obj and end_time_str: end_time_obj = datetime.datetime.strptime(end_time_str, "%H:%M").time(); end_datetime = datetime.datetime.combine(end_date_obj, end_time_obj); event_data["end_datetime"] = end_datetime.isoformat()
            elif end_date_obj: event_data["end_datetime"] = datetime.datetime.combine(end_date_obj, start_time_obj).isoformat()
            created_event = EventService.create_event(self.user_id,event_data)
            if created_event: messagebox.showinfo("Success","Event added.", parent=self); self.load_events()
            else: messagebox.showerror("Error Adding Event", "Failed to create event (service returned None).", parent=self)
            self.entries["title"].delete(0,tk.END); self.entries["description"].delete("1.0",tk.END); self.entries["location"].delete(0,tk.END); self.entries["attendees"].delete(0,tk.END)
        except ValueError as ve: self.logger.warning(f"Data validation error in EventView.add_event: {str(ve)}"); messagebox.showerror("Error","Invalid Time format. Use HH:MM.", parent=self)
        except Exception as ex: self.logger.error(f"UI Error in EventView.add_event: {str(ex)}", exc_info=True); messagebox.showerror("Error Adding Event",f"Failed: {ex}", parent=self)

class ChatView(BaseView):
    def __init__(self, parent, user_id, app=None):
        super().__init__(parent, user_id, app=app)
        self.pending_action_details = None # For slot filling
        self.expected_param_key = None   # Key of param Kairo just asked for

        self.ACTIONS_CONFIG = {
            'create_task': {
                'required': {'title': "What should be the title of the task?"},
                'optional': {
                    'description': "Any description for the task? (Optional)",
                    'due_datetime': "When is it due (e.g., YYYY-MM-DD HH:MM)? (Optional)",
                    'priority': "What's the priority (low, medium, high)? (Optional, defaults to medium)"
                },
                'service_call': TaskService.create_task,
                'view_to_refresh': "Tasks"
            },
            'create_event': {
                'required': {
                    'title': "What is the event's title?",
                    'start_datetime': "When does the event start (e.g., YYYY-MM-DD HH:MM)?"
                },
                'optional': {
                    'description': "Any description for the event? (Optional)",
                    'end_datetime': "When does it end (YYYY-MM-DD HH:MM)? (Optional)",
                    'location': "Where will it take place? (Optional)"
                },
                'service_call': EventService.create_event,
                'view_to_refresh': "Events"
            }
        }

        self.history_text=Text(self,wrap=tk.WORD,state=tk.DISABLED,height=20,font=TEXT_FONT, relief=tk.FLAT, highlightthickness=HIGHLIGHT_THICKNESS, borderwidth=BORDER_WIDTH, padx=5,pady=5, bg=BG_COLOR, fg=TEXT_COLOR);
        self.history_text.pack(fill=tk.BOTH,expand=True,padx=FRAME_PADDING['padx'],pady=(FRAME_PADDING['pady'],0))
        input_frame=ttk.Frame(self); input_frame.pack(fill=tk.X,padx=FRAME_PADDING['padx'],pady=FRAME_PADDING['pady'])
        self.input_entry=ttk.Entry(input_frame,width=70);
        self.input_entry.pack(side=tk.LEFT,fill=tk.X,expand=True,ipady=4, **INPUT_PADDING);
        self.input_entry.bind("<Return>",self.send_message_event)
        self.send_button=ttk.Button(input_frame,text="Send",command=self.send_message);
        self.send_button.pack(side=tk.RIGHT,padx=(INPUT_PADDING['padx'],0))
        self.load_initial_history()

    def add_msg(self,s,m): self.history_text.config(state=tk.NORMAL); stag=f"{s}_tag"; self.history_text.tag_configure(stag,font=(APP_FONT_FAMILY, APP_FONT_SIZE, 'bold')); self.history_text.insert(tk.END,f"{s}",stag); self.history_text.insert(tk.END,f": {m}\n\n"); self.history_text.config(state=tk.DISABLED); self.history_text.see(tk.END)

    def load_initial_history(self):
        try: [self.add_msg(msg['sender'].title(),msg['message']) for msg in kairo_ai.get_conversation_history(self.user_id,limit=15)]
        except Exception as e: self.logger.error(f"UI Error in ChatView.load_initial_history: {str(e)}", exc_info=True); self.add_msg("System",f"Error loading history: {e}")

    def send_message_event(self,event): self.send_message()

    def _execute_action_and_feedback(self, action_type, params):
        self.logger.info(f"Executing action '{action_type}' with params: {params}")
        config = self.ACTIONS_CONFIG[action_type]
        service_method = config['service_call']
        try:
            # Ensure params are cleaned or validated if necessary before passing to service
            # e.g. convert date/time strings to ISO if AI provides them in natural language
            # For now, assume AI provides them in a compatible format or service handles it.
            result = service_method(self.user_id, params)
            if result:
                item_name = params.get('title', 'the item')
                self.add_msg("Kairo", f"Done! I've {action_type.replace('_', ' ')}d '{item_name}' for you.")
                view_name_to_refresh = config.get('view_to_refresh')
                if view_name_to_refresh and self.app and hasattr(self.app, 'views') and view_name_to_refresh in self.app.views:
                    view_to_refresh_instance = self.app.views[view_name_to_refresh]
                    # Dynamically call load_tasks or load_events
                    if hasattr(view_to_refresh_instance, 'load_tasks'): view_to_refresh_instance.load_tasks()
                    elif hasattr(view_to_refresh_instance, 'load_events'): view_to_refresh_instance.load_events()
            else:
                self.add_msg("Kairo", f"Sorry, I couldn't complete the action '{action_type}'. The service did not confirm success.")
        except Exception as e:
            self.logger.error(f"Error executing action '{action_type}' for user {self.user_id}: {str(e)}", exc_info=True)
            self.add_msg("Kairo", f"An error occurred while trying to {action_type.replace('_', ' ')}: {str(e)}")


    def send_message(self):
        user_msg = self.input_entry.get().strip()
        if not user_msg: return

        self.add_msg("You", user_msg)
        self.input_entry.delete(0, tk.END)
        self.input_entry.config(state=tk.DISABLED); self.send_button.config(state=tk.DISABLED)

        try:
            if self.pending_action_details:
                if user_msg.lower() == "cancel":
                    self.add_msg("Kairo", "Okay, I've cancelled the current action.")
                    self.pending_action_details = None; self.expected_param_key = None
                else: # User is providing info for a pending action
                    if self.expected_param_key:
                        self.pending_action_details['params'][self.expected_param_key] = user_msg
                        if self.expected_param_key in self.pending_action_details['missing']:
                            del self.pending_action_details['missing'][self.expected_param_key]
                        self.expected_param_key = None

                    if not self.pending_action_details['missing']: # All params collected
                        action_to_execute = self.pending_action_details['action']
                        params_for_action = self.pending_action_details['params']
                        self.pending_action_details = None
                        self._execute_action_and_feedback(action_to_execute, params_for_action)
                    else: # Still missing params, ask for the next one
                        next_key = list(self.pending_action_details['missing'].keys())[0]
                        self.expected_param_key = next_key
                        question = self.pending_action_details['missing'][next_key]
                        self.add_msg("Kairo", f"Got it. Next, {question}")
            else: # Not in slot-filling mode, process as new query
                hist = kairo_ai.get_conversation_history(self.user_id, limit=10)
                kairo_ai.log_conversation_message(self.user_id, "user", user_msg)
                raw = kairo_ai.get_kairo_response(self.user_id, user_msg, hist)
                kairo_ai.log_conversation_message(self.user_id, "kairo", raw) # Log raw for now
                parsed = kairo_ai.parse_ai_action(raw)
                action_type = parsed.get('action')

                if action_type in self.ACTIONS_CONFIG:
                    config = self.ACTIONS_CONFIG[action_type]
                    provided_params = parsed.get('parameters', {})
                    current_params = {} # Params we have values for
                    missing_params_map = {} # Params we still need, and their questions

                    for key, question in config['required'].items():
                        if key in provided_params and provided_params[key]:
                            current_params[key] = provided_params[key]
                        else:
                            missing_params_map[key] = question

                    # Also populate optional params if AI provided them
                    for key, question in config.get('optional', {}).items():
                         if key in provided_params and provided_params[key]:
                            current_params[key] = provided_params[key]

                    if not missing_params_map: # All required params provided by AI
                        self._execute_action_and_feedback(action_type, current_params)
                    else: # AI suggested an action but missed required params
                        self.pending_action_details = {'action': action_type, 'params': current_params, 'missing': missing_params_map}
                        next_key_to_ask = list(missing_params_map.keys())[0]
                        self.expected_param_key = next_key_to_ask
                        self.add_msg("Kairo", f"Okay, I can help with that. First, {missing_params_map[next_key_to_ask]}")

                elif action_type == 'conversation' or not action_type : # Standard conversational reply
                    self.add_msg("Kairo", parsed.get('response', "I'm not sure how to respond to that."))
                else: # Unknown structured action
                    self.add_msg("Kairo", f"I received an action '{action_type}' but I'm not yet equipped to handle it. Details: {parsed.get('parameters', 'No parameters')}")

        except Exception as e:
            err_msg=f"Error in processing message: {e}"; self.add_msg("System",err_msg)
            self.logger.error(f"UI Error in ChatView.send_message: {str(e)}", exc_info=True)
            if self.pending_action_details : # If error during slot filling, cancel it
                 kairo_ai.log_conversation_message(self.user_id,"system_error", f"Error during slot filling for {self.pending_action_details.get('action')}: {err_msg}")
                 self.pending_action_details = None; self.expected_param_key = None
            else:
                 kairo_ai.log_conversation_message(self.user_id,"system_error", err_msg)
        finally:
            if not self.pending_action_details: # Only re-enable fully if not waiting for more params
                self.input_entry.config(state=tk.NORMAL); self.send_button.config(state=tk.NORMAL); self.input_entry.focus_set()
            elif self.pending_action_details and not self.pending_action_details['missing']: # All params collected, action attempted, re-enable
                 self.input_entry.config(state=tk.NORMAL); self.send_button.config(state=tk.NORMAL); self.input_entry.focus_set()
            else: # Still in slot filling, waiting for user input for next param
                 self.input_entry.config(state=tk.NORMAL); self.send_button.config(state=tk.NORMAL); self.input_entry.focus_set()


class SettingsView(BaseView): # Unchanged
    def __init__(self, parent, user_id, app=None):
        super().__init__(parent, user_id, app=app); self.vars = {}
        frame = ttk.LabelFrame(self, text="User Preferences", padding=LABELFRAME_PADDING); frame.pack(fill=tk.BOTH, expand=True, **FRAME_PADDING)
        settings_fields = [("Theme:", "theme", "dark", ttk.Combobox, ["dark", "light", "system"]), ("Kairo's Personality:", "kairo_style", "professional", ttk.Combobox, ["professional", "friendly", "witty"]), ("Archive Tasks After (days):", "completed_task_archive_duration", "30", ttk.Entry), ("Working Hours Start (HH:MM):", "working_hours_start", "09:00", ttk.Entry), ("Working Hours End (HH:MM):", "working_hours_end", "17:00", ttk.Entry), ("Notification Prefs (JSON):", "notification_preferences", '{"email": true, "in_app": true}', ttk.Entry)]
        for i, field_info in enumerate(settings_fields):
            label_text, key, default, widget_type, *widget_config = field_info
            label = ttk.Label(frame, text=label_text); label.grid(row=i, column=0, sticky="w", **INPUT_PADDING)
            var = tk.StringVar(); self.vars[key] = var
            if widget_type == ttk.Combobox: entry = ttk.Combobox(frame, textvariable=var, values=widget_config[0], width=37); entry.set(default)
            else: entry = ttk.Entry(frame, textvariable=var, width=40)
            entry.grid(row=i, column=1, sticky="ew", **INPUT_PADDING)
        frame.grid_columnconfigure(1, weight=1)
        ttk.Button(frame, text="Save Settings", command=self.save_settings).grid(row=len(settings_fields), column=0, columnspan=2, pady=BASE_PADDING['pady']*4)
        self.load_settings()
    def load_settings(self):
        try:
            settings = SettingsService.get_user_settings(self.user_id)
            for key, var in self.vars.items():
                value = settings.get(key, SettingsService.DEFAULT_SETTINGS.get(key))
                if isinstance(value, dict) or isinstance(value, list): var.set(json.dumps(value))
                else: var.set(str(value))
        except Exception as e: self.logger.error(f"UI Error in SettingsView.load_settings: {str(e)}", exc_info=True); messagebox.showerror("Error Loading Settings", f"Failed to load settings: {e}", parent=self)
    def save_settings(self):
        updated_settings = {}
        try:
            for key, var in self.vars.items():
                value = var.get()
                if key == "completed_task_archive_duration": updated_settings[key] = int(value)
                elif key == "notification_preferences":
                    try: updated_settings[key] = json.loads(value)
                    except json.JSONDecodeError: messagebox.showerror("Error","Invalid JSON for Notification Prefs.", parent=self); return
                else: updated_settings[key] = value
            success = SettingsService.update_user_settings(self.user_id, updated_settings)
            if success: messagebox.showinfo("Success", "Settings saved.", parent=self)
            else: messagebox.showerror("Error", "Failed to save settings (service returned false).", parent=self)
        except ValueError as ve: self.logger.warning(f"Data validation error in SettingsView.save_settings: {str(ve)}"); messagebox.showerror("Error", f"Invalid value: {ve}", parent=self)
        except Exception as e: self.logger.error(f"UI Error in SettingsView.save_settings: {str(e)}", exc_info=True); messagebox.showerror("Error Saving Settings", f"Unexpected error: {e}", parent=self)
        self.load_settings()

class LearningView(BaseView): # Unchanged
    def __init__(self, parent, user_id, app=None):
        super().__init__(parent, user_id, app=app)
        self.learning_service = LearningService()
        session_frame = ttk.LabelFrame(self, text="Create Learning Session", padding=LABELFRAME_PADDING); session_frame.pack(fill=tk.X, **FRAME_PADDING)
        ttk.Label(session_frame, text="Topic:").grid(row=0, column=0, sticky="w", **INPUT_PADDING)
        self.session_topic_entry = ttk.Entry(session_frame, width=40); self.session_topic_entry.grid(row=0, column=1, sticky="ew", **INPUT_PADDING)
        ttk.Label(session_frame, text="Resources (comma-separated):").grid(row=1, column=0, sticky="nw", **INPUT_PADDING)
        self.session_resources_text = Text(session_frame, width=40, height=3, font=TEXT_FONT, relief=tk.SOLID, borderwidth=1); self.session_resources_text.grid(row=1, column=1, sticky="ew", **INPUT_PADDING)
        ttk.Label(session_frame, text="Start Date:").grid(row=2, column=0, sticky="w", **INPUT_PADDING)
        if TKCALENDAR_AVAILABLE:
            self.session_start_date_entry = DateEntry(session_frame, width=18, date_pattern='yyyy-mm-dd', font=ENTRY_FONT, locale='en_US'); self.session_start_date_entry.grid(row=2, column=1, sticky="ew", **INPUT_PADDING)
            ttk.Label(session_frame, text="Start Time (HH:MM):").grid(row=2, column=2, sticky="w", **INPUT_PADDING)
            self.session_start_time_entry = ttk.Entry(session_frame, width=10, font=ENTRY_FONT); self.session_start_time_entry.grid(row=2, column=3, sticky="w", **INPUT_PADDING)
            self.session_start_time_entry.insert(0, (datetime.datetime.now() + datetime.timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).strftime("%H:%M"))
        else:
            self.session_start_datetime_entry = ttk.Entry(session_frame, width=40); self.session_start_datetime_entry.grid(row=2, column=1, columnspan=3, sticky="ew", **INPUT_PADDING)
            self.session_start_datetime_entry.insert(0, (datetime.datetime.now() + datetime.timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M"))
        session_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(session_frame, text="Create Session", command=self.create_session).grid(row=3, column=0, columnspan=4, pady=BASE_PADDING['pady']*2)
        content_frame = ttk.LabelFrame(self, text="Get Personalized Learning Content", padding=LABELFRAME_PADDING); content_frame.pack(fill=tk.BOTH, expand=True, **FRAME_PADDING)
        ttk.Label(content_frame, text="Topic:").grid(row=0, column=0, sticky="w", **INPUT_PADDING)
        self.content_topic_entry = ttk.Entry(content_frame, width=40); self.content_topic_entry.grid(row=0, column=1, sticky="ew", **INPUT_PADDING)
        content_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(content_frame, text="Get Content", command=self.get_content).grid(row=1, column=0, columnspan=2, pady=BASE_PADDING['pady'])
        self.content_display_text = Text(content_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=TEXT_FONT, relief=tk.SOLID, borderwidth=1, padx=5, pady=5); self.content_display_text.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=BASE_PADDING['pady']); content_frame.grid_rowconfigure(2, weight=1)
    def create_session(self):
        try:
            topic = self.session_topic_entry.get(); resources_str = self.session_resources_text.get("1.0", tk.END).strip(); start_datetime_iso = None
            if TKCALENDAR_AVAILABLE:
                date_val = self.session_start_date_entry.get_date(); time_str = self.session_start_time_entry.get()
                if not time_str: messagebox.showerror("Error", "Start Time is required.", parent=self); return
                try: time_obj = datetime.datetime.strptime(time_str, "%H:%M").time(); start_datetime_iso = datetime.datetime.combine(date_val, time_obj).isoformat()
                except ValueError: messagebox.showerror("Error", "Invalid Start Time. Use HH:MM.", parent=self); return
            else:
                start_datetime_str_val = self.session_start_datetime_entry.get()
                if not start_datetime_str_val: messagebox.showerror("Error", "Start Date/Time is required.", parent=self); return
                try: start_datetime_iso = datetime.datetime.strptime(start_datetime_str_val, "%Y-%m-%d %H:%M").isoformat()
                except ValueError: messagebox.showerror("Error", "Invalid Start Date/Time. Use YYYY-MM-DD HH:MM.", parent=self); return
            if not topic: messagebox.showerror("Error", "Topic is required.", parent=self); return
            resources_list = [r.strip() for r in resources_str.split(',') if r.strip()]
            event_details, note_details = self.learning_service.create_learning_session(self.user_id, topic, resources_list, start_datetime_iso)
            if event_details and note_details: messagebox.showinfo("Success", f"Learning session for '{topic}' created.\nEvent ID: {event_details.get('event_id')}\nNote ID: {note_details.get('note_id')}", parent=self)
            else: messagebox.showerror("Error Creating Session", "Failed to create session (service returned None).", parent=self)
            self.session_topic_entry.delete(0, tk.END); self.session_resources_text.delete("1.0", tk.END)
        except Exception as e: self.logger.error(f"UI Error in LearningView.create_session: {str(e)}", exc_info=True); messagebox.showerror("Error Creating Session", f"Failed: {e}", parent=self)
    def get_content(self):
        try:
            topic = self.content_topic_entry.get()
            if not topic: messagebox.showerror("Error", "Topic is required.", parent=self); return
            content = self.learning_service.generate_personalized_content(self.user_id, topic)
            self.content_display_text.config(state=tk.NORMAL); self.content_display_text.delete("1.0", tk.END); self.content_display_text.insert(tk.END, content); self.content_display_text.config(state=tk.DISABLED)
        except Exception as e: self.logger.error(f"UI Error in LearningView.get_content: {str(e)}", exc_info=True); messagebox.showerror("Error Getting Content", f"Failed: {e}", parent=self)

class KairoApp:
    def __init__(self, root):
        self.root = root; self.root.title("Kairo AI Assistant"); self.root.geometry("950x750")
        self.root.configure(bg=BG_COLOR)
        s = ttk.Style();s.configure('.', font=APP_FONT, background=BG_COLOR, foreground=TEXT_COLOR)
        s.configure('TFrame', background=BG_COLOR); s.configure('TLabel', background=BG_COLOR, foreground=TEXT_COLOR, font=APP_FONT)
        s.configure('TLabelFrame', background=BG_COLOR, bordercolor=BORDER_COLOR)
        s.configure('TLabelFrame.Label', background=BG_COLOR, foreground=TEXT_COLOR, font=TITLE_FONT)
        s.configure('TNotebook', background=BG_COLOR, bordercolor=BORDER_COLOR)
        s.configure('TNotebook.Tab', font=APP_FONT, padding=[10, 5], background=BG_COLOR, foreground=TEXT_COLOR)
        s.map('TNotebook.Tab', background=[('selected', BG_COLOR)], foreground=[('selected', TEXT_COLOR)])
        s.configure('Treeview.Heading', font=TITLE_FONT); s.configure('Treeview', fieldbackground=BG_COLOR, foreground=TEXT_COLOR)
        s.configure('TButton', font=APP_FONT, padding=[8, 4]); s.configure('TEntry', font=ENTRY_FONT, fieldbackground='white')
        s.configure('TCombobox', font=ENTRY_FONT, fieldbackground='white',selectbackground='white', selectforeground=TEXT_COLOR)
        self.root.option_add('*TCombobox*Listbox.font', ENTRY_FONT); self.root.option_add('*TCombobox*Listbox.background', 'white'); self.root.option_add('*TCombobox*Listbox.foreground', TEXT_COLOR)
        self.root.option_add('*Menu.font', APP_FONT); self.root.option_add('*tk.OptionMenu.font', APP_FONT); self.root.option_add('*ttk.OptionMenu*Menubutton.font', APP_FONT)
        self.user_id = UserService.get_current_user_id()
        try: database.init_db(); logging.info("Database initialized.")
        except Exception as e: logging.critical(f"Critical DB init error: {e}", exc_info=True); messagebox.showerror("DB Error",f"DB init failed: {e}"); self.root.destroy(); return
        self.notebook = ttk.Notebook(root)
        self.views = {}
        view_configs = [(DashboardView, "Dashboard"), (ChatView, "Kairo AI Chat"), (TaskView, "Tasks"), (EventView, "Events"), (LearningView, "Learning Center"), (SettingsView, "Settings")]
        for i, (ViewClass, text) in enumerate(view_configs):
            view_instance = ViewClass(self.notebook, self.user_id, app=self)
            self.views[text] = view_instance
            if text == "Dashboard": self.notebook.insert(0, view_instance, text=text)
            else: self.notebook.add(view_instance, text=text)
        self.notebook.pack(expand=True,fill='both',**FRAME_PADDING)
        if self.notebook.tabs() and "Dashboard" in self.views: self.notebook.select(self.views["Dashboard"])
        if "Tasks" in self.views: self.views["Tasks"].load_tasks()
        if "Events" in self.views: self.views["Events"].load_events()
    def on_closing(self):
        logging.info("KairoApp closing")
        database.close_db_connection()
        self.root.destroy()

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logging.info(f"KairoApp __main__ started. CWD: {os.getcwd()}. DB Path: {database.DATABASE_PATH}")
    root = tk.Tk();
    app = KairoApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
    logging.info("KairoApp exited mainloop.")
