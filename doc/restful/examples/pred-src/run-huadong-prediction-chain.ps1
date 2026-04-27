param(
    [string]$ConfigPath = (Join-Path $PSScriptRoot "huadong-prediction-chain.config.json")
)

$ErrorActionPreference = "Stop"

function Save-Json {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Object
    )

    $directory = Split-Path -Parent $Path
    if ($directory -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Force -Path $directory | Out-Null
    }

    $json = $Object | ConvertTo-Json -Depth 20
    Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
}

function Invoke-JsonPost {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)]$Payload,
        [Parameter(Mandatory = $true)][string]$RequestPath,
        [Parameter(Mandatory = $true)][string]$ResponsePath
    )

    Save-Json -Path $RequestPath -Object $Payload
    $body = $Payload | ConvertTo-Json -Depth 20
    $response = Invoke-RestMethod -Method Post -Uri $Uri -ContentType "application/json; charset=utf-8" -Body $body
    Save-Json -Path $ResponsePath -Object $response
    return $response
}

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Config file not found: $ConfigPath"
}

$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$runRoot = $config.output_root
$requestDir = Join-Path $runRoot "requests"
$responseDir = Join-Path $runRoot "responses"

New-Item -ItemType Directory -Force -Path $requestDir, $responseDir | Out-Null

$baseUrl = $config.gateway_base_url.TrimEnd("/")
$health = Invoke-RestMethod -Method Get -Uri "$baseUrl/huadong/health"
Save-Json -Path (Join-Path $responseDir "00-health.response.json") -Object $health

$datasetPayload = @{
    dataset_path = $config.dataset_path
    output_root  = (Join-Path $runRoot "dataset")
    options      = @{}
}
$dataset = Invoke-JsonPost -Uri "$baseUrl/huadong/dataset/profile" -Payload $datasetPayload `
    -RequestPath (Join-Path $requestDir "01-dataset-profile.request.json") `
    -ResponsePath (Join-Path $responseDir "01-dataset-profile.response.json")

$assetsPayload = @{
    output_root = (Join-Path $runRoot "assets")
    options     = @{}
}
$assets = Invoke-JsonPost -Uri "$baseUrl/huadong/model-assets/profile" -Payload $assetsPayload `
    -RequestPath (Join-Path $requestDir "02-model-assets-profile.request.json") `
    -ResponsePath (Join-Path $responseDir "02-model-assets-profile.response.json")

$analysisPayload = @{
    dataset_path = $config.dataset_path
    output_root  = (Join-Path $runRoot "analysis")
    options      = @{
        column = $config.analysis_column
    }
}
$analysis = Invoke-JsonPost -Uri "$baseUrl/huadong/analysis" -Payload $analysisPayload `
    -RequestPath (Join-Path $requestDir "03-analysis.request.json") `
    -ResponsePath (Join-Path $responseDir "03-analysis.response.json")

$forecastPayload = @{
    dataset_path = $config.dataset_path
    output_root  = (Join-Path $runRoot "forecast")
    options      = @{}
}
$forecast = Invoke-JsonPost -Uri "$baseUrl/huadong/forecast" -Payload $forecastPayload `
    -RequestPath (Join-Path $requestDir "04-forecast.request.json") `
    -ResponsePath (Join-Path $responseDir "04-forecast.response.json")

$ensemblePayload = @{
    file_path   = $forecast.artifact_paths.forecast
    output_root = (Join-Path $runRoot "ensemble")
    options     = @{
        method              = $config.ensemble_method
        observation_dataset = $config.observation_dataset
        observation_column  = $config.observation_column
    }
}
$ensemble = Invoke-JsonPost -Uri "$baseUrl/huadong/ensemble" -Payload $ensemblePayload `
    -RequestPath (Join-Path $requestDir "05-ensemble.request.json") `
    -ResponsePath (Join-Path $responseDir "05-ensemble.response.json")

