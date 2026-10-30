# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, copy_metadata
datas=[('models','models'),('assets','assets'),('licenses','licenses'),('THIRD_PARTY_NOTICES.md','.')]
for package in ('numpy','opencv-python-headless','onnxruntime','PySide6','PySide6_Essentials','PySide6_Addons','shiboken6','cv2-enumerate-cameras'):
    datas += copy_metadata(package)
a=Analysis(['main.py'], pathex=[], binaries=[], datas=datas,
    hiddenimports=['cv2_enumerate_cameras.windows_backend','cv2_enumerate_cameras._windows_backend'],
    excludes=['tkinter','matplotlib','torch','IPython','pytest'], noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='BehindWatch',console=False,icon='assets/app.ico')
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='BehindWatch')
