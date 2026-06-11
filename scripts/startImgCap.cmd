@echo off
setlocal

set "WORKINGDIRECTORY="C:\Users\%USERNAME%\Documents\Dev\GitHub\image-captioning"
set "VENV=C:\Users\%USERNAME%\Envs\imgcap-gpu-py3119"

cd /d "%WORKINGDIRECTORY%"
call "%VENV%\Scripts\activate.bat"

rem optional sanity checks
python -V
where python

rem start Jupyter in this venv
jupyter notebook