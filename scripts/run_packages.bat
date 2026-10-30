@echo off
set MAIN="%~dp0..\src\main.py"
set URL=https://api.nuget.org/v3/index.json

echo === Serilog, max depth 3 ===
python %MAIN% -p Serilog -r %URL% -d 3
echo.
echo === xunit, max depth 2 ===
python %MAIN% -p xunit -r %URL% -d 2
echo.
echo === System.ValueTuple (no dependencies) ===
python %MAIN% -p System.ValueTuple -r %URL%
echo.
echo === Newtonsoft.Json, max depth 1 (only direct dependencies) ===
python %MAIN% -p Newtonsoft.Json -r %URL% -d 1
