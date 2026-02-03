@echo off
chcp 65001 > nul
echo ========================================
echo Running Butler Project Tests
echo ========================================
echo.

python -m pytest tests/ -v --tb=short --disable-warnings

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo All tests passed!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo Some tests failed. Please review the output above.
    echo ========================================
)

pause
