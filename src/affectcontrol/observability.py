from __future__ import annotations
import json, threading, time
from pathlib import Path
from typing import Protocol, Any

class TraceSink(Protocol):
    def emit(self, event: str, **fields: Any) -> None: ...

class NullTraceSink:
    def emit(self,event: str,**fields: Any) -> None:
        return None

class JsonlTraceSink:
    def __init__(self,path):
        self.path=Path(path); self._lock=threading.Lock()
    def emit(self,event: str,**fields: Any) -> None:
        row={"ts":time.time(),"event":event,**fields}
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self._lock, self.path.open('a',encoding='utf-8') as f:
            f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
