import tkinter as tk
from tkinter import ttk, messagebox
import serial
import struct
import time

class FPGAController:
    # This class is unchanged from the previous correct version.
    # It handles the low-level serial communication.
    CMD_TRIGGER_SEQUENCE = 0x01
    CMD_SET_TRAFO_PERIOD = 0x10
    CMD_SET_TRAFO_DUTY = 0x11
    CMD_SET_TRAFO_PULSE_COUNT = 0x12
    CMD_SET_LED_ON_TIME = 0x20
    CMD_SET_LED_DELAY = 0x21
    CMD_SET_CAMERA_ON_TIME = 0x30
    CMD_SET_CAMERA_DELAY = 0x31

    def __init__(self, port='/dev/ttyUSB1', baudrate=115200, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            print(f"Successfully connected to {self.port}")
            return True
        except serial.SerialException as e:
            messagebox.showerror("Connection Error", f"Could not open port {self.port}.\nDetails: {e}")
            return False

    def is_open(self):
        return self.ser is not None and self.ser.is_open

    def close(self):
        if self.is_open():
            self.ser.close()
            print("Serial port closed.")

    def _send_command(self, command, data1=0, data2=0):
        if not self.is_open():
            print("Error: Not connected to FPGA.")
            return False
        
        packet = struct.pack('>BBB', command, data1, data2)
        print(f"Sending: CMD={command:02X}, D1={data1:02X}, D2={data2:02X}")
        self.ser.write(packet)
        ack = self.ser.read(1)
        
        if not ack or ack[0] != command:
            print(f"Error: Acknowledgment fail. Sent {command:02X}, received {ack.hex().upper() if ack else 'None'}")
            return False
            
        print(f"Ack OK ({ack[0]:02X})")
        return True

    def set_trafo_period(self, period_us):
        d1, d2 = (period_us >> 8) & 0xFF, period_us & 0xFF
        self._send_command(self.CMD_SET_TRAFO_PERIOD, d1, d2)

    def set_trafo_duty(self, duty_us):
        d1, d2 = (duty_us >> 8) & 0xFF, duty_us & 0xFF
        self._send_command(self.CMD_SET_TRAFO_DUTY, d1, d2)
        
    def set_trafo_pulse_count(self, count):
        self._send_command(self.CMD_SET_TRAFO_PULSE_COUNT, count, 0)

    def set_led_on_time(self, on_time_us):
        d1, d2 = (on_time_us >> 8) & 0xFF, on_time_us & 0xFF
        self._send_command(self.CMD_SET_LED_ON_TIME, d1, d2)

    def set_led_delay(self, delay_us):
        d1, d2 = (delay_us >> 8) & 0xFF, delay_us & 0xFF
        self._send_command(self.CMD_SET_LED_DELAY, d1, d2)

    def set_camera_exposure(self, exposure_ms):
        d1, d2 = (exposure_ms >> 8) & 0xFF, exposure_ms & 0xFF
        self._send_command(self.CMD_SET_CAMERA_ON_TIME, d1, d2)

    def set_camera_delay(self, delay_us):
        d1, d2 = (delay_us >> 8) & 0xFF, delay_us & 0xFF
        self._send_command(self.CMD_SET_CAMERA_DELAY, d1, d2)
        
    def trigger_sequence(self, delay_ms=0):
        d1, d2 = (delay_ms >> 8) & 0xFF, delay_ms & 0xFF
        self._send_command(self.CMD_TRIGGER_SEQUENCE, d1, d2)

class PWM_GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("FPGA PWM Controller")
        
        self.controller = FPGAController()
        self.control_widgets = []
        
        # **MODIFIED**: Add state variable for auto-trigger
        self.auto_trigger_running = False

        style = ttk.Style()
        style.configure("TLabelFrame.Label", font=("Helvetica", 10, "bold"))

        self._create_connection_frame()
        self._create_trafo_frame()
        self._create_led_frame()
        self._create_camera_frame()
        self._create_trigger_frame()
        
        self.update_widget_states()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_connection_frame(self):
        # This function is unchanged
        frame = ttk.LabelFrame(self.root, text="Connection", padding=10)
        frame.pack(padx=10, pady=5, fill="x")
        ttk.Label(frame, text="Port:").grid(row=0, column=0, padx=5, pady=5)
        self.port_entry = ttk.Entry(frame)
        self.port_entry.insert(0, "/dev/ttyUSB1")
        self.port_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.connect_button = ttk.Button(frame, text="Connect", command=self._connect)
        self.connect_button.grid(row=0, column=2, padx=5, pady=5)
        self.disconnect_button = ttk.Button(frame, text="Disconnect", command=self._disconnect)
        self.disconnect_button.grid(row=0, column=3, padx=5, pady=5)
        self.status_label = ttk.Label(frame, text="Status: Disconnected", foreground="red")
        self.status_label.grid(row=0, column=4, padx=10, pady=5)
        frame.columnconfigure(1, weight=1)

    def _create_control_slider(self, parent, label, from_, to, resolution, command):
        ttk.Label(parent, text=label).grid(row=len(parent.children)//2, column=0, sticky='w', padx=5, pady=2)
        slider = tk.Scale(parent, from_=from_, to=to, resolution=resolution, orient='horizontal', length=300, command=command)
        slider.grid(row=len(parent.children)//2-1, column=1, sticky='ew', padx=5, pady=2)
        self.control_widgets.append(slider)
        return slider

    def _create_trafo_frame(self):
        frame = ttk.LabelFrame(self.root, text="Transformer PWM", padding=10)
        frame.pack(padx=10, pady=5, fill="x")
        self.trafo_period_slider = self._create_control_slider(frame, "Period (1-100 us):", 1, 100, 1, self._update_trafo_period)
        self.trafo_duty_slider = self._create_control_slider(frame, "Duty Cycle (0-50 us):", 0, 50, 1, self._update_trafo_duty)
        self.trafo_pulses_slider = self._create_control_slider(frame, "Pulse Count (0-20):", 0, 20, 1, self._update_trafo_pulses)

    def _create_led_frame(self):
        frame = ttk.LabelFrame(self.root, text="LED PWM", padding=10)
        frame.pack(padx=10, pady=5, fill="x")
        self.led_delay_slider = self._create_control_slider(frame, "Delay (0-100 us):", 0, 100, 1, self._update_led_delay)
        self.led_on_time_slider = self._create_control_slider(frame, "On-Time (0-1000 us):", 0, 1000, 1, self._update_led_on_time)

    def _create_camera_frame(self):
        frame = ttk.LabelFrame(self.root, text="Camera PWM", padding=10)
        frame.pack(padx=10, pady=5, fill="x")
        self.camera_delay_slider = self._create_control_slider(frame, "Delay (0-100 us):", 0, 100, 1, self._update_camera_delay)
        self.camera_exposure_slider = self._create_control_slider(frame, "Exposure (1-100 ms):", 1, 100, 1, self._update_camera_exposure)

    def _create_trigger_frame(self):
        frame = ttk.LabelFrame(self.root, text="Global Control", padding=10)
        frame.pack(padx=10, pady=5, fill="x")
        
        # Manual Trigger
        ttk.Label(frame, text="Start Delay (ms):").grid(row=0, column=0, padx=5, pady=5)
        self.trigger_delay_entry = ttk.Entry(frame, width=10)
        self.trigger_delay_entry.insert(0, "0")
        self.trigger_delay_entry.grid(row=0, column=1, padx=5, pady=5)
        self.trigger_button = ttk.Button(frame, text="TRIGGER SEQUENCE", command=self._trigger_sequence)
        self.trigger_button.grid(row=0, column=2, padx=20, pady=5)
        
        # **MODIFIED**: Add new buttons
        self.defaults_button = ttk.Button(frame, text="Load Defaults", command=self._load_defaults)
        self.defaults_button.grid(row=1, column=0, columnspan=2, pady=5, sticky='ew')
        
        self.auto_trigger_button = ttk.Button(frame, text="Start 30Hz Auto-Trigger", command=self._toggle_auto_trigger)
        self.auto_trigger_button.grid(row=1, column=2, padx=20, pady=5, sticky='ew')
        
        # Add new widgets to the list to be enabled/disabled
        self.control_widgets.extend([self.trigger_delay_entry, self.trigger_button, self.defaults_button, self.auto_trigger_button])

    # --- Callback Functions ---
    def _connect(self): self.update_widget_states() if self.controller.connect() else None
    def _disconnect(self):
        # Stop auto-trigger if it's running before disconnecting
        if self.auto_trigger_running:
            self._toggle_auto_trigger()
        self.controller.close()
        self.update_widget_states()
        
    def on_closing(self): self._disconnect() if self.controller.is_open() else None; self.root.destroy()
    def update_widget_states(self):
        state = 'normal' if self.controller.is_open() else 'disabled'
        for widget in self.control_widgets: widget.config(state=state)
        self.disconnect_button.config(state='normal' if self.controller.is_open() else 'disabled')
        self.connect_button.config(state='disabled' if self.controller.is_open() else 'normal')
        # Ensure auto-trigger button is correctly labeled if disconnected while running
        if not self.controller.is_open() and self.auto_trigger_running:
             self.auto_trigger_running = False
             self.auto_trigger_button.config(text="Start 1Hz Auto-Trigger")

    def _update_trafo_period(self, value): self.controller.set_trafo_period(int(value))
    def _update_trafo_duty(self, value): self.controller.set_trafo_duty(int(value))
    def _update_trafo_pulses(self, value): self.controller.set_trafo_pulse_count(int(value))
    def _update_led_delay(self, value): self.controller.set_led_delay(int(value))
    def _update_led_on_time(self, value): self.controller.set_led_on_time(int(value))
    def _update_camera_exposure(self, value): self.controller.set_camera_exposure(int(value))
    def _update_camera_delay(self, value): self.controller.set_camera_delay(int(value))

    def _trigger_sequence(self):
        try:
            delay = int(self.trigger_delay_entry.get())
            self.controller.trigger_sequence(delay)
        except ValueError:
            messagebox.showerror("Input Error", "Please enter a valid integer for the start delay.")

    # **MODIFIED**: New function to load default settings
    def _load_defaults(self):
        """Sends a sequence of commands to set the FPGA to a default state."""
        print("\n--- Loading Default Settings ---")
        
        # Note: Assuming 'ontime of 50uS' refers to Transformer Duty Cycle
        # and setting a sensible default period of 100uS.
        defaults = {
            'trafo_period': 100,
            'trafo_duty': 50,
            'trafo_pulses': 10,
            'led_delay': 0,
            'led_on_time': 10,
            'camera_delay': 0,
            'camera_exposure': 10,
        }
        
        # Send commands to FPGA
        self.controller.set_trafo_period(defaults['trafo_period'])
        self.controller.set_trafo_duty(defaults['trafo_duty'])
        self.controller.set_trafo_pulse_count(defaults['trafo_pulses'])
        self.controller.set_led_delay(defaults['led_delay'])
        self.controller.set_led_on_time(defaults['led_on_time'])
        self.controller.set_camera_delay(defaults['camera_delay'])
        self.controller.set_camera_exposure(defaults['camera_exposure'])
        
        # Update GUI sliders to match the new values
        self.trafo_period_slider.set(defaults['trafo_period'])
        self.trafo_duty_slider.set(defaults['trafo_duty'])
        self.trafo_pulses_slider.set(defaults['trafo_pulses'])
        self.led_delay_slider.set(defaults['led_delay'])
        self.led_on_time_slider.set(defaults['led_on_time'])
        self.camera_delay_slider.set(defaults['camera_delay'])
        self.camera_exposure_slider.set(defaults['camera_exposure'])
        
        print("--- Default Settings Loaded ---")

    # **MODIFIED**: New functions to handle the non-blocking auto-trigger loop
    def _toggle_auto_trigger(self):
        if self.auto_trigger_running:
            self.auto_trigger_running = False
            self.auto_trigger_button.config(text="Start 1Hz Auto-Trigger")
            print("\nAuto-trigger stopped.")
        else:
            self.auto_trigger_running = True
            self.auto_trigger_button.config(text="Stop Auto-Trigger")
            print("\nAuto-trigger started.")
            self._auto_trigger_loop()

    def _auto_trigger_loop(self):
        """This function is called repeatedly by Tkinter's `after` method."""
        if not self.auto_trigger_running:
            return # Stop the loop if the flag has been turned off
            
        # Get the current start delay from the entry box
        try:
            delay = int(self.trigger_delay_entry.get())
        except ValueError:
            delay = 0 # Default to 0 if input is invalid
            
        # Send the trigger command
        self.controller.trigger_sequence(delay)
        
        # Schedule this function to be called again in 1000ms (1 second)
        self.root.after(33, self._auto_trigger_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = PWM_GUI(root)
    root.mainloop()
