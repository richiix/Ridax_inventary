param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("set", "get", "delete")]
  [string]$Action,

  [Parameter(Mandatory = $true)]
  [string]$Token,

  [string]$PublicBaseUrl
)

if ($Action -eq "set" -and [string]::IsNullOrWhiteSpace($PublicBaseUrl)) {
  throw "PublicBaseUrl es requerido para action=set"
}

if ($PublicBaseUrl) {
  $PublicBaseUrl = $PublicBaseUrl.TrimEnd('/')
}

$baseApi = "https://api.telegram.org/bot$Token"

switch ($Action) {
  "set" {
    $webhookUrl = "$PublicBaseUrl/api/v1/integrations/telegram/webhook"
    $url = "$baseApi/setWebhook?url=$([uri]::EscapeDataString($webhookUrl))"
    Write-Host "Configurando webhook en: $webhookUrl"
    Invoke-RestMethod -Method Get -Uri $url | ConvertTo-Json -Depth 6
  }
  "get" {
    $url = "$baseApi/getWebhookInfo"
    Invoke-RestMethod -Method Get -Uri $url | ConvertTo-Json -Depth 6
  }
  "delete" {
    $url = "$baseApi/deleteWebhook"
    Invoke-RestMethod -Method Get -Uri $url | ConvertTo-Json -Depth 6
  }
}
