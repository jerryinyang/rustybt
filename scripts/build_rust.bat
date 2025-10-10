@echo off
REM Build Rust extensions for RustyBT (Windows)
REM
REM Usage:
REM   scripts\build_rust.bat [dev|release]
REM
REM Arguments:
REM   dev     - Build in development mode (default, faster builds, no optimizations)
REM   release - Build in release mode (optimized, slower builds)

setlocal enabledelayedexpansion

REM Determine build mode
set BUILD_MODE=%1
if "%BUILD_MODE%"=="" set BUILD_MODE=dev

REM Check if we're in the project root
if not exist "rust\" (
    echo Error: rust\ directory not found
    echo Please run this script from the project root directory
    exit /b 1
)

REM Check if Rust is installed
where cargo >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: Rust toolchain not found
    echo Install Rust from: https://rustup.rs/
    exit /b 1
)

REM Check if maturin is installed
where maturin >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Warning: maturin not found, installing...
    pip install maturin
)

REM Build based on mode
cd rust

if /i "%BUILD_MODE%"=="dev" goto BUILD_DEV
if /i "%BUILD_MODE%"=="develop" goto BUILD_DEV
if /i "%BUILD_MODE%"=="development" goto BUILD_DEV
if /i "%BUILD_MODE%"=="release" goto BUILD_RELEASE
if /i "%BUILD_MODE%"=="prod" goto BUILD_RELEASE
if /i "%BUILD_MODE%"=="production" goto BUILD_RELEASE

echo Error: Invalid build mode: %BUILD_MODE%
echo Usage: %0 [dev^|release]
exit /b 1

:BUILD_DEV
echo Building Rust extension (development mode)...
maturin develop
goto BUILD_DONE

:BUILD_RELEASE
echo Building Rust extension (release mode)...
maturin build --release
echo Wheel created in rust\target\wheels\
goto BUILD_DONE

:BUILD_DONE
cd ..
echo.
echo Build complete!
echo.
echo Test the extension:
echo   python -c "from rustybt import rust_sum; print(rust_sum(2, 3))"
echo.
echo Run tests:
echo   pytest tests\rust\ -v

endlocal
