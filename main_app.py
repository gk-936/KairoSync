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
try:
    from tkcalendar import DateEntry
    TKCALENDAR_AVAILABLE = True
except ImportError:
    TKCALENDAR_AVAILABLE = False
    print("tkcalendar not found, falling back to ttk.Entry for dates. Consider `pip install tkcalendar`.")

# --- Constants for UI Refinement ---
BASE_PADDING = {'padx': 8, 'pady': 4}
INPUT_PADDING = {'padx': 5, 'pady': 5}
FRAME_PADDING = {'padx': 10, 'pady': 5}
LABELFRAME_PADDING = (10, 5)

APP_FONT_FAMILY = "Arial"
APP_FONT_SIZE = 10
APP_FONT = (APP_FONT_FAMILY, APP_FONT_SIZE)
TITLE_FONT_SIZE = 12
TITLE_FONT = (APP_FONT_FAMILY, TITLE_FONT_SIZE, "bold")
TEXT_FONT = (APP_FONT_FAMILY, APP_FONT_SIZE)
ENTRY_FONT = (APP_FONT_FAMILY, APP_FONT_SIZE) # Also for DateEntry

BG_COLOR = "#FAFAFA"
TEXT_COLOR = "#212121"
BORDER_COLOR = "#E0E0E0"
HIGHLIGHT_THICKNESS = 0
BORDER_WIDTH = 0

