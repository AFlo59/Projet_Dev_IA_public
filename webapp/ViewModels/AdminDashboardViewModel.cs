using System;
using System.Collections.Generic;
using System.Linq;
using DnDGameMaster.WebApp.Models;

namespace DnDGameMaster.WebApp.ViewModels
{
    public class AdminDashboardViewModel
    {
        public int TotalRequests24h { get; set; }
        public double SuccessRate24h { get; set; }
        public double AverageResponseTime { get; set; }
        public decimal TotalCost24h { get; set; }
        public List<AIAlerts> ActiveAlerts { get; set; } = new List<AIAlerts>();
        public List<AIModelPerformance> ModelPerformance { get; set; } = new List<AIModelPerformance>();
        public List<RequestDataPoint> RequestsData { get; set; } = new List<RequestDataPoint>();
        public List<ModelDataPoint> ModelsData { get; set; } = new List<ModelDataPoint>();
    }

    public class RequestDataPoint
    {
        public string Date { get; set; } = string.Empty;
        public int Count { get; set; }
    }

    public class ModelDataPoint
    {
        public string Model { get; set; } = string.Empty;
        public int Count { get; set; }
    }
} 