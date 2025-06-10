# main_app.py
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, Text
import database
from user_service import UserService
from services import TaskService, EventService, ReportService
from settings_service import SettingsService
import kairo_ai
import os
import datetime
import json

# --- Constants for UI Refinement ---
BASE_PADDING = {'padx': 8, 'pady': 4}
INPUT_PADDING = {'padx': 5, 'pady': 5}
FRAME_PADDING = {'padx': 10, 'pady': 5}
LABELFRAME_PADDING = (10, 5) # Padding inside LabelFrame

APP_FONT_FAMILY = "Arial" # Changed from "Calibri" to "Arial" for wider compatibility
APP_FONT_SIZE = 10
APP_FONT = (APP_FONT_FAMILY, APP_FONT_SIZE)
TITLE_FONT_SIZE = 12
TITLE_FONT = (APP_FONT_FAMILY, TITLE_FONT_SIZE, "bold")
TEXT_FONT = (APP_FONT_FAMILY, APP_FONT_SIZE) # For tk.Text widgets
ENTRY_FONT = (APP_FONT_FAMILY, APP_FONT_SIZE) # For ttk.Entry, ttk.Combobox

BG_COLOR = "#FAFAFA" # Light gray background
TEXT_COLOR = "#212121" # Dark gray for text
BORDER_COLOR = "#E0E0E0" # Lighter border color
HIGHLIGHT_THICKNESS = 0 # Remove default highlight for Text widgets
BORDER_WIDTH = 0 # Remove default border for Text widgets, using relief=tk.FLAT