class BaseView(ttk.Frame):
    def __init__(self, parent, user_id, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.user_id = user_id

class DashboardView(BaseView):
    def __init__(self, parent, user_id):
        super().__init__(parent, user_id)
        top_frame = ttk.Frame(self); top_frame.pack(fill=tk.X, padx=FRAME_PADDING['padx'], pady=(FRAME_PADDING['pady'],0))
        self.refresh_button = ttk.Button(top_frame, text="Refresh Dashboard", command=self.load_dashboard_data)
        self.refresh_button.pack(side=tk.LEFT, **BASE_PADDING)
        self.summary_text = Text(self, wrap=tk.WORD, state=tk.DISABLED, height=20, font=TEXT_FONT, relief=tk.FLAT, highlightthickness=HIGHLIGHT_THICKNESS, borderwidth=BORDER_WIDTH, padx=5, pady=5, bg=BG_COLOR, fg=TEXT_COLOR)
        self.summary_text.pack(fill=tk.BOTH, expand=True, **FRAME_PADDING)
        self.load_dashboard_data()
    def load_dashboard_data(self):
        self.summary_text.config(state=tk.NORMAL); self.summary_text.delete("1.0", tk.END)
        try: self.summary_text.insert(tk.END, ReportService.generate_daily_summary(self.user_id))
        except Exception as e: error_msg = f"Error loading dashboard: {str(e)}"; self.summary_text.insert(tk.END, error_msg); print(error_msg)
        finally: self.summary_text.config(state=tk.DISABLED)

class TaskView(BaseView):
    def __init__(self, parent, user_id):
        super().__init__(parent, user_id)
        new_task_frame = ttk.LabelFrame(self, text="New Task", padding=LABELFRAME_PADDING); new_task_frame.pack(fill="x", **FRAME_PADDING)

        self.entries = {}
        # Title
        ttk.Label(new_task_frame, text="Title:").grid(row=0, column=0, sticky="w", **INPUT_PADDING)
        self.entries["title"] = ttk.Entry(new_task_frame, width=40)
        self.entries["title"].grid(row=0, column=1, sticky="ew", **INPUT_PADDING)

        # Description
        ttk.Label(new_task_frame, text="Description:").grid(row=1, column=0, sticky="w", **INPUT_PADDING)
        self.entries["description"] = ttk.Entry(new_task_frame, width=40)
        self.entries["description"].grid(row=1, column=1, sticky="ew", **INPUT_PADDING)

        # Due Date
        ttk.Label(new_task_frame, text="Due Date:").grid(row=2, column=0, sticky="w", **INPUT_PADDING)
        if TKCALENDAR_AVAILABLE:
            self.entries["due_date"] = DateEntry(new_task_frame, width=18, date_pattern='yyyy-mm-dd', font=ENTRY_FONT, locale='en_US')
            self.entries["due_date"].grid(row=2, column=1, sticky="ew", **INPUT_PADDING)
            # For time, add a separate entry if DateEntry doesn't handle it well or pattern is just date
            ttk.Label(new_task_frame, text="Time (HH:MM optional):").grid(row=2, column=2, sticky="w", **INPUT_PADDING)
            self.entries["due_time"] = ttk.Entry(new_task_frame, width=10, font=ENTRY_FONT)
            self.entries["due_time"].grid(row=2, column=3, sticky="w", **INPUT_PADDING)
            self.entries["due_time"].insert(0, (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%H:%M"))
        else:
            self.entries["due_date_str"] = ttk.Entry(new_task_frame, width=40) # Fallback
            self.entries["due_date_str"].grid(row=2, column=1, columnspan=3, sticky="ew", **INPUT_PADDING)
            self.entries["due_date_str"].insert(0, (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M"))
            ttk.Label(new_task_frame, text="(YYYY-MM-DD HH:MM)").grid(row=2, column=2, sticky="w", **INPUT_PADDING)


        # Priority
        ttk.Label(new_task_frame, text="Priority:").grid(row=3, column=0, sticky="w", **INPUT_PADDING)
        self.entries["priority_var"] = tk.StringVar(value="medium")
        priority_options = ["low", "medium", "high"]
        priority_menu = ttk.OptionMenu(new_task_frame, self.entries["priority_var"], priority_options[1], *priority_options)
        priority_menu.grid(row=3, column=1, columnspan=3, sticky="ew", **INPUT_PADDING)

        new_task_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(new_task_frame, text="Add Task", command=self.add_task).grid(row=4, column=0, columnspan=4, pady=BASE_PADDING['pady']*2)

        tasks_frame = ttk.LabelFrame(self, text="Tasks", padding=LABELFRAME_PADDING); tasks_frame.pack(fill="both", expand=True, **FRAME_PADDING)
        columns = ("id", "title", "due_date", "priority", "status", "scheduled_start", "scheduled_end")
        self.tree = ttk.Treeview(tasks_frame, columns=columns, show="headings")
        for col in columns: self.tree.heading(col, text=col.replace("_"," ").title()); self.tree.column(col, width=50 if col=="id" else (180 if col=="title" else (110 if "schedule" in col or "date" in col else 80)), stretch=(col!="id"))
        self.tree.pack(fill="both", expand=True, side="left", **BASE_PADDING)
        scrollbar = ttk.Scrollbar(tasks_frame, orient="vertical", command=self.tree.yview); self.tree.configure(yscrollcommand=scrollbar.set); scrollbar.pack(side="right", fill="y")
        buttons_frame = ttk.Frame(self); buttons_frame.pack(fill='x', **FRAME_PADDING)
        ttk.Button(buttons_frame, text="Refresh Tasks", command=self.load_tasks).pack(side="left", **BASE_PADDING)
        ttk.Button(buttons_frame, text="Mark Complete", command=self.complete_task).pack(side="left", **BASE_PADDING)
        ttk.Button(buttons_frame, text="Smart Schedule Tasks", command=self.open_scheduler_dialog).pack(side="left", **BASE_PADDING)

    def _format_dt_display(self, dt_string):
        if not dt_string or not isinstance(dt_string, str): return "N/A"
        try: return datetime.datetime.fromisoformat(dt_string).strftime("%Y-%m-%d %H:%M")
        except ValueError: return dt_string
    def load_tasks(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        try:
            for task in TaskService.get_all_tasks(self.user_id): self.tree.insert("","end",values=(task.get('task_id','N/A')[:8], task.get('title','N/A'), self._format_dt_display(task.get('due_datetime')), task.get('priority','N/A'), task.get('status','N/A'), self._format_dt_display(task.get('scheduled_start')), self._format_dt_display(task.get('scheduled_end'))))
        except Exception as e: messagebox.showerror("Error Loading Tasks",f"Failed: {e}")

    def add_task(self):
        title = self.entries["title"].get()
        description = self.entries["description"].get()
        priority = self.entries["priority_var"].get()
        due_datetime_iso = None

        if TKCALENDAR_AVAILABLE:
            date_val = self.entries["due_date"].get_date() # Returns datetime.date object
            time_str = self.entries["due_time"].get()
            if time_str:
                try:
                    time_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
                    due_datetime_iso = datetime.datetime.combine(date_val, time_obj).isoformat()
                except ValueError:
                    messagebox.showerror("Error", "Invalid time format. Use HH:MM."); return
            else: # Only date provided
                due_datetime_iso = date_val.isoformat()
        else: # Fallback to string entry
            due_date_str_val = self.entries["due_date_str"].get()
            if due_date_str_val:
                try: due_datetime_iso = datetime.datetime.strptime(due_date_str_val, "%Y-%m-%d %H:%M").isoformat()
                except ValueError:
                    try: due_datetime_iso = datetime.datetime.strptime(due_date_str_val, "%Y-%m-%d").date().isoformat()
                    except ValueError: messagebox.showerror("Error","Invalid date. Use YYYY-MM-DD HH:MM or YYYY-MM-DD."); return

        if not title: messagebox.showerror("Error","Title required."); return
        task_data = {"title":title, "description":description, "priority":priority}
        if due_datetime_iso: task_data["due_datetime"] = due_datetime_iso

        try: TaskService.create_task(self.user_id,task_data); messagebox.showinfo("Success","Task added."); self.load_tasks()
        except Exception as e: messagebox.showerror("Error Adding Task",f"Failed: {e}")
        self.entries["title"].delete(0,tk.END); self.entries["description"].delete(0,tk.END)
        if TKCALENDAR_AVAILABLE: self.entries["due_time"].delete(0,tk.END); self.entries["due_time"].insert(0, (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%H:%M"))
        # else: self.entries["due_date_str"].delete(0,tk.END); self.entries["due_date_str"].insert(0, (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M"))


    def complete_task(self):
        sel = self.tree.selection();
        if not sel: messagebox.showerror("Error","No task selected."); return
        disp_id, title = self.tree.item(sel,"values")[0], self.tree.item(sel,"values")[1]; full_id=None
        try:
            for t in TaskService.get_all_tasks(self.user_id):
                if t.get('title')==title and t.get('task_id','').startswith(disp_id): full_id=t.get('task_id'); break
        except Exception as e: messagebox.showerror("Error",f"Could not get full ID: {e}"); return
        if not full_id: messagebox.showerror("Error","Could not find full task ID."); return
        try: TaskService.complete_task(full_id,self.user_id); messagebox.showinfo("Success","Task complete."); self.load_tasks()
        except Exception as e: messagebox.showerror("Error Completing Task",f"Failed: {e}")
    def open_scheduler_dialog(self):
        self.scheduler_dialog = tk.Toplevel(self.master); self.scheduler_dialog.title("Smart Scheduler"); self.scheduler_dialog.geometry("350x150"); self.scheduler_dialog.transient(self.master); self.scheduler_dialog.grab_set()
        dialog_frame = ttk.Frame(self.scheduler_dialog, padding=FRAME_PADDING); dialog_frame.pack(expand=True, fill=tk.BOTH)
        ttk.Label(dialog_frame, text="Select Scheduling Strategy:").pack(pady=BASE_PADDING['pady']*2)
        self.schedule_strategy_var = tk.StringVar(value="priority_based"); strategies = ["priority_based", "time_optimized", "balanced"]
        strategy_combo = ttk.Combobox(dialog_frame, textvariable=self.schedule_strategy_var, values=strategies, state="readonly"); strategy_combo.pack(pady=BASE_PADDING['pady']); strategy_combo.set("priority_based")
        ttk.Button(dialog_frame, text="Schedule All Pending Tasks", command=self.execute_scheduling).pack(pady=BASE_PADDING['pady']*2)
    def execute_scheduling(self):
        strategy = self.schedule_strategy_var.get();
        if not strategy: messagebox.showerror("Error", "Please select a strategy.", parent=self.scheduler_dialog); return
        try:
            all_tasks = TaskService.get_all_tasks(self.user_id); pending_tasks = [task for task in all_tasks if task.get('status', '').lower() in ['pending', 'scheduled']]
            if not pending_tasks: messagebox.showinfo("No Tasks", "No pending tasks to schedule.", parent=self.scheduler_dialog); self.scheduler_dialog.destroy(); return
            scheduler = SchedulingService(self.user_id); scheduled_info = scheduler.schedule_multiple_tasks(pending_tasks, strategy)
            if scheduled_info: messagebox.showinfo("Success", f"{len(scheduled_info)} tasks scheduled/rescheduled.", parent=self.scheduler_dialog)
            else: messagebox.showwarning("Scheduling", "No tasks were scheduled.", parent=self.scheduler_dialog)
            self.load_tasks(); self.scheduler_dialog.destroy()
        except Exception as e: messagebox.showerror("Scheduling Error", f"Failed: {e}", parent=self.scheduler_dialog); print(f"Error in execute_scheduling: {e}")

class EventView(BaseView):
    def __init__(self, parent, user_id):
        super().__init__(parent, user_id);
        new_event_frame = ttk.LabelFrame(self, text="New Event", padding=LABELFRAME_PADDING); new_event_frame.pack(fill="x", **FRAME_PADDING)
        self.entries = {}

        form_fields = {
            "title": {"label": "Title:", "row": 0, "widget": ttk.Entry},
            "description": {"label": "Description:", "row": 1, "widget": Text, "height": 3},
            "start_date": {"label": "Start Date:", "row": 2, "widget": DateEntry if TKCALENDAR_AVAILABLE else ttk.Entry, "pattern": "yyyy-mm-dd"},
            "start_time": {"label": "Start Time (HH:MM):", "row": 2, "widget": ttk.Entry, "width": 10},
            "end_date": {"label": "End Date:", "row": 3, "widget": DateEntry if TKCALENDAR_AVAILABLE else ttk.Entry, "pattern": "yyyy-mm-dd"},
            "end_time": {"label": "End Time (HH:MM):", "row": 3, "widget": ttk.Entry, "width": 10},
            "location": {"label": "Location:", "row": 4, "widget": ttk.Entry},
            "attendees": {"label": "Attendees (comma-sep):", "row": 5, "widget": ttk.Entry}
        }

        for key, field in form_fields.items():
            ttk.Label(new_event_frame,text=field["label"]).grid(row=field["row"],column=0 if "time" not in key else 2, sticky="w" if "time" not in key else "e", **INPUT_PADDING)
            if field["widget"] == Text: entry = Text(new_event_frame,width=40,height=field["height"],font=TEXT_FONT,relief=tk.SOLID, borderwidth=1)
            elif field["widget"] == DateEntry: entry = DateEntry(new_event_frame,width=18 if "time" in key else 12, date_pattern=field["pattern"],font=ENTRY_FONT, locale='en_US')
            else: entry = ttk.Entry(new_event_frame,width=field.get("width", 40))
            entry.grid(row=field["row"],column=1 if "time" not in key else 3, sticky="ew", **INPUT_PADDING)
            self.entries[key] = entry

        now = datetime.datetime.now()
        if TKCALENDAR_AVAILABLE:
            self.entries["start_date"].set_date(now + datetime.timedelta(hours=1))
            self.entries["end_date"].set_date(now + datetime.timedelta(hours=2))
        else: # Fallback for ttk.Entry
            self.entries["start_date"].insert(0, (now + datetime.timedelta(hours=1)).strftime("%Y-%m-%d"))
            self.entries["end_date"].insert(0, (now + datetime.timedelta(hours=2)).strftime("%Y-%m-%d"))
        self.entries["start_time"].insert(0, (now + datetime.timedelta(hours=1)).strftime("%H:%M"))
        self.entries["end_time"].insert(0, (now + datetime.timedelta(hours=2)).strftime("%H:%M"))

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
        except Exception as ex: messagebox.showerror("Error Loading Events",f"Failed: {ex}")

    def add_event(self):
        title = self.entries["title"].get()
        desc = self.entries["description"].get("1.0", tk.END).strip()
        loc = self.entries["location"].get()
        attendees_str = self.entries["attendees"].get()
        attendees = [a.strip() for a in attendees_str.split(',') if a.strip()] if attendees_str else []

        start_time_str = self.entries["start_time"].get()
        end_time_str = self.entries["end_time"].get()

        if TKCALENDAR_AVAILABLE:
            start_date_obj = self.entries["start_date"].get_date()
            end_date_obj = self.entries["end_date"].get_date()
        else: # Fallback
            try:
                start_date_obj = datetime.datetime.strptime(self.entries["start_date"].get(), "%Y-%m-%d").date()
                end_date_obj = datetime.datetime.strptime(self.entries["end_date"].get(), "%Y-%m-%d").date() if self.entries["end_date"].get() else None
            except ValueError: messagebox.showerror("Error", "Invalid Date format. Use YYYY-MM-DD."); return

        if not title or not start_date_obj or not start_time_str : messagebox.showerror("Error","Title, Start Date, and Start Time required."); return

        try:
            start_time_obj = datetime.datetime.strptime(start_time_str, "%H:%M").time()
            start_datetime = datetime.datetime.combine(start_date_obj, start_time_obj)
            event_data = {"title":title, "description":desc, "location":loc, "attendees":attendees, "start_datetime": start_datetime.isoformat()}

            if end_date_obj and end_time_str:
                end_time_obj = datetime.datetime.strptime(end_time_str, "%H:%M").time()
                end_datetime = datetime.datetime.combine(end_date_obj, end_time_obj)
                event_data["end_datetime"] = end_datetime.isoformat()
            elif end_date_obj: # Only end date provided
                 event_data["end_datetime"] = datetime.datetime.combine(end_date_obj, start_time_obj).isoformat() # Default to same time as start

        except ValueError: messagebox.showerror("Error","Invalid Time format. Use HH:MM."); return

        try: EventService.create_event(self.user_id,event_data); messagebox.showinfo("Success","Event added."); self.load_events()
        except Exception as ex: messagebox.showerror("Error Adding Event",f"Failed: {ex}")
        self.entries["title"].delete(0,tk.END); self.entries["description"].delete("1.0",tk.END); self.entries["location"].delete(0,tk.END); self.entries["attendees"].delete(0,tk.END)


class ChatView(BaseView): # Unchanged
    def __init__(self, parent, user_id):
        super().__init__(parent, user_id);
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
        except Exception as e: self.add_msg("System",f"Error loading history: {e}")
    def send_message_event(self,e): self.send_message()
    def send_message(self):
        msg=self.input_entry.get();
        if not msg.strip(): return
        self.add_msg("You",msg); self.input_entry.delete(0,tk.END)
        self.input_entry.config(state=tk.DISABLED); self.send_button.config(state=tk.DISABLED)
        try:
            hist=kairo_ai.get_conversation_history(self.user_id,limit=10); kairo_ai.log_conversation_message(self.user_id,"user",msg)
            raw=kairo_ai.get_kairo_response(self.user_id,msg,hist); kairo_ai.log_conversation_message(self.user_id,"kairo",raw)
            p=kairo_ai.parse_ai_action(raw)
            if p['action']=='conversation': self.add_msg("Kairo",p['response'])
            else: self.add_msg("Kairo",f"Action: {p['action']} | Details: {p.get('parameters',p.get('response','No details'))}")
        except Exception as e: err_msg=f"Error AI response: {e}"; self.add_msg("System",err_msg); kairo_ai.log_conversation_message(self.user_id,"system_error",err_msg)
        finally: self.input_entry.config(state=tk.NORMAL); self.send_button.config(state=tk.NORMAL); self.input_entry.focus_set()

class SettingsView(BaseView): # Unchanged
    def __init__(self, parent, user_id):
        super().__init__(parent, user_id); self.vars = {}
        frame = ttk.LabelFrame(self, text="User Preferences", padding=LABELFRAME_PADDING); frame.pack(fill=tk.BOTH, expand=True, **FRAME_PADDING)
        settings_fields = [("Theme:", "theme", "dark", ttk.Combobox, ["dark", "light", "system"]),
            ("Kairo's Personality:", "kairo_style", "professional", ttk.Combobox, ["professional", "friendly", "witty"]),
            ("Archive Tasks After (days):", "completed_task_archive_duration", "30", ttk.Entry),
            ("Working Hours Start (HH:MM):", "working_hours_start", "09:00", ttk.Entry),
            ("Working Hours End (HH:MM):", "working_hours_end", "17:00", ttk.Entry),
            ("Notification Prefs (JSON):", "notification_preferences", '{"email": true, "in_app": true}', ttk.Entry)]
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
        settings = SettingsService.get_user_settings(self.user_id)
        for key, var in self.vars.items():
            value = settings.get(key, SettingsService.DEFAULT_SETTINGS.get(key))
            if isinstance(value, dict) or isinstance(value, list): var.set(json.dumps(value))
            else: var.set(str(value))
    def save_settings(self):
        updated_settings = {}
        try:
            for key, var in self.vars.items():
                value = var.get()
                if key == "completed_task_archive_duration": updated_settings[key] = int(value)
                elif key == "notification_preferences":
                    try: updated_settings[key] = json.loads(value)
                    except json.JSONDecodeError: messagebox.showerror("Error","Invalid JSON for Notification Prefs."); return
                else: updated_settings[key] = value
            success = SettingsService.update_user_settings(self.user_id, updated_settings)
            if success: messagebox.showinfo("Success", "Settings saved.")
            else: messagebox.showerror("Error", "Failed to save settings.")
        except ValueError as ve: messagebox.showerror("Error", f"Invalid value: {ve}")
        except Exception as e: messagebox.showerror("Error Saving Settings", f"Unexpected error: {e}")
        self.load_settings()

class LearningView(BaseView): # Unchanged
    def __init__(self, parent, user_id):
        super().__init__(parent, user_id)
        self.learning_service = LearningService()
        session_frame = ttk.LabelFrame(self, text="Create Learning Session", padding=LABELFRAME_PADDING); session_frame.pack(fill=tk.X, **FRAME_PADDING)
        ttk.Label(session_frame, text="Topic:").grid(row=0, column=0, sticky="w", **INPUT_PADDING)
        self.session_topic_entry = ttk.Entry(session_frame, width=40); self.session_topic_entry.grid(row=0, column=1, sticky="ew", **INPUT_PADDING)
        ttk.Label(session_frame, text="Resources (comma-separated):").grid(row=1, column=0, sticky="nw", **INPUT_PADDING)
        self.session_resources_text = Text(session_frame, width=40, height=3, font=TEXT_FONT, relief=tk.SOLID, borderwidth=1); self.session_resources_text.grid(row=1, column=1, sticky="ew", **INPUT_PADDING)
        ttk.Label(session_frame, text="Start (YYYY-MM-DD HH:MM):").grid(row=2, column=0, sticky="w", **INPUT_PADDING)
        self.session_start_time_entry = ttk.Entry(session_frame, width=40); self.session_start_time_entry.grid(row=2, column=1, sticky="ew", **INPUT_PADDING)
        self.session_start_time_entry.insert(0, (datetime.datetime.now() + datetime.timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M"))
        session_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(session_frame, text="Create Session", command=self.create_session).grid(row=3, column=0, columnspan=2, pady=BASE_PADDING['pady']*2)
        content_frame = ttk.LabelFrame(self, text="Get Personalized Learning Content", padding=LABELFRAME_PADDING); content_frame.pack(fill=tk.BOTH, expand=True, **FRAME_PADDING)
        ttk.Label(content_frame, text="Topic:").grid(row=0, column=0, sticky="w", **INPUT_PADDING)
        self.content_topic_entry = ttk.Entry(content_frame, width=40); self.content_topic_entry.grid(row=0, column=1, sticky="ew", **INPUT_PADDING)
        content_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(content_frame, text="Get Content", command=self.get_content).grid(row=1, column=0, columnspan=2, pady=BASE_PADDING['pady'])
        self.content_display_text = Text(content_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=TEXT_FONT, relief=tk.SOLID, borderwidth=1, padx=5, pady=5); self.content_display_text.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=BASE_PADDING['pady']); content_frame.grid_rowconfigure(2, weight=1)
    def create_session(self):
        topic = self.session_topic_entry.get(); resources_str = self.session_resources_text.get("1.0", tk.END).strip(); start_time_str = self.session_start_time_entry.get()
        if not topic or not start_time_str: messagebox.showerror("Error", "Topic and Start Date/Time are required.", parent=self); return
        resources_list = [r.strip() for r in resources_str.split(',') if r.strip()]
        try:
            dt_obj = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M"); iso_start_time_str = dt_obj.isoformat()
            event_details, note_details = self.learning_service.create_learning_session(self.user_id, topic, resources_list, iso_start_time_str)
            messagebox.showinfo("Success", f"Learning session for '{topic}' created.\nEvent ID: {event_details.get('event_id')}\nNote ID: {note_details.get('note_id')}", parent=self)
            self.session_topic_entry.delete(0, tk.END); self.session_resources_text.delete("1.0", tk.END)
        except ValueError: messagebox.showerror("Error", "Invalid Start Date/Time format. Please use YYYY-MM-DD HH:MM.", parent=self)
        except Exception as e: messagebox.showerror("Error Creating Session", f"Failed: {e}", parent=self); print(f"Error in create_session: {e}")
    def get_content(self):
        topic = self.content_topic_entry.get()
        if not topic: messagebox.showerror("Error", "Topic is required.", parent=self); return
        try:
            content = self.learning_service.generate_personalized_content(self.user_id, topic)
            self.content_display_text.config(state=tk.NORMAL); self.content_display_text.delete("1.0", tk.END); self.content_display_text.insert(tk.END, content); self.content_display_text.config(state=tk.DISABLED)
        except Exception as e: messagebox.showerror("Error Getting Content", f"Failed: {e}", parent=self); print(f"Error in get_content: {e}")

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
        s.configure('TCombobox', font=ENTRY_FONT, fieldbackground='white',selectbackground='white', selectforeground=TEXT_COLOR) # Added select colors
        self.root.option_add('*TCombobox*Listbox.font', ENTRY_FONT)
        self.root.option_add('*TCombobox*Listbox.background', 'white')
        self.root.option_add('*TCombobox*Listbox.foreground', TEXT_COLOR)
        self.root.option_add('*Menu.font', APP_FONT); self.root.option_add('*tk.OptionMenu.font', APP_FONT); self.root.option_add('*ttk.OptionMenu*Menubutton.font', APP_FONT)
        self.user_id = UserService.get_current_user_id()
        try: database.init_db(); print("DB initialized.")
        except Exception as e: print(f"DB init error: {e}"); messagebox.showerror("DB Error",f"DB init failed: {e}")
        self.notebook = ttk.Notebook(root)
        views = [(DashboardView, "Dashboard"), (ChatView, "Kairo AI Chat"), (TaskView, "Tasks"), (EventView, "Events"), (LearningView, "Learning Center"), (SettingsView, "Settings")]
        self.views = {}
        for i, (ViewClass, text) in enumerate(views):
            view_instance = ViewClass(self.notebook, self.user_id)
            self.views[text] = view_instance
            if text == "Dashboard": self.notebook.insert(0, view_instance, text=text)
            else: self.notebook.add(view_instance, text=text)
        self.notebook.pack(expand=True,fill='both',**FRAME_PADDING)
        if self.notebook.tabs() and "Dashboard" in self.views: self.notebook.select(self.views["Dashboard"])
        if "Tasks" in self.views: self.views["Tasks"].load_tasks()
        if "Events" in self.views: self.views["Events"].load_events()

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir); print(f"CWD: {os.getcwd()}")
    root = tk.Tk(); app = KairoApp(root)
    def on_closing(): print("Closing app, DB conn closed."); database.close_db_connection(); root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_closing); root.mainloop()
