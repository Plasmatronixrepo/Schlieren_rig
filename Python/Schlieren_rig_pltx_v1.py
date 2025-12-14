import pigpio
import time
import math
import threading
import numpy as np
import cv2
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from picamera2 import Picamera2

# --- Configuration ---
SINE_PIN = 17
LED_PIN = 23
CAMERA_PIN = 24

# --- Pigpio Setup ---
pi = pigpio.pi()
if not pi.connected:
    print("ERROR: pigpio not connected.")
    exit()
pi.wave_tx_stop()
pi.wave_clear()
pi.set_mode(SINE_PIN, pigpio.OUTPUT)
pi.set_mode(LED_PIN, pigpio.OUTPUT)
pi.set_mode(CAMERA_PIN, pigpio.OUTPUT)
pi.write(SINE_PIN, 0)
pi.write(LED_PIN, 0)
pi.write(CAMERA_PIN, 1)

app = Flask(__name__)

# --- State & Locking ---
capture_lock = threading.Lock()
frame_lock = threading.Lock()
wave_lock = threading.Lock()

# --- Globals ---
preview_thread = None
stop_preview_event = threading.Event()
strobe_params_changed = threading.Event()
latest_frame = None
scan_status = {"state": "Idle", "message": "Ready", "progress": 0}

# Default Params
params = {
    'freq': 40000, 'cycles': 10, 'led_on': 10, 'led_delay': 0,
    'cam_exp': 10, 'analog_gain': 10.0,
    'strobe_enabled': False,
    'stack_count': 3, 'gain': 5.0, 'gamma': 1.0,
}

# --- Helpers ---
def get_int(key):
    try: return int(float(params.get(key, 0)))
    except: return 0
def get_float(key):
    try: return float(params.get(key, 0.0))
    except: return 0.0

def build_pulse_chain(sine_active, delay_us):
    from itertools import groupby
    freq, cycles, led_on, cam_exp_us, led_delay = get_int('freq'), get_int('cycles'), get_int('led_on'), get_int('cam_exp'), get_int('led_delay')
    base_delay = int(delay_us) if delay_us is not None else 0
    events = [(base_delay, 'off', CAMERA_PIN), (base_delay + cam_exp_us, 'on', CAMERA_PIN)]
    if sine_active:
        sine_period = 1000000 / freq
        for i in range(cycles):
            t = int(i * sine_period)
            events.extend([(t, 'on', SINE_PIN), (int(t + sine_period / 2), 'off', SINE_PIN)])
        events.extend([(led_delay, 'on', LED_PIN), (led_delay + led_on, 'off', LED_PIN)])
    events.sort(key=lambda x: x[0])
    
    pulses, last_t, curr_mask = [], 0, (1 << CAMERA_PIN)
    ALL_PINS = (1 << SINE_PIN) | (1 << LED_PIN) | (1 << CAMERA_PIN)
    grouped_events = {k: list(v) for k, v in groupby(events, key=lambda x: x[0])}
    
    for t in sorted(grouped_events.keys()):
        dt = t - last_t
        if dt > 0: pulses.append(pigpio.pulse(curr_mask, ALL_PINS & ~curr_mask, int(dt)))
        for _, action, pin in grouped_events[t]:
            curr_mask = curr_mask | (1 << pin) if action == 'on' else curr_mask & ~(1 << pin)
        pulses.append(pigpio.pulse(curr_mask, ALL_PINS & ~curr_mask, 0))
        last_t = t
    pulses.append(pigpio.pulse(curr_mask, ALL_PINS & ~curr_mask, 100))
    return pulses

def restart_preview_wave():
    with wave_lock:
        pi.wave_tx_stop()
        pi.wave_clear()
        try:
            strobe_on = str(params.get('strobe_enabled', False)).lower() == 'true'
            pulses = build_pulse_chain(strobe_on, delay_us=None)
            pi.wave_add_generic(pulses)
            target_duration = 33333 # 30Hz target
            padding = target_duration - pi.wave_get_micros()
            if padding > 0:
                pi.wave_add_generic([pigpio.pulse((1 << CAMERA_PIN), (1 << SINE_PIN) | (1 << LED_PIN), int(padding))])
            wid = pi.wave_create()
            if wid >= 0:
                pi.wave_send_repeat(wid)
                print("PREVIEW WAVE: Started.")
        except Exception as e:
            print(f"PREVIEW WAVE: ERROR: {e}")

# --- Preview Thread ---
def preview_worker():
    global latest_frame
    print("PREVIEW THREAD: Starting.")
    
    # 1. START WAVEFORM FIRST
    # The sensor needs the clock signal present BEFORE it initializes
    print("PREVIEW THREAD: Starting hardware triggers...")
    restart_preview_wave()
    
    # 2. Configure Camera
    picam2_preview = Picamera2()
    # Using create_video_configuration because we know it worked in the minimal test
    config = picam2_preview.create_video_configuration(main={"size": (640, 480), "format": "RGB888"})
    picam2_preview.configure(config)
    
    # 3. Start Camera
    print("PREVIEW THREAD: Starting camera...")
    picam2_preview.start()
    
    print("PREVIEW THREAD: Camera started. Entering loop.")
    
    while not stop_preview_event.is_set():
        if strobe_params_changed.is_set():
            strobe_params_changed.clear()
            restart_preview_wave()
        try:
            # Blocks until trigger received
            img = picam2_preview.capture_array("main")
            with frame_lock:
                latest_frame = img
        except Exception as e:
            # time.sleep(0.01)
            pass
            
    print("PREVIEW THREAD: Stopping...")
    with wave_lock: pi.wave_tx_stop()
    picam2_preview.stop()
    picam2_preview.close()
    print("PREVIEW THREAD: Stopped.")

