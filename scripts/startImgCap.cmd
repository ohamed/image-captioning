@echo off
setlocal

set "WORKINGDIRECTORY="C:\Users\o.hamed\Documents\Dev\GitHub\AgraSim"
set "VENV=C:\Users\o.hamed\Envs\agrasim-ydata-py3119"

cd /d "%WORKINGDIRECTORY%"
call "%VENV%\Scripts\activate.bat"

rem optional sanity checks
python -V
where python

rem start Jupyter in this venv
jupyter notebook