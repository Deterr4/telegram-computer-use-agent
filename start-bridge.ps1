# Start (or restart) the Telegram bridge inside the pc-dehren container.
#
# The container restarts itself with Docker, but the bridge does not come back
# with it, so run this after a reboot or whenever the bot goes quiet.
# Credentials are read from the file inside the container, never passed on the
# command line, so they stay out of shell history.

$docker = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe"
$container = "pc-dehren"

$running = & $docker ps --filter "name=$container" --format "{{.Names}}" 2>$null
if (-not $running) {
    Write-Host "Container not running - starting it..." -ForegroundColor Yellow
    & $docker start $container | Out-Null
    Start-Sleep -Seconds 20
}

# Re-copy the script so local edits take effect without rebuilding anything.
$src = Join-Path $PSScriptRoot "bridge.py"
& $docker cp $src "${container}:/home/computeruse/bridge.py" 2>&1 | Out-Null

# Gmail / Calendar access. Credentials are copied separately and only once.
$conn = Join-Path $PSScriptRoot "google_connector.py"
if (Test-Path $conn) {
    & $docker cp $conn "${container}:/home/computeruse/google_connector.py" 2>&1 | Out-Null
}

# The role file gives the agent its job. Swap which one by changing $role,
# or set AGENT_ROLE_FILE to point somewhere else inside the container.
$role = Join-Path $PSScriptRoot "roles\general-assistant.md"
if (Test-Path $role) {
    & $docker cp $role "${container}:/home/computeruse/role.md" 2>&1 | Out-Null
    Write-Host "Role: $(Split-Path $role -Leaf)" -ForegroundColor Cyan
}

# pkill would match the shell running this command, so target the python
# process by its full path instead.
& $docker exec $container bash -c "pkill -f 'python3 bridge.py' || true" 2>&1 | Out-Null
Start-Sleep -Seconds 2

& $docker exec -d $container bash -c "set -a; . /home/computeruse/.tg.env; set +a; cd /home/computeruse && exec python3 bridge.py > /home/computeruse/bridge.log 2>&1"
Start-Sleep -Seconds 8

$log = & $docker exec $container bash -c "cat /home/computeruse/bridge.log" 2>&1
if ($log -match "bridge up as @(\S+)") {
    Write-Host "Bridge running - message @$($Matches[1]) on Telegram" -ForegroundColor Green
} else {
    Write-Host "Bridge did not start cleanly:" -ForegroundColor Red
    Write-Host $log
}
