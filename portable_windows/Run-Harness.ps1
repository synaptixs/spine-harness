[CmdletBinding()]
param(
    [ValidateSet('doctor','bootstrap','login','prepare','run','report','verify','selftest')]
    [string]$Action = 'doctor',
    [string]$Distro = 'Ubuntu',
    [string]$Config = 'benchmark.json',
    [string]$SpineSource = '',
    [switch]$Approved,
    [switch]$ApproveChecklist,
    [switch]$DeviceAuth
)
$ErrorActionPreference = 'Stop'
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw 'Install WSL2 first: wsl --install -d Ubuntu. See QUICKSTART.md.'
}
# Arguments are forwarded as argv, never interpolated into Linux shell code.
$LinuxRoot = & wsl.exe --distribution $Distro --exec wslpath -a -u $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw 'Cannot access package in WSL. Initialize Ubuntu and use a local Windows folder.' }
$LinuxRoot = ($LinuxRoot | Out-String).Trim()
$Command = @('benchmark.py', $Action)
if ($Action -eq 'verify') { $Command = @('verify_package.py') }
elseif ($Action -eq 'selftest') { $Command = @('-m', 'unittest', '-v', 'test_portable', 'test_jira_benchmark', 'test_report_usage', 'test_wsl_support') }
elseif ($Action -ne 'doctor') {
    $ConfigPath = if ([System.IO.Path]::IsPathRooted($Config)) { $Config } else { Join-Path $PSScriptRoot $Config }
    $LinuxConfig = & wsl.exe --distribution $Distro --exec wslpath -a -u $ConfigPath
    if ($LASTEXITCODE -ne 0) { throw 'Cannot convert the config path for WSL.' }
    $Command += @('--config', ($LinuxConfig | Out-String).Trim())
    if ($SpineSource) { $Command += @('--spine-source', $SpineSource) }
    if ($Approved) { $Command += '--approved' }
    if ($ApproveChecklist) { $Command += '--approve-checklist' }
    if ($DeviceAuth) { $Command += '--device-auth' }
}
& wsl.exe --distribution $Distro --exec python3 "$LinuxRoot/wsl_entry.py" @Command
exit $LASTEXITCODE
