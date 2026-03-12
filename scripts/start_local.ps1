$root = Split-Path -Parent $PSScriptRoot

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; python -m apps.airspace_core.main"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; python -m apps.dashboard.main"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; python -m apps.control_gateway.main"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; python -m apps.drone_simulator.main --drones 5"
