$root = Split-Path -Parent $PSScriptRoot
$python = "C:\Users\fedef\AppData\Local\Programs\Python\Python312\python.exe"

function Start-ComponentWindow {
    param(
        [string]$Module,
        [string]$Arguments = ""
    )

    $command = "Set-Location '$root'; & '$python' -m $Module $Arguments"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $command
}

# Start the core first so MQTT subscriptions are active before drones register.
Start-ComponentWindow -Module "apps.airspace_core.main"
Start-Sleep -Seconds 2

Start-ComponentWindow -Module "apps.dashboard.main"
Start-ComponentWindow -Module "apps.control_gateway.main"
Start-Sleep -Seconds 2

Start-ComponentWindow -Module "apps.drone_simulator.main" -Arguments "--drones 6 --manual-drone-id drone-rpi-001"
