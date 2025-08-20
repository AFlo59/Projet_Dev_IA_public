using DnDGameMaster.WebApp.Data;
using DnDGameMaster.WebApp.Models;
using DnDGameMaster.WebApp.ViewModels;
using Microsoft.EntityFrameworkCore;
using System.Text.Json;

namespace DnDGameMaster.WebApp.Services.Monitoring
{
    public interface IAIMonitoringService
    {
        Task LogMetricAsync(string metricName, decimal value, string? unit = null, string? modelName = null, string? provider = null, int? campaignId = null, string? userId = null, object? metadata = null);
        Task LogAsync(string message, string level = "INFO", string? category = null, string? modelName = null, string? provider = null, int? campaignId = null, string? userId = null, string? requestId = null, int? responseTime = null, int? tokensUsed = null, decimal? cost = null, string? stackTrace = null, object? metadata = null);
        Task CreateAlertAsync(string alertType, string message, string level = "WARNING", string? title = null, int? campaignId = null, string? userId = null, object? metadata = null);
        Task LogCostAsync(string provider, string modelName, string operationType, int tokensUsed, decimal costPerToken, decimal totalCost, int? campaignId = null, string? userId = null);
        Task UpdateModelPerformanceAsync(string modelName, string provider, int responseTime, bool isSuccess);
        Task<IEnumerable<AIMetrics>> GetMetricsAsync(DateTime? fromDate = null, DateTime? toDate = null, string? metricName = null, string? modelName = null);
        Task<IEnumerable<AILogs>> GetLogsAsync(DateTime? fromDate = null, DateTime? toDate = null, string? level = null, string? category = null);
        Task<IEnumerable<AIAlerts>> GetAlertsAsync(bool? isResolved = null, string? level = null, DateTime? fromDate = null);
        Task<IEnumerable<AICosts>> GetCostsAsync(DateTime? fromDate = null, DateTime? toDate = null, string? provider = null);
        Task<IEnumerable<AIModelPerformance>> GetModelPerformanceAsync(DateTime? fromDate = null, DateTime? toDate = null, string? modelName = null);
        Task<AdminDashboardViewModel> GetDashboardDataAsync();
        Task ResolveAlertAsync(int alertId, string resolvedBy);
        Task<IEnumerable<AIAlertThresholds>> GetAlertThresholdsAsync();
        Task UpdateAlertThresholdAsync(AIAlertThresholds threshold);
    }

    public class AIMonitoringService : IAIMonitoringService
    {
        private readonly ApplicationDbContext _context;
        private readonly ILogger<AIMonitoringService> _logger;

        public AIMonitoringService(ApplicationDbContext context, ILogger<AIMonitoringService> logger)
        {
            _context = context;
            _logger = logger;
        }

        public async Task LogMetricAsync(string metricName, decimal value, string? unit = null, string? modelName = null, string? provider = null, int? campaignId = null, string? userId = null, object? metadata = null)
        {
            try
            {
                var metric = new AIMetrics
                {
                    MetricName = metricName,
                    MetricValue = value,
                    MetricUnit = unit,
                    ModelName = modelName,
                    Provider = provider,
                    CampaignId = campaignId,
                    UserId = userId,
                    Metadata = metadata != null ? JsonSerializer.Serialize(metadata) : null
                };

                _context.AIMetrics.Add(metric);
                await _context.SaveChangesAsync();

                // Check thresholds and create alerts if needed
                await CheckThresholdsAndCreateAlertsAsync(metricName, value);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error logging AI metric: {MetricName}", metricName);
            }
        }

