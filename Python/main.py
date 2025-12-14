import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import threading
import time
import numpy as np
import cv2
import json
import os
from datetime import datetime
from picamera2 import Picamera2

# No Matplotlib imports needed for the Clean 2D version

import config
import hardware
import processor

class CameraApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Schlieren Controller v9.0 (2D Final)")
        self.root.geometry("1300x850")
        
        self.hw = hardware.HardwareManager()
        
        # State
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.latest_frame = None
        self.preview_thread = None
        self.scan_running = False
        
        self.req_bg = False
        self.bg_img = None
        # Line profile state
        self.line_p1 = None
        self.line_p2 = None
        self.show_profile = False
        
        # Variables
        self.v_freq = tk.IntVar(value=config.DEFAULT_FREQ)
        self.v_cycles = tk.IntVar(value=config.DEFAULT_CYCLES)
        self.v_led = tk.IntVar(value=config.DEFAULT_LED_US)
        self.v_exp = tk.IntVar(value=config.DEFAULT_CAM_EXP)
        self.v_delay = tk.IntVar(value=config.DEFAULT_DELAY)
        self.v_strobe = tk.BooleanVar(value=True)
        
        self.v_trig_fps = tk.IntVar(value=config.DEFAULT_FPS)
        self.v_stack = tk.IntVar(value=config.DEFAULT_STACK)
        self.v_gain_ana = tk.DoubleVar(value=config.DEFAULT_ANA_GAIN)
        self.v_gain_dig = tk.DoubleVar(value=config.DEFAULT_DIG_GAIN)
        
        self.v_mode = tk.StringVar(value="Enhanced")
        self.v_gx = tk.IntVar(value=0)
        self.v_gy = tk.IntVar(value=0)
        self.v_gamp = tk.DoubleVar(value=0.0)
        
        self.v_show_hist = tk.BooleanVar(value=True)
        self.v_live_interleave = tk.BooleanVar(value=True) 
        
        self.v_start = tk.IntVar(value=config.DEFAULT_START)
        self.v_end = tk.IntVar(value=config.DEFAULT_END)
        self.v_step = tk.IntVar(value=config.DEFAULT_STEP)
        self.v_video_fps = tk.IntVar(value=15) # Playback speed
        
        self.v_save_raw = tk.BooleanVar(value=True)
        self.v_ctx = tk.BooleanVar(value=True)
        
        self.status = tk.StringVar(value="Ready")

        self.setup_ui()
        self.start_preview()

    def setup_ui(self):
        # Left: Video Only
        left = tk.Frame(self.root, bg="black")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.video_panel = tk.Label(left, bg="black")
        self.video_panel.pack(fill=tk.BOTH, expand=True)
        
        # Right: Controls
        right = ttk.Frame(self.root, padding=10)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        
        m = tk.Menu(self.root); fm = tk.Menu(m, tearoff=0)
        fm.add_command(label="Save", command=self.save_settings)
        fm.add_command(label="Load", command=self.load_settings)
        m.add_cascade(label="File", menu=fm); self.root.config(menu=m)

        ttk.Label(right, textvariable=self.status, foreground="blue").pack()
        
        # 1. Hardware
        grp_wave = ttk.LabelFrame(right, text="1. Hardware", padding=5)
        grp_wave.pack(fill=tk.X, pady=2)
        self.add_ctrl(grp_wave, "FPS", self.v_trig_fps, 1, 60, True)
        self.add_ctrl(grp_wave, "Freq", self.v_freq, 1000, 50000, True)
        self.add_ctrl(grp_wave, "Cycles", self.v_cycles, 1, 100, True)
        self.add_ctrl(grp_wave, "Delay", self.v_delay, 0, 20000, True)
        self.add_ctrl(grp_wave, "LED", self.v_led, 1, 1000, True)
        self.add_ctrl(grp_wave, "Exp", self.v_exp, 1, 30000, True)
        ttk.Checkbutton(grp_wave, text="Output Sine Wave", variable=self.v_strobe, command=lambda: self.update_hw()).pack()

        # 2. Processing
        grp_img = ttk.LabelFrame(right, text="2. Processing", padding=5)
        grp_img.pack(fill=tk.X, pady=2)
        self.add_ctrl(grp_img, "Ana Gain", self.v_gain_ana, 1.0, 16.0)
        self.add_ctrl(grp_img, "Dig Gain", self.v_gain_dig, 0.1, 50.0)
        
        modes = ["Raw", "Abs Diff (B/W)", "Enhanced", "Colorize", "Heatmap (Jet)", "Heatmap (Inferno)"]
        ttk.Combobox(grp_img, textvariable=self.v_mode, values=modes, state="readonly").pack(fill=tk.X, pady=2)
        
        gf = ttk.Frame(grp_img); gf.pack()
        ttk.Label(gf, text="Ghost X/Y/Amp").pack(side=tk.LEFT)
        ttk.Entry(gf, textvariable=self.v_gx, width=3).pack(side=tk.LEFT)
        ttk.Entry(gf, textvariable=self.v_gy, width=3).pack(side=tk.LEFT)
        ttk.Entry(gf, textvariable=self.v_gamp, width=4).pack(side=tk.LEFT)
        
        ttk.Checkbutton(grp_img, text="Show Histogram", variable=self.v_show_hist).pack()
        ttk.Checkbutton(grp_img, text="Live Auto-Background", variable=self.v_live_interleave, command=lambda: self.update_hw()).pack()
        ttk.Button(grp_img, text="Capture Static BG", command=self.do_bg_cap).pack(fill=tk.X)
        
        # 3. Automation
        grp_scan = ttk.LabelFrame(right, text="3. Automation", padding=5)
        grp_scan.pack(fill=tk.X, pady=2)
        self.add_ctrl(grp_scan, "Start", self.v_start, 0, 20000)
        self.add_ctrl(grp_scan, "End", self.v_end, 0, 20000)
        self.add_ctrl(grp_scan, "Step", self.v_step, 1, 1000)
        self.add_ctrl(grp_scan, "Stack", self.v_stack, 1, 20)
        # Added Video FPS control
        self.add_ctrl(grp_scan, "Vid FPS", self.v_video_fps, 1, 60)
        
        ttk.Checkbutton(grp_scan, text="Save Raw Inputs", variable=self.v_save_raw).pack(anchor='w')
        ttk.Checkbutton(grp_scan, text="Save Context", variable=self.v_ctx).pack(anchor='w')
        
        ttk.Button(right, text="Snapshot", command=self.do_snap).pack(fill=tk.X, pady=2)
        self.btn_scan = ttk.Button(right, text="Start Scan", command=self.do_scan); self.btn_scan.pack(fill=tk.X, pady=5)
        ttk.Button(right, text="Exit", command=self.on_close).pack(side=tk.BOTTOM)

    def add_ctrl(self, p, t, v, minv, maxv, upd=False):
        f = ttk.Frame(p); f.pack(fill=tk.X)
        ttk.Label(f, text=t, width=8).pack(side=tk.LEFT)
        entry = ttk.Entry(f, textvariable=v, width=5); entry.pack(side=tk.RIGHT)
        s = ttk.Scale(f, from_=minv, to=maxv, variable=v)
        if upd: 
            s.configure(command=lambda _: self.update_hw())
            entry.bind('<Return>', lambda e: self.update_hw())
        s.pack(side=tk.RIGHT, expand=True, fill=tk.X)

    def update_hw(self):
        if self.scan_running: return
        is_interleaved = self.v_live_interleave.get()
        self.hw.update_wave(self.v_delay.get(), self.v_exp.get(), self.v_led.get(), self.v_freq.get(), self.v_cycles.get(), self.v_trig_fps.get(), self.v_strobe.get(), True, is_interleaved)

    def start_preview(self):
        self.stop_event.clear()
        self.preview_thread = threading.Thread(target=self.run_preview, daemon=True)
        self.preview_thread.start()
        self.root.after(100, self.update_ui)

    def run_preview(self):
        self.status.set("Starting Preview...")
        self.hw.stop(); self.update_hw()
        cam = Picamera2()
        cam.configure(cam.create_video_configuration(main={"size": (640, 480), "format": "RGB888"}))
        cam.start()
        cam.set_controls({"AeEnable": False, "AwbEnable": False})
        last_gain = -1; last_exp = -1; last_fps = -1
        was_interleaved = self.v_live_interleave.get()

        while not self.stop_event.is_set():
            try:
                is_interleaved = self.v_live_interleave.get()
                curr_fps = self.v_trig_fps.get()
                if is_interleaved != was_interleaved or curr_fps != last_fps:
                    self.update_hw(); was_interleaved = is_interleaved; last_fps = curr_fps; time.sleep(0.1)
                
                g = self.v_gain_ana.get()
                e = max(self.v_exp.get() + 100, 200)
                if g != last_gain or e != last_exp:
                    cam.set_controls({"AnalogueGain": g, "ExposureTime": e})
                    last_gain = g; last_exp = e
                
                if is_interleaved:
                    sig_frame = cam.capture_array("main")
                    bg_frame = cam.capture_array("main")
                    frame = sig_frame; bg_to_use = bg_frame
                else:
                    if self.req_bg:
                        self.hw.update_wave(0, self.v_exp.get(), self.v_led.get(), 0, 0, curr_fps, False, True, False)
                        time.sleep(0.3)
                        cam.capture_array("main") 
                        frames = [cam.capture_array("main") for _ in range(5)]
                        self.bg_img = np.mean(np.array(frames), axis=0)
                        self.req_bg = False
                        self.update_hw()
                    frame = cam.capture_array("main")
                    bg_to_use = self.bg_img

                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                bg_gray = None
                if bg_to_use is not None:
                    if bg_to_use.shape[:2] != gray.shape[:2]: bg_to_use = cv2.resize(bg_to_use, (gray.shape[1], gray.shape[0]))
                    bg_gray = cv2.cvtColor(bg_to_use.astype(np.uint8), cv2.COLOR_RGB2GRAY) if len(bg_to_use.shape)==3 else bg_to_use

                ghost = (self.v_gx.get(), self.v_gy.get(), self.v_gamp.get())
                processed = processor.process_frame(gray, bg_gray, self.v_gain_dig.get(), self.v_mode.get(), ghost)
                
                if self.v_show_hist.get():
                    hist = processor.create_histogram(cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY))
                    h, w, _ = hist.shape
                    processed[0:h, -w:] = hist
                
                with self.lock: self.latest_frame = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
            except: time.sleep(0.01)
        cam.stop(); cam.close(); self.hw.stop()

    def update_ui(self):
        with self.lock:
            if self.latest_frame is not None:
                img = Image.fromarray(self.latest_frame)
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_panel.configure(image=imgtk)
                self.video_panel.image = imgtk
        if not self.stop_event.is_set(): self.root.after(30, self.update_ui)

    def do_bg_cap(self): self.req_bg = True
    def do_snap(self): self.launch_scan(True)
    def do_scan(self): self.launch_scan(False)
    
    def launch_scan(self, single):
        if self.scan_running: return
        self.scan_running = True
        self.btn_scan.config(state=tk.DISABLED)
        threading.Thread(target=self.run_scan_thread, args=(single,)).start()

    def run_scan_thread(self, single_shot):
        try:
            self.status.set("Stopping Preview...")
            self.stop_event.set()
            if self.preview_thread: self.preview_thread.join(2.0)
            self.stop_event.clear(); self.hw.stop(); time.sleep(0.5)
            
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            scan_dir = os.path.join("scans", ts)
            if not os.path.exists(scan_dir): os.makedirs(scan_dir)

            fps = self.v_trig_fps.get()

            if self.v_ctx.get():
                self.status.set("Taking Context (LED Off)...")
                self.hw.update_wave(0, self.v_exp.get(), self.v_led.get(), 0, 0, fps, False, False, False)
                cam = Picamera2()
                cam.configure(cam.create_video_configuration(main={"size": (1440, 1080), "format": "RGB888"}))
                max_safe_us = int(1000000/fps) - 10000
                cam.set_controls({"ExposureTime": max_safe_us, "AnalogueGain": self.v_gain_ana.get(), "AeEnable": False, "AwbEnable": False})
                cam.start(); time.sleep(1)
                frames = [cam.capture_array("main") for _ in range(5)]
                avg = np.mean(np.array(frames), axis=0)
                processor.save_image(avg.astype(np.uint8), scan_dir, "ref_context.png")
                cam.stop(); cam.close(); self.hw.stop(); time.sleep(0.2)

            delays = [self.v_delay.get()] if single_shot else range(self.v_start.get(), self.v_end.get()+1, self.v_step.get())
            
            self.status.set("Init Scan...")
            self.hw.update_wave(delays[0], self.v_exp.get(), self.v_led.get(), self.v_freq.get(), self.v_cycles.get(), fps, True, True, interleaved=True)
            
            cam = Picamera2()
            cam.configure(cam.create_video_configuration(main={"size": (1440, 1080), "format": "RGB888"}))
            cam.set_controls({
                "ExposureTime": max(self.v_exp.get()+100, 200), 
                "AnalogueGain": self.v_gain_ana.get(),
                "AeEnable": False, "AwbEnable": False
            })
            cam.start(); time.sleep(1.0)
            
            for _ in range(4): cam.capture_array("main")
            
            stack = self.v_stack.get()
            save_raw = self.v_save_raw.get()
            
            for i, d in enumerate(delays):
                self.status.set(f"Capturing {d}us...")
                self.hw.update_wave(d, self.v_exp.get(), self.v_led.get(), self.v_freq.get(), self.v_cycles.get(), fps, True, True, interleaved=True)
                time.sleep(0.1)
                
                raw_frames = [cam.capture_array("main") for _ in range(stack * 2)]
                sig_list = raw_frames[0::2]
                bg_list = raw_frames[1::2]
                
                sig_avg = np.mean(np.array(sig_list, dtype=np.float32), axis=0)
                bg_avg = np.mean(np.array(bg_list, dtype=np.float32), axis=0)
                
                s_gray = cv2.cvtColor(np.clip(sig_avg,0,255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
                b_gray = cv2.cvtColor(np.clip(bg_avg,0,255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
                
                if save_raw:
                    cv2.imwrite(os.path.join(scan_dir, f"raw_bg_{d:05d}.png"), b_gray)
                    cv2.imwrite(os.path.join(scan_dir, f"raw_sig_{d:05d}.png"), s_gray)
                
                ghost = (self.v_gx.get(), self.v_gy.get(), self.v_gamp.get())
                final = processor.process_frame(s_gray, b_gray, self.v_gain_dig.get(), self.v_mode.get(), ghost)
                processor.save_image(final, scan_dir, f"frame_{d:05d}.png")
                
                if self.stop_event.is_set(): break

            cam.stop(); cam.close(); self.hw.stop()
            
            # --- VIDEO GENERATION ---
            if not single_shot:
                self.status.set("Generating Video...")
                try:
                    # Ensure we pass the Video FPS value
                    vid_fps = self.v_video_fps.get()
                    vid = processor.generate_video(scan_dir, fps=vid_fps)
                    if vid:
                        self.status.set(f"Saved {os.path.basename(vid)}")
                    else:
                        self.status.set("Video failed: No images found")
                except Exception as ve:
                    print(f"Video Error: {ve}")
                    self.status.set(f"Video Error: {ve}")
            else:
                self.status.set("Snapshot Saved")

        except Exception as e: print(e); self.status.set(f"Error: {e}")
        finally:
            self.scan_running = False; self.hw.stop(); self.stop_event.clear()
            self.preview_thread = threading.Thread(target=self.run_preview, daemon=True)
            self.preview_thread.start()
            self.root.after(0, lambda: self.btn_scan.config(state=tk.NORMAL))
            self.root.after(100, self.update_ui)

    def save_settings(self):
        f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not f: return
        data = {k: getattr(self, k).get() for k in ["v_freq", "v_cycles", "v_delay", "v_gain_dig", "v_gain_ana", "v_gx", "v_gy", "v_gamp", "v_trig_fps", "v_stack", "v_start", "v_end", "v_step"]}
        with open(f, 'w') as file: json.dump(data, file)
    def load_settings(self):
        f = filedialog.askopenfilename(filetypes=[("JSON", "*.json")]); 
        if not f: return
        with open(f, 'r') as file: d = json.load(file)
        for k, v in d.items(): 
            if hasattr(self, k): getattr(self, k).set(v)
        self.update_hw()
    def on_click(self, e): pass # Click logic removed for clean version
    def on_drag(self, e): pass
    def on_release(self, e): pass

    def on_close(self):
        self.stop_event.set(); self.hw.cleanup(); self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk(); app = CameraApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close); root.mainloop()