# --- Capture Worker ---
captured_images = []
def capture_sub_thread(picam2, stack_count):
    global captured_images
    captured_images = []
    for i in range(stack_count):
        request = picam2.capture_request()
        if request is None: continue
        # Wait a tiny bit for request to arm
        # time.sleep(0.005) 
        image_array = request.make_array("main")
        request.release()
        image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB_BGR)
        captured_images.append(image_bgr)

def snapshot_worker():
    global scan_status, preview_thread, captured_images
    if not capture_lock.acquire(blocking=False): return
    picam2_cap = None
    try:
        scan_status.update({"state": "Snapshot", "message": "Switching modes..."})
        
        # 1. Stop Preview
        if preview_thread and preview_thread.is_alive():
            stop_preview_event.set()
            preview_thread.join(timeout=5.0)
        
        # 2. Create Capture Camera
        scan_status['message'] = "Initializing capture..."
        picam2_cap = Picamera2()
        config = picam2_cap.create_video_configuration(main={"size": (1440, 1080), "format": "RGB888"})
        picam2_cap.configure(config)
        
        # 3. Start Wave FIRST (Strobe ON for capture)
        with wave_lock:
            pi.wave_tx_stop(); pi.wave_clear()
            # We need a repeating wave or single shots?
            # Let's use single shots controlled by the loop for precision stacking
            pass 

        # 4. Start Camera
        picam2_cap.start()
        # Wait a moment for sensor to sync to silence (waiting for trigger)
        time.sleep(1.0)

        stack_count = get_int('stack_count')
        
        # Start the listener thread
        cap_thread = threading.Thread(target=capture_sub_thread, args=(picam2_cap, stack_count))
        cap_thread.start()
        time.sleep(0.5)

        # 5. Fire Triggers
        for i in range(stack_count):
            scan_status['message'] = f"Capturing frame {i+1}/{stack_count}"
            with wave_lock:
                pi.wave_tx_stop(); pi.wave_clear()
                pulses = build_pulse_chain(True, delay_us=get_int('led_delay'))
                pi.wave_add_generic(pulses)
                wid = pi.wave_create()
                if wid >= 0:
                    pi.wave_send_once(wid)
                    while pi.wave_tx_busy(): pass
                    pi.wave_delete(wid)
            time.sleep(0.1)

        cap_thread.join(timeout=10.0)
        if not captured_images: raise RuntimeError("Capture failed.")
        
        scan_status['message'] = "Processing..."
        stacked_image_float = np.mean(np.array(captured_images, dtype=np.float32), axis=0)
        final_image = np.clip(stacked_image_float, 0, 255).astype(np.uint8)
        
        timestamp = datetime.now().strftime("Snap_%Y%m%d_%H%M%S.png")
        save_dir = "scans"
        os.makedirs(save_dir, exist_ok=True)
        cv2.imwrite(os.path.join(save_dir, timestamp), final_image)
        scan_status['message'] = f"Saved to {timestamp}"

    except Exception as e:
        scan_status['message'] = f"Error: {e}"
    finally:
        if picam2_cap and picam2_cap.is_open:
            picam2_cap.stop(); picam2_cap.close()
        
        print("WORKER: Restarting preview thread.")
        stop_preview_event.clear()
        preview_thread = threading.Thread(target=preview_worker)
        preview_thread.daemon = True
        preview_thread.start()
        
        scan_status['state'] = "Idle"
        capture_lock.release()

# --- Flask Server ---
def run_flask(): app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

@app.route('/')
def index(): return render_template('index.html')

@app.route('/toggle_strobe', methods=['POST'])
def toggle():
    params['strobe_enabled'] = not str(params.get('strobe_enabled', False)).lower() == 'true'
    strobe_params_changed.set()
    return jsonify({"strobe": params['strobe_enabled']})

@app.route('/take_snapshot', methods=['POST'])
def take_snapshot():
    if not capture_lock.locked():
        if request.is_json: params.update(request.get_json())
        threading.Thread(target=snapshot_worker).start()
        return jsonify({"status": "started"})
    return jsonify({"status": "busy"})

@app.route('/status')
def status(): return jsonify(scan_status)

@app.route('/list_scans')
def list_scans():
    if not os.path.exists("scans"): return jsonify([])
    files = sorted([f for f in os.listdir("scans") if os.path.isdir(os.path.join("scans", f)) or f.endswith('.png')], reverse=True)
    return jsonify(files)

@app.route('/download/<path:filename>')
def download(filename):
    scans_dir = os.path.abspath("scans")
    if filename.endswith(".png"): return send_from_directory(scans_dir, filename, as_attachment=True)
    return "File not found", 404

@app.route('/video_feed')
def video_feed():
    def gen():
        while True:
            frame_to_send = None
            with frame_lock:
                if latest_frame is not None: frame_to_send = latest_frame.copy()
            if frame_to_send is None:
                placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(placeholder, "Starting Stream...", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
                frame_to_send = placeholder
            _, jpg = cv2.imencode('.jpg', frame_to_send, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(jpg) + b'\r\n')
            time.sleep(0.04)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    preview_thread = threading.Thread(target=preview_worker)
    preview_thread.daemon = True
    preview_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nProgram exiting...")
        stop_preview_event.set()
        if preview_thread and preview_thread.is_alive():
            preview_thread.join()
        pi.stop()