        public async Task LogAsync(string message, string level = "INFO", string? category = null, string? modelName = null, string? provider = null, int? campaignId = null, string? userId = null, string? requestId = null, int? responseTime = null, int? tokensUsed = null, decimal? cost = null, string? stackTrace = null, object? metadata = null)
        {
            try
            {
                var log = new AILogs
                {
                    LogLevel = level,
                    LogMessage = message,
                    LogCategory = category,
                    ModelName = modelName,
                    Provider = provider,
                    CampaignId = campaignId,
                    UserId = userId,
                    RequestId = requestId,
                    ResponseTime = responseTime,
                    TokensUsed = tokensUsed,
                    Cost = cost,
                    StackTrace = stackTrace,
                    Metadata = metadata != null ? JsonSerializer.Serialize(metadata) : null
                };

                _context.AILogs.Add(log);
                await _context.SaveChangesAsync();

                // Log to application logs as well
                var logLevel = level.ToUpper() switch
                {
                    "ERROR" => LogLevel.Error,
                    "WARNING" => LogLevel.Warning,
                    "INFO" => LogLevel.Information,
                    "DEBUG" => LogLevel.Debug,
                    _ => LogLevel.Information
                };

                _logger.Log(logLevel, "AI Log [{Category}]: {Message}", category ?? "AI", message);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error logging AI log: {Message}", message);
            }
        }

        public async Task CreateAlertAsync(string alertType, string message, string level = "WARNING", string? title = null, int? campaignId = null, string? userId = null, object? metadata = null)
        {
            try
            {
                var alert = new AIAlerts
                {
                    AlertType = alertType,
                    AlertLevel = level,
                    AlertMessage = message,
                    AlertTitle = title,
                    CampaignId = campaignId,
                    UserId = userId,
                    Metadata = metadata != null ? JsonSerializer.Serialize(metadata) : null
                };

                _context.AIAlerts.Add(alert);
                await _context.SaveChangesAsync();

                _logger.LogWarning("AI Alert [{Level}]: {Message}", level, message);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error creating AI alert: {Message}", message);
            }
        }

        public async Task LogCostAsync(string provider, string modelName, string operationType, int tokensUsed, decimal costPerToken, decimal totalCost, int? campaignId = null, string? userId = null)
        {
            try
            {
                var cost = new AICosts
                {
                    Provider = provider,
                    ModelName = modelName,
                    OperationType = operationType,
                    TokensUsed = tokensUsed,
                    CostPerToken = costPerToken,
                    TotalCost = totalCost,
                    CampaignId = campaignId,
                    UserId = userId
                };

                _context.AICosts.Add(cost);
                await _context.SaveChangesAsync();

                // Log cost metric
                await LogMetricAsync("cost_per_request", totalCost, "USD", modelName, provider, campaignId, userId);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error logging AI cost");
            }
        }

        public async Task UpdateModelPerformanceAsync(string modelName, string provider, int responseTime, bool isSuccess)
        {
            try
            {
                var today = DateTime.Today;
                var performance = await _context.AIModelPerformance
                    .FirstOrDefaultAsync(p => p.ModelName == modelName && p.Provider == provider && p.Date == today);

                if (performance == null)
                {
                    performance = new AIModelPerformance
                    {
                        ModelName = modelName,
                        Provider = provider,
                        Date = today,
                        AverageResponseTime = responseTime,
                        SuccessRate = isSuccess ? 100 : 0,
                        ErrorRate = isSuccess ? 0 : 100,
                        TotalRequests = 1,
                        TotalErrors = isSuccess ? 0 : 1
                    };
                    _context.AIModelPerformance.Add(performance);
                }
                else
                {
                    // Update existing performance data
                    var totalRequests = performance.TotalRequests + 1;
                    var totalErrors = performance.TotalErrors + (isSuccess ? 0 : 1);
                    
                    performance.AverageResponseTime = (performance.AverageResponseTime * performance.TotalRequests + responseTime) / totalRequests;
                    performance.SuccessRate = (decimal)((totalRequests - totalErrors) * 100.0 / totalRequests);
                    performance.ErrorRate = (decimal)(totalErrors * 100.0 / totalRequests);
                    performance.TotalRequests = totalRequests;
                    performance.TotalErrors = totalErrors;
                    performance.UpdatedAt = DateTime.UtcNow;
                }

                await _context.SaveChangesAsync();

                // Log performance metrics
                await LogMetricAsync("response_time", responseTime, "ms", modelName, provider);
                await LogMetricAsync("success_rate", performance.SuccessRate, "%", modelName, provider);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error updating model performance for {ModelName}", modelName);
            }
        }

