@echo off
set PYTHONIOENCODING=utf-8
uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