class BaseView(ttk.Frame):
    def __init__(self, parent, user_id, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.user_id = user_id
        # self.configure(style='App.TFrame') # Apply a base style for frames if defined via ttk.Style

class DashboardView(BaseView):
    def __init__(self, parent, user_id):
        super().__init__(parent, user_id)

        top_frame = ttk.Frame(self) # Removed style='App.TFrame' for simplicity, can be added
        top_frame.pack(fill=tk.X, padx=FRAME_PADDING['padx'], pady=(FRAME_PADDING['pady'], 0))

        self.refresh_button = ttk.Button(top_frame, text="Refresh Dashboard", command=self.load_dashboard_data)
        self.refresh_button.pack(side=tk.LEFT, **BASE_PADDING)

        self.summary_text = Text(self, wrap=tk.WORD, state=tk.DISABLED, height=20,
                                 font=TEXT_FONT, relief=tk.FLAT,
                                 highlightthickness=HIGHLIGHT_THICKNESS, borderwidth=BORDER_WIDTH,
                                 padx=5, pady=5, bg=BG_COLOR, fg=TEXT_COLOR)
        self.summary_text.pack(fill=tk.BOTH, expand=True, **FRAME_PADDING)

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

class TaskView(BaseView):
    def __init__(self, parent, user_id):
        super().__init__(parent, user_id)

        new_task_frame = ttk.LabelFrame(self, text="New Task", padding=LABELFRAME_PADDING)
        new_task_frame.pack(fill="x", **FRAME_PADDING)

        fields_info = [
            ("Title:", ttk.Entry, {}), ("Description:", ttk.Entry, {}),
            ("Due Date (YYYY-MM-DD HH:MM):", ttk.Entry, {"insert": (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M")}),
            ("Priority:", ttk.OptionMenu, {"variable_name": "priority_var", "options": ["low", "medium", "high"], "default": "medium"})
        ]
        self.entries = {}
        for i, (label_text, widget_type, config) in enumerate(fields_info):
            label = ttk.Label(new_task_frame, text=label_text) # Font set by global style
            label.grid(row=i, column=0, sticky="w", **INPUT_PADDING)
            if widget_type == ttk.OptionMenu:
                var = tk.StringVar(value=config["default"])
                # OptionMenu does not directly support font via constructor in all ttk themes, style it globally
                entry = widget_type(new_task_frame, var, config["default"], *config["options"])
                self.entries[config["variable_name"]] = var
            else:
                entry = widget_type(new_task_frame, width=40) # Font set by global style
                if "insert" in config: entry.insert(0, config["insert"])
            entry.grid(row=i, column=1, sticky="ew", **INPUT_PADDING)
            if widget_type != ttk.OptionMenu:
                 self.entries[label_text.lower().split(" (")[0].replace(":", "").replace(" ", "_")] = entry
        new_task_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(new_task_frame, text="Add Task", command=self.add_task).grid(row=len(fields_info), column=0, columnspan=2, pady=BASE_PADDING['pady']*2)

        tasks_frame = ttk.LabelFrame(self, text="Tasks", padding=LABELFRAME_PADDING)
        tasks_frame.pack(fill="both", expand=True, **FRAME_PADDING)
        columns = ("id", "title", "due_date", "priority", "status")
        self.tree = ttk.Treeview(tasks_frame, columns=columns, show="headings") # Heading font set by global style
        for col in columns:
            self.tree.heading(col, text=col.replace("_"," ").title())
            self.tree.column(col, width=100 if col not in ["id","title"] else (50 if col=="id" else 200), stretch=(col!="id"))
        self.tree.pack(fill="both", expand=True, side="left", **BASE_PADDING)
        scrollbar = ttk.Scrollbar(tasks_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set); scrollbar.pack(side="right", fill="y")

        buttons_frame = ttk.Frame(self)
        buttons_frame.pack(fill='x', **FRAME_PADDING)
        ttk.Button(buttons_frame, text="Refresh Tasks", command=self.load_tasks).pack(side="left", **BASE_PADDING)
        ttk.Button(buttons_frame, text="Mark Complete", command=self.complete_task).pack(side="left", **BASE_PADDING)

    def load_tasks(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        try:
            for task in TaskService.get_all_tasks(self.user_id):
                due = task.get('due_datetime','N/A');
                if due and isinstance(due,str) and len(due) > 10: # Check if it's likely a full datetime string
                    try: due = datetime.datetime.fromisoformat(due).strftime("%Y-%m-%d %H:%M")
                    except ValueError: pass # Keep original if not ISO parsable
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
        for name, entry_widget_or_var in self.entries.items():
            if name not in ["priority_var", "due_date"]: # due_date has default, priority_var is tk.StringVar
                if hasattr(entry_widget_or_var, 'delete'): entry_widget_or_var.delete(0, tk.END)

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

class EventView(BaseView):
    def __init__(self, parent, user_id):
        super().__init__(parent, user_id)
        new_event_frame = ttk.LabelFrame(self, text="New Event", padding=LABELFRAME_PADDING); new_event_frame.pack(fill="x", **FRAME_PADDING)
        self.entries = {}; fields=[("Title:",0,False),("Description:",1,True),("Start (YYYY-MM-DD HH:MM):",2,False),("End (YYYY-MM-DD HH:MM):",3,False),("Location:",4,False),("Attendees (comma-sep):",5,False)]
        for text,row,is_text in fields:
            ttk.Label(new_event_frame,text=text).grid(row=row,column=0,sticky="nw" if is_text else "w", **INPUT_PADDING) # Font from global
            entry = Text(new_event_frame,width=40,height=3,font=TEXT_FONT,relief=tk.SOLID, borderwidth=1, highlightthickness=HIGHLIGHT_THICKNESS) if is_text else ttk.Entry(new_event_frame,width=40) # Font from global
            entry.grid(row=row,column=1,sticky="ew", **INPUT_PADDING); self.entries[text.split(" (")[0].lower().replace(":","").replace(" ","_")] = entry
        self.entries["start"].insert(0,(datetime.datetime.now()+datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"))
        self.entries["end"].insert(0,(datetime.datetime.now()+datetime.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"))
        new_event_frame.grid_columnconfigure(1,weight=1)
        ttk.Button(new_event_frame,text="Add Event",command=self.add_event).grid(row=len(fields),column=0,columnspan=2,pady=BASE_PADDING['pady']*2)

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
        for n,e_widget in self.entries.items(): # Renamed to avoid conflict
            if n not in ["start","end"]: (e_widget.delete("1.0",tk.END) if isinstance(e_widget,Text) else e_widget.delete(0,tk.END))

class ChatView(BaseView):
    def __init__(self, parent, user_id):
        super().__init__(parent, user_id)
        self.history_text=Text(self,wrap=tk.WORD,state=tk.DISABLED,height=20,font=TEXT_FONT, relief=tk.FLAT, highlightthickness=HIGHLIGHT_THICKNESS, borderwidth=BORDER_WIDTH, padx=5,pady=5, bg=BG_COLOR, fg=TEXT_COLOR);
        self.history_text.pack(fill=tk.BOTH,expand=True,padx=FRAME_PADDING['padx'],pady=(FRAME_PADDING['pady'],0))

        input_frame=ttk.Frame(self); input_frame.pack(fill=tk.X,padx=FRAME_PADDING['padx'],pady=FRAME_PADDING['pady'])
        self.input_entry=ttk.Entry(input_frame,width=70); # Font from global style
        self.input_entry.pack(side=tk.LEFT,fill=tk.X,expand=True,ipady=4, **INPUT_PADDING);
        self.input_entry.bind("<Return>",self.send_message_event)
        self.send_button=ttk.Button(input_frame,text="Send",command=self.send_message);
        self.send_button.pack(side=tk.RIGHT,padx=(INPUT_PADDING['padx'],0)) # No pady for button in same line
        self.load_initial_history()

    def add_msg(self,s,m):
        self.history_text.config(state=tk.NORMAL);
        stag=f"{s}_tag";
        self.history_text.tag_configure(stag,font=(APP_FONT_FAMILY, APP_FONT_SIZE, 'bold')); # Use defined font
        self.history_text.insert(tk.END,f"{s}",stag);
        self.history_text.insert(tk.END,f": {m}\n\n");
        self.history_text.config(state=tk.DISABLED);
        self.history_text.see(tk.END)

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

class SettingsView(BaseView):
    def __init__(self, parent, user_id):
        super().__init__(parent, user_id)
        self.vars = {}

        frame = ttk.LabelFrame(self, text="User Preferences", padding=LABELFRAME_PADDING)
        frame.pack(fill=tk.BOTH, expand=True, **FRAME_PADDING)

        settings_fields = [
            ("Theme:", "theme", "dark", ttk.Combobox, ["dark", "light", "system"]),
            ("Kairo's Personality:", "kairo_style", "professional", ttk.Combobox, ["professional", "friendly", "witty"]),
            ("Archive Tasks After (days):", "completed_task_archive_duration", "30", ttk.Entry),
            ("Working Hours Start (HH:MM):", "working_hours_start", "09:00", ttk.Entry),
            ("Working Hours End (HH:MM):", "working_hours_end", "17:00", ttk.Entry),
            ("Notification Prefs (JSON):", "notification_preferences", '{"email": true, "in_app": true}', ttk.Entry)
        ]

        for i, field_info in enumerate(settings_fields):
            label_text, key, default, widget_type, *widget_config = field_info
            label = ttk.Label(frame, text=label_text) # Font from global style
            label.grid(row=i, column=0, sticky="w", **INPUT_PADDING)
            var = tk.StringVar()
            self.vars[key] = var
            if widget_type == ttk.Combobox: # Font from global style for Combobox text, values from widget_config
                entry = ttk.Combobox(frame, textvariable=var, values=widget_config[0], width=37)
                entry.set(default)
            else: # ttk.Entry, font from global style
                entry = ttk.Entry(frame, textvariable=var, width=40)
            entry.grid(row=i, column=1, sticky="ew", **INPUT_PADDING)
        frame.grid_columnconfigure(1, weight=1)
        save_button = ttk.Button(frame, text="Save Settings", command=self.save_settings)
        save_button.grid(row=len(settings_fields), column=0, columnspan=2, pady=BASE_PADDING['pady']*4) # More pady
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

class KairoApp:
    def __init__(self, root):
        self.root = root; self.root.title("Kairo AI Assistant"); self.root.geometry("950x750")
        self.root.configure(bg=BG_COLOR) # Set root background

        # --- Style Configuration ---
        s = ttk.Style()
        s.configure('.', font=APP_FONT, background=BG_COLOR, foreground=TEXT_COLOR)
        s.configure('TFrame', background=BG_COLOR) # Ensure frames also get BG
        s.configure('TLabel', background=BG_COLOR, foreground=TEXT_COLOR, font=APP_FONT)
        s.configure('TLabelFrame', background=BG_COLOR, bordercolor=BORDER_COLOR)
        s.configure('TLabelFrame.Label', background=BG_COLOR, foreground=TEXT_COLOR, font=TITLE_FONT) # LabelFrame title
        s.configure('TNotebook', background=BG_COLOR, bordercolor=BORDER_COLOR)
        s.configure('TNotebook.Tab', font=APP_FONT, padding=[10, 5], background=BG_COLOR, foreground=TEXT_COLOR)
        s.map('TNotebook.Tab', background=[('selected', BG_COLOR)], foreground=[('selected', TEXT_COLOR)]) # Keep selected tab consistent
        s.configure('Treeview.Heading', font=TITLE_FONT) # Treeview header
        s.configure('Treeview', fieldbackground=BG_COLOR, foreground=TEXT_COLOR) # Treeview rows
        s.configure('TButton', font=APP_FONT, padding=[8, 4]) # Adjusted padding
        s.configure('TEntry', font=ENTRY_FONT, fieldbackground='white') # Entry fields
        s.configure('TCombobox', font=ENTRY_FONT, fieldbackground='white') # Combobox fields
        # For OptionMenu, font styling is more complex as it's based on underlying tk.Menu
        # Often, direct font configuration on ttk.OptionMenu doesn't work as expected.
        # We can try to set it for the Menubutton part if possible.
        self.root.option_add('*TCombobox*Listbox.font', ENTRY_FONT) # For Combobox dropdown list
        self.root.option_add('*Menu.font', APP_FONT) # For OptionMenu dropdown (might not always work)
        self.root.option_add('*tk.OptionMenu.font', APP_FONT) # Another attempt for OptionMenu text
        self.root.option_add('*ttk.OptionMenu*Menubutton.font', APP_FONT)


        self.user_id = UserService.get_current_user_id()
        try: database.init_db(); print("DB initialized.")
        except Exception as e: print(f"DB init error: {e}"); messagebox.showerror("DB Error",f"DB init failed: {e}")

        self.notebook = ttk.Notebook(root)
        # Apply a style to the notebook itself if needed, e.g. s.configure('My.TNotebook')

        views = [
            (DashboardView, "Dashboard"), (ChatView, "Kairo AI Chat"),
            (TaskView, "Tasks"), (EventView, "Events"), (SettingsView, "Settings")
        ]
        self.views = {}

        for i, (ViewClass, text) in enumerate(views):
            # Pass the style to the view if BaseView is configured to use it
            view_instance = ViewClass(self.notebook, self.user_id)
            self.views[text] = view_instance
            if i == 0: self.notebook.insert(0, view_instance, text=text)
            else: self.notebook.add(view_instance, text=text)

        self.notebook.pack(expand=True,fill='both',**FRAME_PADDING) # Consistent padding for notebook
        if self.notebook.tabs(): self.notebook.select(self.views["Dashboard"])

        if "Tasks" in self.views: self.views["Tasks"].load_tasks()
        if "Events" in self.views: self.views["Events"].load_events()

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir); print(f"CWD: {os.getcwd()}")
    root = tk.Tk(); app = KairoApp(root)
    def on_closing(): print("Closing app, DB conn closed."); database.close_db_connection(); root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_closing); root.mainloop()
