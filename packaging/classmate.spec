# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 빌드 설정 — 실행:  pyinstaller --noconfirm --clean packaging/classmate.spec
# 결과: dist/ClassMate/ClassMate.exe (폴더형, 설치 파일은 packaging/installer.iss 로 만듦)
import importlib.util
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 (PyInstaller 가 제공)

hidden = ["openpyxl", "et_xmlfile"]
# AI 보조 기능의 Anthropic 연결 구성요소는 설치되어 있을 때만 함께 묶는다 (없어도 나머지 기능은 모두 작동)
if importlib.util.find_spec("anthropic") is not None:
    hidden.append("anthropic")

a = Analysis(  # noqa: F821
    [os.path.join(ROOT, "server.py")],
    pathex=[ROOT, os.path.join(ROOT, "vendor")],
    datas=[(os.path.join(ROOT, "static"), "static")],
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "PIL", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ClassMate",
    icon=os.path.join(ROOT, "packaging", "classmate.ico"),
    console=True,  # 검은 창을 닫으면 프로그램이 종료됨 (교사가 종료 방법을 알기 쉽게)
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="ClassMate", upx=False)  # noqa: F821
