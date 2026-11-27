@echo off
chcp 65001 > nul
title 학급 편성 도우미
cd /d "%~dp0"
echo.
echo  학급 편성 도우미를 시작합니다...
echo.
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" > nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" > nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo  [안내] Python 3.9 이상이 필요합니다. 아직 설치되어 있지 않습니다.
  echo.
  echo   1. 곧 열리는 python.org 페이지에서 Python 을 내려받아 설치하세요.
  echo   2. 설치 첫 화면에서 "Add python.exe to PATH" 에 꼭 체크하세요.
  echo   3. 설치가 끝나면 이 파일 ^(실행하기.bat^)을 다시 더블클릭하세요.
  echo.
  start "" "https://www.python.org/downloads/windows/"
  pause
  exit /b 1
)
echo  잠시 후 웹브라우저가 자동으로 열립니다.
echo  이 검은 창을 닫으면 프로그램이 종료됩니다. (자료는 자동 저장되어 있습니다)
echo.
%PY% server.py
if errorlevel 1 (
  echo.
  echo  [오류] 프로그램을 시작하지 못했습니다. 위의 메시지를 확인하세요.
  pause
)
