# Segurito — Backup automático de la base SQLite
#
# Estrategia:
#   1. Forzar wal_checkpoint(TRUNCATE) para que TODO esté en el .db principal.
#   2. Copiar atómicamente el archivo a un destino con timestamp.
#   3. Mantener máximo $Keep copias (FIFO) para no llenar disco.
#
# Uso manual:   .\scripts\backup_db.ps1
# Programado:   ver scripts/backup_db.README.md
#
# Salida con código != 0 si algo falla, para que Task Scheduler reporte.

[CmdletBinding()]
param(
    [string]$DbPath = "$PSScriptRoot\..\segurito.db",
    [string]$DestDir = "$env:USERPROFILE\Google Drive\segurito-backup",
    [int]$Keep = 96  # ~48 h con un backup cada 30 min
)

$ErrorActionPreference = 'Stop'

function Resolve-FullPath([string]$path) {
    $resolved = Resolve-Path -LiteralPath $path -ErrorAction SilentlyContinue
    if ($null -ne $resolved) { return $resolved.Path }
    return [System.IO.Path]::GetFullPath($path)
}

$DbPath = Resolve-FullPath $DbPath

if (-not (Test-Path -LiteralPath $DbPath)) {
    Write-Error "No existe la base: $DbPath"
    exit 1
}

if (-not (Test-Path -LiteralPath $DestDir)) {
    New-Item -ItemType Directory -Path $DestDir -Force | Out-Null
}

# --- 1) Checkpoint WAL ------------------------------------------------------
# Usamos sqlite3.exe si está; si no, hacemos checkpoint vía Python (que viene
# en el .venv del repo).
$sqlite3 = Get-Command sqlite3 -ErrorAction SilentlyContinue
if ($sqlite3) {
    & $sqlite3.Path $DbPath "PRAGMA wal_checkpoint(TRUNCATE);" | Out-Null
} else {
    $venvPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        & $venvPython -c "import sqlite3, sys; c = sqlite3.connect(sys.argv[1]); c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c.close()" $DbPath
    } else {
        Write-Warning "No se encontró sqlite3 ni .venv\python; el backup copiará el .db sin checkpoint."
    }
}

# --- 2) Copia con timestamp -------------------------------------------------
$ts = Get-Date -Format 'yyyyMMdd_HHmm'
$dest = Join-Path $DestDir "segurito_$ts.db"
Copy-Item -LiteralPath $DbPath -Destination $dest -Force

# Copiamos también los auxiliares por si quedó algo en el WAL.
foreach ($suffix in @('-wal', '-shm')) {
    $aux = "$DbPath$suffix"
    if (Test-Path -LiteralPath $aux) {
        Copy-Item -LiteralPath $aux -Destination "$dest$suffix" -Force
    }
}

Write-Host "[backup] OK -> $dest"

# --- 3) Rotación ------------------------------------------------------------
$pattern = 'segurito_*.db'
$old = Get-ChildItem -LiteralPath $DestDir -Filter $pattern |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip $Keep
foreach ($f in $old) {
    Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
    foreach ($suffix in @('-wal', '-shm')) {
        $aux = "$($f.FullName)$suffix"
        if (Test-Path -LiteralPath $aux) {
            Remove-Item -LiteralPath $aux -Force -ErrorAction SilentlyContinue
        }
    }
}
