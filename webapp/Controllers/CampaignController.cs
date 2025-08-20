using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc.Rendering;
using Microsoft.EntityFrameworkCore;
using System.Security.Claims;
using System.ComponentModel.DataAnnotations;
using DnDGameMaster.WebApp.Data;
using DnDGameMaster.WebApp.Models;
using DnDGameMaster.WebApp.Services.Game;
using DnDGameMaster.WebApp.Services.LLM;
using DnDGameMaster.WebApp.ViewModels;
using System.Threading.Tasks;
using System;
using System.Linq;
using System.Collections.Generic;
using Microsoft.Extensions.Configuration;
using System.Net.Http;

namespace DnDGameMaster.WebApp.Controllers
{
    [Authorize]
    public class CampaignController : Controller
    {
        private readonly ICampaignService _campaignService;
        private readonly ICharacterService _characterService;
        private readonly IGameSessionService _gameSessionService;
        private readonly ILLMGameMasterService _llmService;
        private readonly UserManager<ApplicationUser> _userManager;
        private readonly ILogger<CampaignController> _logger;
        private readonly ApplicationDbContext _context;
        private readonly IConfiguration _configuration;
        
        public CampaignController(
            ICampaignService campaignService,
            ICharacterService characterService,
            IGameSessionService gameSessionService,
            ILLMGameMasterService llmService,
            UserManager<ApplicationUser> userManager,
            ILogger<CampaignController> logger,
            ApplicationDbContext context,
            IConfiguration configuration)
        {
            _campaignService = campaignService;
            _characterService = characterService;
            _gameSessionService = gameSessionService;
            _llmService = llmService;
            _userManager = userManager;
            _logger = logger;
            _context = context;
            _configuration = configuration;
        }

        // GET: Campaign
        public async Task<IActionResult> Index()
        {
            var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
            var userCampaigns = await _campaignService.GetCampaignsForUserAsync(userId);
            var publicCampaigns = await _campaignService.GetPublicCampaignsAsync();
            
            var model = new CampaignIndexViewModel
            {
                UserCampaigns = userCampaigns,
                PublicCampaigns = publicCampaigns.Where(c => !userCampaigns.Any(uc => uc.Id == c.Id)).ToList()
            };
            
            return View(model);
        }

        // GET: Campaign/Details/5
        public async Task<IActionResult> Details(int id)
        {
            var campaign = await _campaignService.GetCampaignByIdAsync(id);
            if (campaign == null)
            {
                return NotFound();
            }

            var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
            var userInCampaign = await _campaignService.IsUserInCampaignAsync(id, userId);
            var isOwner = await _campaignService.IsUserCampaignOwnerAsync(id, userId);
            
            if (!isOwner && !userInCampaign && !campaign.IsPublic)
            {
                return Forbid();
            }

            var campaignCharacters = await _campaignService.GetCampaignCharactersAsync(id);
            var campaignSessions = await _campaignService.GetCampaignSessionsAsync(id);
            
            var model = new CampaignDetailsViewModel
            {
                Campaign = campaign,
                Characters = campaignCharacters,
                Sessions = campaignSessions,
                IsOwner = isOwner,
                UserInCampaign = userInCampaign
            };

            return View(model);
        }

        // GET: Campaign/Create
        public IActionResult Create()
        {
            return View();
        }

