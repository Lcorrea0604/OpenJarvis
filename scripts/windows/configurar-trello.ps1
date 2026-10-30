<#
.SYNOPSIS
  Conecta JARVIS con tu cuenta de Trello (una sola vez).

  1. Abre https://trello.com/power-ups/admin, crea una integracion ("New")
     y copia su API Key.
  2. En esa misma pagina, haz clic en el enlace "Token" (junto a la API Key),
     pulsa "Permitir" y copia el token.
  3. Corre este script y pega los dos valores cuando te los pida.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\windows\configurar-trello.ps1
#>
$ErrorActionPreference = "Stop"

Write-Host "Configuracion de Trello para JARVIS" -ForegroundColor Cyan
Write-Host "Si aun no tienes la API Key, abre: https://trello.com/power-ups/admin"
Write-Host ""

$key = (Read-Host "Pega tu API Key de Trello").Trim()
$token = (Read-Host "Pega tu Token de Trello").Trim()
if (-not $key -or -not $token) { throw "Faltan la API Key o el Token." }

try {
    $me = Invoke-RestMethod "https://api.trello.com/1/members/me?fields=fullName,username&key=$key&token=$token"
} catch {
    Write-Host "Trello rechazo la clave o el token. Revisa que los copiaste completos." -ForegroundColor Red
    exit 1
}

$boards = Invoke-RestMethod "https://api.trello.com/1/members/me/boards?filter=open&fields=name&key=$key&token=$token"

[Environment]::SetEnvironmentVariable("TRELLO_API_KEY", $key, "User")
[Environment]::SetEnvironmentVariable("TRELLO_TOKEN", $token, "User")
Write-Host ""
Write-Host "Conectado como $($me.fullName) (@$($me.username))." -ForegroundColor Green
Write-Host "Tableros encontrados:"
$i = 1
foreach ($b in $boards) { Write-Host ("  {0}. {1}" -f $i, $b.name.Trim()); $i++ }

$choice = Read-Host "Numero del tablero que Jarvis usara por defecto (Enter para ninguno)"
if ($choice -match '^\d+$' -and [int]$choice -ge 1 -and [int]$choice -le $boards.Count) {
    $default = $boards[[int]$choice - 1].name.Trim()
    [Environment]::SetEnvironmentVariable("TRELLO_DEFAULT_BOARD", $default, "User")
    Write-Host "Tablero por defecto: $default" -ForegroundColor Green
}

Write-Host ""
Write-Host "Listo. Cierra esta ventana y abre JARVIS de nuevo para que tome los cambios."
