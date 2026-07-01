$ErrorActionPreference = "Stop"

$AgentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AgentsRoot = Split-Path -Parent $AgentDir
$AdkDir = Join-Path $AgentDir ".adk"
$ArtifactsDir = Join-Path $AdkDir "artifacts"
$SessionDb = Join-Path $AdkDir "session.db"
$SessionDbUriPath = $SessionDb.Replace("\", "/")
$ArtifactsUriPath = $ArtifactsDir.Replace("\", "/")
$AdkExe = "C:\Users\Andre\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\adk.exe"

New-Item -ItemType Directory -Force -Path $AdkDir | Out-Null
New-Item -ItemType Directory -Force -Path $ArtifactsDir | Out-Null

Set-Location $AgentsRoot
& $AdkExe web `
  --session_service_uri "sqlite:///$SessionDbUriPath" `
  --artifact_service_uri "file:///$ArtifactsUriPath" `
  --port 8000 `
  .
