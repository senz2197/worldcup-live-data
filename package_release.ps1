param(
    [switch]$CreateSharePackage,
    [string]$ShareOutputDirectory = ""
)

$ErrorActionPreference = "Stop"

$projectDir = (Resolve-Path $PSScriptRoot).Path
$versionInfo = Get-Content -LiteralPath (Join-Path $projectDir "version.json") -Raw |
    ConvertFrom-Json
$version = [string]$versionInfo.version
$publishRoot = Join-Path $projectDir "publish"
$releaseRoot = Join-Path $publishRoot "v$version"
$portableDir = Join-Path $releaseRoot "WorldCupFloat_Portable"
$localDir = Join-Path $publishRoot "WorldCupFloat_Local"
$archivePath = Join-Path $releaseRoot "WorldCupFloat_Portable.zip"

function Test-SecretsContainCredentials {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    try {
        $value = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        return (
            [bool][string]$value.agnes_api_key -or
            [bool][string]$value.ai_api_keys.agnes -or
            [bool][string]$value.ai_api_keys.glm -or
            [bool][string]$value.tencent_translate_secret_id -or
            [bool][string]$value.tencent_translate_secret_key
        )
    }
    catch {
        return $false
    }
}

function Find-PrivateSecrets {
    $stableSecrets = Join-Path $localDir "secrets.json"
    if (Test-SecretsContainCredentials -Path $stableSecrets) {
        return $stableSecrets
    }

    $candidates = @(
        Get-ChildItem -LiteralPath $publishRoot -Recurse -Filter "secrets.json" -File -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -ne $stableSecrets } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -ExpandProperty FullName
    )
    $candidates += (Join-Path $projectDir "secrets.json")

    foreach ($candidate in $candidates) {
        if (Test-SecretsContainCredentials -Path $candidate) {
            return $candidate
        }
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return $null
}

$privateSecretsSource = Find-PrivateSecrets
$legacyRuntimeSource = $null
if ($privateSecretsSource) {
    $privateRuntimeCandidate = Split-Path -Parent $privateSecretsSource
    if (
        (Test-Path -LiteralPath (Join-Path $privateRuntimeCandidate "WorldCupFloat.exe")) -and
        (Test-Path -LiteralPath (Join-Path $privateRuntimeCandidate "config.json"))
    ) {
        $legacyRuntimeSource = Get-Item -LiteralPath $privateRuntimeCandidate
    }
}
if (-not $legacyRuntimeSource) {
    $legacyRuntimeSource = Get-ChildItem -LiteralPath $publishRoot -Directory -Filter "v*" -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        ForEach-Object {
            $legacyRoot = $_
            @("WorldCupFloat_Local", "WorldCupFloat_Portable") | ForEach-Object {
                $candidate = Join-Path $legacyRoot.FullName $_
                if (Test-Path -LiteralPath $candidate) {
                    Get-Item -LiteralPath $candidate
                }
            }
        } |
        Select-Object -First 1
}

