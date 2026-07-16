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

        # Threading Shared State Cache
        self.running = True
        self.hardware_state = {
            "cat_detected": False,
            "confidence": 0.0,
            "live_frame": None,
            "in_zone": False,
        }
        self.state_lock = threading.Lock()

        # Spray Trigger Zone (normalized 0.0-1.0 fraction of frame: x1, y1, x2, y2).
        # Only cats centered inside this box are eligible to trigger the sprayer.
        # Source of truth on startup is whatever the detector was constructed
        # with (see pyproject.toml [tool.catsprayer.detector] trigger_zone);
        # only fall back to a hardcoded default if the detector has none.
        self.trigger_zone = self.detector.trigger_zone or (0.30, 0.30, 0.70, 0.70)
        if self.detector.trigger_zone is None:
            self.detector.set_trigger_zone(self.trigger_zone)
        self.zone_edit_mode = False
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

        self.btn_zone_edit = tk.Button(
            self.sidebar,
            text="🎯 Edit Spray Zone",
            font=("Arial", 11),
            bg="#37474F",
            fg="white",
            command=self.toggle_zone_edit_mode,
        )
        self.btn_zone_edit.pack(side=tk.TOP, fill=tk.X, padx=15, pady=(2, 8))

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

    def toggle_zone_edit_mode(self):
        self.zone_edit_mode = not self.zone_edit_mode
        if self.zone_edit_mode:
            self.btn_zone_edit.config(text="🎯 Drag on video, then release", bg="#F9A825", fg="black")
        else:
            self.btn_zone_edit.config(text="🎯 Edit Spray Zone", bg="#37474F", fg="white")
            self._zone_drag_start_px = None
            self._zone_drag_current_px = None

    def _on_zone_press(self, event):
        if not self.zone_edit_mode:
            return
        self._zone_drag_start_px = (event.x, event.y)
        self._zone_drag_current_px = (event.x, event.y)

    def _on_zone_drag(self, event):
        if not self.zone_edit_mode or self._zone_drag_start_px is None:
            return
        self._zone_drag_current_px = (event.x, event.y)

    def _on_zone_release(self, event):
        if not self.zone_edit_mode or self._zone_drag_start_px is None:
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

        self.trigger_zone = (nx1, ny1, nx2, ny2)
        self.detector.set_trigger_zone(self.trigger_zone)

    def _show_appropriate_controls(self):
        self.review_panel.pack_forget()
        self.playback_panel.pack_forget()

        if self.current_mode == "LIVE":
            return
        
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
        while self.running:
            try:
                detections = self.camera.get_detections()
                result = self.detector.process(detections)
                self.event_recorder.update(result["cat_detected"])

                if result["trigger"]:
                    print(">>> SPRAYER TRIGGERED <<<")
                    self.sprayer.activate()

                live_frame = self.camera.get_annotated_frame()

                with self.state_lock:
                    self.hardware_state["cat_detected"] = result["cat_detected"]
                    self.hardware_state["confidence"] = result.get("confidence", 0.0)
                    self.hardware_state["live_frame"] = live_frame
                    self.hardware_state["in_zone"] = result.get("in_zone", False)

            except Exception as e:
                print(f"Error in hardware background thread: {e}")
            
            # Tiny sleep interval ensures the thread doesn't hog the CPU core completely
            time.sleep(0.01)

    def _draw_trigger_zone(self, img_pil, canvas_w, canvas_h, in_zone):
        draw = ImageDraw.Draw(img_pil)

        if self.zone_edit_mode and self._zone_drag_start_px is not None and self._zone_drag_current_px is not None:
            # Live preview of the box currently being dragged out.
            x0, y0 = self._zone_drag_start_px
            x1, y1 = self._zone_drag_current_px
            box_px = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            color = "#FFEB3B"
        else:
            zx1, zy1, zx2, zy2 = self.trigger_zone
            box_px = (zx1 * canvas_w, zy1 * canvas_h, zx2 * canvas_w, zy2 * canvas_h)
            if self.zone_edit_mode:
                color = "#FFEB3B"
            elif in_zone:
                color = "#00E676"
            else:
                color = "#00E5FF"

        draw.rectangle(box_px, outline=color, width=3)

    def update_loop(self):
        """Lightweight UI draw loop running on the main Tkinter thread."""
        if not self.running:
            return

        # 1. Fetch values safely from the cache
        with self.state_lock:
            cat_detected = self.hardware_state["cat_detected"]
            confidence = self.hardware_state["confidence"]
            live_frame = self.hardware_state["live_frame"]
            in_zone = self.hardware_state.get("in_zone", False)

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
                ret, raw_frame = self.cap.read()
                if ret:
                    frame = raw_frame
                else:
                    if self.is_looping_new_clip or self.current_mode == "REVIEW_QUEUE":
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, raw_frame = self.cap.read()
                        if ret:
                            frame = raw_frame
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
                self._draw_trigger_zone(img_pil, canvas_w, canvas_h, in_zone)

            img_tk = ImageTk.PhotoImage(image=img_pil)

            self.video_label.img_tk = img_tk
            self.video_label.config(image=img_tk)

        self.root.after(33, self.update_loop)

    def quit_application(self):
        self.running = False
        self._close_file_capture()
        self.root.destroy()
        sys.exit(0)