        // POST: Campaign/Create
        [HttpPost]
        [ValidateAntiForgeryToken]
        public async Task<IActionResult> Create(CampaignCreateViewModel model)
        {
            if (ModelState.IsValid)
            {
                var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
                if (string.IsNullOrEmpty(userId))
                {
                    // Si userId est null, redirigez vers la page de connexion
                    return RedirectToAction("Login", "Account");
                }
                
                // Vérifier que l'utilisateur existe dans la base de données
                var user = await _userManager.FindByIdAsync(userId);
                if (user == null)
                {
                    ModelState.AddModelError(string.Empty, "User account not found. Please contact support.");
                    return View(model);
                }
                
                var campaign = new Campaign
                {
                    Name = model.Name,
                    Description = model.Description,
                    Settings = model.Settings,
                    Language = model.Language,
                    StartingLevel = model.StartingLevel,
                    MaxPlayers = model.MaxPlayers,
                    IsPublic = model.IsPublic,
                    OwnerId = userId,
                    CreatedAt = DateTime.UtcNow
                };

                try
                {
                    var createdCampaign = await _campaignService.CreateCampaignAsync(campaign);
                    // Rediriger vers la création de personnage au lieu des détails de la campagne
                    return RedirectToAction("Create", "Character", new { campaignId = createdCampaign.Id });
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error creating campaign");
                    ModelState.AddModelError(string.Empty, "An error occurred while creating the campaign. Please try again.");
                }
            }
            
            return View(model);
        }

        // GET: Campaign/Edit/5
        [Authorize(Roles = "Admin,GameMaster")]
        public async Task<IActionResult> Edit(int id)
        {
            var campaign = await _campaignService.GetCampaignByIdAsync(id);
            if (campaign == null)
            {
                return NotFound();
            }

            var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
            var isOwner = await _campaignService.IsUserCampaignOwnerAsync(id, userId);
            
            if (!isOwner && !User.IsInRole("Admin"))
            {
                return Forbid();
            }

            var model = new CampaignEditViewModel
            {
                Id = campaign.Id,
                Name = campaign.Name,
                Description = campaign.Description,
                Settings = campaign.Settings,
                Language = campaign.Language,
                StartingLevel = campaign.StartingLevel,
                MaxPlayers = campaign.MaxPlayers,
                IsPublic = campaign.IsPublic,
                Status = campaign.Status
            };

            return View(model);
        }

        // POST: Campaign/Edit/5
        [HttpPost]
        [ValidateAntiForgeryToken]
        [Authorize(Roles = "Admin,GameMaster")]
        public async Task<IActionResult> Edit(int id, CampaignEditViewModel model)
        {
            if (id != model.Id)
            {
                return NotFound();
            }

            if (ModelState.IsValid)
            {
                var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
                var isOwner = await _campaignService.IsUserCampaignOwnerAsync(id, userId);
                
                if (!isOwner && !User.IsInRole("Admin"))
                {
                    return Forbid();
                }

                var campaign = await _campaignService.GetCampaignByIdAsync(id);
                if (campaign == null)
                {
                    return NotFound();
                }

                // Update campaign properties
                campaign.Name = model.Name;
                campaign.Description = model.Description;
                campaign.Settings = model.Settings;
                campaign.Language = model.Language;
                campaign.StartingLevel = model.StartingLevel;
                campaign.MaxPlayers = model.MaxPlayers;
                campaign.IsPublic = model.IsPublic;
                campaign.Status = model.Status;
                campaign.UpdatedAt = DateTime.UtcNow;

                try
                {
                    await _campaignService.UpdateCampaignAsync(campaign);
                    return RedirectToAction(nameof(Details), new { id = campaign.Id });
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error updating campaign");
                    ModelState.AddModelError(string.Empty, "An error occurred while updating the campaign. Please try again.");
                }
            }
            
            return View(model);
        }

        // GET: Campaign/Delete/5
        [Authorize(Roles = "Admin,GameMaster")]
        public async Task<IActionResult> Delete(int id)
        {
            var campaign = await _campaignService.GetCampaignByIdAsync(id);
            if (campaign == null)
            {
                return NotFound();
            }

            var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
            var isOwner = await _campaignService.IsUserCampaignOwnerAsync(id, userId);
            
            if (!isOwner && !User.IsInRole("Admin"))
            {
                return Forbid();
            }

            return View(campaign);
        }

