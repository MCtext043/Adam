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
        "SMTP_FROM"
    )
    $optionalKeys = @(
        "SESSION_SECRET",
        "ADMIN_USERNAME",
        "ADMIN_PASSWORD"
    )

    $envLines = @()
    foreach ($line in Get-Content ".env") {
        if ($line -match "^\s*#" -or $line -notmatch "=") {
            continue
        }

        $key = ($line -split "=", 2)[0].Trim()
        $value = ($line -split "=", 2)[1].Trim()

        if ($alwaysKeys -contains $key) {
            $envLines += $line
            continue
        }

        if (($optionalKeys -contains $key) -and $value -and ($value -notmatch "замените_")) {
            $envLines += $line
        }
    }

    # Docker Compose expects env files without BOM and with Unix line endings.
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
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

$remoteScript = @'
set -euo pipefail
mkdir -p /opt/adam-delivery
cd /opt/adam-delivery

if [ -f .env ]; then
  cp .env ".env.backup.$(date +%Y%m%d%H%M%S)"
else
  touch .env
fi

# Normalize old Windows/BOM env content left from previous deploy attempts.
sed -i 's/\xEF\xBB\xBF//g; s/\r$//' .env

# Remove app-level values that are refreshed from the local .env, keep server DB/port values.
for key in SMTP_HOST SMTP_PORT SMTP_USE_TLS SMTP_USER SMTP_PASSWORD SMTP_FROM SESSION_SECRET ADMIN_USERNAME ADMIN_PASSWORD; do
  sed -i "/^${key}=/d" .env
done

cat /tmp/adam-smtp.env >> .env
sed -i 's/\xEF\xBB\xBF//g; s/\r$//' .env
tar -xzf /tmp/adam-deploy.tar.gz -C /opt/adam-delivery

docker compose --profile app up -d --build
docker compose ps

echo "Waiting for app health..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${APP_PORT:-8010}/health"; then
    echo
    echo "Health check passed."
    rm -f /tmp/adam-deploy.tar.gz /tmp/adam-smtp.env
    exit 0
  fi
  sleep 2
done

echo "Health check failed. Last app logs:"
docker logs --tail=120 adam-web || true
exit 1
'@

Write-Host "Deploying on server. Enter SSH password when prompted."
$remoteScript | ssh "${User}@${Server}" "bash -s"
Assert-LastExitCode "Remote deploy"

Remove-Item -Force $archive, $smtpEnv -ErrorAction SilentlyContinue
Write-Host "Deploy complete."
