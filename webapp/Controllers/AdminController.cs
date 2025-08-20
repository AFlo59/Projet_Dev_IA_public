using DnDGameMaster.WebApp.Models;
using DnDGameMaster.WebApp.Services.Monitoring;
using DnDGameMaster.WebApp.ViewModels;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;
using System.Text.Json;

namespace DnDGameMaster.WebApp.Controllers
{
    [Authorize(Roles = "Admin")]
    public class AdminController : Controller
    {
        private readonly IAIMonitoringService _monitoringService;
        private readonly ILogger<AdminController> _logger;
        private readonly HttpClient _httpClient;
        private readonly IConfiguration _configuration;

        public AdminController(IAIMonitoringService monitoringService, ILogger<AdminController> logger, HttpClient httpClient, IConfiguration configuration)
        {
            _monitoringService = monitoringService;
            _logger = logger;
            _httpClient = httpClient;
            _configuration = configuration;
        }

        // Dashboard principal
        public async Task<IActionResult> Dashboard()
        {
            try
            {
                // 🔧 NEW: Get data from llmgamemaster API instead of local DB
                var dashboardData = await GetDashboardDataFromLLMAsync();
                if (dashboardData != null)
                {
                    return View(dashboardData);
                }
                
                // Fallback to local service if API fails
                var localDashboardData = await _monitoringService.GetDashboardDataAsync();
                return View(localDashboardData);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error loading admin dashboard");
                return View("Error");
            }
        }

        // Métriques IA
        public async Task<IActionResult> Metrics(DateTime? fromDate, DateTime? toDate, string? metricName, string? modelName)
        {
            try
            {
                // 🔧 NEW: Get data from llmgamemaster API
                var metrics = await GetMetricsFromLLMAsync(fromDate, toDate, metricName, modelName);
                if (metrics != null)
                {
                    ViewBag.FromDate = fromDate;
                    ViewBag.ToDate = toDate;
                    ViewBag.MetricName = metricName;
                    ViewBag.ModelName = modelName;
                    return View(metrics);
                }
                
                // Fallback to local service
                var localMetrics = await _monitoringService.GetMetricsAsync(fromDate, toDate, metricName, modelName);
                ViewBag.FromDate = fromDate;
                ViewBag.ToDate = toDate;
                ViewBag.MetricName = metricName;
                ViewBag.ModelName = modelName;
                return View(localMetrics);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error loading AI metrics");
                return View("Error");
            }
        }

        // Logs IA
        public async Task<IActionResult> Logs(DateTime? fromDate, DateTime? toDate, string? level, string? category)
        {
            try
            {
                // 🔧 NEW: Get data from llmgamemaster API
                var logs = await GetLogsFromLLMAsync(fromDate, toDate, level, category);
                if (logs != null)
                {
                    ViewBag.FromDate = fromDate;
                    ViewBag.ToDate = toDate;
                    ViewBag.Level = level;
                    ViewBag.Category = category;
                    return View(logs);
                }
                
                // Fallback to local service
                var localLogs = await _monitoringService.GetLogsAsync(fromDate, toDate, level, category);
                ViewBag.FromDate = fromDate;
                ViewBag.ToDate = toDate;
                ViewBag.Level = level;
                ViewBag.Category = category;
                return View(localLogs);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error loading AI logs");
                return View("Error");
            }
        }
        
        // Alertes IA
        public async Task<IActionResult> Alerts(bool? isResolved, string? level, DateTime? fromDate)
        {
            try
            {
                var alerts = await _monitoringService.GetAlertsAsync(isResolved, level, fromDate);
                ViewBag.IsResolved = isResolved;
                ViewBag.Level = level;
                ViewBag.FromDate = fromDate;
                return View(alerts);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error loading AI alerts");
                return View("Error");
            }
        }

        // Coûts IA
        public async Task<IActionResult> Costs(DateTime? fromDate, DateTime? toDate, string? provider)
        {
            try
            {
                var costs = await _monitoringService.GetCostsAsync(fromDate, toDate, provider);
                ViewBag.FromDate = fromDate;
                ViewBag.ToDate = toDate;
                ViewBag.Provider = provider;
                return View(costs);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error loading AI costs");
                return View("Error");
            }
        }

