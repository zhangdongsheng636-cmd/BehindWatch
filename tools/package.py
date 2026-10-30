from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json

root=Path(__file__).resolve().parents[1]
delivery=root/'release-assets'
delivery.mkdir(exist_ok=True)
archives=[]
for filename,folder,prefix,skip in [
    ('BehindWatch-1.1.0-Windows-x64.zip',root/'dist/BehindWatch','BehindWatch',set()),
    ('BehindWatch-1.1.0-Python-source.zip',root,'BehindWatch-source',{'dist','build','dist-1.1','build-1.1','release-assets','__pycache__','.venv','.git'}),
]:
    dest=delivery/filename
    with ZipFile(dest,'w',ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(folder.rglob('*')):
            relative=p.relative_to(folder)
            if p.is_file() and not (set(relative.parts)&skip) and p.suffix!='.pyc':
                z.write(p,str(Path(prefix)/relative))
    with ZipFile(dest) as z:
        assert z.testzip() is None
    archives.append({'file':filename,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
(delivery/'SHA256.json').write_text(json.dumps(archives,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(archives,ensure_ascii=False,indent=2))
