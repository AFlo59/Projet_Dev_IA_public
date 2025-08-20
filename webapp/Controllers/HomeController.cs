using DnDGameMaster.WebApp.Models;
using DnDGameMaster.WebApp.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using System.Diagnostics;

namespace DnDGameMaster.WebApp.Controllers
{
    public class HomeController : Controller
    {
        private readonly ILogger<HomeController> _logger;
        private readonly ApplicationDbContext _context;
        private readonly IConfiguration _configuration;

        public HomeController(ILogger<HomeController> logger, ApplicationDbContext context, IConfiguration configuration)
        {
            _logger = logger;
            _context = context;
            _configuration = configuration;
        }

        public IActionResult Index()
        {
            return View();
        }

        public IActionResult Privacy()
        {
            return View();
        }
        
        public IActionResult About()
        {
            return View();
        }

        [ResponseCache(Duration = 0, Location = ResponseCacheLocation.None, NoStore = true)]
        public IActionResult Error()
        {
            return View(new ErrorViewModel { RequestId = Activity.Current?.Id ?? HttpContext.TraceIdentifier });
        }

        [HttpGet("health")]
        public IActionResult Health()
        {
            try
            {
                // Vérifier la connectivité à la base de données
                var dbConnection = _context.Database.CanConnect();
                
                // Vérifier la connectivité au service LLM
                var llmHealth = CheckLLMHealth();
                
                var healthStatus = new
                {
                    Status = "Healthy",
                    Timestamp = DateTime.UtcNow,
                    Database = dbConnection ? "Connected" : "Disconnected",
                    LLMService = llmHealth ? "Available" : "Unavailable",
                    Version = "1.0.0"
                };
                
                return Ok(healthStatus);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Health check failed");
                return StatusCode(500, new
                {
                    Status = "Unhealthy",
                    Timestamp = DateTime.UtcNow,
                    Error = ex.Message
                });
            }
        }
        
        private bool CheckLLMHealth()
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, "api/health");
                
                using var client = new HttpClient();
                client.Timeout = TimeSpan.FromSeconds(5);
                
                var response = client.GetAsync(requestUri).Result;
                return response.IsSuccessStatusCode;
            }
            catch
            {
                return false;
            }
        }
    }
    
    public class ErrorViewModel
    {
        public string? RequestId { get; set; } = string.Empty;
        public bool ShowRequestId => !string.IsNullOrEmpty(RequestId);
    }
} 