        // Performance des modèles
        public async Task<IActionResult> ModelPerformance(DateTime? fromDate, DateTime? toDate, string? modelName)
        {
            try
            {
                // 🔧 NEW: Get data from llmgamemaster API
                var performance = await GetModelPerformanceFromLLMAsync(fromDate, toDate, modelName);
                if (performance != null)
                {
                    ViewBag.FromDate = fromDate;
                    ViewBag.ToDate = toDate;
                    ViewBag.ModelName = modelName;
                    return View(performance);
                }
                
                // Fallback to local service
                var localPerformance = await _monitoringService.GetModelPerformanceAsync(fromDate, toDate, modelName);
                ViewBag.FromDate = fromDate;
                ViewBag.ToDate = toDate;
                ViewBag.ModelName = modelName;
                return View(localPerformance);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error loading model performance");
                return View("Error");
            }
        }

        // Seuils d'alerte
        public async Task<IActionResult> AlertThresholds()
        {
            try
            {
                var thresholds = await _monitoringService.GetAlertThresholdsAsync();
                return View(thresholds);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error loading alert thresholds");
                return View("Error");
            }
        }

        [HttpPost]
        public async Task<IActionResult> UpdateThreshold(AIAlertThresholds threshold)
        {
            try
            {
                if (ModelState.IsValid)
                {
                    await _monitoringService.UpdateAlertThresholdAsync(threshold);
                    TempData["Success"] = "Seuil d'alerte mis à jour avec succès.";
                }
                else
                {
                    TempData["Error"] = "Données invalides.";
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error updating alert threshold");
                TempData["Error"] = "Erreur lors de la mise à jour du seuil.";
            }

            return RedirectToAction(nameof(AlertThresholds));
        }

        [HttpPost]
        public async Task<IActionResult> ResolveAlert(int alertId)
        {
            try
            {
                var userId = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new UnauthorizedAccessException("User ID not found");
                await _monitoringService.ResolveAlertAsync(alertId, userId);
                TempData["Success"] = "Alerte résolue avec succès.";
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error resolving alert {AlertId}", alertId);
                TempData["Error"] = "Erreur lors de la résolution de l'alerte.";
            }

            return RedirectToAction(nameof(Alerts));
        }

        // API endpoints pour les graphiques
        [HttpGet]
        public async Task<IActionResult> GetMetricsData(DateTime? fromDate, DateTime? toDate, string? metricName)
        {
            try
            {
                var metrics = await _monitoringService.GetMetricsAsync(fromDate, toDate, metricName);
                var data = metrics.Select(m => new
                {
                    timestamp = m.Timestamp,
                    value = m.MetricValue,
                    unit = m.MetricUnit,
                    modelName = m.ModelName,
                    provider = m.Provider
                });

                return Json(new { success = true, data });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting metrics data");
                return Json(new { success = false, error = ex.Message });
            }
        }

        [HttpGet]
        public async Task<IActionResult> GetCostsData(DateTime? fromDate, DateTime? toDate)
        {
            try
            {
                var costs = await _monitoringService.GetCostsAsync(fromDate, toDate);
                var data = costs.GroupBy(c => c.Date)
                    .Select(g => new
                    {
                        date = g.Key,
                        totalCost = g.Sum(c => c.TotalCost),
                        totalTokens = g.Sum(c => c.TokensUsed),
                        provider = g.First().Provider
                    });

                return Json(new { success = true, data });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting costs data");
                return Json(new { success = false, error = ex.Message });
            }
        }

        [HttpGet]
        public async Task<IActionResult> GetPerformanceData(DateTime? fromDate, DateTime? toDate)
        {
            try
            {
                var performance = await _monitoringService.GetModelPerformanceAsync(fromDate, toDate);
                var data = performance.Select(p => new
                {
                    date = p.Date,
                    modelName = p.ModelName,
                    provider = p.Provider,
                    averageResponseTime = p.AverageResponseTime,
                    successRate = p.SuccessRate,
                    errorRate = p.ErrorRate,
                    totalRequests = p.TotalRequests
                });

                return Json(new { success = true, data });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting performance data");
                return Json(new { success = false, error = ex.Message });
            }
        }

        // Export des données
        [HttpGet]
        public async Task<IActionResult> ExportMetrics(DateTime? fromDate, DateTime? toDate, string? metricName)
        {
            try
            {
                var metrics = await _monitoringService.GetMetricsAsync(fromDate, toDate, metricName);
                var csv = "Timestamp,MetricName,MetricValue,MetricUnit,ModelName,Provider,CampaignId,UserId\n";
                
                foreach (var metric in metrics)
                {
                    csv += $"{metric.Timestamp:yyyy-MM-dd HH:mm:ss},{metric.MetricName},{metric.MetricValue},{metric.MetricUnit},{metric.ModelName},{metric.Provider},{metric.CampaignId},{metric.UserId}\n";
                }

                var bytes = System.Text.Encoding.UTF8.GetBytes(csv);
                return File(bytes, "text/csv", $"ai_metrics_{DateTime.Now:yyyyMMdd_HHmmss}.csv");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error exporting metrics");
                TempData["Error"] = "Erreur lors de l'export des métriques.";
                return RedirectToAction(nameof(Metrics));
            }
        }

        [HttpGet]
        public async Task<IActionResult> ExportLogs(DateTime? fromDate, DateTime? toDate, string? level)
        {
            try
            {
                var logs = await _monitoringService.GetLogsAsync(fromDate, toDate, level);
                var csv = "Timestamp,LogLevel,LogMessage,LogCategory,ModelName,Provider,CampaignId,UserId,RequestId,ResponseTime,TokensUsed,Cost\n";
                
                foreach (var log in logs)
                {
                    csv += $"{log.Timestamp:yyyy-MM-dd HH:mm:ss},{log.LogLevel},{log.LogMessage.Replace(",", ";")},{log.LogCategory},{log.ModelName},{log.Provider},{log.CampaignId},{log.UserId},{log.RequestId},{log.ResponseTime},{log.TokensUsed},{log.Cost}\n";
                }

                var bytes = System.Text.Encoding.UTF8.GetBytes(csv);
                return File(bytes, "text/csv", $"ai_logs_{DateTime.Now:yyyyMMdd_HHmmss}.csv");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error exporting logs");
                TempData["Error"] = "Erreur lors de l'export des logs.";
                return RedirectToAction(nameof(Logs));
            }
        }
        
        // 🆕 NEW: Index method for Admin area
        public IActionResult Index()
        {
            try
            {
                return RedirectToAction(nameof(Dashboard));
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error loading admin index");
                return View("Error");
            }
        }
        
        // 🆕 NEW METHODS: Get data from llmgamemaster API
        private async Task<AdminDashboardViewModel?> GetDashboardDataFromLLMAsync()
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, "api/monitoring/dashboard");
                
