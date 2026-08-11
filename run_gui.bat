@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
if exist "E:\python\3.12\pythonw.exe" (
  start "" "E:\python\3.12\pythonw.exe" -m fenix_default_navdata.gui
) else (
  start "" pyw -3 -m fenix_default_navdata.gui
)
