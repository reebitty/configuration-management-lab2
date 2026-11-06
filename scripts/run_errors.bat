@echo off
set MAIN="%~dp0..\src\main.py"
set URL=https://api.nuget.org/v3/index.json

echo === 1. No parameters ===
python %MAIN%
echo.
echo === 2. Invalid package name ===
python %MAIN% --package "bad name!" --repo %URL%
echo.
echo === 3. Invalid repository URL ===
python %MAIN% --package Newtonsoft.Json --repo ftp://nuget.org
echo.
echo === 4. Test repository file not found ===
python %MAIN% --package A --repo missing_repo.txt --test-mode
echo.
echo === 5. File path without test mode ===
python %MAIN% --package A --repo "%~dp0..\repos\test_repo.txt"
echo.
echo === 6. Wrong image file extension ===
python %MAIN% --package Newtonsoft.Json --repo %URL% --output graph.png
echo.
echo === 7. Forbidden characters in image file name ===
python %MAIN% --package Newtonsoft.Json --repo %URL% --output "gr*ph.svg"
echo.
echo === 8. Directory for image file does not exist ===
python %MAIN% --package Newtonsoft.Json --repo %URL% --output missing_dir\graph.svg
echo.
echo === 9. Max depth is not a number ===
python %MAIN% --package Newtonsoft.Json --repo %URL% --max-depth abc
echo.
echo === 10. Max depth less than 1 ===
python %MAIN% --package Newtonsoft.Json --repo %URL% --max-depth 0
echo.
echo === 11. Several errors at once ===
python %MAIN% --package "bad name!" --repo nuget --output graph.png --max-depth -5
echo.
echo === 12. Package not found in repository ===
python %MAIN% --package NoSuchPackageXyz123 --repo %URL%
echo.
echo === 13. URL is not a NuGet service index ===
python %MAIN% --package Serilog --repo https://example.com/
echo.
echo === 14. Repository host is unreachable ===
python %MAIN% --package Serilog --repo https://no-such-host.invalid/index.json
