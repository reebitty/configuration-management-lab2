@echo off
set MAIN="%~dp0..\src\main.py"
set REPOS=%~dp0..\repos

echo === 1. Who depends on D: B and C, then A (repos\test_repo.txt) ===
python %MAIN% -p D -r "%REPOS%\test_repo.txt" -t -R
echo.
echo === 2. Library L used directly and transitively (repos\library.txt) ===
python %MAIN% -p L -r "%REPOS%\library.txt" -t -R
echo.
echo === 3. Library L, max depth 1 (only direct dependents) ===
python %MAIN% -p L -r "%REPOS%\library.txt" -t -R -d 1
echo.
echo === 4. Package F: no package depends on it ===
python %MAIN% -p F -r "%REPOS%\library.txt" -t -R
echo.
echo === 5. Cycle A-B-C-A (repos\cycle.txt) ===
python %MAIN% -p A -r "%REPOS%\cycle.txt" -t -R -d 5
echo.
echo === 6. Package E depends on itself ===
python %MAIN% -p E -r "%REPOS%\cycle.txt" -t -R
echo.
echo === 7. End of chain F, max depth 2 (repos\chain.txt) ===
python %MAIN% -p F -r "%REPOS%\chain.txt" -t -R -d 2
echo.
echo === 8. End of chain F, max depth 10 ===
python %MAIN% -p F -r "%REPOS%\chain.txt" -t -R -d 10
echo.
echo === 9. Package not found in test repository ===
python %MAIN% -p Z -r "%REPOS%\library.txt" -t -R
echo.
echo === 10. Reverse mode without test repository ===
python %MAIN% -p Serilog -r https://api.nuget.org/v3/index.json -R
