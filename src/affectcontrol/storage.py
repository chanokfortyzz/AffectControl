from __future__ import annotations
import json, os, threading
from contextlib import contextmanager
from pathlib import Path
from .types import AffectiveState
try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None
try:
    import msvcrt
except ImportError:  # pragma: no cover
    msvcrt = None

class JsonStateStore:
    """Durable per-scope state store with process-safe read/modify/write on POSIX.

    Atomic replace prevents torn files; a separate lock file prevents lost updates.
    For distributed writers, replace this adapter with a transactional database.
    """
    def __init__(self, path):
        self.path=Path(path); self.lock_path=self.path.with_suffix(self.path.suffix+".lock"); self._thread_lock=threading.RLock()
    @contextmanager
    def _locked(self, exclusive: bool=True):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._thread_lock:
            fd=os.open(self.lock_path, os.O_CREAT|os.O_RDWR, 0o600)
            try:
                if fcntl is not None:
                    fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
                elif msvcrt is not None:  # pragma: no cover - exercised on Windows
                    if os.fstat(fd).st_size == 0:
                        os.write(fd, b"0"); os.fsync(fd)
                    os.lseek(fd, 0, os.SEEK_SET); msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                elif msvcrt is not None:  # pragma: no cover
                    os.lseek(fd, 0, os.SEEK_SET); msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                os.close(fd)
    def _read_unlocked(self):
        try: return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError: return {"schema_version":2,"states":{}}
        except json.JSONDecodeError as exc: raise ValueError(f"invalid state store: {self.path}") from exc
    def _write_unlocked(self, doc):
        tmp=self.path.with_name(self.path.name+f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        os.replace(tmp,self.path)
    def load(self, key: str) -> AffectiveState | None:
        with self._locked(False): raw=(self._read_unlocked().get("states") or {}).get(key)
        if not isinstance(raw,dict): return None
        allowed=AffectiveState.__dataclass_fields__.keys(); return AffectiveState(**{k:v for k,v in raw.items() if k in allowed})
    def load_all(self) -> dict[str,AffectiveState]:
        with self._locked(False): rows=(self._read_unlocked().get("states") or {}).copy()
        allowed=AffectiveState.__dataclass_fields__.keys()
        return {k:AffectiveState(**{x:y for x,y in v.items() if x in allowed}) for k,v in rows.items() if isinstance(v,dict)}
    def update(self, key: str, updater) -> AffectiveState:
        """Serialize a state transition for one scope and return the committed state."""
        with self._locked(True):
            doc=self._read_unlocked(); states=doc.setdefault("states",{}); raw=states.get(key)
            allowed=AffectiveState.__dataclass_fields__.keys()
            current=AffectiveState(**{k:v for k,v in raw.items() if k in allowed}) if isinstance(raw,dict) else AffectiveState()
            updated=updater(current)
            if not isinstance(updated,AffectiveState): raise TypeError("updater must return AffectiveState")
            doc.setdefault("schema_version",2); states[key]=updated.asdict(); self._write_unlocked(doc); return updated
    def save(self, key: str, state: AffectiveState) -> None:
        self.update(key, lambda _current: state)
    def delete(self, key: str) -> None:
        with self._locked(True):
            doc=self._read_unlocked(); doc.setdefault("states",{}).pop(key,None); self._write_unlocked(doc)