$correctionPayload = @{
    file_path   = $ensemble.artifact_paths.ensemble
    output_root = (Join-Path $runRoot "correction")
    options     = @{
        observation_dataset = $config.observation_dataset
        observation_column  = $config.observation_column
    }
}
$correction = Invoke-JsonPost -Uri "$baseUrl/huadong/correction" -Payload $correctionPayload `
    -RequestPath (Join-Path $requestDir "06-correction.request.json") `
    -ResponsePath (Join-Path $responseDir "06-correction.response.json")

$riskPayload = @{
    file_path   = $correction.artifact_paths.correction
    output_root = (Join-Path $runRoot "risk")
    options     = @{
        thresholds    = $config.risk_thresholds
        model_columns = $config.risk_model_columns
    }
}
$risk = Invoke-JsonPost -Uri "$baseUrl/huadong/risk" -Payload $riskPayload `
    -RequestPath (Join-Path $requestDir "07-risk.request.json") `
    -ResponsePath (Join-Path $responseDir "07-risk.response.json")

$warningPayload = @{
    file_path   = $correction.artifact_paths.correction
    output_root = (Join-Path $runRoot "warning")
    options     = @{
        forecast_column   = $config.warning_forecast_column
        warning_threshold = [double]$config.warning_threshold
        lead_time_hours   = [int]$config.warning_lead_time_hours
    }
}
$warning = Invoke-JsonPost -Uri "$baseUrl/huadong/warning" -Payload $warningPayload `
    -RequestPath (Join-Path $requestDir "08-warning.request.json") `
    -ResponsePath (Join-Path $responseDir "08-warning.response.json")

$summary = @{
    gateway_health = $health
    steps = @{
        dataset_profile = @{
            request_path  = (Join-Path $requestDir "01-dataset-profile.request.json")
            response_path = (Join-Path $responseDir "01-dataset-profile.response.json")
        }
        model_assets_profile = @{
            request_path  = (Join-Path $requestDir "02-model-assets-profile.request.json")
            response_path = (Join-Path $responseDir "02-model-assets-profile.response.json")
        }
        analysis = @{
            request_path  = (Join-Path $requestDir "03-analysis.request.json")
            response_path = (Join-Path $responseDir "03-analysis.response.json")
        }
        forecast = @{
            request_path  = (Join-Path $requestDir "04-forecast.request.json")
            response_path = (Join-Path $responseDir "04-forecast.response.json")
            forecast_csv  = $forecast.artifact_paths.forecast
        }
        ensemble = @{
            request_path  = (Join-Path $requestDir "05-ensemble.request.json")
            response_path = (Join-Path $responseDir "05-ensemble.response.json")
            ensemble_csv  = $ensemble.artifact_paths.ensemble
        }
        correction = @{
            request_path  = (Join-Path $requestDir "06-correction.request.json")
            response_path = (Join-Path $responseDir "06-correction.response.json")
            corrected_csv = $correction.artifact_paths.correction
        }
        risk = @{
            request_path  = (Join-Path $requestDir "07-risk.request.json")
            response_path = (Join-Path $responseDir "07-risk.response.json")
            risk_json     = $risk.artifact_paths.risk
        }
        warning = @{
            request_path  = (Join-Path $requestDir "08-warning.request.json")
            response_path = (Join-Path $responseDir "08-warning.response.json")
            warning_json  = $warning.artifact_paths.warning
        }
    }
}

Save-Json -Path (Join-Path $runRoot "pipeline-summary.json") -Object $summary

Write-Host "Huadong prediction chain completed."
Write-Host "Forecast CSV :" $forecast.artifact_paths.forecast
Write-Host "Ensemble CSV :" $ensemble.artifact_paths.ensemble
Write-Host "Corrected CSV:" $correction.artifact_paths.correction
Write-Host "Risk JSON    :" $risk.artifact_paths.risk
Write-Host "Warning JSON :" $warning.artifact_paths.warning
