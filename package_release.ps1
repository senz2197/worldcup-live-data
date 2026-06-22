$ErrorActionPreference = "Stop"

$projectDir = (Resolve-Path $PSScriptRoot).Path
$versionInfo = Get-Content -LiteralPath (Join-Path $projectDir "version.json") -Raw |
    ConvertFrom-Json
$version = [string]$versionInfo.version
$publishRoot = Join-Path $projectDir "publish"
$releaseRoot = Join-Path $publishRoot "v$version"
$portableDir = Join-Path $releaseRoot "WorldCupFloat_Portable"
$localDir = Join-Path $releaseRoot "WorldCupFloat_Local"
$archivePath = Join-Path $releaseRoot "WorldCupFloat_Portable.zip"
$shareArchivePath = Join-Path $releaseRoot "WorldCup_Realtime_Data_v${version}_Share.zip"

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
Copy-Item -LiteralPath $archivePath -Destination $shareArchivePath
Copy-Item -LiteralPath $portableDir -Destination $localDir -Recurse
Copy-Item -LiteralPath (Join-Path $projectDir "secrets.json") -Destination $localDir -Force
Write-Output "Packaged: $archivePath"
Write-Output "Share package: $shareArchivePath"
Write-Output "Local private package: $localDir"
