$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$pythonExecutable = Join-Path $projectDirectory '../../work/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Prepared local environment not found. Follow README installation instructions.'
}
Push-Location $projectDirectory
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $projectDirectory 'src'
    & $pythonExecutable -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Validation tests failed.' }
    & $pythonExecutable -m solar_hosting.cli
    if ($LASTEXITCODE -ne 0) { throw 'Baseline generation failed.' }
    $env:OPENBLAS_NUM_THREADS = '1'
    & $pythonExecutable -m solar_hosting.study
    if ($LASTEXITCODE -ne 0) { throw 'Study generation failed.' }
    & $pythonExecutable tools/build_report.py
    if ($LASTEXITCODE -ne 0) { throw 'Report generation failed.' }
} finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