$resolvedPublishRoot = [IO.Path]::GetFullPath($publishRoot).TrimEnd("\") + "\"
$resolvedReleaseRoot = [IO.Path]::GetFullPath($releaseRoot).TrimEnd("\") + "\"
if (-not $resolvedReleaseRoot.StartsWith(
    $resolvedPublishRoot,
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw "Release path escaped the publish directory."
}

if (Test-Path -LiteralPath $releaseRoot) {
    Remove-Item -LiteralPath $releaseRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $portableDir | Out-Null

Copy-Item -LiteralPath (Join-Path $projectDir "dist\WorldCupFloat.exe") -Destination $portableDir
Copy-Item -LiteralPath (Join-Path $projectDir "assets") -Destination $portableDir -Recurse
Copy-Item -LiteralPath (Join-Path $projectDir "config.json") -Destination $portableDir
Copy-Item -LiteralPath (Join-Path $projectDir "version.json") -Destination $portableDir
Copy-Item -LiteralPath (Join-Path $projectDir "selected_app_icon.ico") -Destination $portableDir
Copy-Item -LiteralPath (Join-Path $projectDir "README.md") -Destination $portableDir
Copy-Item -LiteralPath (Join-Path $projectDir "START_HERE.txt") -Destination $portableDir

$blankSecrets = @{
    agnes_api_key = ""
    ai_api_keys = @{
        agnes = ""
        glm = ""
    }
    tencent_translate_secret_id = ""
    tencent_translate_secret_key = ""
} | ConvertTo-Json -Depth 4
Set-Content -LiteralPath (Join-Path $portableDir "secrets.json") -Value $blankSecrets -Encoding UTF8

$cacheSource = Join-Path $projectDir "cache"
$cacheTarget = Join-Path $portableDir "cache"
New-Item -ItemType Directory -Path $cacheTarget | Out-Null
$publicCachePatterns = @(
    "espn_*_teams.json",
    "espn_*_standings.json",
    "espn_*_stats.json",
    "espn_*_scoreboard_*.json",
    "espn_*_roster_*.json",
    "ai_name_localization.json"
)
foreach ($pattern in $publicCachePatterns) {
    Get-ChildItem -LiteralPath $cacheSource -Filter $pattern -File |
        Copy-Item -Destination $cacheTarget
}
$imageSource = Join-Path $cacheSource "images"
if (Test-Path -LiteralPath $imageSource) {
    Copy-Item -LiteralPath $imageSource -Destination $cacheTarget -Recurse
}

$packagedSecrets = Get-Content -LiteralPath (Join-Path $portableDir "secrets.json") -Raw |
    ConvertFrom-Json
$containsSecret = (
    [bool][string]$packagedSecrets.agnes_api_key -or
    [bool][string]$packagedSecrets.ai_api_keys.agnes -or
    [bool][string]$packagedSecrets.ai_api_keys.glm -or
    [bool][string]$packagedSecrets.tencent_translate_secret_id -or
    [bool][string]$packagedSecrets.tencent_translate_secret_key
)
if ($containsSecret) {
    throw "Refusing to package a non-empty API key."
}

Compress-Archive -LiteralPath $portableDir -DestinationPath $archivePath -CompressionLevel Optimal

if (-not (Test-Path -LiteralPath $localDir)) {
    if ($legacyRuntimeSource) {
        Copy-Item -LiteralPath $legacyRuntimeSource.FullName -Destination $localDir -Recurse
    }
    else {
        Copy-Item -LiteralPath $portableDir -Destination $localDir -Recurse
    }
}

# Keep private runtime state stable across releases. Only application files and
# bundled assets are refreshed; local settings, API keys, and caches stay put.
Get-ChildItem -LiteralPath $portableDir | Where-Object {
    $_.Name -notin @("config.json", "secrets.json", "cache")
} | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $localDir -Recurse -Force
}
if (-not (Test-Path -LiteralPath (Join-Path $localDir "config.json"))) {
    Copy-Item -LiteralPath (Join-Path $projectDir "config.json") -Destination $localDir
}
if ($privateSecretsSource) {
    $localSecretsPath = Join-Path $localDir "secrets.json"
    if (
        [IO.Path]::GetFullPath($privateSecretsSource) -ne
        [IO.Path]::GetFullPath($localSecretsPath)
    ) {
        Copy-Item -LiteralPath $privateSecretsSource -Destination $localSecretsPath -Force
    }
}
elseif (-not (Test-Path -LiteralPath (Join-Path $localDir "secrets.json"))) {
    Set-Content -LiteralPath (Join-Path $localDir "secrets.json") -Value $blankSecrets -Encoding UTF8
}
if (-not (Test-Path -LiteralPath (Join-Path $localDir "cache"))) {
    Copy-Item -LiteralPath $cacheTarget -Destination (Join-Path $localDir "cache") -Recurse
}

Write-Output "Packaged: $archivePath"
Write-Output "Local private package: $localDir"

if ($CreateSharePackage) {
    if ([string]::IsNullOrWhiteSpace($ShareOutputDirectory)) {
        $ShareOutputDirectory = $releaseRoot
    }
    New-Item -ItemType Directory -Path $ShareOutputDirectory -Force | Out-Null
    $shareArchivePath = Join-Path $ShareOutputDirectory "WorldCup_Realtime_Data_v${version}_Share.zip"
    Copy-Item -LiteralPath $archivePath -Destination $shareArchivePath -Force
    Write-Output "Share package: $shareArchivePath"
}
