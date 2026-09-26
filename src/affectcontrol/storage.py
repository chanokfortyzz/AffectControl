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
    SCHEMA_VERSION=2
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
        try: doc=json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError: return {"schema_version":self.SCHEMA_VERSION,"states":{}}
        except json.JSONDecodeError as exc: raise ValueError(f"invalid state store: {self.path}") from exc
        version=int(doc.get("schema_version",1))
        if version==1:
            doc={"schema_version":self.SCHEMA_VERSION,"states":dict(doc.get("states") or {})}
        elif version!=self.SCHEMA_VERSION:
            raise ValueError(f"unsupported JsonStateStore schema_version={version}")
        return doc
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
            doc["schema_version"]=self.SCHEMA_VERSION; states[key]=updated.asdict(); self._write_unlocked(doc); return updated
    def save(self, key: str, state: AffectiveState) -> None:
        self.update(key, lambda _current: state)
    def delete(self, key: str) -> None:
        with self._locked(True):
            doc=self._read_unlocked(); doc.setdefault("states",{}).pop(key,None); self._write_unlocked(doc)
    def cleanup(self,ttl_s:float,*,now_s:float):
        cutoff=float(now_s)-float(ttl_s); removed=0
        with self._locked(True):
            doc=self._read_unlocked(); states=doc.setdefault("states",{})
            for key in list(states):
                if float((states[key] or {}).get("last_update_s") or 0.0) < cutoff:
                    states.pop(key,None); removed+=1
            if removed: self._write_unlocked(doc)
        return removed


class SQLiteStateStore:
    """Transactional single-host store for larger state sets. Uses only stdlib sqlite3."""
    SCHEMA_VERSION=1
    def __init__(self,path):
        import sqlite3
        self.sqlite3=sqlite3; self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._thread_lock=threading.RLock(); self._init()
    def _connect(self):
        c=self.sqlite3.connect(self.path,timeout=30,isolation_level=None)
        c.execute('PRAGMA busy_timeout=30000')
        return c
    def _init(self):
        import time
        last=None
        for attempt in range(60):
            try:
                with self._connect() as c:
                    c.execute('PRAGMA journal_mode=WAL')
                    c.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
                    c.execute('CREATE TABLE IF NOT EXISTS states (key TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at REAL NOT NULL)')
                    row=c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
                    if row is None:
                        c.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version',?)",(str(self.SCHEMA_VERSION),))
                        row=c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
                    if int(row[0])!=self.SCHEMA_VERSION: raise ValueError(f'unsupported SQLiteStateStore schema_version={row[0]}')
                return
            except self.sqlite3.OperationalError as exc:
                last=exc
                if 'locked' not in str(exc).lower(): raise
                time.sleep(min(0.5,0.01*(attempt+1)))
        raise last or RuntimeError('SQLiteStateStore initialization failed')
    def _decode(self,payload):
        raw=json.loads(payload); allowed=AffectiveState.__dataclass_fields__.keys(); return AffectiveState(**{k:v for k,v in raw.items() if k in allowed})
    def load(self,key):
        with self._connect() as c: row=c.execute('SELECT payload FROM states WHERE key=?',(key,)).fetchone()
        return self._decode(row[0]) if row else None
    def load_all(self):
        with self._connect() as c: rows=c.execute('SELECT key,payload FROM states').fetchall()
        return {k:self._decode(v) for k,v in rows}
    def update(self,key,updater):
        import time
        with self._thread_lock, self._connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT payload FROM states WHERE key=?',(key,)).fetchone(); current=self._decode(row[0]) if row else AffectiveState()
            updated=updater(current)
            if not isinstance(updated,AffectiveState): c.execute('ROLLBACK'); raise TypeError('updater must return AffectiveState')
            c.execute('INSERT INTO states(key,payload,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at',(key,json.dumps(updated.asdict(),ensure_ascii=False),time.time()))
            c.execute('COMMIT'); return updated
    def save(self,key,state): self.update(key,lambda _current:state)
    def delete(self,key):
        with self._connect() as c: c.execute('DELETE FROM states WHERE key=?',(key,))
    def cleanup(self,ttl_s,*,now_s=None):
        import time
        now=time.time() if now_s is None else float(now_s); cutoff=now-float(ttl_s)
        with self._connect() as c:
            cur=c.execute('DELETE FROM states WHERE updated_at < ?',(cutoff,)); return cur.rowcount