        public async Task<IEnumerable<AIMetrics>> GetMetricsAsync(DateTime? fromDate = null, DateTime? toDate = null, string? metricName = null, string? modelName = null)
        {
            var query = _context.AIMetrics.AsQueryable();

            if (fromDate.HasValue)
                query = query.Where(m => m.Timestamp >= fromDate.Value);

            if (toDate.HasValue)
                query = query.Where(m => m.Timestamp <= toDate.Value);

            if (!string.IsNullOrEmpty(metricName))
                query = query.Where(m => m.MetricName == metricName);

            if (!string.IsNullOrEmpty(modelName))
                query = query.Where(m => m.ModelName == modelName);

            return await query.OrderByDescending(m => m.Timestamp).ToListAsync();
        }

        public async Task<IEnumerable<AILogs>> GetLogsAsync(DateTime? fromDate = null, DateTime? toDate = null, string? level = null, string? category = null)
        {
            var query = _context.AILogs.AsQueryable();

            if (fromDate.HasValue)
                query = query.Where(l => l.Timestamp >= fromDate.Value);

            if (toDate.HasValue)
                query = query.Where(l => l.Timestamp <= toDate.Value);

            if (!string.IsNullOrEmpty(level))
                query = query.Where(l => l.LogLevel == level);

            if (!string.IsNullOrEmpty(category))
                query = query.Where(l => l.LogCategory == category);

            return await query.OrderByDescending(l => l.Timestamp).ToListAsync();
        }

        public async Task<IEnumerable<AIAlerts>> GetAlertsAsync(bool? isResolved = null, string? level = null, DateTime? fromDate = null)
        {
            var query = _context.AIAlerts.AsQueryable();

            if (isResolved.HasValue)
                query = query.Where(a => a.IsResolved == isResolved.Value);

            if (!string.IsNullOrEmpty(level))
                query = query.Where(a => a.AlertLevel == level);

            if (fromDate.HasValue)
                query = query.Where(a => a.CreatedAt >= fromDate.Value);

            return await query.OrderByDescending(a => a.CreatedAt).ToListAsync();
        }

        public async Task<IEnumerable<AICosts>> GetCostsAsync(DateTime? fromDate = null, DateTime? toDate = null, string? provider = null)
        {
            var query = _context.AICosts.AsQueryable();

            if (fromDate.HasValue)
                query = query.Where(c => c.Date >= fromDate.Value.Date);

            if (toDate.HasValue)
                query = query.Where(c => c.Date <= toDate.Value.Date);

            if (!string.IsNullOrEmpty(provider))
                query = query.Where(c => c.Provider == provider);

            return await query.OrderByDescending(c => c.Date).ToListAsync();
        }

        public async Task<IEnumerable<AIModelPerformance>> GetModelPerformanceAsync(DateTime? fromDate = null, DateTime? toDate = null, string? modelName = null)
        {
            var query = _context.AIModelPerformance.AsQueryable();

            if (fromDate.HasValue)
                query = query.Where(p => p.Date >= fromDate.Value.Date);

            if (toDate.HasValue)
                query = query.Where(p => p.Date <= toDate.Value.Date);

            if (!string.IsNullOrEmpty(modelName))
                query = query.Where(p => p.ModelName == modelName);

            return await query.OrderByDescending(p => p.Date).ToListAsync();
        }

