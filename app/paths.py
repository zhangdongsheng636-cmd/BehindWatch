"""User-selected local storage, with a small fixed bootstrap/lock directory."""
import json
import os
from pathlib import Path

CONTROL = Path(os.environ.get('BEHINDWATCH_DATA', str(Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'BehindWatch')))
LOCATOR = CONTROL / 'location.json'

def read_location():
    if os.environ.get('BEHINDWATCH_DATA'):
        return CONTROL
    if LOCATOR.exists():
        obj = json.loads(LOCATOR.read_text(encoding='utf-8'))
        path = Path(obj['data_dir'])
        if not path.is_absolute():
            raise ValueError('保存的数据目录不是绝对路径')
        return path
    return CONTROL

_data = read_location()

def data_dir():
    return _data

def select_directory(path):
    global _data
    path = Path(path).resolve()
    CONTROL.mkdir(parents=True, exist_ok=True)
    tmp = LOCATOR.with_suffix('.tmp')
    tmp.write_text(json.dumps({'data_dir':str(path)}, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        tmp.replace(LOCATOR)
    except OSError as e:
        # Some redirected Windows profile folders reject MoveFileEx with
        # ERROR_INVALID_HANDLE although ordinary file writes are supported.
        if getattr(e, 'winerror', None) != 6:
            raise
        payload = tmp.read_bytes()
        previous = LOCATOR.read_bytes() if LOCATOR.exists() else None
        if previous is not None:
            (CONTROL/'location.previous.json').write_bytes(previous)
        with LOCATOR.open('wb') as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        if LOCATOR.read_bytes() != payload:
            raise OSError('数据目录位置记录校验失败')
        tmp.unlink(missing_ok=True)
    _data = path
