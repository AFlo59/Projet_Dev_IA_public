using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using DnDGameMaster.WebApp.Models;
using Microsoft.Extensions.Configuration;
using System.Text.Json.Serialization;
using Microsoft.Extensions.Logging;
using System.Net.Http;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Identity;
using System.Security.Claims;

namespace DnDGameMaster.WebApp.Services.LLM
{
    public class LLMGameMasterService : ILLMGameMasterService
    {
        private readonly HttpClient _httpClient;
        private readonly IConfiguration _configuration;
        private readonly ILogger<LLMGameMasterService> _logger;
        private readonly IJWTTokenService _jwtTokenService;
        private readonly IHttpContextAccessor _httpContextAccessor;
        private readonly UserManager<ApplicationUser> _userManager;
        
        public LLMGameMasterService(
            HttpClient httpClient, 
            IConfiguration configuration, 
            ILogger<LLMGameMasterService> logger,
            IJWTTokenService jwtTokenService,
            IHttpContextAccessor httpContextAccessor,
            UserManager<ApplicationUser> userManager)
        {
            _httpClient = httpClient;
            _configuration = configuration;
            _logger = logger;
            _jwtTokenService = jwtTokenService;
            _httpContextAccessor = httpContextAccessor;
            _userManager = userManager;
        }
        
        /// <summary>
        /// Configure l'authentification JWT pour les requêtes vers l'API LLM
        /// </summary>
        private async Task<bool> ConfigureAuthenticationAsync()
        {
            try
            {
                // Vérifier si l'authentification JWT est activée pour l'API LLM
                var authEnabled = _configuration.GetValue<bool>("LLM_ENABLE_AUTH", true);
                if (!authEnabled)
                {
                    _logger.LogDebug("JWT authentication disabled for LLM API");
                    return true;
                }
                
                // Obtenir l'utilisateur actuel
                var httpContext = _httpContextAccessor.HttpContext;
                if (httpContext?.User?.Identity?.IsAuthenticated == true)
                {
                    var userId = httpContext.User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
                    if (!string.IsNullOrEmpty(userId))
                    {
                        var user = await _userManager.FindByIdAsync(userId);
                        if (user != null)
                        {
                            // Générer le token JWT
                            var token = await _jwtTokenService.GenerateTokenAsync(user);
                            if (!string.IsNullOrEmpty(token))
                            {
                                // Configurer l'header Authorization
                                _httpClient.DefaultRequestHeaders.Authorization = 
                                    new AuthenticationHeaderValue("Bearer", token);
                                
                                _logger.LogDebug($"JWT token configured for user {user.Email}");
                                return true;
                            }
                            else
                            {
                                _logger.LogError($"Failed to generate JWT token for user {user.Email}");
                                return false;
                            }
                        }
                    }
                }
                
                _logger.LogWarning("No authenticated user found for LLM API call");
                return false;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error configuring JWT authentication for LLM API");
                return false;
            }
        }
        
        public async Task<GameMasterResponse> GenerateNarrativeResponseAsync(int campaignId, string message, string userId, int? characterId = null)
        {
            try
            {
                // Configurer l'authentification JWT
                var authConfigured = await ConfigureAuthenticationAsync();
                if (!authConfigured)
                {
                    _logger.LogWarning("JWT authentication configuration failed, proceeding without auth");
                }
                
                var requestData = new
                {
                    campaign_id = campaignId,
                    user_id = userId,
                    character_id = characterId,
                    message = message,
                    message_type = "narrative"
                };
                
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, "generate");
                
                _logger.LogInformation($"Sending narrative response request to: {requestUri}");
                
                var response = await _httpClient.PostAsJsonAsync(requestUri, requestData);
                response.EnsureSuccessStatusCode();
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<Dictionary<string, string>>(responseContent);
                
                return new GameMasterResponse
                {
                    Success = true,
                    Message = data?.GetValueOrDefault("response", "The Game Master is pondering...") ?? "The Game Master is pondering...",
                    GeneratedImageUrl = data?.GetValueOrDefault("image_url")?.ToString()
                };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error generating narrative response");
                return new GameMasterResponse
                {
                    Success = false,
                    Message = "The Game Master is having trouble responding. Please try again."
                };
            }
        }
        
