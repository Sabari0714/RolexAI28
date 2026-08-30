"""Small local automation primitives used by future scheduled workers."""
import threading
import time


class LocalScheduler:
    def __init__(self):
        self._jobs = []
        self._stop = threading.Event()

    def add_once(self, delay_seconds, callback, *args, **kwargs):
        timer = threading.Timer(max(0, delay_seconds), callback, args=args, kwargs=kwargs)
        timer.daemon = True
        self._jobs.append(timer)
        timer.start()
        return timer

    def stop(self):
        self._stop.set()
        for job in list(self._jobs):
            try:
                job.cancel()
            except Exception:
                pass
        self._jobs.clear()
