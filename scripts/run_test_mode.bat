@echo off
set MAIN="%~dp0..\src\main.py"
set REPOS=%~dp0..\repos

echo === 1. Shared dependency D (repos\test_repo.txt) ===
python %MAIN% -p A -r "%REPOS%\test_repo.txt" -t
echo.
echo === 2. Graph of another package C ===
python %MAIN% -p C -r "%REPOS%\test_repo.txt" -t
echo.
echo === 3. Cycle A-B-C-A and self-dependency E (repos\cycle.txt) ===
python %MAIN% -p A -r "%REPOS%\cycle.txt" -t -d 5
echo.
echo === 4. Same cycle from package B, max depth 3 ===
python %MAIN% -p B -r "%REPOS%\cycle.txt" -t
echo.
echo === 5. Chain A-B-C-D-E-F, max depth 1 (repos\chain.txt) ===
python %MAIN% -p A -r "%REPOS%\chain.txt" -t -d 1
echo.
echo === 6. Chain, max depth 3 ===
python %MAIN% -p A -r "%REPOS%\chain.txt" -t -d 3
echo.
echo === 7. Chain, max depth 10 (whole graph) ===
python %MAIN% -p A -r "%REPOS%\chain.txt" -t -d 10
echo.
echo === 8. Package not found in test repository ===
python %MAIN% -p Z -r "%REPOS%\test_repo.txt" -t
echo.
echo === 9. Invalid test repository file (repos\invalid.txt) ===
python %MAIN% -p A -r "%REPOS%\invalid.txt" -t
