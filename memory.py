import json, threading, time
from pathlib import Path

class MemoryStore:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {"users": {}}
        self._lock = threading.Lock()
        self._ensure()

    def _ensure(self):
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
            except Exception:
                self.data = {"users": {}}
        else:
            self.data = {"users": {}}

    def persist(self):
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def get_user_memory(self, userId):
        self._ensure()
        return self.data.get("users", {}).get(userId, {}).get("memory", {})

    def save_user_memory(self, userId, mem):
        self._ensure()
        self.data.setdefault("users", {}).setdefault(userId, {"memory":{}, "history": []})
        self.data["users"][userId]["memory"].update(mem)
        self.persist()

    def append_user_history(self, userId, entry):
        self._ensure()
        self.data.setdefault("users", {}).setdefault(userId, {"memory":{}, "history": []})
        self.data["users"][userId]["history"].append(entry)
        if len(self.data["users"][userId]["history"]) > 500:
            self.data["users"][userId]["history"] = self.data["users"][userId]["history"][-500:]
        self.persist()