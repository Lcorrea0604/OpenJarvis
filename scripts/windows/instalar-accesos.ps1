<#
.SYNOPSIS
  Crea el acceso directo de JARVIS en el escritorio y, opcionalmente, lo
  configura para iniciar solo al encender Windows.

.EXAMPLE
  # Solo el acceso directo del escritorio
  powershell -ExecutionPolicy Bypass -File scripts\windows\instalar-accesos.ps1

.EXAMPLE
  # Acceso directo + inicio automatico con Windows
  powershell -ExecutionPolicy Bypass -File scripts\windows\instalar-accesos.ps1 -AlIniciar

.EXAMPLE
  # Quitar el inicio automatico
  powershell -ExecutionPolicy Bypass -File scripts\windows\instalar-accesos.ps1 -QuitarInicio
#>
param(
    [switch]$AlIniciar,
    [switch]$QuitarInicio
)

$ErrorActionPreference = "Stop"
$bat = Join-Path $PSScriptRoot "Jarvis.bat"
if (-not (Test-Path $bat)) { throw "No se encontro $bat" }
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$icon = Join-Path $repo "assets\jarvis.ico"

$shell = New-Object -ComObject WScript.Shell

function New-JarvisShortcut([string]$path, [int]$windowStyle) {
    $lnk = $shell.CreateShortcut($path)
    $lnk.TargetPath = $bat
    $lnk.WorkingDirectory = $repo
    $lnk.WindowStyle = $windowStyle   # 1 = normal, 7 = minimizada
    $lnk.Description = "JARVIS - asistente por voz (manos libres)"
    if (Test-Path $icon) { $lnk.IconLocation = $icon }
    $lnk.Save()
}

$startupLnk = Join-Path ([Environment]::GetFolderPath("Startup")) "JARVIS.lnk"

if ($QuitarInicio) {
    if (Test-Path $startupLnk) {
        Remove-Item $startupLnk
        Write-Host "Listo: JARVIS ya no inicia con Windows." -ForegroundColor Green
    } else {
        Write-Host "JARVIS no estaba configurado para iniciar con Windows."
    }
    return
}

$desktopLnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "JARVIS.lnk"
New-JarvisShortcut $desktopLnk 1
Write-Host "Acceso directo creado en el escritorio: $desktopLnk" -ForegroundColor Green

if ($AlIniciar) {
    New-JarvisShortcut $startupLnk 7
    Write-Host "JARVIS iniciara solo (minimizado) cada vez que enciendas Windows." -ForegroundColor Green
    Write-Host "Para quitarlo: powershell -ExecutionPolicy Bypass -File scripts\windows\instalar-accesos.ps1 -QuitarInicio"
}
