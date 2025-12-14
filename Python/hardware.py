# hardware.py
import pigpio
from itertools import groupby
import config

class HardwareManager:
    def __init__(self):
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError("Failed to connect to pigpio daemon.")
        
        self.pi.set_mode(config.PIN_SINE, pigpio.OUTPUT)
        self.pi.set_mode(config.PIN_LED, pigpio.OUTPUT)
        self.pi.set_mode(config.PIN_CAM, pigpio.OUTPUT)
        
        self.pi.write(config.PIN_SINE, 0)
        self.pi.write(config.PIN_LED, 0)
        self.pi.write(config.PIN_CAM, 1) 
        
        self.current_wid = -1
        self.pi.wave_tx_stop()
        self.pi.wave_clear()

    def stop(self):
        try:
            self.pi.wave_tx_stop()
            self.pi.wave_clear()
            self.current_wid = -1
        except: pass

    def cleanup(self):
        self.stop()
        self.pi.stop()

    def update_wave(self, delay_us, cam_exp, led_on, freq, cycles, fps, sine_en=True, led_en=True, interleaved=False):
        try:
            # Calculate Padding based on FPS
            total_period_us = int(1000000.0 / max(1, fps))
            padding_us = int(total_period_us / 2) if interleaved else total_period_us
            padding_us = max(2000, padding_us)

            pulses = self._build_pulses(delay_us, cam_exp, led_on, freq, cycles, sine_en, led_en, interleaved, padding_us)
            
            self.pi.wave_add_generic(pulses)
            new_wid = self.pi.wave_create()
            
            if new_wid >= 0:
                self.pi.wave_send_repeat(new_wid)
                if self.current_wid >= 0:
                    try: self.pi.wave_delete(self.current_wid)
                    except: pass
                self.current_wid = new_wid
            else:
                self.pi.wave_clear()
        except Exception as e:
            print(f"Hardware Error: {e}")

    def _build_pulses(self, delay, cam_exp, led_on, freq, cycles, sine_en, led_en, interleaved, padding_us):
        all_pulses = []
        passes = [sine_en, False] if interleaved else [sine_en]
        
        for current_sine_state in passes:
            events = []
            events.append((int(delay), 'off', config.PIN_CAM))
            events.append((int(delay + cam_exp), 'on', config.PIN_CAM))
            
            if current_sine_state and freq > 0:
                period = 1000000 / freq
                for i in range(int(cycles)):
                    t = int(i * period)
                    events.append((int(t), 'on', config.PIN_SINE))
                    events.append((int(t + period/2), 'off', config.PIN_SINE))
            else:
                events.append((0, 'off', config.PIN_SINE))
            
            if led_en:
                events.append((int(delay), 'on', config.PIN_LED))
                events.append((int(delay + led_on), 'off', config.PIN_LED))

            events.sort(key=lambda x: x[0])
            
            last_t = 0
            curr_mask = (1 << config.PIN_CAM) 
            ALL = (1 << config.PIN_SINE) | (1 << config.PIN_LED) | (1 << config.PIN_CAM)
            
            grouped = {k: list(v) for k, v in groupby(events, key=lambda x: x[0])}
            
            for t in sorted(grouped.keys()):
                dt = t - last_t
                if dt > 0:
                    all_pulses.append(pigpio.pulse(curr_mask, ALL & ~curr_mask, int(dt)))
                for _, action, pin in grouped[t]:
                    if action == 'on': curr_mask |= (1 << pin)
                    else: curr_mask &= ~(1 << pin)
                all_pulses.append(pigpio.pulse(curr_mask, ALL & ~curr_mask, 0))
                last_t = t
            
            all_pulses.append(pigpio.pulse(curr_mask, ALL & ~curr_mask, padding_us))

        return all_pulses
