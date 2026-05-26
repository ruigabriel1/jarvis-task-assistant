import os
import json
import threading

class TaskManager:
    def __init__(self, filepath):
        self.filepath = filepath
        self._lock = threading.RLock()

    def read_tasks(self):
        """Thread-safe read from tasks.json."""
        with self._lock:
            if not os.path.exists(self.filepath):
                return []
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[TaskManager] Error reading tasks: {e}")
                return []

    def write_tasks(self, tasks):
        """Thread-safe write to tasks.json."""
        with self._lock:
            try:
                with open(self.filepath, 'w', encoding='utf-8') as f:
                    json.dump(tasks, f, ensure_ascii=False, indent=2)
                return True
            except Exception as e:
                print(f"[TaskManager] Error writing tasks: {e}")
                return False

    def update_tasks(self, modify_callback):
        """Thread-safe and atomic read-modify-write cycle."""
        with self._lock:
            tasks = self.read_tasks()
            modified_tasks = modify_callback(tasks)
            if modified_tasks is not None:
                return self.write_tasks(modified_tasks)
            return False
