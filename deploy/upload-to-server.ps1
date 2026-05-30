param(
    [string]$Server = "45.11.26.79",
    [string]$User = "root",
    [string]$RemoteDir = "/opt/adam-delivery"
)

$ErrorActionPreference = "Stop"

function Assert-LastExitCode {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$stamp = Get-Date -Format "yyyyMMddHHmmss"
$archive = Join-Path $env:TEMP "adam-deploy-$stamp.tar.gz"
$smtpEnv = Join-Path $env:TEMP "adam-smtp-$stamp.env"
$remoteSh = Join-Path $env:TEMP "adam-remote-$stamp.sh"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

Write-Host "Preparing deploy package from $repoRoot"
Push-Location $repoRoot
try {
    if (-not (Test-Path ".env")) {
        throw "Local .env not found. Fill .env before deploy."
    }

    $alwaysKeys = @(
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USE_TLS",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "SMTP_FROM",
        "SMTP_FROM_NAME"
    )
    $optionalKeys = @(
        "SESSION_SECRET",
        "ADMIN_USERNAME",
        "ADMIN_PASSWORD",
        "PUBLIC_BASE_URL",
        "ELPLAT_ENABLED",
        "ELPLAT_API_URL",
        "ELPLAT_LOGIN",
        "ELPLAT_PASSWORD",
        "ELPLAT_ORG_ID"
    )

    function Normalize-SmtpFrom([string]$Value, [string]$SmtpUser) {
        if ($Value -match '<([^>]+@[^>]+)>') {
            return $Matches[1].Trim()
        }
        if ($Value -match '@' -and $Value -notmatch '\s') {
            return $Value.Trim()
        }
        if ($SmtpUser) {
            return $SmtpUser.Trim()
        }
        return $Value.Trim()
    }

    $vars = @{}
    foreach ($line in Get-Content ".env" -Encoding utf8) {
        if ($line -match "^\s*#" -or $line -notmatch "=") {
            continue
        }
        $key = ($line -split "=", 2)[0].Trim()
        $value = ($line -split "=", 2)[1].Trim().Trim('"').Trim("'")
        $vars[$key] = $value
    }

    $smtpUser = $vars["SMTP_USER"]
    if (-not $smtpUser -and $vars.ContainsKey("SMTP_FROM")) {
        $smtpUser = Normalize-SmtpFrom $vars["SMTP_FROM"] ""
        if ($smtpUser) {
            $vars["SMTP_USER"] = $smtpUser
            Write-Host "SMTP_USER taken from SMTP_FROM: $smtpUser"
        }
    }

    if ($vars.ContainsKey("SMTP_HOST") -and $vars["SMTP_HOST"]) {
        $missing = @()
        if (-not $vars["SMTP_USER"]) { $missing += "SMTP_USER" }
        if (-not $vars["SMTP_PASSWORD"]) { $missing += "SMTP_PASSWORD" }
        if ($missing.Count -gt 0) {
            throw "Local .env: SMTP_HOST is set but missing: $($missing -join ', '). Add them before deploy."
        }
    }

    $envLines = @()
    foreach ($key in $alwaysKeys) {
        if (-not $vars.ContainsKey($key)) { continue }
        $value = $vars[$key]
        if ($key -eq "SMTP_FROM") {
            $value = Normalize-SmtpFrom $value $smtpUser
            if (-not $vars["SMTP_USER"]) {
                $vars["SMTP_USER"] = $value
            }
        }
        $envLines += "$key=$value"
    }

    # Всегда корректное UTF-8 имя отправителя (в .env часто cp1251 -> кракозябры в почте)
    $cafeFromName = -join @(
        [char]0x041A, [char]0x0430, [char]0x0444, [char]0x0435, " ",
        [char]0x00AB, [char]0x0410, [char]0x0434, [char]0x0430, [char]0x043C, [char]0x00BB
    )
    $envLines = @($envLines | Where-Object { $_ -notmatch "^SMTP_FROM_NAME=" })
    $envLines += "SMTP_FROM_NAME=$cafeFromName"

    if ($envLines.Count -gt 0) {
        $synced = @($alwaysKeys | Where-Object { $vars.ContainsKey($_) })
        Write-Host "SMTP keys to sync on server: $($synced -join ', ')"
    } else {
        Write-Host "WARNING: no SMTP keys in local .env - server mail settings will be REMOVED on deploy."
    }
    foreach ($key in $optionalKeys) {
        if (-not $vars.ContainsKey($key)) { continue }
        $value = $vars[$key]
        if ($value -and ($value -notmatch "замените_")) {
            $envLines += "$key=$value"
        }
    }
    if ($envLines -notmatch "PUBLIC_BASE_URL=") {
        $envLines += "PUBLIC_BASE_URL=http://kafeadam.ru"
    }

    # Docker Compose expects env files without BOM and with Unix line endings.
    [System.IO.File]::WriteAllText($smtpEnv, (($envLines -join "`n") + "`n"), $utf8NoBom)

    tar -czf $archive `
        --exclude="./.git" `
        --exclude="./.venv" `
        --exclude="./__pycache__" `
        --exclude="./.env" `
        --exclude="./.cursor" `
        --exclude="./terminals" `
        --exclude="*.pyc" `
        .
}
finally {
    Pop-Location
}

Write-Host "Uploading archive. Enter SSH password when prompted."
scp $archive "${User}@${Server}:/tmp/adam-deploy.tar.gz"
Assert-LastExitCode "Upload archive"
scp $smtpEnv "${User}@${Server}:/tmp/adam-smtp.env"
Assert-LastExitCode "Upload env"

$remoteShTemplate = Join-Path $PSScriptRoot "remote-deploy.sh"
if (-not (Test-Path $remoteShTemplate)) {
    throw "Missing deploy/remote-deploy.sh"
}
$remoteScriptUnix = (Get-Content $remoteShTemplate -Raw).Replace('__REMOTE_DIR__', $RemoteDir)
$remoteScriptUnix = ($remoteScriptUnix -replace "`r`n", "`n") -replace "`r", "`n"
[System.IO.File]::WriteAllText($remoteSh, $remoteScriptUnix, $utf8NoBom)

Write-Host "Uploading remote deploy script."
scp $remoteSh "${User}@${Server}:/tmp/adam-deploy-remote.sh"
Assert-LastExitCode "Upload remote script"

Write-Host "Deploying on server. Enter SSH password when prompted."
ssh "${User}@${Server}" "bash /tmp/adam-deploy-remote.sh"
Assert-LastExitCode "Remote deploy"

Remove-Item -Force $archive, $smtpEnv, $remoteSh -ErrorAction SilentlyContinue
Write-Host "Deploy complete."
