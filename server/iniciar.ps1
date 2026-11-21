<#
.SYNOPSIS
  Inicia el servidor del puesto de mando en Windows sin Docker.

.DESCRIPTION
  Abre una ventana por servicio: broker MQTT, mensajería, localización, dashboard y
  (opcional) listener de radio. Al final muestra las direcciones que deben usar los
  teléfonos conectados a la misma red Wi-Fi.

.EXAMPLE
  .\iniciar.ps1                       # con nodos FSK simulados
  .\iniciar.ps1 -Radio ninguno        # solo teléfonos por Wi-Fi (prueba entre teléfonos)
  .\iniciar.ps1 -Radio usb            # gateway ESP32-S3 por USB (detecta el puerto)
  .\iniciar.ps1 -Radio usb -Puerto COM5
#>
param(
  [ValidateSet("sim", "usb", "ninguno")]
  [string]$Radio = "sim",
  [string]$Puerto = ""
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
$py = Join-Path $here ".venv\Scripts\python.exe"

# 1. Entorno de Python
if (-not (Test-Path $py)) {
  Write-Host "Creando entorno de Python (solo la primera vez)..." -ForegroundColor Cyan
  python -m venv .venv
  & $py -m pip install --quiet -r requirements.txt amqtt
}

function Start-Service-Window([string]$title, [string]$command) {
  $full = "`$host.UI.RawUI.WindowTitle = '$title'; Set-Location '$here'; $command"
  Start-Process powershell -ArgumentList "-NoExit", "-Command", $full | Out-Null
}

# 2. Broker MQTT: Mosquitto si está instalado; si no, amqtt (Python)
$mosquitto = Get-Command mosquitto -ErrorAction SilentlyContinue
if ($mosquitto) {
  Start-Service-Window "Broker MQTT (Mosquitto)" "& '$($mosquitto.Source)' -p 1883"
} else {
  Start-Service-Window "Broker MQTT (amqtt)" "& '$here\.venv\Scripts\amqtt.exe'"
}
Start-Sleep -Seconds 3

# 3. Servicios
Start-Service-Window "Mensajeria" "& '$py' -m sarabhel.messaging"
Start-Service-Window "Localizacion" "& '$py' -m sarabhel.location"
Start-Service-Window "Dashboard" "& '$py' -m sarabhel.dashboard"

switch ($Radio) {
  "sim"    { Start-Service-Window "Listener (simulado)" "`$env:MESH_CONNECTION='sim'; & '$py' -m sarabhel.listener" }
  "usb"    { Start-Service-Window "Listener (gateway USB $Puerto)" "`$env:MESH_CONNECTION='usb'; `$env:MESH_USB_DEVICE='$Puerto'; & '$py' -m sarabhel.listener" }
  "ninguno" { }
}

# 4. Direcciones para los teléfonos
# Solo interfaces reales: las que tienen puerta de enlace (Wi-Fi / Ethernet) y la
# zona con cobertura de Windows (192.168.137.1). Se omiten adaptadores virtuales (WSL, VirtualBox).
$ips = @(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } |
  ForEach-Object { $_.IPv4Address.IPAddress })
$hotspot = Get-NetIPAddress -AddressFamily IPv4 -IPAddress "192.168.137.1" -ErrorAction SilentlyContinue
if ($hotspot) { $ips += "192.168.137.1 (zona con cobertura de este PC)" }
if (-not $ips) { $ips = @("(no se detectó red; conecta el PC a un Wi-Fi o activa la zona con cobertura)") }

Write-Host ""
Write-Host "Servidor iniciado (radio: $Radio)." -ForegroundColor Green
Write-Host "Dashboard en este PC:  http://localhost:8080"
Write-Host ""
Write-Host "En los teléfonos (misma red Wi-Fi), usa una de estas direcciones como servidor:" -ForegroundColor Yellow
foreach ($ip in $ips) { Write-Host "   http://${ip}:8080" }
Write-Host ""
Write-Host "Si los teléfonos no conectan: cuando Windows pregunte, permite a Python en redes privadas" -ForegroundColor DarkGray
Write-Host "(Firewall de Windows). Para detener todo, cierra las ventanas abiertas." -ForegroundColor DarkGray
