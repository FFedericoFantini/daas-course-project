import os
import time
import json
try:
    import requests
except Exception:
    requests = None

def get_sense_class():
    # Prefer real Sense HAT on a Pi; avoid importing sense_emu on headless laptop
    try:
        from sense_hat import SenseHat
        return SenseHat
    except Exception:
        # Only load sense_emu if a display is available or user explicitly allows it
        if os.environ.get('DISPLAY') or os.environ.get('USE_SENSE_EMU'):
            try:
                from sense_emu import SenseHat
                return SenseHat
            except Exception:
                pass

        # Fallback mock for headless testing
        class Event:
            def __init__(self, action, direction):
                self.action = action
                self.direction = direction

        class MockStick:
            def __init__(self):
                self._events = []
            def get_events(self):
                evs, self._events = self._events, []
                return evs
            # helper to inject events in tests
            def _push(self, e):
                self._events.append(e)

        class MockSenseHat:
            def __init__(self):
                self.stick = MockStick()

        return MockSenseHat

SenseHat = get_sense_class()

w = (150, 150, 150)
e = (0, 0, 0)

# Create images for three different coloured arrows

arrow = [
e,e,e,w,w,e,e,e,
e,e,w,w,w,w,e,e,
e,w,w,w,w,w,w,e,
w,w,w,w,w,w,w,w,
e,e,e,w,w,e,e,e,
e,e,e,w,w,e,e,e,
e,e,e,w,w,e,e,e,
e,e,e,w,w,e,e,e
]

sense = SenseHat()

# Control endpoint settings (override via env vars)
CONTROL_BASE = os.environ.get('CONTROL_URL', 'http://192.168.0.196:5002/control')
DRONE_ID = os.environ.get('DRONE_ID', 'drone-rpi-001')

def send_control(drone_id, payload):
    """Send a JSON POST to the control endpoint. Prints response or error."""
    if not requests:
        print('requests library not available; install with: pip install requests')
        print('Would send to', f"{CONTROL_BASE}/{drone_id}", 'payload=', json.dumps(payload))
        return False

    url = f"{CONTROL_BASE}/{drone_id}"
    try:
        resp = requests.post(url, json=payload, timeout=2)
        try:
            print(resp.status_code, resp.text)
        except Exception:
            print('Posted, status:', resp.status_code)
        return resp.ok
    except Exception as e:
        print('Error sending control POST:', e)
        return False


def payload_for_direction(direction):
    if direction == 'up':
        sense.set_rotation(0)
        sense.set_pixels(arrow)
        return {"heading_delta": 0, "throttle_delta": 10, "speed_delta": 100}
    elif direction == 'down':
        sense.set_rotation(180)
        sense.set_pixels(arrow)
        return {"heading_delta": 0, "throttle_delta": -10, "speed_delta": -100}
    elif direction == 'left':
        sense.set_rotation(270)
        sense.set_pixels(arrow)
        return {"heading_delta": -40, "throttle_delta": 0, "speed_delta": 100}
    elif direction == 'right':
        sense.set_rotation(90)
        sense.set_pixels(arrow)
        return {"heading_delta": 40, "throttle_delta": 0, "speed_delta": 100}
    return None

# Track currently held directions and last send times
held_directions = set()
last_sent = {}
# Default send interval while holding (seconds); can be overridden via env var
SEND_INTERVAL = float(os.environ.get('JOYSTICK_SEND_INTERVAL', '0.25'))

try:
    while True:
        for event in sense.stick.get_events():
            if event.action == 'pressed':
                payload = payload_for_direction(event.direction)
                if not payload:
                    sense.clear()
                    continue

                print(f"Joystick pressed: {event.direction} -> sending: {payload}")
                send_control(DRONE_ID, payload)
                # start tracking as held
                held_directions.add(event.direction)
                last_sent[event.direction] = time.time()

            elif event.action == 'held':
                # ensure tracking exists; send only if interval elapsed
                if event.direction not in held_directions:
                    held_directions.add(event.direction)
                    last_sent[event.direction] = 0
                payload = payload_for_direction(event.direction)
                if payload:
                    now = time.time()
                    if now - last_sent.get(event.direction, 0) >= SEND_INTERVAL:
                        print(f"Joystick held: {event.direction} -> sending: {payload}")
                        send_control(DRONE_ID, payload)
                        last_sent[event.direction] = now

            elif event.action == 'released':
                print(f"Joystick released: {event.direction}")
                held_directions.discard(event.direction)
                last_sent.pop(event.direction, None)

        # periodic repeats for held directions
        now = time.time()
        for d in list(held_directions):
            if now - last_sent.get(d, 0) >= SEND_INTERVAL:
                payload = payload_for_direction(d)
                if payload:
                    print(f"Joystick held (repeat): {d} -> sending: {payload}")
                    send_control(DRONE_ID, payload)
                    last_sent[d] = now

        time.sleep(0.05)
except KeyboardInterrupt:
    print('Exiting joystick controller')