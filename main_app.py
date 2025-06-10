# main_app.py
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, Text
import database
from user_service import UserService
from services import TaskService, EventService, ReportService
from settings_service import SettingsService # Added SettingsService
import kairo_ai
import os
import datetime
import json # For parsing notification_preferences in SettingsView

class DashboardView(ttk.Frame):
    def __init__(self, parent, user_id):
        super().__init__(parent)
        self.user_id = user_id
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=(10,0))
        self.refresh_button = ttk.Button(top_frame, text="Refresh Dashboard", command=self.load_dashboard_data)
        self.refresh_button.pack(side=tk.LEFT)
        self.summary_text = Text(self, wrap=tk.WORD, state=tk.DISABLED, height=20, font=("Arial", 12), relief=tk.SOLID, borderwidth=1)
        self.summary_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.load_dashboard_data()

    def load_dashboard_data(self):
        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.delete("1.0", tk.END)
        try:
            summary = ReportService.generate_daily_summary(self.user_id)
            self.summary_text.insert(tk.END, summary)
        except Exception as e:
            error_msg = f"Error loading dashboard summary: {str(e)}"
            self.summary_text.insert(tk.END, error_msg)
            print(error_msg)
        finally:
            self.summary_text.config(state=tk.DISABLED)

class TaskView(ttk.Frame):
    def __init__(self, parent, user_id):
        super().__init__(parent)
        self.user_id = user_id
        new_task_frame = ttk.LabelFrame(self, text="New Task")
        new_task_frame.pack(fill="x", padx=10, pady=10)
        fields_info = [
            ("Title:", ttk.Entry, {}),
            ("Description:", ttk.Entry, {}),
            ("Due Date (YYYY-MM-DD HH:MM):", ttk.Entry, {"insert": (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M")}),
            ("Priority:", ttk.OptionMenu, {"variable_name": "priority_var", "options": ["low", "medium", "high"], "default": "medium"})
        ]
        self.entries = {}
        for i, (label_text, widget_type, config) in enumerate(fields_info):
            ttk.Label(new_task_frame, text=label_text).grid(row=i, column=0, padx=5, pady=5, sticky="w")
            if widget_type == ttk.OptionMenu:
                var = tk.StringVar(value=config["default"])
                entry = widget_type(new_task_frame, var, config["default"], *config["options"])
                self.entries[config["variable_name"]] = var # Store the variable
            else:
                entry = widget_type(new_task_frame, width=40)
                if "insert" in config: entry.insert(0, config["insert"])
            entry.grid(row=i, column=1, padx=5, pady=5, sticky="ew")
            if widget_type != ttk.OptionMenu: # Store entry widget directly if not OptionMenu
                 self.entries[label_text.lower().split(" (")[0].replace(":", "").replace(" ", "_")] = entry

        new_task_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(new_task_frame, text="Add Task", command=self.add_task).grid(row=len(fields_info), column=0, columnspan=2, pady=10)

        tasks_frame = ttk.LabelFrame(self, text="Tasks")
        tasks_frame.pack(fill="both", expand=True, padx=10, pady=10)
        columns = ("id", "title", "due_date", "priority", "status")
        self.tree = ttk.Treeview(tasks_frame, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col.replace("_"," ").title());
            self.tree.column(col, width=100 if col not in ["id","title"] else (50 if col=="id" else 200), stretch=(col!="id"))
        self.tree.pack(fill="both", expand=True, side="left")
        scrollbar = ttk.Scrollbar(tasks_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set); scrollbar.pack(side="right", fill="y")
        buttons_frame = ttk.Frame(self)
        buttons_frame.pack(fill='x', padx=10, pady=5)
        ttk.Button(buttons_frame, text="Refresh Tasks", command=self.load_tasks).pack(side="left", padx=5)
        ttk.Button(buttons_frame, text="Mark Complete", command=self.complete_task).pack(side="left", padx=5)

    def load_tasks(self): # Simplified from previous version
        for i in self.tree.get_children(): self.tree.delete(i)
        try:
            for task in TaskService.get_all_tasks(self.user_id):
                due = task.get('due_datetime','N/A');
                if due and isinstance(due,str): due = datetime.datetime.fromisoformat(due).strftime("%Y-%m-%d %H:%M") if len(due)>10 else due
                self.tree.insert("","end",values=(task.get('task_id','N/A')[:8],task.get('title','N/A'),due,task.get('priority','N/A'),task.get('status','N/A')))
        except Exception as e: messagebox.showerror("Error Loading Tasks",f"Failed: {e}")

    def add_task(self):
        data = {name: entry.get() for name, entry in self.entries.items()}
        if not data["title"]: messagebox.showerror("Error","Title required."); return
        task_data = {"title":data["title"], "description":data["description"], "priority":data["priority_var"]}
        if data["due_date"]:
            try: task_data["due_datetime"] = datetime.datetime.strptime(data["due_date"],"%Y-%m-%d %H:%M").isoformat()
            except ValueError:
                try: task_data["due_datetime"] = datetime.datetime.strptime(data["due_date"],"%Y-%m-%d").date().isoformat()
                except ValueError: messagebox.showerror("Error","Invalid date. Use YYYY-MM-DD HH:MM or YYYY-MM-DD."); return
        try: TaskService.create_task(self.user_id,task_data); messagebox.showinfo("Success","Task added."); self.load_tasks()
        except Exception as e: messagebox.showerror("Error Adding Task",f"Failed: {e}")
        for name, entry in self.entries.items():
            if name not in ["priority_var", "due_date"]: entry.delete(0, tk.END)


    def complete_task(self): # Simplified from previous version
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

class EventView(ttk.Frame): # Simplified from previous version
    def __init__(self, parent, user_id):
        super().__init__(parent); self.user_id = user_id
        new_event_frame = ttk.LabelFrame(self, text="New Event"); new_event_frame.pack(fill="x", padx=10, pady=10)
        self.entries = {}; fields=[("Title:",0,False),("Description:",1,True),("Start (YYYY-MM-DD HH:MM):",2,False),("End (YYYY-MM-DD HH:MM):",3,False),("Location:",4,False),("Attendees (comma-sep):",5,False)]
        for text,row,is_text in fields:
            ttk.Label(new_event_frame,text=text).grid(row=row,column=0,padx=5,pady=5,sticky="nw" if is_text else "w")
            entry = Text(new_event_frame,width=40,height=3) if is_text else ttk.Entry(new_event_frame,width=40)
            entry.grid(row=row,column=1,padx=5,pady=5,sticky="ew"); self.entries[text.split(" (")[0].lower().replace(":","").replace(" ","_")] = entry
        self.entries["start"].insert(0,(datetime.datetime.now()+datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"))
        self.entries["end"].insert(0,(datetime.datetime.now()+datetime.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"))
        new_event_frame.grid_columnconfigure(1,weight=1)
        ttk.Button(new_event_frame,text="Add Event",command=self.add_event).grid(row=len(fields),column=0,columnspan=2,pady=10)
        events_frame=ttk.LabelFrame(self,text="Events"); events_frame.pack(fill="both",expand=True,padx=10,pady=10)
        cols=("id","title","start_datetime","end_datetime","location"); self.event_tree=ttk.Treeview(events_frame,columns=cols,show="headings")
        for c in cols: self.event_tree.heading(c,text=c.replace("_"," ").title()); self.event_tree.column(c,width=120 if c not in ["id","title"] else (50 if c=="id" else 200),stretch=(c!="id"))
        self.event_tree.pack(fill="both",expand=True,side="left")
        scroll=ttk.Scrollbar(events_frame,orient="vertical",command=self.event_tree.yview); self.event_tree.configure(yscrollcommand=scroll.set); scroll.pack(side="right",fill="y")
        ttk.Button(self,text="Refresh Events",command=self.load_events).pack(pady=5)

    def _fmt_dt(self,s): return datetime.datetime.fromisoformat(s).strftime("%Y-%m-%d %H:%M") if s and isinstance(s,str) else "N/A"
    def load_events(self):
        for i in self.event_tree.get_children(): self.event_tree.delete(i)
        try:
            for e in EventService.get_all_events(self.user_id): self.event_tree.insert("","end",values=(e.get('event_id','N/A')[:8],e.get('title','N/A'),self._fmt_dt(e.get('start_datetime')),self._fmt_dt(e.get('end_datetime')),e.get('location','N/A')))
        except Exception as ex: messagebox.showerror("Error Loading Events",f"Failed: {ex}")
    def add_event(self):
        d={n:(v.get("1.0",tk.END).strip() if isinstance(v,Text) else v.get()) for n,v in self.entries.items()}
        if not d["title"] or not d["start"]: messagebox.showerror("Error","Title & Start required."); return
        ed={"title":d["title"],"description":d["description"],"location":d["location"],"attendees":[a.strip() for a in d["attendees"].split(',') if a.strip()] if d["attendees"] else []}
        try:
            ed["start_datetime"]=datetime.datetime.strptime(d["start"],"%Y-%m-%d %H:%M").isoformat()
            if d["end"]: ed["end_datetime"]=datetime.datetime.strptime(d["end"],"%Y-%m-%d %H:%M").isoformat()
        except ValueError: messagebox.showerror("Error","Invalid datetime. Use YYYY-MM-DD HH:MM."); return
        try: EventService.create_event(self.user_id,ed); messagebox.showinfo("Success","Event added."); self.load_events()
        except Exception as ex: messagebox.showerror("Error Adding Event",f"Failed: {ex}")
        for n,e in self.entries.items():
            if n not in ["start","end"]: (e.delete("1.0",tk.END) if isinstance(e,Text) else e.delete(0,tk.END))

class ChatView(ttk.Frame): # Simplified from previous version
    def __init__(self, parent, user_id):
        super().__init__(parent); self.user_id = user_id
        self.history_text=Text(self,wrap=tk.WORD,state=tk.DISABLED,height=20,relief=tk.SOLID,borderwidth=1); self.history_text.pack(fill=tk.BOTH,expand=True,padx=10,pady=(10,0))
        input_frame=ttk.Frame(self); input_frame.pack(fill=tk.X,padx=10,pady=10)
        self.input_entry=ttk.Entry(input_frame,width=70); self.input_entry.pack(side=tk.LEFT,fill=tk.X,expand=True,ipady=4); self.input_entry.bind("<Return>",self.send_message_event)
        self.send_button=ttk.Button(input_frame,text="Send",command=self.send_message); self.send_button.pack(side=tk.RIGHT,padx=(5,0))
        self.load_initial_history()
    def add_msg(self,s,m): self.history_text.config(state=tk.NORMAL); stag=f"{s}_tag"; self.history_text.tag_configure(stag,font=('TkDefaultFont',10,'bold')); self.history_text.insert(tk.END,f"{s}",stag); self.history_text.insert(tk.END,f": {m}\n\n"); self.history_text.config(state=tk.DISABLED); self.history_text.see(tk.END)
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

class SettingsView(ttk.Frame):
    def __init__(self, parent, user_id):
        super().__init__(parent)
        self.user_id = user_id
        self.vars = {} # To store StringVars

        frame = ttk.LabelFrame(self, text="User Preferences", padding=(10,10))
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Define settings fields: (label, key_name, default_value, widget_type (optional))
        settings_fields = [
            ("Theme:", "theme", "dark", ttk.Combobox, ["dark", "light", "system"]),
            ("Kairo's Personality:", "kairo_style", "professional", ttk.Combobox, ["professional", "friendly", "witty"]),
            ("Archive Tasks After (days):", "completed_task_archive_duration", "30", ttk.Entry),
            ("Working Hours Start (HH:MM):", "working_hours_start", "09:00", ttk.Entry),
            ("Working Hours End (HH:MM):", "working_hours_end", "17:00", ttk.Entry),
            # Notification preferences might be more complex (e.g., checkboxes in a subframe)
            # For simplicity, using an Entry for JSON string or a simplified representation.
            ("Notification Prefs (JSON):", "notification_preferences", '{"email": true, "in_app": true}', ttk.Entry)
        ]

        for i, field_info in enumerate(settings_fields):
            label_text, key, default, widget_type, *widget_config = field_info
            ttk.Label(frame, text=label_text).grid(row=i, column=0, padx=5, pady=8, sticky="w")

            var = tk.StringVar()
            self.vars[key] = var

            if widget_type == ttk.Combobox:
                entry = ttk.Combobox(frame, textvariable=var, values=widget_config[0], width=37)
                entry.set(default) # Set default for combobox
            else: # ttk.Entry
                entry = ttk.Entry(frame, textvariable=var, width=40)
            entry.grid(row=i, column=1, padx=5, pady=8, sticky="ew")

        frame.grid_columnconfigure(1, weight=1)

        save_button = ttk.Button(frame, text="Save Settings", command=self.save_settings)
        save_button.grid(row=len(settings_fields), column=0, columnspan=2, pady=20)

        self.load_settings()

    def load_settings(self):
        settings = SettingsService.get_user_settings(self.user_id)
        for key, var in self.vars.items():
            value = settings.get(key, SettingsService.DEFAULT_SETTINGS.get(key))
            if isinstance(value, dict) or isinstance(value, list): # For JSON fields like notification_preferences
                var.set(json.dumps(value))
            else:
                var.set(str(value)) # Ensure it's a string for StringVar

    def save_settings(self):
        updated_settings = {}
        try:
            for key, var in self.vars.items():
                value = var.get()
                if key == "completed_task_archive_duration":
                    updated_settings[key] = int(value)
                elif key == "notification_preferences":
                    try: updated_settings[key] = json.loads(value) # Parse JSON string back to dict
                    except json.JSONDecodeError: messagebox.showerror("Error","Invalid JSON for Notification Prefs."); return
                else:
                    updated_settings[key] = value

            success = SettingsService.update_user_settings(self.user_id, updated_settings)
            if success:
                messagebox.showinfo("Success", "Settings saved successfully.")
            else:
                messagebox.showerror("Error", "Failed to save settings.")
        except ValueError as ve: # For int conversion
            messagebox.showerror("Error", f"Invalid value for number field: {ve}")
        except Exception as e:
            messagebox.showerror("Error Saving Settings", f"An unexpected error occurred: {e}")

        self.load_settings() # Refresh displayed settings


class KairoApp:
    def __init__(self, root):
        self.root = root; self.root.title("Kairo AI Assistant"); self.root.geometry("950x750")
        self.user_id = UserService.get_current_user_id()
        try: database.init_db(); print("DB initialized.")
        except Exception as e: print(f"DB init error: {e}"); messagebox.showerror("DB Error",f"DB init failed: {e}")
        self.notebook = ttk.Notebook(root)

        views = [
            (DashboardView, "Dashboard"), (ChatView, "Kairo AI Chat"),
            (TaskView, "Tasks"), (EventView, "Events"), (SettingsView, "Settings")
        ]
        self.views = {}

        for i, (ViewClass, text) in enumerate(views):
            view_instance = ViewClass(self.notebook, self.user_id)
            self.views[text] = view_instance
            if i == 0: # Insert first tab differently to make it the default selected
                 self.notebook.insert(0, view_instance, text=text)
            else:
                 self.notebook.add(view_instance, text=text)

        self.notebook.pack(expand=True,fill='both',padx=10,pady=10)
        if self.notebook.tabs(): self.notebook.select(self.views["Dashboard"]) # Select Dashboard

        # Initial data loads for views that need it (Dashboard, Chat, Settings load their own)
        if "Tasks" in self.views: self.views["Tasks"].load_tasks()
        if "Events" in self.views: self.views["Events"].load_events()


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir); print(f"CWD: {os.getcwd()}")
    root = tk.Tk(); app = KairoApp(root)
    def on_closing(): print("Closing app, DB conn closed."); database.close_db_connection(); root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_closing); root.mainloop()
