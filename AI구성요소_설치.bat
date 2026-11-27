@echo off
chcp 65001 > nul
title AI 연결 구성요소 설치
cd /d "%~dp0"
echo.
echo  Anthropic Claude API 연결 구성요소(anthropic)를 설치합니다.
echo  - AI 보조 기능에서 'Anthropic Claude API' 를 사용할 때만 필요합니다.
echo  - 내장 간이 해석기, 이 PC의 Ollama 등은 설치 없이 사용할 수 있습니다.
echo  - 인터넷 연결이 필요합니다.
echo.
pause
set "PY=py -3"
py -3 --version > nul 2>&1
if errorlevel 1 set "PY=python"
%PY% -m pip install --user --upgrade anthropic
echo.
if errorlevel 1 (echo  [오류] 설치하지 못했습니다. 인터넷 연결과 학교 보안 정책을 확인하세요.) else (echo  설치가 끝났습니다. 프로그램을 다시 실행하세요.)
pause