        // POST: Campaign/Delete/5
        [HttpPost, ActionName("Delete")]
        [ValidateAntiForgeryToken]
        [Authorize(Roles = "Admin,GameMaster")]
        public async Task<IActionResult> DeleteConfirmed(int id)
        {
            var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
            var isOwner = await _campaignService.IsUserCampaignOwnerAsync(id, userId);
            
            if (!isOwner && !User.IsInRole("Admin"))
            {
                return Forbid();
            }

            await _campaignService.DeleteCampaignAsync(id);
            return RedirectToAction(nameof(Index));
        }

        // GET: Campaign/Join/5
        public async Task<IActionResult> Join(int id)
        {
            var campaign = await _campaignService.GetCampaignByIdAsync(id);
            if (campaign == null)
            {
                return NotFound();
            }

            var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
            var userInCampaign = await _campaignService.IsUserInCampaignAsync(id, userId);
            
            if (userInCampaign)
            {
                return RedirectToAction(nameof(Details), new { id = id });
            }

            if (!campaign.IsPublic)
            {
                return Forbid();
            }

            var userCharacters = await _characterService.GetCharactersForUserAsync(userId);
            
            var model = new CampaignJoinViewModel
            {
                CampaignId = id,
                CampaignName = campaign.Name,
                AvailableCharacters = userCharacters
                    .Select(c => new SelectListItem { Value = c.Id.ToString(), Text = c.Name })
                    .ToList()
            };

            return View(model);
        }

        // POST: Campaign/Join/5
        [HttpPost]
        [ValidateAntiForgeryToken]
        public async Task<IActionResult> Join(CampaignJoinViewModel model)
        {
            if (ModelState.IsValid)
            {
                var campaign = await _campaignService.GetCampaignByIdAsync(model.CampaignId);
                if (campaign == null)
                {
                    return NotFound();
                }

                var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
                var userInCampaign = await _campaignService.IsUserInCampaignAsync(model.CampaignId, userId);
                
                if (userInCampaign)
                {
                    return RedirectToAction(nameof(Details), new { id = model.CampaignId });
                }

                if (!campaign.IsPublic)
                {
                    return Forbid();
                }

                await _characterService.AddCharacterToCampaignAsync(model.CampaignId, model.CharacterId);
                return RedirectToAction(nameof(Details), new { id = model.CampaignId });
            }
            
            return View(model);
        }