        public async Task<AdminDashboardViewModel> GetDashboardDataAsync()
        {
            try
            {
                var fromDate = DateTime.UtcNow.AddDays(-7);
                var toDate = DateTime.UtcNow;

                // Get 24h statistics
                var yesterday = DateTime.UtcNow.AddDays(-1);
                var logs24h = await _context.AILogs
                    .Where(l => l.Timestamp >= yesterday)
                    .ToListAsync();

                var totalRequests24h = logs24h.Count;
                var successRate24h = totalRequests24h > 0 
                    ? (double)logs24h.Count(l => l.LogLevel != "ERROR") * 100.0 / totalRequests24h 
                    : 0;
                var averageResponseTime = totalRequests24h > 0 
                    ? logs24h.Where(l => l.ResponseTime.HasValue).Average(l => l.ResponseTime!.Value) 
                    : 0;
                var totalCost24h = logs24h.Where(l => l.Cost.HasValue).Sum(l => l.Cost!.Value);

                // Get active alerts
                var activeAlerts = await GetAlertsAsync(isResolved: false);

                // Get model performance
                var modelPerformance = await GetModelPerformanceAsync(fromDate, toDate);

                // Prepare chart data
                var requestsData = await _context.AILogs
                    .Where(l => l.Timestamp >= fromDate)
                    .GroupBy(l => l.Timestamp.Date)
                    .Select(g => new RequestDataPoint
                    {
                        Date = g.Key.ToString("yyyy-MM-dd"),
                        Count = g.Count()
                    })
                    .ToListAsync();

                var modelsData = await _context.AILogs
                    .Where(l => l.Timestamp >= fromDate && !string.IsNullOrEmpty(l.ModelName))
                    .GroupBy(l => l.ModelName!)
                    .Select(g => new ModelDataPoint
                    {
                        Model = g.Key,
                        Count = g.Count()
                    })
                    .ToListAsync();

                return new AdminDashboardViewModel
                {
                    TotalRequests24h = totalRequests24h,
                    SuccessRate24h = successRate24h,
                    AverageResponseTime = averageResponseTime,
                    TotalCost24h = totalCost24h,
                    ActiveAlerts = activeAlerts.ToList(),
                    ModelPerformance = modelPerformance.ToList(),
                    RequestsData = requestsData,
                    ModelsData = modelsData
                };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting dashboard data");
                return new AdminDashboardViewModel();
            }
        }

        public async Task ResolveAlertAsync(int alertId, string resolvedBy)
        {
            var alert = await _context.AIAlerts.FindAsync(alertId);
            if (alert != null)
            {
                alert.IsResolved = true;
                alert.ResolvedAt = DateTime.UtcNow;
                alert.ResolvedBy = resolvedBy;
                alert.UpdatedAt = DateTime.UtcNow;

                await _context.SaveChangesAsync();
            }
        }

        public async Task<IEnumerable<AIAlertThresholds>> GetAlertThresholdsAsync()
        {
            return await _context.AIAlertThresholds
                .Where(t => t.IsActive)
                .OrderBy(t => t.MetricName)
                .ToListAsync();
        }

        public async Task UpdateAlertThresholdAsync(AIAlertThresholds threshold)
        {
            threshold.UpdatedAt = DateTime.UtcNow;
            _context.AIAlertThresholds.Update(threshold);
            await _context.SaveChangesAsync();
        }

        private async Task CheckThresholdsAndCreateAlertsAsync(string metricName, decimal value)
        {
            var thresholds = await _context.AIAlertThresholds
                .Where(t => t.MetricName == metricName && t.IsActive)
                .ToListAsync();

            foreach (var threshold in thresholds)
            {
                bool shouldAlert = threshold.ThresholdType switch
                {
                    "MAX" => value > threshold.ThresholdValue,
                    "MIN" => value < threshold.ThresholdValue,
                    "AVERAGE" => value > threshold.ThresholdValue, // Simplified for now
                    _ => false
                };

                if (shouldAlert)
                {
                    await CreateAlertAsync(
                        "THRESHOLD_EXCEEDED",
                        $"Metric '{metricName}' value {value} exceeded threshold {threshold.ThresholdValue} ({threshold.ThresholdType})",
                        threshold.AlertLevel,
                        $"Threshold Alert: {metricName}",
                        metadata: new { threshold.ThresholdValue, threshold.ThresholdType, currentValue = value }
                    );
                }
            }
        }
    }

    public class AIMonitoringDashboard
    {
        public IEnumerable<AIMetrics> RecentMetrics { get; set; } = new List<AIMetrics>();
        public IEnumerable<AILogs> RecentLogs { get; set; } = new List<AILogs>();
        public IEnumerable<AIAlerts> ActiveAlerts { get; set; } = new List<AIAlerts>();
        public IEnumerable<DailyCostSummary> DailyCosts { get; set; } = new List<DailyCostSummary>();
        public IEnumerable<AIModelPerformance> ModelPerformance { get; set; } = new List<AIModelPerformance>();
    }

    public class DailyCostSummary
    {
        public DateTime Date { get; set; }
        public decimal TotalCost { get; set; }
        public int TotalTokens { get; set; }
    }
} 