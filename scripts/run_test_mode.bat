@echo off
rem Run in test repository mode (short options)
python "%~dp0..\src\main.py" -p A -r "%~dp0..\repos\test_repo.txt" -t -o test_graph.svg -a -d 5
echo.
rem Run with default values of optional parameters
python "%~dp0..\src\main.py" -p A -r "%~dp0..\repos\test_repo.txt" -t
