"""Copy first, switch last. Never delete or overwrite existing user data."""
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from contextlib import closing

def validate_destination(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target:
        return source, target
    if source in target.parents or target in source.parents:
        raise ValueError('新旧数据目录不能互相包含，请选择另一个空文件夹。')
    if os.name == 'nt':
        import ctypes
        if str(target).startswith('\\\\') or ctypes.windll.kernel32.GetDriveTypeW(str(target.anchor)) == 4:
            raise ValueError('请选择本机磁盘目录，不支持网络共享目录。')
        if not Path(target.anchor).exists():
            raise ValueError('所选磁盘不可用。')
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ValueError('目标目录不是空文件夹；为避免覆盖数据，请新建一个空文件夹。')
    return source, target

def copy_data(source, target):
    """Caller must stop capture and drain Store before copying a running app."""
    source, target = validate_destination(source, target)
    if source == target:
        return {'files':0,'same_directory':True}
    target.mkdir(parents=True, exist_ok=True)
    # This owned temporary directory is always within the validated destination.
    with tempfile.TemporaryDirectory(prefix='.behindwatch-copy-', dir=target) as temp:
        stage = Path(temp)
        for name in ('settings.json','startup-error.txt'):
            p = source/name
            if p.is_file():
                shutil.copy2(p, stage/name)
        snapshots = source/'snapshots'
        if snapshots.exists():
            for p in snapshots.rglob('*'):
                if p.is_symlink() or not p.resolve().is_relative_to(source):
                    raise ValueError('截图目录包含外部链接，未迁移。')
                if p.is_file():
                    dest = stage/p.relative_to(source)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, dest)
        if (source/'events.sqlite3').exists():
            with closing(sqlite3.connect(source/'events.sqlite3')) as src, closing(sqlite3.connect(stage/'events.sqlite3')) as dst:
                src.backup(dst)
                # Log links must point to the new copies, not the preserved originals.
                rows = dst.execute("SELECT id,image FROM events WHERE image != ''").fetchall()
                for event_id, image in rows:
                    p = Path(image).resolve()
                    if p.is_relative_to(source):
                        dst.execute('UPDATE events SET image=? WHERE id=?', (str(target/p.relative_to(source)),event_id))
                dst.commit()
                if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise OSError('数据库完整性检查失败，保留原目录。')
        files = sum(p.is_file() for p in stage.rglob('*'))
        # All bytes and the SQLite integrity check are complete before publication.
        for p in stage.iterdir():
            dest = target/p.name
            if dest.exists():
                raise FileExistsError(f'目标目录发生变化：{p.name}')
            p.rename(dest)
    return {'files':files,'source':str(source),'target':str(target)}
