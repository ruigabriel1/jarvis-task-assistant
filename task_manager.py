import os
import json
import sqlite3
import threading

class TaskManager:
    def __init__(self, filepath):
        # Translate .json to .db to ensure we always use SQLite
        if filepath.endswith('.json'):
            self.filepath = filepath[:-5] + '.db'
            self.json_filepath = filepath
        else:
            self.filepath = filepath
            self.json_filepath = filepath.replace('.db', '.json')

        self._lock = threading.RLock()
        self._init_db()
        self._migrate_if_needed()

    def _init_db(self):
        """Initialize the SQLite database and create the tasks table if it doesn't exist."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(self.filepath)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY,
                        text TEXT NOT NULL,
                        completed INTEGER NOT NULL CHECK (completed IN (0, 1)),
                        priority TEXT NOT NULL
                    )
                """)
                conn.commit()
            except Exception as e:
                print(f"[TaskManager] Error initializing database: {e}")
            finally:
                if conn:
                    conn.close()

    def _migrate_if_needed(self):
        """Migrate tasks from the old tasks.json file to the SQLite database if the JSON file exists."""
        with self._lock:
            if os.path.exists(self.json_filepath):
                try:
                    # Check if database already has tasks
                    existing_tasks = self.read_tasks()
                    if not existing_tasks:
                        with open(self.json_filepath, 'r', encoding='utf-8') as f:
                            tasks = json.load(f)
                        if isinstance(tasks, list) and tasks:
                            self.write_tasks(tasks)
                            print(f"[TaskManager] Successfully migrated {len(tasks)} tasks from JSON to SQLite.")
                    
                    # Rename the json file to tasks.json.bak to prevent future migration attempts
                    bak_path = self.json_filepath + '.bak'
                    if os.path.exists(bak_path):
                        try:
                            os.remove(bak_path)
                        except Exception:
                            pass
                    os.rename(self.json_filepath, bak_path)
                    print(f"[TaskManager] Archived old JSON file to {bak_path}")
                except Exception as e:
                    print(f"[TaskManager] Error migrating tasks from JSON: {e}")

    def read_tasks(self):
        """Thread-safe read from the SQLite database."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(self.filepath)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT id, text, completed, priority FROM tasks")
                rows = cursor.fetchall()
                tasks = []
                for row in rows:
                    tasks.append({
                        "id": row["id"],
                        "text": row["text"],
                        "completed": bool(row["completed"]),
                        "priority": row["priority"]
                    })
                return tasks
            except Exception as e:
                print(f"[TaskManager] Error reading tasks from SQLite: {e}")
                return []
            finally:
                if conn:
                    conn.close()

    def write_tasks(self, tasks):
        """Thread-safe and atomic write to the SQLite database."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(self.filepath)
                conn.execute("BEGIN TRANSACTION")
                conn.execute("DELETE FROM tasks")
                for t in tasks:
                    conn.execute(
                        "INSERT INTO tasks (id, text, completed, priority) VALUES (?, ?, ?, ?)",
                        (t["id"], t["text"], 1 if t["completed"] else 0, t["priority"])
                    )
                conn.commit()
                return True
            except Exception as e:
                print(f"[TaskManager] Error writing tasks to SQLite: {e}")
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                return False
            finally:
                if conn:
                    conn.close()

    def update_tasks(self, modify_callback):
        """Thread-safe and atomic read-modify-write cycle."""
        with self._lock:
            tasks = self.read_tasks()
            modified_tasks = modify_callback(tasks)
            if modified_tasks is not None:
                return self.write_tasks(modified_tasks)
            return False
