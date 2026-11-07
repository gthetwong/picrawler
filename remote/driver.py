import threading
import queue
import time


class RobotDriver:
    TIMEOUT = 0.5
    DEADZONE = 0.25
    ACTION_SPEED = 70
    SPEED_MIN = 50
    SPEED_MAX = 90

    def __init__(self, crawler):
        self.crawler = crawler
        self.x, self.y = 0.0, 0.0
        self.last_update = 0.0
        self.lock = threading.Lock()
        self.actions = queue.Queue()
        self.stop_event = threading.Event()

    def drive(self, x, y):
        with self.lock:
            self.x = max(-1.0, min(1.0, x))
            self.y = max(-1.0, min(1.0, y))
            self.last_update = time.monotonic()

    def action(self, name):
        self.actions.put(name)

    def _choose_move(self):
        with self.lock:
            x = self.x
            y = self.y
            last_update = self.last_update
        if time.monotonic() - last_update > self.TIMEOUT:
            return None
        strength = max(abs(x), abs(y))
        if strength < self.DEADZONE:
            return None
        if abs(y) >= abs(x):
            gait = "forward" if y > 0 else "backward"
        else:
            gait = "turn right" if x > 0 else "turn left"
        fraction = (strength - self.DEADZONE) / (1.0 - self.DEADZONE)    # 0.0 at the deadzone edge, 1.0 at full push
        speed = round(self.SPEED_MIN + fraction * (self.SPEED_MAX - self.SPEED_MIN))
        return (gait, speed)

    def run(self):
        try:
            while not self.stop_event.is_set():
                try:
                    name = self.actions.get_nowait()
                except queue.Empty:
                    name = None
                if name is not None:
                    self.crawler.do_action(name, 1, self.ACTION_SPEED)
                    continue
                move = self._choose_move()
                if move is not None:
                    gait, speed = move
                    self.crawler.do_action(gait, 1, speed)
                else:
                    self.stop_event.wait(0.02)
        finally:
            self.crawler.do_step("sit", 40)

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=5)