                _logger.LogInformation($"Getting dashboard data from: {requestUri}");
                
                var response = await _httpClient.GetAsync(requestUri);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogWarning($"Failed to get dashboard data: {response.StatusCode}");
                    return null;
                }
                
                var content = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<JsonElement>(content);
                
                if (data.TryGetProperty("status", out var statusProp) && statusProp.GetString() == "success" &&
                    data.TryGetProperty("data", out var dataProp))
                {
                    // Parse the dashboard data
                    var dashboardData = new AdminDashboardViewModel();
                    
                    // Parse recent metrics for statistics
                    if (dataProp.TryGetProperty("recent_metrics", out var metricsArray))
                    {
                        var parsedMetrics = ParseMetricsFromLLM(metricsArray);
                        
                        // Calculate 24h stats from actual metrics
                        var yesterday = DateTime.UtcNow.AddDays(-1);
                        var last24hMetrics = parsedMetrics.Where(m => m.Timestamp >= yesterday).ToList();
                        
                        dashboardData.TotalRequests24h = last24hMetrics.Count(m => m.MetricName == "response_time");
                        
                        var responseTimeMetrics = last24hMetrics.Where(m => m.MetricName == "response_time").ToList();
                        dashboardData.AverageResponseTime = responseTimeMetrics.Any() 
                            ? (int)responseTimeMetrics.Average(m => m.MetricValue)
                            : 0;
                        
                        // Calculate success rate from error metrics (if available)
                        var errorMetrics = last24hMetrics.Where(m => m.MetricName == "error_count").ToList();
                        var totalRequests = dashboardData.TotalRequests24h;
                        var totalErrors = errorMetrics.Sum(m => m.MetricValue);
                        dashboardData.SuccessRate24h = totalRequests > 0 
                            ? (double)(totalRequests - (int)totalErrors) / totalRequests * 100
                            : 100.0;
                        
                        dashboardData.TotalCost24h = 0.50m; // Default for now, could be calculated from cost metrics
                    }
                    
                    // Parse model performance
                    if (dataProp.TryGetProperty("model_performance", out var perfArray))
                    {
                        dashboardData.ModelPerformance = ParseModelPerformanceFromLLM(perfArray);
                    }
                    
                    // Parse active alerts
                    if (dataProp.TryGetProperty("active_alerts", out var alertsArray))
                    {
                        dashboardData.ActiveAlerts = ParseAlertsFromLLM(alertsArray);
                    }
                    
                    // Generate requests data from actual metrics
                    if (dataProp.TryGetProperty("recent_metrics", out var metricsForChart))
                    {
                        var chartMetrics = ParseMetricsFromLLM(metricsForChart);
                        var requestsData = new List<RequestDataPoint>();
                        
                        for (int i = 6; i >= 0; i--)
                        {
                            var date = DateTime.Today.AddDays(-i);
                            var dayRequests = chartMetrics.Count(m => 
                                m.MetricName == "response_time" && 
                                m.Timestamp.Date == date);
                            
                            requestsData.Add(new RequestDataPoint 
                            { 
                                Date = date.ToString("yyyy-MM-dd"), 
                                Count = dayRequests 
                            });
                        }
                        
                        dashboardData.RequestsData = requestsData;
                    }
                    
                    // Generate models data from actual performance data
                    if (dashboardData.ModelPerformance?.Any() == true)
                    {
                        dashboardData.ModelsData = dashboardData.ModelPerformance
                            .GroupBy(p => p.ModelName)
                            .Select(g => new ModelDataPoint 
                            { 
                                Model = g.Key ?? "Unknown", 
                                Count = g.Sum(p => p.TotalRequests) 
                            })
                            .ToList();
                    }
                    else
                    {
                        // Fallback to default data
                        dashboardData.ModelsData = new List<ModelDataPoint>
                        {
                            new ModelDataPoint { Model = "GPT-4", Count = dashboardData.TotalRequests24h },
                            new ModelDataPoint { Model = "Other", Count = 0 }
                        };
                    }
                    
                    return dashboardData;
                }
                
