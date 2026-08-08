"""
CatSprayer Graphical User Interface Dashboard
"""

from __future__ import annotations

import os
import sys
import time
import threading
import queue
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk, ImageDraw

# Import our unified path rule from the paths system
from catsprayer.paths import VIDEOS_DIR
from catsprayer.config import save_detector_settings
from catsprayer import stats
from catsprayer.logger import get_logger

logger = get_logger(__name__)

class CatSprayerGUI:

    def __init__(self, root: tk.Tk, camera, detector, sprayer, event_recorder):
        self.root = root
        self.camera = camera
        self.detector = detector
        self.sprayer = sprayer
        self.event_recorder = event_recorder

        # Config paths absolute to project runtime root (using centralized paths module)
        self.video_dir = VIDEOS_DIR
        os.makedirs(self.video_dir, exist_ok=True)

        # Application State
        self.current_mode = "LIVE"
        self.current_playback_file = None
        self.cap = None
        
        # New Feature State Tracking
        self.is_looping_new_clip = False
        self.delete_timer_id = None
        self.delete_countdown_ticks = 0
        self.restart_requested = False

        # Slow-motion playback (clips only, not live view). Rather than
        # slowing the whole update_loop's redraw cadence (which would make
        # button state / other UI feel sluggish too), a new frame is only
        # actually read from the clip every SLOW_MOTION_DIVISOR ticks; the
        # rest of the time the last-read frame is redisplayed. Keeps the UI
        # redraw rate constant while the video content itself plays slower.
        self.slow_motion_enabled = False
        self.SLOW_MOTION_DIVISOR = 4
        self._playback_tick_counter = 0
        self._last_playback_frame = None

        # Threading Shared State Cache
        self.running = True
        self.hardware_state = {
            "cat_detected": False,
            "confidence": 0.0,
            "live_frame": None,
            "in_zone": False,
            "active_trigger_indices": [],
            "active_exclusion_indices": [],
        }
        self.state_lock = threading.Lock()

        # _hardware_worker_loop stall watchdog -- tracks consecutive failures
        # and how long it's been since a successful reading, so a sustained
        # camera/detector stall gets one clear log entry instead of either
        # total silence or thousands of repeated tracebacks.
        self._hw_consecutive_errors = 0
        self._hw_last_success_time = time.time()
        self._hw_stall_logged = False

        # Separate watchdog for a *silent* stall: the AI inference channel
        # can go quiet (get_outputs() never returns again) without ever
        # raising a Python exception, since that happens at the libcamera/
        # hardware layer -- the loop above wouldn't catch this at all on
        # its own. Checked from the background thread, but the actual
        # restart is only ever triggered from the main thread (in
        # update_loop), since Tkinter calls aren't safe to make directly
        # from a background thread.
        self.AI_STALL_RESTART_SECONDS = 60
        self._ai_stall_restart_requested = False

        # Spray/Exclusion Zones (each a normalized 0.0-1.0 rect x1,y1,x2,y2).
        # A cat is eligible to trigger the sprayer if it's centered inside at
        # least one spray zone (or there are none, meaning the whole frame
        # counts), AND not centered inside any exclusion zone. Source of
        # truth on startup is whatever the detector was constructed with
        # (see pyproject.toml [tool.catsprayer.detector]).
        self.spray_zones = list(self.detector.trigger_zones)
        self.exclusion_zones = list(self.detector.exclusion_zones)
        # Ordered history of ("spray"|"exclusion", zone) for the Undo button.
        self.zone_history = []
        # None, "spray", or "exclusion" -- which kind of zone a drag will add.
        self.zone_edit_mode = None
        self._zone_drag_start_px = None
        self._zone_drag_current_px = None

        # Set up window layout
        self.root.title("CatSprayer Intelligent Dashboard")
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="#1e1e1e")

        # Main horizontal pane split
        self.main_pane = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL, bg="#1e1e1e", bd=0, sashwidth=4
        )
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        # Left Container (Video Frame Viewport)
        self.video_container = tk.Frame(self.main_pane, bg="#111111")
        self.main_pane.add(self.video_container, stretch="always")

        self.video_label = tk.Label(self.video_container, bg="#111111")
        self.video_label.pack(fill=tk.BOTH, expand=True)

        self.video_label.bind("<ButtonPress-1>", self._on_zone_press)
        self.video_label.bind("<B1-Motion>", self._on_zone_drag)
        self.video_label.bind("<ButtonRelease-1>", self._on_zone_release)

        # Right Container (Control Sidebar)
        self.sidebar = tk.Frame(self.main_pane, bg="#2d2d2d", width=350)
        self.main_pane.add(self.sidebar, stretch="never")

        self._build_sidebar_widgets()

        # Keyboard short-circuit listeners
        self.root.bind("<q>", lambda e: self.quit_application())
        self.root.bind("<Escape>", lambda e: self.quit_application())

        # Force Tkinter to map layout geometries before starting threads
        self.root.update_idletasks()

        # Start the background hardware thread
        self.hardware_thread = threading.Thread(target=self._hardware_worker_loop, daemon=True)
        self.hardware_thread.start()

        # Start background UI loops
        self.video_watcher_loop()
        self.update_loop()

    def _build_sidebar_widgets(self):
        # BOTTOM ANCHORS FIRST (Forces them into view)
        self.context_frame = tk.Frame(self.sidebar, bg="#2d2d2d")
        self.context_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=(5, 15))

        # 1. New Clip Decision Panel Layout
        self.review_panel = tk.Frame(self.context_frame, bg="#2d2d2d")
        
        tk.Label(
            self.review_panel,
            text="NEW RECORDING ACTIONS",
            font=("Arial", 9, "bold"),
            fg="#FFD54F",
            bg="#2d2d2d"
        ).pack(fill=tk.X, pady=(0, 2))

        row1 = tk.Frame(self.review_panel, bg="#2d2d2d")
        row1.pack(fill=tk.X)
        tk.Button(row1, text="Keep", bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), pady=4, command=self.action_keep).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=2)
        tk.Button(row1, text="Favorite ⭐", bg="#FFB300", fg="black", font=("Arial", 11, "bold"), pady=4, command=self.action_favorite_and_keep).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=2)

        row2 = tk.Frame(self.review_panel, bg="#2d2d2d")
        row2.pack(fill=tk.X)
        tk.Button(row2, text="Delete", bg="#D32F2F", fg="white", font=("Arial", 11, "bold"), pady=4, command=self.action_immediate_delete).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=2)
        tk.Button(row2, text="Decide Later", bg="#78909C", fg="white", font=("Arial", 11, "bold"), pady=4, command=self.action_decide_later).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=2)

        # Shared bar shown alongside EITHER review_panel or playback_panel --
        # slow motion is useful when reviewing new/queued clips too, not
        # just regular archive playback.
        self.slow_motion_bar = tk.Frame(self.context_frame, bg="#2d2d2d")

        self.btn_slow_motion = tk.Button(
            self.slow_motion_bar,
            text="🐢 Slow Motion: Off",
            font=("Arial", 11, "bold"),
            bg="#37474F",
            fg="white",
            command=self.toggle_slow_motion,
        )
        self.btn_slow_motion.pack(fill=tk.X, pady=2)

        # 2. Standard Playback Manipulation Panel
        self.playback_panel = tk.Frame(self.context_frame, bg="#2d2d2d")
        
        self.btn_favorite = tk.Button(
            self.playback_panel,
            text="❤️ Add / Remove Favorite",
            font=("Arial", 11, "bold"),
            bg="#37474F",
            fg="white",
            command=self.toggle_favorite_status,
        )
        self.btn_favorite.pack(fill=tk.X, pady=2)

        self.btn_delete_hold = tk.Button(
            self.playback_panel,
            text="⚠️ Hold 3s to Delete",
            font=("Arial", 11, "bold"),
            bg="#b71c1c",
            fg="white",
            activebackground="#ef5350",
            activeforeground="white"
        )
        self.btn_delete_hold.pack(fill=tk.X, pady=2)
        
        self.btn_delete_hold.bind("<ButtonPress-1>", self._on_delete_press)
        self.btn_delete_hold.bind("<ButtonRelease-1>", self._on_delete_release)

        # TOP ANCHORS SECOND (Fills out upper space remaining)
        self.status_frame = tk.Frame(self.sidebar, bg="#3d3d3d", height=70)
        self.status_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        self.status_title = tk.Label(
            self.status_frame,
            text="SYSTEM ONLINE",
            font=("Arial", 14, "bold"),
            fg="#4CAF50",
            bg="#3d3d3d",
        )
        self.status_title.pack(pady=3)

        self.status_desc = tk.Label(
            self.status_frame,
            text="Mode: Live Feed Tracking",
            font=("Arial", 10),
            fg="#cccccc",
            bg="#3d3d3d",
        )
        self.status_desc.pack(pady=1)

        tk.Label(
            self.sidebar,
            text="VIEW SELECTOR",
            font=("Arial", 9, "bold"),
            fg="#888888",
            bg="#2d2d2d",
        ).pack(side=tk.TOP, anchor="w", padx=15, pady=(5, 1))

        self.btn_live = tk.Button(
            self.sidebar,
            text="🎥 Live Camera Feed",
            font=("Arial", 11, "bold"),
            bg="#455A64",
            fg="white",
            command=self.set_mode_live,
        )
        self.btn_live.pack(side=tk.TOP, fill=tk.X, padx=15, pady=2)

        self.btn_all = tk.Button(
            self.sidebar,
            text="📂 Play All Clips",
            font=("Arial", 11),
            bg="#37474F",
            fg="white",
            command=self.set_mode_all,
        )
        self.btn_all.pack(side=tk.TOP, fill=tk.X, padx=15, pady=2)

        self.btn_favs = tk.Button(
            self.sidebar,
            text="⭐ Play Favorites Only",
            font=("Arial", 11),
            bg="#37474F",
            fg="white",
            command=self.set_mode_favs,
        )
        self.btn_favs.pack(side=tk.TOP, fill=tk.X, padx=15, pady=2)

        self.btn_queue = tk.Button(
            self.sidebar,
            text="🆕 Review Queue",
            font=("Arial", 11),
            bg="#37474F",
            fg="white",
            command=self.set_mode_queue,
        )
        self.btn_queue.pack(side=tk.TOP, fill=tk.X, padx=15, pady=2)

        zone_add_row = tk.Frame(self.sidebar, bg="#2d2d2d")
        zone_add_row.pack(side=tk.TOP, fill=tk.X, padx=15, pady=(2, 2))

        self.btn_add_spray_zone = tk.Button(
            zone_add_row,
            text="➕ Spray Zone",
            font=("Arial", 10),
            bg="#37474F",
            fg="white",
            command=lambda: self.set_zone_edit_mode("spray"),
        )
        self.btn_add_spray_zone.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        self.btn_add_exclusion_zone = tk.Button(
            zone_add_row,
            text="🚫 Exclusion Zone",
            font=("Arial", 10),
            bg="#37474F",
            fg="white",
            command=lambda: self.set_zone_edit_mode("exclusion"),
        )
        self.btn_add_exclusion_zone.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        zone_manage_row = tk.Frame(self.sidebar, bg="#2d2d2d")
        zone_manage_row.pack(side=tk.TOP, fill=tk.X, padx=15, pady=(0, 8))

        self.btn_undo_zone = tk.Button(
            zone_manage_row,
            text="↩️ Undo Last",
            font=("Arial", 10),
            bg="#546E7A",
            fg="white",
            command=self.undo_last_zone,
        )
        self.btn_undo_zone.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        self.btn_clear_zones = tk.Button(
            zone_manage_row,
            text="🗑️ Clear All",
            font=("Arial", 10),
            bg="#546E7A",
            fg="white",
            command=self.clear_all_zones,
        )
        self.btn_clear_zones.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        self.btn_settings = tk.Button(
            self.sidebar,
            text="⚙️ Detector Settings",
            font=("Arial", 11),
            bg="#37474F",
            fg="white",
            command=self.open_settings_window,
        )
        self.btn_settings.pack(side=tk.TOP, fill=tk.X, padx=15, pady=(0, 4))

        self.btn_stats = tk.Button(
            self.sidebar,
            text="📊 Spray Stats",
            font=("Arial", 11),
            bg="#37474F",
            fg="white",
            command=self.open_stats_window,
        )
        self.btn_stats.pack(side=tk.TOP, fill=tk.X, padx=15, pady=(0, 8))

        tk.Label(
            self.sidebar,
            text="RECORDED CLIPS",
            font=("Arial", 9, "bold"),
            fg="#888888",
            bg="#2d2d2d",
        ).pack(side=tk.TOP, anchor="w", padx=15, pady=(8, 1))

        list_frame = tk.Frame(self.sidebar, bg="#2d2d2d")
        list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=15, pady=2)

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg="#1e1e1e",
            fg="#ffffff",
            selectbackground="#0288D1",
            font=("Arial", 11),
            bd=0,
            highlightthickness=0,
        )
        scrollbar.config(command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_clip_selected)

        self.refresh_video_list()
        self._show_appropriate_controls()

    def open_settings_window(self):
        win = tk.Toplevel(self.root)
        win.title("Detector Settings")
        win.configure(bg="#2d2d2d")
        win.geometry("440x510")
        win.transient(self.root)
        win.grab_set()

        # label -> [current_value] (mutable single-element list so the
        # nested functions below can read/update it without needing globals)
        values = {}

        def add_stepper(label_text, initial_value, step, min_val, max_val, row, is_int=False, fmt="{:.2f}"):
            tk.Label(
                win, text=label_text, font=("Arial", 11), fg="white", bg="#2d2d2d", anchor="w"
            ).grid(row=row, column=0, sticky="w", padx=15, pady=8)

            control = tk.Frame(win, bg="#2d2d2d")
            control.grid(row=row, column=1, sticky="e", padx=15, pady=8)

            values[label_text] = [initial_value]
            value_label = tk.Label(
                control, text="", font=("Arial", 12, "bold"), fg="white", bg="#37474F", width=7,
            )

            def refresh():
                v = values[label_text][0]
                value_label.config(text=str(v) if is_int else fmt.format(v))

            def step_value(delta):
                v = values[label_text][0] + delta
                v = max(min_val, min(max_val, v))
                v = int(round(v)) if is_int else round(v, 4)
                values[label_text][0] = v
                refresh()

            tk.Button(
                control, text="−", font=("Arial", 16, "bold"), width=3, bg="#546E7A", fg="white",
                command=lambda: step_value(-step),
            ).pack(side=tk.LEFT, padx=(0, 8))

            value_label.pack(side=tk.LEFT)

            tk.Button(
                control, text="+", font=("Arial", 16, "bold"), width=3, bg="#546E7A", fg="white",
                command=lambda: step_value(step),
            ).pack(side=tk.LEFT, padx=(8, 0))

            refresh()

        tk.Label(
            win, text="Detector Tuning", font=("Arial", 13, "bold"), fg="white", bg="#2d2d2d"
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(15, 5))

        add_stepper("Confidence threshold", self.detector.confidence_threshold, 0.05, 0.05, 1.0, 1, fmt="{:.2f}")
        add_stepper("Required detections", self.detector.required_detections, 1, 1, 30, 2, is_int=True)
        add_stepper("Trigger delay (sec)", self.detector.trigger_delay, 0.5, 0.0, 30.0, 3, fmt="{:.1f}")
        add_stepper("Cooldown time (sec)", self.detector.cooldown_time, 1.0, 0.0, 120.0, 4, fmt="{:.1f}")
        add_stepper("Max detection size", self.detector.max_box_fraction, 0.05, 0.10, 1.0, 5, fmt="{:.0%}")

        tk.Label(
            win,
            text=f"Spray zones: {len(self.spray_zones)}   |   Exclusion zones: {len(self.exclusion_zones)}\n"
                 "(edit zones by dragging on the live video, not here)",
            font=("Arial", 10), fg="#AAAAAA", bg="#2d2d2d", justify="left", wraplength=400,
        ).grid(row=6, column=0, columnspan=2, sticky="w", padx=15, pady=(15, 5))

        status_label = tk.Label(win, text="", font=("Arial", 10), fg="#FF8A80", bg="#2d2d2d", wraplength=400, justify="left")
        status_label.grid(row=7, column=0, columnspan=2, sticky="w", padx=15, pady=(5, 0))

        def on_save():
            confidence_threshold = values["Confidence threshold"][0]
            required_detections = values["Required detections"][0]
            trigger_delay = values["Trigger delay (sec)"][0]
            cooldown_time = values["Cooldown time (sec)"][0]
            max_box_fraction = values["Max detection size"][0]

            try:
                save_detector_settings({
                    "confidence_threshold": confidence_threshold,
                    "required_detections": required_detections,
                    "trigger_delay": trigger_delay,
                    "cooldown_time": cooldown_time,
                    "max_box_fraction": max_box_fraction,
                })
            except Exception as e:
                status_label.config(text=f"Could not save: {e}")
                return

            win.destroy()
            self.show_restart_prompt()

        button_row = tk.Frame(win, bg="#2d2d2d")
        button_row.grid(row=8, column=0, columnspan=2, pady=20)

        tk.Button(
            button_row, text="Save", font=("Arial", 11, "bold"), bg="#4CAF50", fg="white",
            command=on_save, padx=20,
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(
            button_row, text="Cancel", font=("Arial", 11), bg="#78909C", fg="white",
            command=win.destroy, padx=20,
        ).pack(side=tk.LEFT, padx=10)

    def show_restart_prompt(self):
        win = tk.Toplevel(self.root)
        win.title("Restart Required")
        win.configure(bg="#2d2d2d")
        win.geometry("380x180")
        win.transient(self.root)
        win.grab_set()

        tk.Label(
            win,
            text="Settings saved.\nRestart CatSprayer for the changes to take effect.",
            font=("Arial", 12), fg="white", bg="#2d2d2d", justify="center", wraplength=340,
        ).pack(padx=20, pady=(25, 15))

        button_row = tk.Frame(win, bg="#2d2d2d")
        button_row.pack(pady=10)

        def do_restart():
            self.restart_requested = True
            win.destroy()
            self.quit_application()

        tk.Button(
            button_row, text="Restart Now", font=("Arial", 11, "bold"), bg="#4CAF50", fg="white",
            command=do_restart, padx=20,
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(
            button_row, text="Later", font=("Arial", 11), bg="#78909C", fg="white",
            command=win.destroy, padx=20,
        ).pack(side=tk.LEFT, padx=10)

    def open_stats_window(self):
        win = tk.Toplevel(self.root)
        win.title("Spray Stats")
        win.configure(bg="#2d2d2d")
        win.geometry("360x420")
        win.transient(self.root)
        win.grab_set()

        tk.Label(
            win, text="Spray Stats", font=("Arial", 14, "bold"), fg="white", bg="#2d2d2d"
        ).pack(anchor="w", padx=15, pady=(15, 10))

        value_labels = {}

        def stat_row(key, label):
            row = tk.Frame(win, bg="#2d2d2d")
            row.pack(fill=tk.X, padx=15, pady=6)
            tk.Label(row, text=label, font=("Arial", 11), fg="#AAAAAA", bg="#2d2d2d").pack(side=tk.LEFT)
            value_label = tk.Label(row, text="", font=("Arial", 11, "bold"), fg="white", bg="#2d2d2d")
            value_label.pack(side=tk.RIGHT)
            value_labels[key] = value_label

        stat_row("today", "Sprays today")
        stat_row("week", "Sprays this week")
        stat_row("total", "Sprays all-time")
        stat_row("hour", "Most common hour")
        stat_row("last", "Last spray")

        def refresh_display():
            result = stats.get_stats()
            value_labels["today"].config(text=str(result["today_count"]))
            value_labels["week"].config(text=str(result["week_count"]))
            value_labels["total"].config(text=str(result["total_count"]))

            if result["most_common_hour"] is not None:
                hour = result["most_common_hour"]
                hour_label = time.strftime(
                    "%I %p", time.localtime(time.mktime((2000, 1, 1, hour, 0, 0, 0, 0, 0)))
                ).lstrip("0")
                value_labels["hour"].config(text=hour_label)
            else:
                value_labels["hour"].config(text="—")

            if result["last_event_timestamp"] is not None:
                last_str = time.strftime(
                    "%b %d, %I:%M %p", time.localtime(result["last_event_timestamp"])
                ).replace(" 0", " ")
                value_labels["last"].config(text=last_str)
            else:
                value_labels["last"].config(text="Never")

        refresh_display()

        # --- Hold 3s to Reset ---
        reset_hold_state = {"ticks": 0, "timer_id": None}

        def reset_button_visual():
            btn_reset.config(bg="#B71C1C", text="⚠️ Hold 3s to Reset Stats")

        def on_reset_press(event):
            reset_hold_state["ticks"] = 3
            btn_reset.config(bg="#FF3D00", text="Holding... 3s")
            tick_reset_timer()

        def tick_reset_timer():
            if reset_hold_state["ticks"] > 1:
                reset_hold_state["ticks"] -= 1
                btn_reset.config(text=f"Holding... {reset_hold_state['ticks']}s")
                reset_hold_state["timer_id"] = win.after(1000, tick_reset_timer)
            else:
                reset_hold_state["timer_id"] = None
                reset_button_visual()
                stats.reset_stats()
                refresh_display()

        def on_reset_release(event):
            if reset_hold_state["timer_id"] is not None:
                win.after_cancel(reset_hold_state["timer_id"])
                reset_hold_state["timer_id"] = None
            reset_button_visual()

        btn_reset = tk.Button(
            win, text="⚠️ Hold 3s to Reset Stats", font=("Arial", 11, "bold"),
            bg="#B71C1C", fg="white", activebackground="#B71C1C", activeforeground="white",
        )
        btn_reset.pack(fill=tk.X, padx=15, pady=(15, 5))
        btn_reset.bind("<ButtonPress-1>", on_reset_press)
        btn_reset.bind("<ButtonRelease-1>", on_reset_release)

        tk.Button(
            win, text="Close", font=("Arial", 11), bg="#78909C", fg="white",
            command=win.destroy, padx=20,
        ).pack(pady=15)

    def set_zone_edit_mode(self, mode):
        """
        mode is "spray", "exclusion", or None. Selecting a mode cancels
        any in-progress drag and highlights whichever add-button is active;
        selecting the already-active mode turns editing off.
        """

        if self.zone_edit_mode == mode:
            mode = None

        self.zone_edit_mode = mode
        self._zone_drag_start_px = None
        self._zone_drag_current_px = None

        if mode == "spray":
            self.btn_add_spray_zone.config(text="Drag to add, tap to cancel", bg="#66BB6A", fg="black")
            self.btn_add_exclusion_zone.config(text="🚫 Exclusion Zone", bg="#37474F", fg="white")
        elif mode == "exclusion":
            self.btn_add_exclusion_zone.config(text="Drag to add, tap to cancel", bg="#E57373", fg="black")
            self.btn_add_spray_zone.config(text="➕ Spray Zone", bg="#37474F", fg="white")
        else:
            self.btn_add_spray_zone.config(text="➕ Spray Zone", bg="#37474F", fg="white")
            self.btn_add_exclusion_zone.config(text="🚫 Exclusion Zone", bg="#37474F", fg="white")

    def _persist_zones(self):
        """
        Write the current spray/exclusion zones to pyproject.toml so they
        survive a restart. Called after every add/undo/clear -- zone edits
        made by dragging on the video were previously only ever pushed into
        the live detector object and lost the moment the app restarted.
        """
        try:
            save_detector_settings({
                "spray_zones": [list(z) for z in self.spray_zones],
                "exclusion_zones": [list(z) for z in self.exclusion_zones],
            })
        except Exception as e:
            print(f"Notice: could not save zones to pyproject.toml: {e}")

    def undo_last_zone(self):
        if not self.zone_history:
            return

        kind, _ = self.zone_history.pop()

        if kind == "spray" and self.spray_zones:
            self.spray_zones.pop()
            self.detector.remove_trigger_zone(len(self.detector.trigger_zones) - 1)
        elif kind == "exclusion" and self.exclusion_zones:
            self.exclusion_zones.pop()
            self.detector.remove_exclusion_zone(len(self.detector.exclusion_zones) - 1)

        self._persist_zones()

    def clear_all_zones(self):
        self.spray_zones = []
        self.exclusion_zones = []
        self.zone_history = []
        self.detector.set_zones([], [])
        self._persist_zones()

    def _on_zone_press(self, event):
        if self.zone_edit_mode is None:
            return
        self._zone_drag_start_px = (event.x, event.y)
        self._zone_drag_current_px = (event.x, event.y)

    def _on_zone_drag(self, event):
        if self.zone_edit_mode is None or self._zone_drag_start_px is None:
            return
        self._zone_drag_current_px = (event.x, event.y)

    def _on_zone_release(self, event):
        if self.zone_edit_mode is None or self._zone_drag_start_px is None:
            return

        x0, y0 = self._zone_drag_start_px
        x1, y1 = event.x, event.y
        self._zone_drag_start_px = None
        self._zone_drag_current_px = None

        w = self.video_label.winfo_width()
        h = self.video_label.winfo_height()
        if w <= 1 or h <= 1:
            return

        # Normalize, order so (x1,y1) is top-left, and clamp to [0, 1]
        nx1, nx2 = sorted((x0 / w, x1 / w))
        ny1, ny2 = sorted((y0 / h, y1 / h))
        nx1, nx2 = max(0.0, min(1.0, nx1)), max(0.0, min(1.0, nx2))
        ny1, ny2 = max(0.0, min(1.0, ny1)), max(0.0, min(1.0, ny2))

        # Ignore accidental taps / drags too small to be a real box
        if (nx2 - nx1) < 0.03 or (ny2 - ny1) < 0.03:
            return

        zone = (nx1, ny1, nx2, ny2)

        if self.zone_edit_mode == "spray":
            self.spray_zones.append(zone)
            self.detector.add_trigger_zone(zone)
            self.zone_history.append(("spray", zone))
        elif self.zone_edit_mode == "exclusion":
            self.exclusion_zones.append(zone)
            self.detector.add_exclusion_zone(zone)
            self.zone_history.append(("exclusion", zone))
        else:
            return

        self._persist_zones()

    def _show_appropriate_controls(self):
        self.review_panel.pack_forget()
        self.playback_panel.pack_forget()
        self.slow_motion_bar.pack_forget()

        if self.current_mode == "LIVE":
            return

        self.slow_motion_bar.pack(fill=tk.X)

        if self.is_looping_new_clip or self.current_mode == "REVIEW_QUEUE":
            self.review_panel.pack(fill=tk.X)
        else:
            self.playback_panel.pack(fill=tk.X)

    def refresh_video_list(self):
        self.listbox.delete(0, tk.END)
        if not os.path.exists(self.video_dir):
            return

        files = sorted(
            [f for f in os.listdir(self.video_dir) if f.endswith(".mp4")],
            reverse=True,
        )

        for filename in files:
            is_fav = "_fav" in filename
            is_new = "_new" in filename
            
            if self.current_mode == "PLAYBACK_FAV" and not is_fav:
                continue
            if self.current_mode == "REVIEW_QUEUE" and not is_new:
                continue

            display_name = filename.replace("recording_", "").replace(".mp4", "")
            if is_fav:
                display_name = f"⭐ {display_name.replace('_fav', '')}"
            elif is_new:
                display_name = f"🆕 {display_name.replace('_new', '')}"

            self.listbox.insert(tk.END, display_name)

    def video_watcher_loop(self):
        if not self.running:
            return
        try:
            if os.path.exists(self.video_dir):
                new_clips = [f for f in os.listdir(self.video_dir) if f.endswith("_new.mp4")]
                count = len(new_clips)
                
                if count > 0:
                    self.btn_queue.config(text=f"🆕 Review Queue ({count})", fg="#FFD54F", font=("Arial", 11, "bold"))
                else:
                    self.btn_queue.config(text="🆕 Review Queue", fg="white", font=("Arial", 11, "normal"))
                    
                    if self.current_mode == "REVIEW_QUEUE":
                        self.set_mode_live()
        except Exception as e:
            print(f"Error inside video notification engine: {e}")
            
        self.root.after(1500, self.video_watcher_loop)

    def set_mode_live(self):
        self.current_mode = "LIVE"
        self.is_looping_new_clip = False
        self.status_title.config(text="SYSTEM ONLINE", fg="#4CAF50")
        self.status_desc.config(text="Mode: Live Feed Tracking")
        self._highlight_active_mode_button(self.btn_live)
        self._close_file_capture()
        self.refresh_video_list()
        self._show_appropriate_controls()

    def set_mode_all(self):
        self.current_mode = "PLAYBACK_ALL"
        self.is_looping_new_clip = False
        self.status_title.config(text="ARCHIVE REVIEW", fg="#0288D1")
        self.status_desc.config(text="Viewing: All Recorded Clips")
        self._highlight_active_mode_button(self.btn_all)
        self._close_file_capture()
        self.refresh_video_list()
        self._show_appropriate_controls()
        self._play_first_available_clip()

    def set_mode_favs(self):
        self.current_mode = "PLAYBACK_FAV"
        self.is_looping_new_clip = False
        self.status_title.config(text="FAVORITES REVIEW", fg="#FFD54F")
        self.status_desc.config(text="Viewing: Favorited Highlights")
        self._highlight_active_mode_button(self.btn_favs)
        self._close_file_capture()
        self.refresh_video_list()
        self._show_appropriate_controls()
        self._play_first_available_clip()

    def set_mode_queue(self):
        self.current_mode = "REVIEW_QUEUE"
        self.is_looping_new_clip = True
        self.status_title.config(text="🚨 REVIEW QUEUE 🚨", fg="#FFCA28")
        self.status_desc.config(text="Action Required: Loop Active")
        self._highlight_active_mode_button(self.btn_queue)
        self._close_file_capture()
        self.refresh_video_list()
        self._show_appropriate_controls()
        self._play_first_available_clip()

    def _play_first_available_clip(self):
        if self.listbox.size() > 0:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(0)
            self.listbox.activate(0)
            self.on_clip_selected(None)

    def _highlight_active_mode_button(self, target_btn):
        for btn in [self.btn_live, self.btn_all, self.btn_favs, self.btn_queue]:
            btn.config(bg="#37474F", font=("Arial", 11, "normal"))
        target_btn.config(bg="#455A64", font=("Arial", 11, "bold"))

    def on_clip_selected(self, event):
        selection = self.listbox.curselection()
        if not selection:
            return

        selected_text = self.listbox.get(selection[0])
        clean_name = selected_text.replace("⭐ ", "").replace("🆕 ", "")
        
        if "⭐" in selected_text:
            filename = f"recording_{clean_name}_fav.mp4"
            self.is_looping_new_clip = False
        elif "🆕" in selected_text:
            filename = f"recording_{clean_name}_new.mp4"
            self.is_looping_new_clip = True
        else:
            self.is_looping_new_clip = False
            if os.path.exists(os.path.join(self.video_dir, f"recording_{clean_name}_fav.mp4")):
                filename = f"recording_{clean_name}_fav.mp4"
            elif os.path.exists(os.path.join(self.video_dir, f"recording_{clean_name}_new.mp4")):
                filename = f"recording_{clean_name}_new.mp4"
                self.is_looping_new_clip = True
            else:
                filename = f"recording_{clean_name}.mp4"

        filepath = os.path.join(self.video_dir, filename)

        self._close_file_capture()
        
        old_ld_path = os.environ.get('LD_LIBRARY_PATH')
        if getattr(sys, 'frozen', False) and 'LD_LIBRARY_PATH_ORIG' in os.environ:
            os.environ['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH_ORIG']
            
        try:
            self.cap = cv2.VideoCapture(filepath)
        finally:
            if old_ld_path is not None:
                os.environ['LD_LIBRARY_PATH'] = old_ld_path

        self.current_playback_file = filepath
        self._last_playback_frame = None
        self._playback_tick_counter = 0
        self._show_appropriate_controls()

    def _advance_queue_or_exit(self):
        self.refresh_video_list()
        if self.current_mode == "REVIEW_QUEUE" and self.listbox.size() > 0:
            self._play_first_available_clip()
        else:
            self.set_mode_live()

    def action_keep(self):
        if self.current_playback_file and os.path.exists(self.current_playback_file):
            if "_new.mp4" in self.current_playback_file:
                new_filepath = self.current_playback_file.replace("_new.mp4", ".mp4")
                try:
                    self._close_file_capture()
                    os.rename(self.current_playback_file, new_filepath)
                except Exception as e:
                    print(f"Error keeping file: {e}")
        self._advance_queue_or_exit()

    def action_favorite_and_keep(self):
        if self.current_playback_file and os.path.exists(self.current_playback_file):
            directory, old_filename = os.path.split(self.current_playback_file)
            if "_new.mp4" in old_filename:
                new_filename = old_filename.replace("_new.mp4", "_fav.mp4")
            elif "_fav" not in old_filename:
                new_filename = old_filename.replace(".mp4", "_fav.mp4")
            else:
                new_filename = old_filename

            try:
                self._close_file_capture()
                os.rename(self.current_playback_file, os.path.join(directory, new_filename))
            except Exception as e:
                print(f"Error favoriting: {e}")
        self._advance_queue_or_exit()

    def action_immediate_delete(self):
        if self.current_playback_file and os.path.exists(self.current_playback_file):
            try:
                self._close_file_capture()
                os.remove(self.current_playback_file)
            except Exception as e:
                print(f"Error removing file: {e}")
        self._advance_queue_or_exit()

    def action_decide_later(self):
        self._advance_queue_or_exit()

    def _on_delete_press(self, event):
        self.delete_countdown_ticks = 3
        self.btn_delete_hold.config(bg="#ff3d00", text="Holding... 3s")
        self._tick_delete_timer()

    def _tick_delete_timer(self):
        if self.delete_countdown_ticks > 1:
            self.delete_countdown_ticks -= 1
            self.btn_delete_hold.config(text=f"Holding... {self.delete_countdown_ticks}s")
            self.delete_timer_id = self.root.after(1000, self._tick_delete_timer)
        else:
            self.delete_timer_id = None
            self._reset_delete_button_visual()
            self._execute_confirmed_deletion()

    def _on_delete_release(self, event):
        if self.delete_timer_id is not None:
            self.root.after_cancel(self.delete_timer_id)
            self.delete_timer_id = None
        self._reset_delete_button_visual()

    def _reset_delete_button_visual(self):
        self.btn_delete_hold.config(bg="#b71c1c", text="⚠️ Hold 3s to Delete")

    def _execute_confirmed_deletion(self):
        if not self.current_playback_file or not os.path.exists(self.current_playback_file):
            return

        selection = self.listbox.curselection()
        current_index = selection[0] if selection else 0

        self._close_file_capture()
        
        try:
            os.remove(self.current_playback_file)
            self.current_playback_file = None
            self.refresh_video_list()
            
            if self.listbox.size() > 0:
                next_index = min(current_index, self.listbox.size() - 1)
                self.listbox.selection_set(next_index)
                self.on_clip_selected(None)
            else:
                self.set_mode_live()
        except Exception as e:
            messagebox.showerror("IO Error", f"Could not remove video: {e}")

    def toggle_slow_motion(self):
        self.slow_motion_enabled = not self.slow_motion_enabled
        self._playback_tick_counter = 0

        if self.slow_motion_enabled:
            self.btn_slow_motion.config(text="🐢 Slow Motion: On", bg="#F9A825", fg="black")
        else:
            self.btn_slow_motion.config(text="🐢 Slow Motion: Off", bg="#37474F", fg="white")

    def toggle_favorite_status(self):
        selection = self.listbox.curselection()
        if not selection or not self.current_playback_file or not os.path.exists(self.current_playback_file):
            return

        current_index = selection[0]
        directory, old_filename = os.path.split(self.current_playback_file)

        if "_fav" in old_filename:
            new_filename = old_filename.replace("_fav", "")
        elif "_new" in old_filename:
            new_filename = old_filename.replace("_new", "_fav")
        else:
            new_filename = old_filename.replace(".mp4", "_fav.mp4")

        new_filepath = os.path.join(directory, new_filename)
        self._close_file_capture()

        try:
            os.rename(self.current_playback_file, new_filepath)
            self.current_playback_file = new_filepath
            self.refresh_video_list()
            
            if self.current_mode == "PLAYBACK_FAV":
                if current_index < self.listbox.size():
                    self.listbox.selection_set(current_index)
                elif self.listbox.size() > 0:
                    self.listbox.selection_set(self.listbox.size() - 1)
            else:
                if current_index < self.listbox.size():
                    self.listbox.selection_set(current_index)
            
            if self.listbox.curselection():
                self.on_clip_selected(None)
            else:
                self.set_mode_live()
        except Exception as e:
            messagebox.showerror("IO Error", f"Could not change status: {e}")

    def _close_file_capture(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def _hardware_worker_loop(self):
        """Background worker thread dedicated solely to processing pipeline hardware tasks."""
        STALL_WARNING_SECONDS = 30

        while self.running:
            try:
                detections = self.camera.get_detections()
                result = self.detector.process(detections)
                self.event_recorder.update(result["cat_detected"], result["trigger"])

                if result["trigger"]:
                    logger.info("Sprayer triggered (confidence=%.2f)", result.get("confidence", 0.0))
                    self.sprayer.activate()
                    stats.log_spray_event(result.get("confidence", 0.0))

                live_frame = self.camera.get_annotated_frame()

                with self.state_lock:
                    self.hardware_state["cat_detected"] = result["cat_detected"]
                    self.hardware_state["confidence"] = result.get("confidence", 0.0)
                    self.hardware_state["live_frame"] = live_frame
                    self.hardware_state["in_zone"] = result.get("in_zone", False)
                    self.hardware_state["active_trigger_indices"] = result.get("active_trigger_indices", [])
                    self.hardware_state["active_exclusion_indices"] = result.get("active_exclusion_indices", [])

                if self._hw_stall_logged:
                    downtime = time.time() - self._hw_last_success_time
                    logger.warning(
                        "Hardware loop recovered after %d consecutive errors (~%.0fs of downtime)",
                        self._hw_consecutive_errors, downtime,
                    )
                    self._hw_stall_logged = False

                if not self._ai_stall_restart_requested:
                    ai_silence = self.camera.seconds_since_last_ai_output()
                    if ai_silence >= self.AI_STALL_RESTART_SECONDS:
                        logger.critical(
                            "AI inference channel has produced no output in %.0fs "
                            "(camera/frames otherwise fine) -- requesting automatic restart",
                            ai_silence,
                        )
                        self._ai_stall_restart_requested = True

                self._hw_consecutive_errors = 0
                self._hw_last_success_time = time.time()

            except Exception:
                self._hw_consecutive_errors += 1

                if self._hw_consecutive_errors == 1:
                    # Full traceback on the first failure of a new streak --
                    # most useful moment to capture detail, without flooding
                    # the log if this turns into a sustained stall.
                    logger.exception("Error in hardware background thread")

                stall_duration = time.time() - self._hw_last_success_time
                if stall_duration >= STALL_WARNING_SECONDS and not self._hw_stall_logged:
                    logger.critical(
                        "Camera/detector has not produced a successful reading in "
                        "%.0fs (%d consecutive errors) -- pipeline may be stuck",
                        stall_duration, self._hw_consecutive_errors,
                    )
                    self._hw_stall_logged = True

            # Tiny sleep interval ensures the thread doesn't hog the CPU core completely
            time.sleep(0.01)

    def _draw_zones(self, img_pil, canvas_w, canvas_h, active_trigger_indices, active_exclusion_indices):
        draw = ImageDraw.Draw(img_pil)

        for i, (zx1, zy1, zx2, zy2) in enumerate(self.spray_zones):
            box_px = (zx1 * canvas_w, zy1 * canvas_h, zx2 * canvas_w, zy2 * canvas_h)
            color = "#00E676" if i in active_trigger_indices else "#00E5FF"
            draw.rectangle(box_px, outline=color, width=3)

        for i, (zx1, zy1, zx2, zy2) in enumerate(self.exclusion_zones):
            box_px = (zx1 * canvas_w, zy1 * canvas_h, zx2 * canvas_w, zy2 * canvas_h)
            color = "#FF1744" if i in active_exclusion_indices else "#FF8A65"
            draw.rectangle(box_px, outline=color, width=3)

        # Live preview of the zone currently being dragged out.
        if self.zone_edit_mode is not None and self._zone_drag_start_px is not None and self._zone_drag_current_px is not None:
            x0, y0 = self._zone_drag_start_px
            x1, y1 = self._zone_drag_current_px
            box_px = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            color = "#66BB6A" if self.zone_edit_mode == "spray" else "#E57373"
            draw.rectangle(box_px, outline=color, width=3)

    def update_loop(self):
        """Lightweight UI draw loop running on the main Tkinter thread."""
        if not self.running:
            return

        if self._ai_stall_restart_requested:
            self.restart_requested = True
            self.quit_application()
            return

        # 1. Fetch values safely from the cache
        with self.state_lock:
            cat_detected = self.hardware_state["cat_detected"]
            confidence = self.hardware_state["confidence"]
            live_frame = self.hardware_state["live_frame"]
            active_trigger_indices = self.hardware_state.get("active_trigger_indices", [])
            active_exclusion_indices = self.hardware_state.get("active_exclusion_indices", [])

        frame = None

        # 2. Assign or process frame selection based on mode
        if self.current_mode == "LIVE":
            if cat_detected:
                self.status_title.config(text="⚠️ CAT SPOTTED ⚠️", fg="#FF5252")
                self.status_desc.config(text=f"Confidence: {confidence:.2f}")
            else:
                self.status_title.config(text="SYSTEM ONLINE", fg="#4CAF50")
                self.status_desc.config(text="Mode: Live Feed Tracking")

            frame = live_frame

        else:
            if cat_detected:
                self.status_title.config(text="⚠️ CAT DETECTED IN YARD ⚠️", fg="#FF5252")
                self.status_desc.config(text="Background monitoring active!")
            else:
                if self.current_mode == "PLAYBACK_ALL":
                    self.status_title.config(text="ARCHIVE REVIEW", fg="#0288D1")
                    self.status_desc.config(text="Viewing: All Recorded Clips")
                elif self.current_mode == "PLAYBACK_FAV":
                    self.status_title.config(text="FAVORITES REVIEW", fg="#FFD54F")
                    self.status_desc.config(text="Viewing: Favorited Highlights")
                elif self.current_mode == "REVIEW_QUEUE":
                    self.status_title.config(text="🚨 REVIEW QUEUE 🚨", fg="#FFCA28")
                    self.status_desc.config(text="Action Required: Loop Active")

            if self.cap is not None and self.cap.isOpened():
                if self.slow_motion_enabled:
                    self._playback_tick_counter += 1
                    should_advance = (self._playback_tick_counter % self.SLOW_MOTION_DIVISOR == 0)
                else:
                    should_advance = True

                if not should_advance and self._last_playback_frame is not None:
                    frame = self._last_playback_frame
                else:
                    ret, raw_frame = self.cap.read()
                    if ret:
                        frame = raw_frame
                        self._last_playback_frame = raw_frame
                    else:
                        if self.is_looping_new_clip or self.current_mode == "REVIEW_QUEUE":
                            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            ret, raw_frame = self.cap.read()
                            if ret:
                                frame = raw_frame
                                self._last_playback_frame = raw_frame
                        else:
                            selection = self.listbox.curselection()
                            if selection:
                                next_index = selection[0] + 1
                                if next_index < self.listbox.size():
                                    self.listbox.selection_clear(0, tk.END)
                                    self.listbox.selection_set(next_index)
                                    self.listbox.see(next_index)
                                    self.on_clip_selected(None)
                                else:
                                    self.listbox.selection_clear(0, tk.END)
                                    self.listbox.selection_set(0)
                                    self.listbox.see(0)
                                    self.on_clip_selected(None)

        # 3. Handle Tkinter image compilation and frame drawing
        if frame is not None:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            canvas_w = self.video_label.winfo_width()
            canvas_h = self.video_label.winfo_height()

            if canvas_w <= 10 or canvas_h <= 10:
                canvas_w, canvas_h = 800, 600

            img_pil = Image.fromarray(frame_rgb)
            img_pil = img_pil.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)

            if self.current_mode == "LIVE":
                self._draw_zones(img_pil, canvas_w, canvas_h, active_trigger_indices, active_exclusion_indices)

            img_tk = ImageTk.PhotoImage(image=img_pil)

            self.video_label.img_tk = img_tk
            self.video_label.config(image=img_tk)

        self.root.after(33, self.update_loop)

    def quit_application(self):
        self.running = False
        self._close_file_capture()
        self.root.destroy()
        if not self.restart_requested:
            sys.exit(0)
