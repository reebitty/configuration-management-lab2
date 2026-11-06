@echo off
set MAIN="%~dp0..\src\main.py"
set URL=https://api.nuget.org/v3/index.json

echo === 1. Polly, max depth 3 -^> polly.svg ===
python %MAIN% -p Polly -r %URL% -d 3 -o polly.svg -a
echo.
echo === 2. Serilog, max depth 3 -^> serilog.svg ===
python %MAIN% -p Serilog -r %URL% -d 3 -o serilog.svg -a
echo.
echo === 3. xunit, max depth 2 -^> xunit.svg ===
python %MAIN% -p xunit -r %URL% -d 2 -o xunit.svg -a
echo.
echo === 4. Test repository with cycles -^> cycle.svg ===
python %MAIN% -p A -r "%~dp0..\repos\cycle.txt" -t -d 5 -o cycle.svg -a