                return null;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting dashboard data from LLM API");
                return null;
            }
        }
        
        private async Task<IEnumerable<AIMetrics>?> GetMetricsFromLLMAsync(DateTime? fromDate, DateTime? toDate, string? metricName, string? modelName)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var queryParams = new List<string>();
                
                if (fromDate.HasValue)
                    queryParams.Add($"from_date={fromDate.Value:yyyy-MM-dd}");
                if (toDate.HasValue)  
                    queryParams.Add($"to_date={toDate.Value:yyyy-MM-dd}");
                if (!string.IsNullOrEmpty(metricName))
                    queryParams.Add($"metric_name={Uri.EscapeDataString(metricName)}");
                if (!string.IsNullOrEmpty(modelName))
                    queryParams.Add($"model_name={Uri.EscapeDataString(modelName)}");
                
                var queryString = queryParams.Any() ? "?" + string.Join("&", queryParams) : "";
                var requestUri = new Uri(baseUri, $"api/monitoring/metrics{queryString}");
                
                _logger.LogInformation($"Getting metrics from: {requestUri}");
                
                var response = await _httpClient.GetAsync(requestUri);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogWarning($"Failed to get metrics: {response.StatusCode}");
                    return null;
                }
                
                var content = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<JsonElement>(content);
                
                if (data.TryGetProperty("status", out var statusProp) && statusProp.GetString() == "success" &&
                    data.TryGetProperty("data", out var dataProp))
                {
                    return ParseMetricsFromLLM(dataProp);
                }
                
                return null;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting metrics from LLM API");
                return null;
            }
        }
        
        private async Task<IEnumerable<AILogs>?> GetLogsFromLLMAsync(DateTime? fromDate, DateTime? toDate, string? level, string? category)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var queryParams = new List<string>();
                
                if (fromDate.HasValue)
                    queryParams.Add($"from_date={fromDate.Value:yyyy-MM-dd}");
                if (toDate.HasValue)  
                    queryParams.Add($"to_date={toDate.Value:yyyy-MM-dd}");
                if (!string.IsNullOrEmpty(level))
                    queryParams.Add($"level={Uri.EscapeDataString(level)}");
                if (!string.IsNullOrEmpty(category))
                    queryParams.Add($"category={Uri.EscapeDataString(category)}");
                
                var queryString = queryParams.Any() ? "?" + string.Join("&", queryParams) : "";
                var requestUri = new Uri(baseUri, $"api/monitoring/logs{queryString}");
                
                _logger.LogInformation($"Getting logs from: {requestUri}");
                
                var response = await _httpClient.GetAsync(requestUri);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogWarning($"Failed to get logs: {response.StatusCode}");
                    return null;
                }
                
                var content = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<JsonElement>(content);
                
                if (data.TryGetProperty("status", out var statusProp) && statusProp.GetString() == "success" &&
                    data.TryGetProperty("data", out var dataProp))
                {
                    return ParseLogsFromLLM(dataProp);
                }
                
                return null;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting logs from LLM API");
                return null;
            }
        }
        
        private async Task<IEnumerable<AIModelPerformance>?> GetModelPerformanceFromLLMAsync(DateTime? fromDate, DateTime? toDate, string? modelName)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var queryParams = new List<string>();
                
                if (fromDate.HasValue)
                    queryParams.Add($"from_date={fromDate.Value:yyyy-MM-dd}");
                if (toDate.HasValue)  
                    queryParams.Add($"to_date={toDate.Value:yyyy-MM-dd}");
                if (!string.IsNullOrEmpty(modelName))
                    queryParams.Add($"model_name={Uri.EscapeDataString(modelName)}");
                
                var queryString = queryParams.Any() ? "?" + string.Join("&", queryParams) : "";
                var requestUri = new Uri(baseUri, $"api/monitoring/model_performance{queryString}");
                
                _logger.LogInformation($"Getting model performance from: {requestUri}");
                
                var response = await _httpClient.GetAsync(requestUri);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogWarning($"Failed to get model performance: {response.StatusCode}");
                    return null;
                }
                
                var content = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<JsonElement>(content);
                
                if (data.TryGetProperty("status", out var statusProp) && statusProp.GetString() == "success" &&
                    data.TryGetProperty("data", out var dataProp))
                {
                    return ParseModelPerformanceFromLLM(dataProp);
                }
                
                return null;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting model performance from LLM API");
                return null;
            }
        }
        
        private List<AIMetrics> ParseMetricsFromLLM(JsonElement dataArray)
        {
            var metrics = new List<AIMetrics>();
            
            foreach (var item in dataArray.EnumerateArray())
            {
                try
                {
                    var metric = new AIMetrics
                    {
                        MetricName = item.GetProperty("MetricName").GetString() ?? "",
                        MetricValue = item.GetProperty("MetricValue").GetDecimal(),
                        MetricUnit = GetStringProperty(item, "MetricUnit"),
                        ModelName = GetStringProperty(item, "ModelName"),
                        Provider = GetStringProperty(item, "Provider"),
                        CampaignId = GetIntProperty(item, "CampaignId"),
                        UserId = GetStringProperty(item, "UserId"),
                        Metadata = GetStringProperty(item, "Metadata"),
                        Timestamp = DateTime.Parse(item.GetProperty("Timestamp").GetString() ?? DateTime.Now.ToString())
                    };
                    metrics.Add(metric);
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Error parsing metric item");
                }
            }
            
            return metrics;
        }
        
        private List<AILogs> ParseLogsFromLLM(JsonElement dataArray)
        {
            var logs = new List<AILogs>();
            
            foreach (var item in dataArray.EnumerateArray())
            {
                try
                {
                    var log = new AILogs
                    {
                        LogLevel = item.GetProperty("LogLevel").GetString() ?? "INFO",
                        LogMessage = item.GetProperty("LogMessage").GetString() ?? "",
                        LogCategory = GetStringProperty(item, "LogCategory"),
                        ModelName = GetStringProperty(item, "ModelName"),
                        Provider = GetStringProperty(item, "Provider"),
                        ResponseTime = GetIntProperty(item, "ResponseTime"),
                        TokensUsed = GetIntProperty(item, "TokensUsed"),
                        Cost = GetDecimalProperty(item, "Cost"),
                        CampaignId = GetIntProperty(item, "CampaignId"),
                        UserId = GetStringProperty(item, "UserId"),
                        Metadata = GetStringProperty(item, "Metadata"),
                        StackTrace = GetStringProperty(item, "StackTrace"),
                        Timestamp = DateTime.Parse(item.GetProperty("Timestamp").GetString() ?? DateTime.Now.ToString())
                    };
                    logs.Add(log);
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Error parsing log item");
                }
            }
            
            return logs;
        }
        
        private List<AIModelPerformance> ParseModelPerformanceFromLLM(JsonElement dataArray)
        {
            var performances = new List<AIModelPerformance>();
            
            foreach (var item in dataArray.EnumerateArray())
            {
                try
                {
                    var perf = new AIModelPerformance
                    {
                        ModelName = item.GetProperty("ModelName").GetString() ?? "",
                        Provider = item.GetProperty("Provider").GetString() ?? "",
                        AverageResponseTime = (int)item.GetProperty("AverageResponseTime").GetDecimal(),
                        SuccessRate = item.GetProperty("SuccessRate").GetDecimal(),
                        ErrorRate = item.GetProperty("ErrorRate").GetDecimal(),
                        TotalRequests = GetIntProperty(item, "TotalRequests") ?? 0,
                        TotalErrors = GetIntProperty(item, "TotalErrors") ?? 0,
                        Date = DateTime.Parse(item.GetProperty("Date").GetString() ?? DateTime.Today.ToString())
                    };
                    performances.Add(perf);
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Error parsing performance item");
                }
            }
            
            return performances;
        }
        
        private List<AIAlerts> ParseAlertsFromLLM(JsonElement dataArray)
        {
            var alerts = new List<AIAlerts>();
            
            foreach (var item in dataArray.EnumerateArray())
            {
                try
                {
                    var alert = new AIAlerts
                    {
                        AlertType = item.GetProperty("AlertType").GetString() ?? "",
                        AlertLevel = item.GetProperty("AlertLevel").GetString() ?? "INFO",
                        AlertMessage = item.GetProperty("AlertMessage").GetString() ?? "",
                        CreatedAt = DateTime.Parse(item.GetProperty("CreatedAt").GetString() ?? DateTime.Now.ToString())
                    };
                    alerts.Add(alert);
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Error parsing alert item");
                }
            }
            
            return alerts;
        }
        
        private string? GetStringProperty(JsonElement element, string propertyName)
        {
            return element.TryGetProperty(propertyName, out var prop) && prop.ValueKind != JsonValueKind.Null 
                ? prop.GetString() 
                : null;
        }
        
        private int? GetIntProperty(JsonElement element, string propertyName)
        {
            if (element.TryGetProperty(propertyName, out var prop) && prop.ValueKind != JsonValueKind.Null)
            {
                if (prop.ValueKind == JsonValueKind.Number && prop.TryGetInt32(out var intValue))
                {
                    return intValue;
                }
                if (prop.ValueKind == JsonValueKind.String && int.TryParse(prop.GetString(), out var stringIntValue))
                {
                    return stringIntValue;
                }
            }
            return null;
        }
        
        private decimal? GetDecimalProperty(JsonElement element, string propertyName)
        {
            if (element.TryGetProperty(propertyName, out var prop) && prop.ValueKind != JsonValueKind.Null)
            {
                if (prop.ValueKind == JsonValueKind.Number && prop.TryGetDecimal(out var decimalValue))
                {
                    return decimalValue;
                }
                if (prop.ValueKind == JsonValueKind.String && decimal.TryParse(prop.GetString(), out var stringDecimalValue))
                {
                    return stringDecimalValue;
                }
            }
            return null;
        }
    }
} 