        // GET: Campaign/Play/5
        [HttpGet]
        public async Task<IActionResult> Play(int id, int? characterId = null)
        {
            var userId = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new UnauthorizedAccessException("User ID not found");
            var campaign = await _campaignService.GetCampaignByIdAsync(id);
            
            if (campaign == null)
            {
                return NotFound();
            }

            if (!await _campaignService.IsUserInCampaignAsync(id, userId))
            {
                return Forbid();
            }

            var userCharacters = await _campaignService.GetUserCharactersInCampaignAsync(id, userId);
            
            if (!userCharacters.Any())
            {
                return RedirectToAction("CreateCharacter", "Character", new { campaignId = id });
            }

            // Check if character portraits are generated
            var charactersWithMissingPortraits = userCharacters.Where(uc => 
                uc.Character != null && string.IsNullOrEmpty(uc.Character.PortraitUrl)).ToList();
            
            if (charactersWithMissingPortraits.Any())
            {
                // Redirect to a waiting page or show a message
                TempData["Warning"] = "Character portraits are still being generated. Please wait a moment and refresh the page.";
                return RedirectToAction("Details", new { id });
            }

            // Get or create current session
            var session = await _gameSessionService.GetOrCreateCurrentSessionAsync(id);
            
            // Get messages for the current session
            var messages = await _gameSessionService.GetSessionMessagesAsync(session.Id);

            // If no messages exist, initialize the campaign with Game Master
            if (!messages.Any())
            {
                try
                {
                    _logger.LogInformation($"Attempting to initialize campaign {id} session {session.Id} for user {userId}");
                    
                    var selectedCharacter = userCharacters.FirstOrDefault(uc => uc.CharacterId == characterId) 
                                          ?? userCharacters.First();
                    
                    var character = await _characterService.GetCharacterByIdAsync(selectedCharacter.CharacterId);
                    
                    if (character != null)
                    {
                        // ✅ NOUVELLE LOGIQUE : Le GM est SOUVERAIN sur les locations
                        // webapp ne devrait JAMAIS écraser les décisions du GM
                        _logger.LogInformation($"🎮 Game Master will handle location assignment for character {character.Name}");

                        // Start the campaign with the Game Master
                        var response = await _llmService.StartCampaignAsync(
                            id, 
                            session.Id, 
                            character.Id, 
                            character.Name
                        );

                        if (response.Success)
                        {
                            // Create the initialization message atomically
                            var gmMessage = new CampaignMessage
                            {
                                CampaignId = id,
                                SessionId = session.Id,
                                Content = response.Message,
                                MessageType = "gm",
                                CreatedAt = DateTime.UtcNow
                            };

                            // Use atomic method to prevent race conditions
                            var messageCreated = await _gameSessionService.TryCreateInitializationMessageAsync(session.Id, gmMessage);
                            
                            if (messageCreated)
                            {
                                _logger.LogInformation($"Successfully initialized campaign {id} session {session.Id}");
                            }
                            else
                            {
                                _logger.LogInformation($"Campaign {id} session {session.Id} was already initialized by another request");
                            }
                            
                            // Refresh messages to include the new introduction (if any)
                            messages = await _gameSessionService.GetSessionMessagesAsync(session.Id);
                        }
                        else
                        {
                            _logger.LogWarning($"Failed to initialize campaign {id} session {session.Id}: {response.Message}");
                        }
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error initializing campaign with Game Master");
                    // Continue without the introduction - the user can still play
                    // Refresh messages in case another request completed the initialization
                    messages = await _gameSessionService.GetSessionMessagesAsync(session.Id);
                }
            }

            var viewModel = new CampaignPlayViewModel
            {
                Campaign = campaign,
                Session = session,
                Messages = messages,
                UserCharacters = userCharacters,
                SelectedCharacterId = characterId ?? userCharacters.First().CharacterId
            };

            return View(viewModel);
        }

        // POST: Campaign/SendMessage
        [HttpPost]
        [ValidateAntiForgeryToken]
        public async Task<IActionResult> SendMessage([FromBody] SendMessageViewModel model)
        {
            try
            {
                var userId = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new UnauthorizedAccessException("User ID not found");
                
                if (!await _campaignService.IsUserInCampaignAsync(model.CampaignId, userId))
                {
                    return Forbid();
                }

                var session = await _gameSessionService.GetOrCreateCurrentSessionAsync(model.CampaignId);
                var character = await _characterService.GetCharacterByIdAsync(model.CharacterId);

                if (character == null || character.UserId != userId)
                {
                    return BadRequest("Invalid character selection");
                }

                // Add player message to the session
                var playerMessage = new CampaignMessage
                {
                    CampaignId = model.CampaignId,
                    SessionId = session.Id,
                    CharacterId = model.CharacterId,
                    Content = model.Content,
                    MessageType = "player",
                    CreatedAt = DateTime.UtcNow
                };

                await _gameSessionService.AddMessageAsync(playerMessage);

                // Get response from Game Master
                var response = await _llmService.SendMessageAsync(
                    model.CampaignId,
                    session.Id,
                    model.CharacterId,
                    model.Content
                );

                if (response.Success)
                {
                    // Add Game Master response to the session
                    var gmMessage = new CampaignMessage
                    {
                        CampaignId = model.CampaignId,
                        SessionId = session.Id,
                        Content = response.Message,
                        MessageType = "gm",
                        CreatedAt = DateTime.UtcNow
                    };

                    await _gameSessionService.AddMessageAsync(gmMessage);

                    return Json(new
                    {
                        success = true,
                        gmMessage = new
                        {
                            id = gmMessage.Id,
                            content = gmMessage.Content,
                            timestamp = gmMessage.CreatedAt.ToString("g")
                        },
                        imageUrl = response.GeneratedImageUrl
                    });
                }

                return Json(new { success = false, message = response.Message });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error sending message");
                return Json(new { success = false, message = "An error occurred while processing your message." });
            }
        }

        [HttpPost]
        public async Task<IActionResult> EndSession(int id)
        {
            try
            {
                var userId = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new UnauthorizedAccessException("User ID not found");
                var campaign = await _campaignService.GetCampaignByIdAsync(id);
                
                if (campaign == null)
                {
                    return NotFound();
                }

                if (!await _campaignService.IsUserCampaignOwnerAsync(id, userId))
                {
                    return Forbid();
                }

                var session = await _gameSessionService.GetOrCreateCurrentSessionAsync(id);
                
                // Get session summary from Game Master
                var response = await _llmService.EndSessionAsync(id, session.Id);
                
                if (response.Success)
                {
                    // End the session with the summary
                    await _gameSessionService.EndSessionAsync(session.Id, response.Message);
                    return RedirectToAction("Details", new { id });
                }

                return BadRequest(response.Message);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error ending session");
                return BadRequest("An error occurred while ending the session.");
            }
        }

        // GET: Campaign/GetElements/5
        [HttpGet]
        public async Task<IActionResult> GetElements(int id)
        {
            try
            {
                var userId = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new UnauthorizedAccessException("User ID not found");
                
                if (!await _campaignService.IsUserInCampaignAsync(id, userId))
                {
                    return Forbid();
                }

                var elements = await _llmService.GetCampaignElementsAsync(id);
                
                if (elements.Success)
                {
                    return Json(new
                    {
                        success = true,
                        npcs = elements.NPCs,
                        locations = elements.Locations,
                        quests = elements.Quests
                    });
                }
                else
                {
                    return Json(new { success = false, message = "Unable to retrieve campaign elements" });
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting campaign elements");
                return Json(new { success = false, message = "An error occurred while retrieving campaign elements" });
            }
        }

        // GET: Campaign/GetImageStatus/5
        [HttpGet]
        public async Task<IActionResult> GetImageStatus(int id)
        {
            try
            {
                var userId = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new UnauthorizedAccessException("User ID not found");
                
                if (!await _campaignService.IsUserInCampaignAsync(id, userId))
                {
                    return Forbid();
                }

                var status = await _llmService.GetImageStatusAsync(id);
                
                if (status.Success)
                {
                    return Json(new
                    {
                        success = true,
                        campaign_id = id,
                        status = status.Status
                    });
                }
                else
                {
                    return Json(new { success = false, message = "Unable to retrieve image status" });
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting image status");
                return Json(new { success = false, message = "An error occurred while retrieving image status" });
            }
        }

        // POST: Campaign/GenerateMissingImages/5
        [HttpPost]
        public async Task<IActionResult> GenerateMissingImages(int id)
        {
            try
            {
                var userId = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new UnauthorizedAccessException("User ID not found");
                
                if (!await _campaignService.IsUserInCampaignAsync(id, userId))
                {
                    return Forbid();
                }

                var result = await _llmService.GenerateMissingImagesAsync(id);
                
                if (result.Success)
                {
                    return Json(new
                    {
                        success = true,
                        campaign_id = id,
                        message = result.Message,
                        status = result.Status
                    });
                }
                else
                {
                    return Json(new { success = false, message = "Unable to start image generation" });
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error starting image generation");
                return Json(new { success = false, message = "An error occurred while starting image generation" });
            }
        }

        // POST: Campaign/GenerateElementImage/5
        [HttpPost]
        public async Task<IActionResult> GenerateElementImage(int id, [FromBody] GenerateElementImageRequest request)
        {
            try
            {
                var userId = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new UnauthorizedAccessException("User ID not found");
                
                if (!await _campaignService.IsUserInCampaignAsync(id, userId))
                {
                    return Forbid();
                }

                if (string.IsNullOrEmpty(request.ElementType) || request.ElementId <= 0)
                {
                    return BadRequest("Element type and element ID are required");
                }

                var result = await _llmService.GenerateElementImageAsync(id, request.ElementType, request.ElementId);
                
                if (result.Success)
                {
                    return Json(new
                    {
                        success = true,
                        campaign_id = id,
                        element_type = request.ElementType,
                        element_id = request.ElementId,
                        image_url = result.ImageUrl,
                        message = result.Message
                    });
                }
                else
                {
                    return Json(new { success = false, message = "Unable to generate element image" });
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error generating element image");
                return Json(new { success = false, message = "An error occurred while generating element image" });
            }
        }
        
        // POST: Campaign/GenerateContent/5
        [HttpPost]
        public async Task<IActionResult> GenerateContent(int id)
        {
            try
            {
                var userId = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new UnauthorizedAccessException("User ID not found");
                
                if (!await _campaignService.IsUserCampaignOwnerAsync(id, userId))
                {
                    return Forbid();
                }

                var result = await _llmService.GenerateCampaignContentAsync(id);
                
                if (result.Success)
                {
                    await _campaignService.UpdateContentGenerationStatusAsync(id, "InProgress");
                    
                    return Json(new
                    {
                        success = true,
                        campaign_id = id,
                        message = result.Message,
                        status = result.Status
                    });
                }
                else
                {
                    return Json(new { success = false, message = "Unable to start content generation" });
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error starting content generation");
                return Json(new { success = false, message = "An error occurred while starting content generation" });
            }
        }
        
        // GET: Campaign/GetContentStatus/5
        [HttpGet]
        public async Task<IActionResult> GetContentStatus(int id)
        {
            try
            {
                var userId = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new UnauthorizedAccessException("User ID not found");
                
                if (!await _campaignService.IsUserInCampaignAsync(id, userId))
                {
                    return Forbid();
                }

                // Get both content generation status from LLM service and campaign info from database
                var result = await _llmService.GetContentGenerationStatusAsync(id);
                var campaign = await _campaignService.GetCampaignByIdAsync(id);
                
                if (result.Success && campaign != null)
                {
                    return Json(new
                    {
                        success = true,
                        campaign_id = id,
                        status = result.Status,
                        characterStatus = campaign.CharacterGenerationStatus ?? "NotStarted",
                        error = result.Error,
                        started_at = result.StartedAt,
                        completed_at = result.CompletedAt
                    });
                }
                else
                {
                    return Json(new { success = false, message = "Unable to get content generation status" });
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting content generation status");
                return Json(new { success = false, message = "An error occurred while getting content generation status" });
            }
        }

        // GET: Campaign/DiagnosticLLMConnection
        [HttpGet]
        public async Task<IActionResult> DiagnosticLLMConnection()
        {
            try
            {
                var diagnosticResults = new List<object>();
                
                // Test 1: Basic connectivity
                try
                {
                    var llmUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                    var baseUri = new Uri(llmUrl);
                    var healthUri = new Uri(baseUri, "health");
                    
                    using var httpClient = new HttpClient();
                    httpClient.Timeout = TimeSpan.FromSeconds(10);
                    
                    var response = await httpClient.GetAsync(healthUri);
                    diagnosticResults.Add(new { 
                        Test = "Basic Connectivity", 
                        Status = response.IsSuccessStatusCode ? "✅ Success" : "❌ Failed",
                        Details = $"Status: {response.StatusCode}, Response time: {DateTime.Now:HH:mm:ss}"
                    });
                }
                catch (Exception ex)
                {
                    diagnosticResults.Add(new { 
                        Test = "Basic Connectivity", 
                        Status = "❌ Failed",
                        Details = $"Error: {ex.Message}"
                    });
                }
                
                // Test 2: Content generation status
                try
                {
                    var testCampaignId = 1; // Use first available campaign
                    var statusResponse = await _llmService.GetContentGenerationStatusAsync(testCampaignId);
                    diagnosticResults.Add(new { 
                        Test = "Content Generation API", 
                        Status = statusResponse != null ? "✅ Success" : "⚠️ No Response",
                        Details = statusResponse?.Status ?? "No status returned"
                    });
                }
                catch (Exception ex)
                {
                    diagnosticResults.Add(new { 
                        Test = "Content Generation API", 
                        Status = "❌ Failed",
                        Details = $"Error: {ex.Message}"
                    });
                }
                
                return Json(new { diagnostics = diagnosticResults, timestamp = DateTime.Now });
            }
            catch (Exception ex)
            {
                return Json(new { error = ex.Message, timestamp = DateTime.Now });
            }
        }
        
        // POST: Campaign/InitializeGameState
        [HttpPost]
        public async Task<IActionResult> InitializeGameState(int campaignId)
        {
            try
            {
                // Check if user has access to this campaign
                var userId = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new UnauthorizedAccessException("User ID not found");
                if (userId == null)
                {
                    return Json(new { success = false, error = "User not authenticated" });
                }
                
                var isOwner = await _campaignService.IsUserCampaignOwnerAsync(campaignId, userId);
                var isInCampaign = await _campaignService.IsUserInCampaignAsync(campaignId, userId);
                
                if (!isOwner && !isInCampaign)
                {
                    return Json(new { success = false, error = "Access denied" });
                }
                
                // Initialize game state
                await _campaignService.InitializeCampaignGameStateAsync(campaignId);
                
                return Json(new { 
                    success = true, 
                    message = "Game state initialized successfully",
                    timestamp = DateTime.Now
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error initializing game state for campaign {campaignId}");
                return Json(new { 
                    success = false, 
                    error = "Failed to initialize game state",
                    details = ex.Message
                });
            }
        }
        
        // GET: Campaign/GetCurrentLocationData
        [HttpGet]
        public async Task<IActionResult> GetCurrentLocationData(int campaignId, int characterId)
        {
            try
            {
                // Check if user has access to this character
                var userId = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new UnauthorizedAccessException("User ID not found");
                if (userId == null)
                {
                    return Json(new { success = false, error = "User not authenticated" });
                }
                
                var isInCampaign = await _campaignService.IsUserInCampaignAsync(campaignId, userId);
                if (!isInCampaign)
                {
                    return Json(new { success = false, error = "Access denied" });
                }
                
                // Force refresh of character location to get latest GM updates
                await _campaignService.RefreshCharacterLocationFromDatabaseAsync(campaignId, characterId);
                
                // Get current location data
                var locationData = await _campaignService.GetCurrentLocationDataAsync(campaignId, characterId);
                
                return Json(new { 
                    success = true, 
                    locationData = locationData,
                    timestamp = DateTime.Now
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error getting location data for character {characterId} in campaign {campaignId}");
                return Json(new { 
                    success = false, 
                    error = "Failed to get location data",
                    details = ex.Message
                });
            }
        }
        
        // GET: Campaign/GetDiscoveredQuests
        [HttpGet]
        public async Task<IActionResult> GetDiscoveredQuests(int campaignId, string? questGiver = null)
        {
            try
            {
                // Check if user has access to this campaign
                var userId = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new UnauthorizedAccessException("User ID not found");
                if (userId == null)
                {
                    return Json(new { success = false, error = "User not authenticated" });
                }
                
                var isInCampaign = await _campaignService.IsUserInCampaignAsync(campaignId, userId);
                if (!isInCampaign)
                {
                    return Json(new { success = false, error = "Access denied" });
                }
                
                // Get discovered quests
                var discoveredQuests = await _campaignService.GetDiscoveredQuestsAsync(campaignId, questGiver);
                
                return Json(new { 
                    success = true, 
                    quests = discoveredQuests,
                    timestamp = DateTime.Now
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error getting discovered quests for campaign {campaignId}");
                return Json(new { 
                    success = false, 
                    error = "Failed to get discovered quests",
                    details = ex.Message
                });
            }
        }
        
        // POST: Campaign/InteractWithNPC
        [HttpPost]
        public async Task<IActionResult> InteractWithNPC(int campaignId, int characterId, string npcName)
        {
            try
            {
                // Check if user has access to this character
                var userId = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new UnauthorizedAccessException("User ID not found");
                if (userId == null)
                {
                    return Json(new { success = false, error = "User not authenticated" });
                }
                
                var isInCampaign = await _campaignService.IsUserInCampaignAsync(campaignId, userId);
                if (!isInCampaign)
                {
                    return Json(new { success = false, error = "Access denied" });
                }
                
                // Verify the character belongs to the user
                var userCharacters = await _campaignService.GetUserCharactersInCampaignAsync(campaignId, userId);
                var userCharacter = userCharacters.FirstOrDefault(uc => uc.CharacterId == characterId);
                
                if (userCharacter == null)
                {
                    return Json(new { success = false, error = "Character not found or access denied" });
                }
                
                // Handle NPC interaction and quest discovery
                var questsDiscovered = await _campaignService.HandleNPCInteractionAsync(campaignId, characterId, npcName);
                
                // Get updated discovered quests to return
                var discoveredQuests = await _campaignService.GetDiscoveredQuestsAsync(campaignId, npcName);
                
                return Json(new { 
                    success = true, 
                    npcName = npcName,
                    questsDiscovered = questsDiscovered,
                    discoveredQuests = discoveredQuests,
                    message = questsDiscovered ? $"Discovered new quests from {npcName}!" : $"Interacted with {npcName}",
                    timestamp = DateTime.Now
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error handling NPC interaction for character {characterId} with {npcName} in campaign {campaignId}");
                return Json(new { 
                    success = false, 
                    error = "Failed to handle NPC interaction",
                    details = ex.Message
                });
            }
        }
    }

    public class CampaignEditViewModel
    {
        public int Id { get; set; }
        
        [Required]
        [StringLength(100)]
        public string Name { get; set; } = string.Empty;
        
        [StringLength(1000)]
        public string? Description { get; set; } = string.Empty;
        
        [StringLength(500)]
        public string? Settings { get; set; } = string.Empty;
        
        [Required]
        [StringLength(50)]
        public string Language { get; set; } = "English";
        
        [Range(1, 20)]
        public int StartingLevel { get; set; } = 1;
        
        [Range(1, 10)]
        public int MaxPlayers { get; set; } = 5;
        
        public bool IsPublic { get; set; } = false;
        
        [StringLength(20)]
        public string Status { get; set; } = "Active"; // Active, Completed, Paused
    }

    public class CampaignJoinViewModel
    {
        public int CampaignId { get; set; }
        
        public string CampaignName { get; set; } = string.Empty;
        
        [Required]
        [Display(Name = "Select Character")]
        public int CharacterId { get; set; }
        
        public List<SelectListItem> AvailableCharacters { get; set; } = new List<SelectListItem>();
    }

    public class CampaignPlayViewModel
    {
        public Campaign Campaign { get; set; } = null!;
        public CampaignSession Session { get; set; } = null!;
        public List<CampaignMessage> Messages { get; set; } = new();
        public List<CampaignCharacter> UserCharacters { get; set; } = new();
        public int SelectedCharacterId { get; set; }
    }

    public class GenerateElementImageRequest
    {
        public string ElementType { get; set; } = string.Empty;
        public int ElementId { get; set; }
    }
} 