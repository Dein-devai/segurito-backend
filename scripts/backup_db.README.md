# Backup de la base SQLite

`backup_db.ps1` toma un snapshot consistente de `segurito.db`:

1. Ejecuta `PRAGMA wal_checkpoint(TRUNCATE)` para volcar el WAL.
2. Copia el `.db` (y sus `-wal` / `-shm` si existen) a `$DestDir\segurito_<timestamp>.db`.
3. Mantiene las últimas `$Keep` copias (default 96 ≈ 48 h con frecuencia 30 min).

## Ejecución manual

```powershell
.\scripts\backup_db.ps1
.\scripts\backup_db.ps1 -DbPath C:\dev\PoC-MVP-Challenge\segurito.db -DestDir D:\backups\segurito
```

## Programar cada 30 minutos (Task Scheduler)

Desde una PowerShell **como administrador**, en la raíz del repo:

```powershell
$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PWD\scripts\backup_db.ps1`""

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 30) `
    -RepetitionDuration ([TimeSpan]::MaxValue)

Register-ScheduledTask -TaskName 'Segurito-BackupDB' `
    -Action $action -Trigger $trigger `
    -Description 'Backup cada 30 min de segurito.db' `
    -RunLevel Highest
```

Para desinstalar: `Unregister-ScheduledTask -TaskName 'Segurito-BackupDB' -Confirm:$false`.