        public async Task<GameMasterResponse> StartCampaignAsync(int campaignId, int sessionId, int characterId, string playerName)
        {
            try
            {
                // Configurer l'authentification JWT
                await ConfigureAuthenticationAsync();
                
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, "api/gamemaster/start_campaign");
                
                _logger.LogInformation($"Sending start campaign request to: {requestUri}");
                
                var requestData = new
                {
                    campaignId,
                    sessionId,
                    characterId,
                    playerName
                };
                
                var response = await _httpClient.PostAsJsonAsync(requestUri, requestData);

                if (!response.IsSuccessStatusCode)
                {
                    var errorContent = await response.Content.ReadAsStringAsync();
                    _logger.LogError($"LLM service returned error: {response.StatusCode}, Content: {errorContent}");
                    return new GameMasterResponse 
                    { 
                        Success = false, 
                        Message = "Failed to start campaign with Game Master" 
                    };
                }

                var responseContent = await response.Content.ReadAsStringAsync();
                _logger.LogInformation($"LLM service response: {responseContent}");
                
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                if (data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True")
                {
                    var message = data.TryGetValue("introduction", out var introObj) ? introObj.ToString() : 
                                 data.TryGetValue("message", out var msgObj) ? msgObj.ToString() : 
                                 "Welcome to the adventure!";
                    
                    return new GameMasterResponse
                    {
                        Success = true,
                        Message = message ?? "Welcome to the adventure!"
                    };
                }
                else
                {
                    var errorMessage = data?.TryGetValue("message", out var errObj) == true ? errObj.ToString() : "Unknown error";
                    return new GameMasterResponse
                    {
                        Success = false,
                        Message = errorMessage ?? "Failed to start campaign"
                    };
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error starting campaign with LLM service");
                return new GameMasterResponse
                {
                    Success = false,
                    Message = "Error communicating with Game Master service"
                };
            }
        }

        public async Task<GameMasterResponse> SendMessageAsync(int campaignId, int sessionId, int characterId, string message, bool isSystemMessage = false)
        {
            try
            {
                // Configurer l'authentification JWT
                await ConfigureAuthenticationAsync();
                
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, "api/gamemaster/send_message");
                
                _logger.LogInformation($"Sending message to LLM service at: {requestUri}");
                
                var requestData = new
                {
                    campaignId,
                    sessionId,
                    characterId,
                    message,
                    isSystemMessage
                };
                
                var response = await _httpClient.PostAsJsonAsync(requestUri, requestData);

                if (!response.IsSuccessStatusCode)
                {
                    var errorContent = await response.Content.ReadAsStringAsync();
                    _logger.LogError($"LLM service returned error: {response.StatusCode}, Content: {errorContent}");
                    return new GameMasterResponse 
                    { 
                        Success = false, 
                        Message = "The Game Master is having trouble responding. Please try again." 
                    };
                }

                var responseContent = await response.Content.ReadAsStringAsync();
                _logger.LogInformation($"LLM service response: {responseContent}");
                
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                if (data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True")
                {
                    var responseMessage = data.TryGetValue("message", out var msgObj) ? msgObj.ToString() : 
                                        "The Game Master ponders your words...";
                    
                    return new GameMasterResponse
                    {
                        Success = true,
                        Message = responseMessage ?? "The Game Master ponders your words..."
                    };
                }
                else
                {
                    var errorMessage = data?.TryGetValue("message", out var errObj) == true ? errObj.ToString() : "Unknown error";
                    return new GameMasterResponse
                    {
                        Success = false,
                        Message = errorMessage ?? "The Game Master is having trouble responding."
                    };
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error sending message to LLM service");
                return new GameMasterResponse
                {
                    Success = false,
                    Message = "Error communicating with Game Master service"
                };
            }
        }

        public async Task<GameMasterResponse> EndSessionAsync(int campaignId, int sessionId)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, "api/gamemaster/end_session");
                
                _logger.LogInformation($"Sending end session request to: {requestUri}");
                
                var response = await _httpClient.PostAsJsonAsync(requestUri, new
                {
                    campaignId,
                    sessionId,
                    message_type = "session_summary"
                });

                response.EnsureSuccessStatusCode();
                return await response.Content.ReadFromJsonAsync<GameMasterResponse>() ?? 
                       new GameMasterResponse { Message = "Unable to parse response from LLM service", Success = false };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error ending session with LLM service");
                return new GameMasterResponse
                {
                    Success = false,
                    Message = $"Error communicating with LLM service: {ex.Message}"
                };
            }
        }

        public async Task<CampaignElementsResponse> GetCampaignElementsAsync(int campaignId)
        {
            try
            {
                // Configurer l'authentification JWT
                await ConfigureAuthenticationAsync();
                
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, $"api/gamemaster/campaign/{campaignId}/elements");
                
                _logger.LogInformation($"Getting campaign elements from: {requestUri}");
                
                var response = await _httpClient.GetAsync(requestUri);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError($"Failed to get campaign elements: {response.StatusCode}");
                    return new CampaignElementsResponse { Success = false };
                }
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                if (data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True")
                {
                    var npcs = await GetElementsFromEndpointAsync<CampaignNPCDto>($"api/gamemaster/campaign/{campaignId}/npcs");
                    var locations = await GetElementsFromEndpointAsync<CampaignLocationDto>($"api/gamemaster/campaign/{campaignId}/locations");
                    var quests = await GetElementsFromEndpointAsync<CampaignQuestDto>($"api/gamemaster/campaign/{campaignId}/quests");
                    
                    return new CampaignElementsResponse
                    {
                        Success = true,
                        NPCs = npcs,
                        Locations = locations,
                        Quests = quests
                    };
                }
                
                return new CampaignElementsResponse { Success = false };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting campaign elements");
                return new CampaignElementsResponse { Success = false };
            }
        }

        private async Task<List<T>> GetElementsFromEndpointAsync<T>(string endpoint)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, endpoint);
                
                var response = await _httpClient.GetAsync(requestUri);
                response.EnsureSuccessStatusCode();
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                if (data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True")
                {
                    var elementsKey = typeof(T).Name.ToLower().Contains("npc") ? "npcs" :
                                     typeof(T).Name.ToLower().Contains("location") ? "locations" : "quests";
                    
                    if (data.TryGetValue(elementsKey, out var elementsObj))
                    {
                        var elementsJson = elementsObj?.ToString() ?? "[]";
                        return JsonSerializer.Deserialize<List<T>>(elementsJson) ?? new List<T>();
                    }
                }
                
                return new List<T>();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error getting elements from endpoint {endpoint}");
                return new List<T>();
            }
        }

        public async Task<ImageStatusResponse> GetImageStatusAsync(int campaignId)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, $"api/gamemaster/campaign/{campaignId}/image_status");
                
                _logger.LogInformation($"Getting image status from: {requestUri}");
                
                var response = await _httpClient.GetAsync(requestUri);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError($"Failed to get image status: {response.StatusCode}");
                    return new ImageStatusResponse { Success = false, CampaignId = campaignId };
                }
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                if (data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True")
                {
                    var statusData = data.TryGetValue("status", out var statusObj) ? statusObj : null;
                    var status = JsonSerializer.Deserialize<ImageStatus>(JsonSerializer.Serialize(statusData));
                    
                    return new ImageStatusResponse
                    {
                        Success = true,
                        CampaignId = campaignId,
                        Status = status ?? new ImageStatus()
                    };
                }
                
                return new ImageStatusResponse { Success = false, CampaignId = campaignId };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting image status");
                return new ImageStatusResponse { Success = false, CampaignId = campaignId };
            }
        }

        public async Task<ImageGenerationResponse> GenerateMissingImagesAsync(int campaignId)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, $"api/gamemaster/campaign/{campaignId}/generate_missing_images");
                
                _logger.LogInformation($"Starting missing image generation for campaign {campaignId}");
                
                var response = await _httpClient.PostAsync(requestUri, null);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError($"Failed to start image generation: {response.StatusCode}");
                    return new ImageGenerationResponse { Success = false, CampaignId = campaignId };
                }
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                if (data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True")
                {
                    var message = data.TryGetValue("message", out var msgObj) ? msgObj.ToString() : "Image generation started";
                    var status = data.TryGetValue("status", out var statusObj) ? statusObj.ToString() : "started";
                    
                    return new ImageGenerationResponse
                    {
                        Success = true,
                        CampaignId = campaignId,
                        Message = message ?? "Image generation started",
                        Status = status ?? "started"
                    };
                }
                
                return new ImageGenerationResponse { Success = false, CampaignId = campaignId };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error starting image generation");
                return new ImageGenerationResponse { Success = false, CampaignId = campaignId };
            }
        }

        public async Task<ImageGenerationResponse> GenerateElementImageAsync(int campaignId, string elementType, int elementId)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, $"api/gamemaster/campaign/{campaignId}/elements/{elementType}/{elementId}/generate_image");
                
                _logger.LogInformation($"Generating image for {elementType} {elementId} in campaign {campaignId}");
                
                var response = await _httpClient.PostAsync(requestUri, null);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError($"Failed to generate image: {response.StatusCode}");
                    return new ImageGenerationResponse { Success = false, CampaignId = campaignId, ElementType = elementType, ElementId = elementId };
                }
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                if (data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True")
                {
                    var imageUrl = data.TryGetValue("image_url", out var imgObj) ? imgObj.ToString() : null;
                    var message = data.TryGetValue("message", out var msgObj) ? msgObj.ToString() : "Image generated successfully";
                    
                    return new ImageGenerationResponse
                    {
                        Success = true,
                        CampaignId = campaignId,
                        ElementType = elementType,
                        ElementId = elementId,
                        ImageUrl = imageUrl ?? string.Empty,
                        Message = message ?? "Image generated successfully"
                    };
                }
                
                return new ImageGenerationResponse { Success = false, CampaignId = campaignId, ElementType = elementType, ElementId = elementId };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error generating element image");
                return new ImageGenerationResponse { Success = false, CampaignId = campaignId, ElementType = elementType, ElementId = elementId };
            }
        }
        
        public async Task<ContentGenerationResponse> GenerateCampaignContentAsync(int campaignId)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, $"api/gamemaster/campaign/{campaignId}/generate_content");
                
                _logger.LogInformation($"Starting content generation for campaign {campaignId}");
                _logger.LogInformation($"Sending request to: {requestUri}");
                
                // Add timeout and retry logic
                using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
                
                // First, test connectivity to the service
                try
                {
                    var healthUri = new Uri(baseUri, "health");
                    var healthResponse = await _httpClient.GetAsync(healthUri, cts.Token);
                    if (!healthResponse.IsSuccessStatusCode)
                    {
                        _logger.LogWarning($"LLM GameMaster service health check failed: {healthResponse.StatusCode}");
                    }
                    else
                    {
                        _logger.LogInformation("LLM GameMaster service is healthy");
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning($"Health check failed: {ex.Message}");
                    // Continue anyway, maybe the health endpoint is not available
                }
                
                var response = await _httpClient.PostAsync(requestUri, null, cts.Token);
                
                if (!response.IsSuccessStatusCode)
                {
                    var errorContent = await response.Content.ReadAsStringAsync();
                    _logger.LogError($"Failed to start content generation: {response.StatusCode} - {errorContent}");
                    return new ContentGenerationResponse { Success = false, CampaignId = campaignId };
                }
                
                var responseContent = await response.Content.ReadAsStringAsync();
                _logger.LogInformation($"Response content: {responseContent}");
                
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                if (data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True")
                {
                    var message = data.TryGetValue("message", out var msgObj) ? msgObj.ToString() : "Content generation started";
                    var status = data.TryGetValue("status", out var statusObj) ? statusObj.ToString() : "started";
                    
                    _logger.LogInformation($"Content generation started successfully for campaign {campaignId}");
                    
                    return new ContentGenerationResponse
                    {
                        Success = true,
                        CampaignId = campaignId,
                        Message = message ?? "Content generation started",
                        Status = status ?? "started"
                    };
                }
                
                _logger.LogError($"Invalid response format for campaign {campaignId}: {responseContent}");
                return new ContentGenerationResponse { Success = false, CampaignId = campaignId };
            }
            catch (TaskCanceledException ex) when (ex.InnerException is TimeoutException)
            {
                _logger.LogError($"Timeout while starting content generation for campaign {campaignId}: {ex.Message}");
                return new ContentGenerationResponse { Success = false, CampaignId = campaignId };
            }
            catch (HttpRequestException ex)
            {
                _logger.LogError($"Network error while starting content generation for campaign {campaignId}: {ex.Message}");
                return new ContentGenerationResponse { Success = false, CampaignId = campaignId };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error starting content generation for campaign {campaignId}");
                return new ContentGenerationResponse { Success = false, CampaignId = campaignId };
            }
        }
        
        public async Task<ContentGenerationStatusResponse> GetContentGenerationStatusAsync(int campaignId)
        {
            const int maxRetries = 3;
            const int timeoutSeconds = 180; // Augmenté à 3 minutes
            
            for (int attempt = 1; attempt <= maxRetries; attempt++)
            {
                try
                {
                    var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                    var requestUri = new Uri(baseUri, $"api/gamemaster/campaign/{campaignId}/content_status");
                    
                    _logger.LogInformation($"Getting content generation status for campaign {campaignId} (attempt {attempt}/{maxRetries})");
                    _logger.LogDebug($"Sending request to: {requestUri}");
                    
                    // Timeout plus long pour les vérifications de statut
                    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(timeoutSeconds));
                    
                    var response = await _httpClient.GetAsync(requestUri, cts.Token);
                    
                    if (!response.IsSuccessStatusCode)
                    {
                        var errorContent = await response.Content.ReadAsStringAsync();
                        _logger.LogError($"Failed to get content generation status: {response.StatusCode} - {errorContent}");
                        
                        if (attempt < maxRetries)
                        {
                            _logger.LogWarning($"Retrying in 10 seconds... (attempt {attempt}/{maxRetries})");
                            await Task.Delay(10000, cts.Token);
                            continue;
                        }
                        
                        return new ContentGenerationStatusResponse { Success = false, CampaignId = campaignId };
                    }
                    
                    var responseContent = await response.Content.ReadAsStringAsync();
                    _logger.LogDebug($"Status response content: {responseContent}");
                    
                    var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                    
                    if (data != null && data.TryGetValue("success", out var successObj) && successObj?.ToString() == "True")
                    {
                        var status = data.TryGetValue("status", out var statusObj) ? statusObj?.ToString() ?? "Unknown" : "Unknown";
                        var error = data.TryGetValue("error", out var errorObj) ? errorObj?.ToString() : null;
                        var startedAt = data.TryGetValue("started_at", out var startedObj) ? startedObj?.ToString() : null;
                        var completedAt = data.TryGetValue("completed_at", out var completedObj) ? completedObj?.ToString() : null;
                        
                        _logger.LogDebug($"Status for campaign {campaignId}: {status}");
                        
                        return new ContentGenerationStatusResponse
                        {
                            Success = true,
                            CampaignId = campaignId,
                            Status = status,
                            Error = error,
                            StartedAt = !string.IsNullOrEmpty(startedAt) ? DateTime.Parse(startedAt) : null,
                            CompletedAt = !string.IsNullOrEmpty(completedAt) ? DateTime.Parse(completedAt) : null
                        };
                    }
                    
                    _logger.LogWarning($"Invalid status response format for campaign {campaignId}: {responseContent}");
                    
                    if (attempt < maxRetries)
                    {
                        _logger.LogWarning($"Retrying in 10 seconds... (attempt {attempt}/{maxRetries})");
                        await Task.Delay(10000, cts.Token);
                        continue;
                    }
                    
                    return new ContentGenerationStatusResponse { Success = false, CampaignId = campaignId };
                }
                catch (TaskCanceledException ex) when (ex.InnerException is TimeoutException)
                {
                    _logger.LogError($"Timeout while getting content status for campaign {campaignId} (attempt {attempt}/{maxRetries}): {ex.Message}");
                    
                    if (attempt < maxRetries)
                    {
                        _logger.LogWarning($"Retrying in 15 seconds... (attempt {attempt}/{maxRetries})");
                        await Task.Delay(15000);
                        continue;
                    }
                    
                    return new ContentGenerationStatusResponse { Success = false, CampaignId = campaignId };
                }
                catch (HttpRequestException ex)
                {
                    _logger.LogError($"Network error while getting content status for campaign {campaignId} (attempt {attempt}/{maxRetries}): {ex.Message}");
                    
                    if (attempt < maxRetries)
                    {
                        _logger.LogWarning($"Retrying in 15 seconds... (attempt {attempt}/{maxRetries})");
                        await Task.Delay(15000);
                        continue;
                    }
                    
                    return new ContentGenerationStatusResponse { Success = false, CampaignId = campaignId };
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, $"Error getting content generation status for campaign {campaignId} (attempt {attempt}/{maxRetries})");
                    
                    if (attempt < maxRetries)
                    {
                        _logger.LogWarning($"Retrying in 15 seconds... (attempt {attempt}/{maxRetries})");
                        await Task.Delay(15000);
                        continue;
                    }
                    
                    return new ContentGenerationStatusResponse { Success = false, CampaignId = campaignId };
                }
            }
            
            return new ContentGenerationStatusResponse { Success = false, CampaignId = campaignId };
        }
        
        // ===============================
        // LOCATION SYNCHRONIZATION METHODS  
        // ===============================
        
        public async Task<CampaignNPCsResponse> GetCampaignNPCsAsync(int campaignId)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, $"api/gamemaster/campaign/{campaignId}/npcs");
                
                _logger.LogInformation($"Getting campaign NPCs for campaign {campaignId}");
                
                var response = await _httpClient.GetAsync(requestUri);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError($"Failed to get campaign NPCs: {response.StatusCode}");
                    return new CampaignNPCsResponse { Success = false };
                }
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                if (data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True")
                {
                    var npcs = await GetElementsFromEndpointAsync<CampaignNPCDto>($"api/gamemaster/campaign/{campaignId}/npcs");
                    return new CampaignNPCsResponse { Success = true, NPCs = npcs };
                }
                
                return new CampaignNPCsResponse { Success = false };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error getting campaign NPCs for campaign {campaignId}");
                return new CampaignNPCsResponse { Success = false };
            }
        }
        
        public async Task<CampaignLocationsResponse> GetCampaignLocationsAsync(int campaignId)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, $"api/gamemaster/campaign/{campaignId}/locations");
                
                _logger.LogInformation($"Getting campaign locations for campaign {campaignId}");
                
                var response = await _httpClient.GetAsync(requestUri);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError($"Failed to get campaign locations: {response.StatusCode}");
                    return new CampaignLocationsResponse { Success = false };
                }
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                if (data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True")
                {
                    var locations = await GetElementsFromEndpointAsync<CampaignLocationDto>($"api/gamemaster/campaign/{campaignId}/locations");
                    return new CampaignLocationsResponse { Success = true, Locations = locations };
                }
                
                return new CampaignLocationsResponse { Success = false };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error getting campaign locations for campaign {campaignId}");
                return new CampaignLocationsResponse { Success = false };
            }
        }
        
        public async Task<CampaignQuestsResponse> GetCampaignQuestsAsync(int campaignId)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, $"api/gamemaster/campaign/{campaignId}/quests");
                
                _logger.LogInformation($"Getting campaign quests for campaign {campaignId}");
                
                using var httpClient = new HttpClient();
                httpClient.Timeout = TimeSpan.FromSeconds(60);
                
                var response = await httpClient.GetAsync(requestUri);
                
                if (response.IsSuccessStatusCode)
                {
                    var content = await response.Content.ReadAsStringAsync();
                    var result = JsonSerializer.Deserialize<CampaignQuestsResponse>(content, new JsonSerializerOptions
                    {
                        PropertyNameCaseInsensitive = true
                    });
                    
                    if (result != null)
                    {
                        _logger.LogInformation($"Successfully retrieved {result.Quests.Count} quests for campaign {campaignId}");
                        return result;
                    }
                }
                
                _logger.LogWarning($"Failed to get campaign quests for campaign {campaignId}. Status: {response.StatusCode}");
                return new CampaignQuestsResponse { Success = false };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error getting campaign quests for campaign {campaignId}");
                return new CampaignQuestsResponse { Success = false };
            }
        }
        
        public async Task<CampaignQuestsResponse> GetCharacterQuestsAsync(int campaignId)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, $"api/gamemaster/campaign/{campaignId}/character_quests");
                
                _logger.LogInformation($"Getting character quests for campaign {campaignId}");
                
                using var httpClient = new HttpClient();
                httpClient.Timeout = TimeSpan.FromSeconds(60);
                
                var response = await httpClient.GetAsync(requestUri);
                
                if (response.IsSuccessStatusCode)
                {
                    var content = await response.Content.ReadAsStringAsync();
                    var result = JsonSerializer.Deserialize<CampaignQuestsResponse>(content, new JsonSerializerOptions
                    {
                        PropertyNameCaseInsensitive = true
                    });
                    
                    if (result != null)
                    {
                        _logger.LogInformation($"Successfully retrieved {result.Quests.Count} character quests for campaign {campaignId}");
                        return result;
                    }
                }
                
                _logger.LogWarning($"Failed to get character quests for campaign {campaignId}. Status: {response.StatusCode}");
                return new CampaignQuestsResponse { Success = false };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error getting character quests for campaign {campaignId}");
                return new CampaignQuestsResponse { Success = false };
            }
        }
        
        public async Task<bool> UpdateCharacterLocationAsync(int campaignId, int characterId, string location)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, $"api/gamemaster/campaign/{campaignId}/character/{characterId}/location");
                
                _logger.LogInformation($"Updating character {characterId} location to {location} in campaign {campaignId}");
                
                var requestData = new { location = location };
                var response = await _httpClient.PostAsJsonAsync(requestUri, requestData);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError($"Failed to update character location: {response.StatusCode}");
                    return false;
                }
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                return data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True";
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error updating character {characterId} location in campaign {campaignId}");
                return false;
            }
        }
        
        public async Task<bool> SyncAllCharacterLocationsAsync(int campaignId, Dictionary<int, string> characterLocations)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, $"api/gamemaster/campaign/{campaignId}/sync_locations");
                
                _logger.LogInformation($"Syncing all character locations for campaign {campaignId}");
                
                var requestData = new { character_locations = characterLocations };
                var response = await _httpClient.PostAsJsonAsync(requestUri, requestData);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError($"Failed to sync character locations: {response.StatusCode}");
                    return false;
                }
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                return data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True";
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error syncing character locations for campaign {campaignId}");
                return false;
            }
        }
        
        public async Task<CharacterLocationResponse> GetCharacterLocationAsync(int campaignId, int characterId)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, $"api/gamemaster/campaign/{campaignId}/character/{characterId}/location");
                
                _logger.LogInformation($"Getting character {characterId} location from campaign {campaignId}");
                
                var response = await _httpClient.GetAsync(requestUri);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError($"Failed to get character location: {response.StatusCode}");
                    return new CharacterLocationResponse { Success = false, CharacterId = characterId };
                }
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                if (data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True")
                {
                    var currentLocation = data.TryGetValue("current_location", out var locObj) ? locObj.ToString() : string.Empty;
                    var characterName = data.TryGetValue("character_name", out var nameObj) ? nameObj.ToString() : string.Empty;
                    
                    return new CharacterLocationResponse
                    {
                        Success = true,
                        CharacterId = characterId,
                        CurrentLocation = currentLocation ?? string.Empty,
                        CharacterName = characterName ?? string.Empty
                    };
                }
                
                return new CharacterLocationResponse { Success = false, CharacterId = characterId };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error getting character {characterId} location from campaign {campaignId}");
                return new CharacterLocationResponse { Success = false, CharacterId = characterId };
            }
        }

        // Additional methods for test compatibility
        public async Task<GameMasterResponse> GenerateNarrativeAsync(int campaignId, string message, string userId, int? characterId = null)
        {
            // This is an alias for GenerateNarrativeResponseAsync for test compatibility
            return await GenerateNarrativeResponseAsync(campaignId, message, userId, characterId);
        }

        public async Task<GameMasterResponse> GenerateCharacterDescriptionAsync(string characterName, string characterClass, string characterRace, string background, string language)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, "api/gamemaster/character/description");
                
                _logger.LogInformation($"Generating character description for: {characterName}");
                
                var requestData = new
                {
                    characterName,
                    characterClass,
                    characterRace,
                    background,
                    language
                };
                
                var response = await _httpClient.PostAsJsonAsync(requestUri, requestData);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError($"Failed to generate character description: {response.StatusCode}");
                    return new GameMasterResponse 
                    { 
                        Success = false, 
                        Message = "Failed to generate character description" 
                    };
                }
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                if (data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True")
                {
                    var description = data.TryGetValue("description", out var descObj) ? descObj.ToString() : 
                                    $"A {characterRace} {characterClass} named {characterName} with {background} background.";
                    
                    return new GameMasterResponse
                    {
                        Success = true,
                        Message = description ?? $"A {characterRace} {characterClass} named {characterName} with {background} background."
                    };
                }
                
                return new GameMasterResponse
                {
                    Success = false,
                    Message = "Failed to generate character description"
                };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error generating character description");
                return new GameMasterResponse
                {
                    Success = false,
                    Message = $"A {characterRace} {characterClass} named {characterName} with {background} background."
                };
            }
        }

        public async Task<CampaignMetricsResponse> GetCampaignMetricsAsync(int campaignId)
        {
            try
            {
                var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                var baseUri = new Uri(llmUrl);
                var requestUri = new Uri(baseUri, $"api/gamemaster/campaign/{campaignId}/metrics");
                
                _logger.LogInformation($"Getting campaign metrics for: {campaignId}");
                
                var response = await _httpClient.GetAsync(requestUri);
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError($"Failed to get campaign metrics: {response.StatusCode}");
                    return new CampaignMetricsResponse 
                    { 
                        Success = false, 
                        CampaignId = campaignId,
                        Message = "Failed to get campaign metrics"
                    };
                }
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<Dictionary<string, object>>(responseContent);
                
                if (data != null && data.TryGetValue("success", out var successObj) && successObj.ToString() == "True")
                {
                    var totalMessages = data.TryGetValue("total_messages", out var msgObj) && int.TryParse(msgObj.ToString(), out var msgCount) ? msgCount : 0;
                    var totalSessions = data.TryGetValue("total_sessions", out var sesObj) && int.TryParse(sesObj.ToString(), out var sesCount) ? sesCount : 0;
                    var activePlayers = data.TryGetValue("active_players", out var playObj) && int.TryParse(playObj.ToString(), out var playCount) ? playCount : 0;
                    var avgSessionLength = data.TryGetValue("average_session_length", out var avgObj) && double.TryParse(avgObj.ToString(), out var avgLen) ? avgLen : 0.0;
                    
                    return new CampaignMetricsResponse
                    {
                        Success = true,
                        CampaignId = campaignId,
                        TotalMessages = totalMessages,
                        TotalSessions = totalSessions,
                        ActivePlayers = activePlayers,
                        AverageSessionLength = avgSessionLength,
                        Message = "Campaign metrics retrieved successfully"
                    };
                }
                
                return new CampaignMetricsResponse
                {
                    Success = false,
                    CampaignId = campaignId,
                    Message = "Failed to get campaign metrics"
                };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting campaign metrics");
                return new CampaignMetricsResponse
                {
                    Success = false,
                    CampaignId = campaignId,
                    Message = "Error retrieving campaign metrics"
                };
            }
        }
    }

    public class GameMasterResponse
    {
        [JsonPropertyName("success")]
        public bool Success { get; set; }

        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;

        [JsonPropertyName("campaign_state")]
        public string? CampaignState { get; set; }

        [JsonPropertyName("generated_image_url")]
        public string? GeneratedImageUrl { get; set; }
    }

    public class CampaignElementsResponse
    {
        public bool Success { get; set; }
        public List<CampaignNPCDto> NPCs { get; set; } = new List<CampaignNPCDto>();
        public List<CampaignLocationDto> Locations { get; set; } = new List<CampaignLocationDto>();
        public List<CampaignQuestDto> Quests { get; set; } = new List<CampaignQuestDto>();
    }

    public class CampaignNPCDto
    {
        [JsonPropertyName("Id")]
        public int Id { get; set; }
        
        [JsonPropertyName("Name")]
        public string Name { get; set; } = string.Empty;
        
        [JsonPropertyName("Type")]
        public string Type { get; set; } = string.Empty;
        
        [JsonPropertyName("Race")]
        public string Race { get; set; } = string.Empty;
        
        [JsonPropertyName("Class")]
        public string? Class { get; set; }
        
        [JsonPropertyName("Level")]
        public int Level { get; set; }
        
        [JsonPropertyName("HitPoints")]
        public int HitPoints { get; set; }
        
        [JsonPropertyName("ArmorClass")]
        public int ArmorClass { get; set; }
        
        [JsonPropertyName("Alignment")]
        public string? Alignment { get; set; }
        
        [JsonPropertyName("Description")]
        public string? Description { get; set; }
        
        [JsonPropertyName("CurrentLocation")]
        public string? CurrentLocation { get; set; }
        
        [JsonPropertyName("Status")]
        public string Status { get; set; } = "Active";
        
        [JsonPropertyName("Notes")]
        public string? Notes { get; set; }
        
        [JsonPropertyName("PortraitUrl")]
        public string? PortraitUrl { get; set; }
    }

    public class CampaignLocationDto
    {
        [JsonPropertyName("Id")]
        public int Id { get; set; }
        
        [JsonPropertyName("Name")]
        public string Name { get; set; } = string.Empty;
        
        [JsonPropertyName("Type")]
        public string Type { get; set; } = string.Empty;
        
        [JsonPropertyName("Description")]
        public string? Description { get; set; }
        
        [JsonPropertyName("ShortDescription")]
        public string? ShortDescription { get; set; }
        
        [JsonPropertyName("ParentLocationId")]
        public int? ParentLocationId { get; set; }
        
        [JsonPropertyName("IsDiscovered")]
        public bool IsDiscovered { get; set; }
        
        [JsonPropertyName("IsAccessible")]
        public bool IsAccessible { get; set; }
        
        [JsonPropertyName("Climate")]
        public string? Climate { get; set; }
        
        [JsonPropertyName("Terrain")]
        public string? Terrain { get; set; }
        
        [JsonPropertyName("Population")]
        public string? Population { get; set; }
        
        [JsonPropertyName("Notes")]
        public string? Notes { get; set; }
        
        [JsonPropertyName("ImageUrl")]
        public string? ImageUrl { get; set; }
    }

    public class CampaignQuestDto
    {
        [JsonPropertyName("Id")]
        public int Id { get; set; }
        
        [JsonPropertyName("Title")]
        public string Title { get; set; } = string.Empty;
        
        [JsonPropertyName("Description")]
        public string? Description { get; set; }
        
        [JsonPropertyName("ShortDescription")]
        public string? ShortDescription { get; set; }
        
        [JsonPropertyName("Type")]
        public string Type { get; set; } = "Side";
        
        [JsonPropertyName("Status")]
        public string Status { get; set; } = "Available";
        
        [JsonPropertyName("Reward")]
        public string? Reward { get; set; }
        
        [JsonPropertyName("Requirements")]
        public string? Requirements { get; set; }
        
        [JsonPropertyName("RequiredLevel")]
        public int? RequiredLevel { get; set; }
        
        [JsonPropertyName("LocationId")]
        public int? LocationId { get; set; }
        
        [JsonPropertyName("QuestGiver")]
        public string? QuestGiver { get; set; }
        
        [JsonPropertyName("Difficulty")]
        public string? Difficulty { get; set; }
        
        [JsonPropertyName("Notes")]
        public string? Notes { get; set; }
        
        [JsonPropertyName("Progress")]
        public string? Progress { get; set; }
    }


} 