<#
.SYNOPSIS
  One-command setup of saved-reels-digest on Windows.

.DESCRIPTION
  Finds Python 3.9 or newer, checks the computer with doctor.py, creates the private
  Python environment the plugin uses (setup_env.py, about a minute and ~600 MB) and
  explains how to add the plugin to Claude Code. Running it again is safe: it only
  installs what is missing.

  From a clone of the repository:
    powershell -ExecutionPolicy Bypass -File install.ps1

  Without cloning anything (downloads the scripts to a temporary folder):
    irm https://raw.githubusercontent.com/ArmasCitoZ/saved-reels-digest/main/install.ps1 | iex

  Your files go to %USERPROFILE%\saved-reels-digest, or to the folder in the SRD_HOME
  environment variable.

.PARAMETER CheckOnly
  Only check the computer (Python, disk, folder, RAM); install nothing.

.NOTES
  Keep this file ASCII and compatible with Windows PowerShell 5.1, which is what a fresh
  Windows has: no ?? or ?. operators, no && or || between commands, no ternaries.
  tests/test_install_ps1.py checks this.
#>
param(
    [switch]$CheckOnly
)

$RepoZip = 'https://github.com/ArmasCitoZ/saved-reels-digest/archive/refs/heads/main.zip'
$MinPython = [version]'3.9'

function Write-Step([string]$Text) {
    Write-Host ''
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Get-PythonVersion([string[]]$Command) {
    # The Microsoft Store "python" alias exists even when Python is not installed: it opens
    # the Store and prints nothing, so a command only counts when it really answers.
    if (-not (Get-Command $Command[0] -ErrorAction SilentlyContinue)) { return $null }
    $rest = @($Command | Select-Object -Skip 1)
    try {
        $out = & $Command[0] @rest -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
    } catch {
        return $null
    }
    if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
    try {
        return [version]("$($out | Select-Object -Last 1)".Trim())
    } catch {
        return $null
    }
}

function Find-Python {
    # py is the launcher python.org installs on Windows; python3 and python cover the rest
    $tooOld = $null
    foreach ($candidate in @(@('py', '-3'), @('python3'), @('python'))) {
        $version = Get-PythonVersion $candidate
        if ($null -eq $version) { continue }
        if ($version -ge $MinPython) {
            return @{ Command = $candidate; Version = $version }
        }
        if ($null -eq $tooOld) { $tooOld = $version }
    }
    if ($null -ne $tooOld) { return @{ Command = $null; Version = $tooOld } }
    return $null
}

function Get-ScriptsFolder([string]$Temp) {
    # Inside a clone, use its scripts; when piped through iex there is no file, so download them.
    if ($PSScriptRoot) {
        $local = Join-Path (Join-Path (Join-Path $PSScriptRoot 'skills') 'digest') 'scripts'
        if (Test-Path (Join-Path $local 'setup_env.py')) { return $local }
    }
    Write-Step 'Downloading the plugin scripts from GitHub'
    $zip = Join-Path $Temp 'saved-reels-digest.zip'
    # Windows PowerShell 5.1 may still default to TLS 1.0, which GitHub refuses
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor
        [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $RepoZip -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $Temp -Force
    $root = Get-ChildItem -Path $Temp -Directory | Select-Object -First 1
    return Join-Path (Join-Path (Join-Path $root.FullName 'skills') 'digest') 'scripts'
}

function Invoke-Python([string[]]$Python, [string]$Script, [string[]]$Arguments) {
    $rest = @($Python | Select-Object -Skip 1)
    # Out-Host: show the output now, and keep it out of this function's return value
    & $Python[0] @rest $Script @Arguments | Out-Host
    return $LASTEXITCODE
}

function Install-SavedReels([switch]$CheckOnly) {
    $ErrorActionPreference = 'Stop'
    Write-Host 'saved-reels-digest: setup for Windows' -ForegroundColor Green

    Write-Step "Looking for Python $MinPython or newer"
    $found = Find-Python
    if ($null -eq $found) {
        Write-Host 'Python is not installed (or not in the PATH).' -ForegroundColor Yellow
        Write-Host 'Install it with:   winget install -e --id Python.Python.3.12'
        Write-Host 'or from https://www.python.org/downloads/ ticking "Add python.exe to PATH".'
        Write-Host 'Then open a NEW PowerShell window and run this again.'
        return 1
    }
    if ($null -eq $found.Command) {
        Write-Host "Found Python $($found.Version), but $MinPython or newer is needed." -ForegroundColor Yellow
        Write-Host 'Install a newer one with:   winget install -e --id Python.Python.3.12'
        return 1
    }
    $python = $found.Command
    Write-Host "Using Python $($found.Version) ($($python -join ' '))"

    $temp = Join-Path ([IO.Path]::GetTempPath()) ('saved-reels-digest-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $temp | Out-Null
    try {
        $scripts = Get-ScriptsFolder $temp

        Write-Step 'Checking this computer (doctor.py)'
        if ((Invoke-Python $python (Join-Path $scripts 'doctor.py') @()) -ne 0) {
            Write-Host 'Fix the FAIL lines above and run this again.' -ForegroundColor Yellow
            return 1
        }
        if ($CheckOnly) {
            Write-Host ''
            Write-Host 'Check only: nothing was installed.'
            return 0
        }

        Write-Step 'Creating the Python environment (setup_env.py, first time about a minute)'
        if ((Invoke-Python $python (Join-Path $scripts 'setup_env.py') @()) -ne 0) {
            Write-Host 'Setup failed: read the error above. Running this again resumes it.' -ForegroundColor Yellow
            return 1
        }
    } finally {
        Remove-Item -Recurse -Force -Path $temp -ErrorAction SilentlyContinue
    }

    Write-Step 'Last step: add the plugin to Claude Code'
    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
        Write-Host 'Claude Code is not installed yet: https://code.claude.com/docs/en/setup' -ForegroundColor Yellow
        Write-Host 'Install it, open a new PowerShell window, then:'
    }
    Write-Host 'Type "claude" and, inside Claude Code, run:'
    Write-Host '  /plugin marketplace add ArmasCitoZ/saved-reels-digest'
    Write-Host '  /plugin install saved-reels@saved-reels-digest'
    Write-Host 'Restart Claude Code and type /saved-reels:digest'
    return 0
}

$code = Install-SavedReels -CheckOnly:$CheckOnly
# Run as a file, report the exit code. Piped through iex, "exit" would close the user's window.
if ($PSCommandPath) { exit $code }
