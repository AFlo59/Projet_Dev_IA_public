using DnDGameMaster.WebApp.Models;
using DnDGameMaster.WebApp.Services;
using DnDGameMaster.WebApp.Services.Game;
using DnDGameMaster.WebApp.Services.LLM;
using DnDGameMaster.WebApp.Services.Reference;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using System.ComponentModel.DataAnnotations;
using System.Text.Json;
using System.Threading.Tasks;
using System.Net.Http.Json;

namespace DnDGameMaster.WebApp.Controllers
{
    [Authorize]
    public class CharacterController : Controller
    {
        private readonly ICharacterService _characterService;
        private readonly ICampaignService _campaignService;
        private readonly UserManager<ApplicationUser> _userManager;
        private readonly IDataReferenceService _dataService;
        private readonly ILogger<CharacterController> _logger;
        private readonly ILLMService _llmService;
        private readonly IConfiguration _configuration;
        private readonly IHttpClientFactory _httpClientFactory;

        public CharacterController(
            ICharacterService characterService,
            ICampaignService campaignService,
            UserManager<ApplicationUser> userManager,
            IDataReferenceService dataService,
            ILogger<CharacterController> logger,
            ILLMService llmService,
            IConfiguration configuration,
            IHttpClientFactory httpClientFactory)
        {
            _characterService = characterService;
            _campaignService = campaignService;
            _userManager = userManager;
            _dataService = dataService;
            _logger = logger;
            _llmService = llmService;
            _configuration = configuration;
            _httpClientFactory = httpClientFactory;
        }

        // GET: Character
        public async Task<IActionResult> Index()
        {
            var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
            var characters = await _characterService.GetCharactersForUserAsync(userId);
            return View(characters);
        }

        // GET: Character/Details/5
        public async Task<IActionResult> Details(int id)
        {
            var character = await _characterService.GetCharacterByIdAsync(id);
            if (character == null)
            {
                return NotFound();
            }

            var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
            if (character.UserId != userId && !User.IsInRole("Admin"))
            {
                return Forbid();
            }

            var campaigns = await _characterService.GetCharacterCampaignsAsync(id);
            
            var model = new CharacterDetailsViewModel
            {
                Character = character,
                Campaigns = campaigns
            };

            return View(model);
        }

        // GET: Character/Create
        public async Task<IActionResult> Create(int campaignId)
        {
            // Validate that the campaign exists
            var campaign = await _campaignService.GetCampaignByIdAsync(campaignId);
            if (campaign == null)
            {
                return RedirectToAction("Index", "Campaign");
            }

            // Validate that the user has access to this campaign
            var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
            var isOwner = await _campaignService.IsUserCampaignOwnerAsync(campaignId, userId);
            var userInCampaign = await _campaignService.IsUserInCampaignAsync(campaignId, userId);
            
            if (!isOwner && !userInCampaign && !campaign.IsPublic)
            {
                return Forbid();
            }
            
            var model = new CharacterCreateViewModel
            {
                CampaignId = campaignId,
                CampaignName = campaign.Name,
                Level = campaign.StartingLevel // Set default level to campaign's starting level
            };
            
            // Use default D&D 5e options instead of external data service
            model.AvailableRaces = new List<string> 
            { 
                "Human", "Elf", "Dwarf", "Halfling", "Dragonborn", "Gnome", "Half-Elf", "Half-Orc", "Tiefling"
            };
            
            model.AvailableClasses = new List<string> 
            { 
                "Barbarian", "Bard", "Cleric", "Druid", "Fighter", "Monk", "Paladin", "Ranger", "Rogue", "Sorcerer", "Warlock", "Wizard"
            };
            
            model.AvailableBackgrounds = new List<string> 
            { 
                "Acolyte", "Criminal", "Folk Hero", "Noble", "Sage", "Soldier", "Charlatan", "Entertainer", "Guild Artisan", "Hermit", "Outlander", "Sailor"
            };
            
            return View(model);
        }

        // POST: Character/Create
        [HttpPost]
        [ValidateAntiForgeryToken]
        public async Task<IActionResult> Create(CharacterCreateViewModel model)
        {
            // Validate that the campaign exists
            var campaign = await _campaignService.GetCampaignByIdAsync(model.CampaignId);
            if (campaign == null)
            {
                return RedirectToAction("Index", "Campaign");
            }

            // Validate that the user has access to this campaign
            var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
            var isOwner = await _campaignService.IsUserCampaignOwnerAsync(model.CampaignId, userId);
            var isInCampaign = await _campaignService.IsUserInCampaignAsync(model.CampaignId, userId);
            
            if (!isOwner && !isInCampaign)
            {
                return Forbid();
            }
            
            // Check if user already has a character in this campaign
            var existingCharacters = await _campaignService.GetUserCharactersInCampaignAsync(model.CampaignId, userId);
            if (existingCharacters.Any())
            {
                TempData["Error"] = "You already have a character in this campaign.";
                return RedirectToAction("Details", "Campaign", new { id = model.CampaignId });
            }

            // Validate MaxPlayers limit (count unique users, not characters)
            var uniquePlayers = await _campaignService.GetUniquePlayersInCampaignAsync(model.CampaignId);
            if (uniquePlayers.Count >= campaign.MaxPlayers && !isOwner)
            {
                TempData["Error"] = $"This campaign is full (maximum {campaign.MaxPlayers} players).";
                return RedirectToAction("Details", "Campaign", new { id = model.CampaignId });
            }

            // Validate point allocation for point buy system
            if (!model.UseRandomStats)
            {
                var pointsUsed = CalculatePointsUsed(model);
                if (pointsUsed > 27)
                {
                    ModelState.AddModelError("", "You have exceeded the 27 point allocation limit.");
                }
            }
            
            // Generate random stats if requested
            if (model.UseRandomStats)
            {
                GenerateRandomStats(model);
            }
            
            if (ModelState.IsValid)
            {
            try
            {
                // Create character immediately with placeholder description
                var character = new Character
                {
                    Name = model.Name,
                    Race = model.Race,
                    Gender = model.Gender,
                    Class = model.Class,
                    Level = model.Level,
                    Background = model.Background,
                    Alignment = model.Alignment,
                    Strength = model.Strength,
                    Dexterity = model.Dexterity,
                    Constitution = model.Constitution,
                    Intelligence = model.Intelligence,
                    Wisdom = model.Wisdom,
                    Charisma = model.Charisma,
                    Equipment = model.Equipment,
                    UserId = userId,
                    Description = "Description and portrait are being generated...", // Placeholder
                    PortraitUrl = "", // Will be updated later
                    CreatedAt = DateTime.UtcNow,
                    UpdatedAt = DateTime.UtcNow
                };

                // Save character to database immediately
                var createdCharacter = await _characterService.CreateCharacterAsync(character);
                
                // Add character to campaign
                await _campaignService.AddCharacterToCampaignAsync(model.CampaignId, createdCharacter.Id);
                
                // Update campaign character generation status to InProgress
                await _campaignService.UpdateCharacterGenerationStatusAsync(model.CampaignId, "InProgress");
                
                // Trigger background generation of description and portrait
                _ = Task.Run(async () =>
                {
                    try
                    {
                        // Use the configured LLM service base URL
                        var baseUrl = _configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
                        using var httpClient = _httpClientFactory.CreateClient();
                        httpClient.BaseAddress = new Uri(baseUrl);
                        httpClient.Timeout = TimeSpan.FromMinutes(10); // Longer timeout for character generation
                        
                        var requestData = new
                        {
                            campaign_id = model.CampaignId,
                            character_id = createdCharacter.Id,
                            character_name = createdCharacter.Name,
                            character_race = createdCharacter.Race,
                            character_gender = createdCharacter.Gender,
                            character_class = createdCharacter.Class,
                            character_background = createdCharacter.Background,
                            character_alignment = createdCharacter.Alignment
                        };
                        
                        _logger.LogInformation($"Starting character generation for character {createdCharacter.Id} in campaign {model.CampaignId}");
                        
                        var response = await httpClient.PostAsJsonAsync("api/gamemaster/generate_character_content", requestData);
                        
                        if (response.IsSuccessStatusCode)
                        {
                            _logger.LogInformation($"Successfully triggered character generation for character {createdCharacter.Id}");
                            // Status will be updated to "Completed" by the LLM service when finished
                        }
                        else
                        {
                            _logger.LogError($"Character generation request failed with status: {response.StatusCode}");
                            // Update status to failed
                            await _campaignService.UpdateCharacterGenerationStatusAsync(model.CampaignId, "Failed", "Character generation request failed");
                        }
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, $"Error triggering character generation for character {createdCharacter.Id}");
                        // Update status to failed
                        await _campaignService.UpdateCharacterGenerationStatusAsync(model.CampaignId, "Failed", ex.Message);
                    }
                });

                // Set success message
                TempData["Success"] = $"Character '{character.Name}' created successfully! Description and portrait are being generated in the background.";
                
                return RedirectToAction("Details", "Campaign", new { id = model.CampaignId });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error creating character");
                
                if (ex.Message.Contains("duplicate") || ex.Message.Contains("unique"))
                {
                    TempData["Error"] = "You already have a character in this campaign.";
                }
                else
                {
                    TempData["Error"] = "An error occurred while creating the character. Please try again.";
                }
            }
            }
            
            // Repopulate dropdown lists before returning view on error
            PopulateDropdownLists(model);
            return View(model);
        }

        // Helper method to populate dropdown lists
        private void PopulateDropdownLists(CharacterCreateViewModel model)
        {
            model.AvailableRaces = new List<string> 
            { 
                "Human", "Elf", "Dwarf", "Halfling", "Dragonborn", "Gnome", "Half-Elf", "Half-Orc", "Tiefling"
            };
            
            model.AvailableClasses = new List<string> 
            { 
                "Barbarian", "Bard", "Cleric", "Druid", "Fighter", "Monk", "Paladin", "Ranger", "Rogue", "Sorcerer", "Warlock", "Wizard"
            };
            
            model.AvailableBackgrounds = new List<string> 
            { 
                "Acolyte", "Criminal", "Folk Hero", "Noble", "Sage", "Soldier", "Charlatan", "Entertainer", "Guild Artisan", "Hermit", "Outlander", "Sailor"
            };
        }

        // Helper method to populate dropdown lists for Edit
        private void PopulateDropdownLists(CharacterEditViewModel model)
        {
            model.AvailableRaces = new List<string> 
            { 
                "Human", "Elf", "Dwarf", "Halfling", "Dragonborn", "Gnome", "Half-Elf", "Half-Orc", "Tiefling"
            };
            
            model.AvailableClasses = new List<string> 
            { 
                "Barbarian", "Bard", "Cleric", "Druid", "Fighter", "Monk", "Paladin", "Ranger", "Rogue", "Sorcerer", "Warlock", "Wizard"
            };
            
            model.AvailableBackgrounds = new List<string> 
            { 
                "Acolyte", "Criminal", "Folk Hero", "Noble", "Sage", "Soldier", "Charlatan", "Entertainer", "Guild Artisan", "Hermit", "Outlander", "Sailor"
            };
        }

        // Calculate points used for ability scores using D&D 5e point buy system
        private int CalculatePointsUsed(CharacterCreateViewModel model)
        {
            int totalPoints = 0;
            
            totalPoints += GetPointCost(model.Strength);
            totalPoints += GetPointCost(model.Dexterity);
            totalPoints += GetPointCost(model.Constitution);
            totalPoints += GetPointCost(model.Intelligence);
            totalPoints += GetPointCost(model.Wisdom);
            totalPoints += GetPointCost(model.Charisma);
            
            return totalPoints;
        }
        
        // Get point cost for an ability score based on D&D 5e point buy system
        private int GetPointCost(int score)
        {
            // Each score starts at 8 (which costs 0 points)
            if (score <= 8) return 0;
            
            // Costs for scores 9-15 are 1, 2, 3, 4, 5, 7, 9 points respectively
            int[] costs = { 0, 1, 2, 3, 4, 5, 7, 9 };
            
            if (score <= 15)
                return costs[score - 8];
            
            // If somehow score is higher than 15 (shouldn't happen in point buy)
            return 9 + ((score - 15) * 2);
        }
        
        // Generate random stats using 4d6 drop lowest method
        private void GenerateRandomStats(CharacterCreateViewModel model)
        {
            Random rnd = new Random();
            
            model.Strength = RollStat(rnd);
            model.Dexterity = RollStat(rnd);
            model.Constitution = RollStat(rnd);
            model.Intelligence = RollStat(rnd);
            model.Wisdom = RollStat(rnd);
            model.Charisma = RollStat(rnd);
        }
        
        // Roll 4d6, drop lowest, sum the rest
        private int RollStat(Random rnd)
        {
            int[] rolls = new int[4];
            for (int i = 0; i < 4; i++)
            {
                rolls[i] = rnd.Next(1, 7);
            }
            
            // Drop the lowest roll
            Array.Sort(rolls);
            
            // Sum the three highest rolls
            return rolls[1] + rolls[2] + rolls[3];
        }
        
        // Generate character description using LLM service
        private async Task<string> GenerateCharacterDescriptionAsync(CharacterCreateViewModel model, Dictionary<string, int> stats)
        {
            try
            {
                // Try to use LLM service if available
                string statString = string.Join(", ", stats.Select(s => $"{s.Key}: {s.Value}"));
                string gender = !string.IsNullOrEmpty(model.Gender) ? model.Gender : "Male";
                
                string prompt = $"Generate a detailed D&D 5e character description for the following character:\n" +
                                $"Name: {model.Name}\n" +
                                $"Race: {model.Race}\n" +
                                $"Class: {model.Class}\n" +
                                $"Gender: {gender}\n" +
                                $"Background: {model.Background ?? "Unknown"}\n" +
                                $"Alignment: {model.Alignment ?? "Unknown"}\n" +
                                $"Ability Scores: {statString}\n\n" +
                                "Include the following details:\n" +
                                "1. Physical appearance (height, build, distinctive features, eye color, hair color/style)\n" +
                                "2. Personality traits (virtues, flaws, motivations)\n" +
                                "3. Background story (upbringing, defining events, how they became their class)\n" +
                                "4. A unique quirk or habit\n" +
                                "5. One or two personal goals\n" +
                                "6. How they typically behave in combat\n\n" +
                                "Keep it under 500 words, focus on making them unique and interesting. Use proper D&D terminology.";
                
                // Use the LLM service to generate a description
                _logger.LogInformation($"Generating character description with prompt: {prompt}");
                var description = await _llmService.GetGeneratedTextAsync(prompt);
                return !string.IsNullOrEmpty(description) ? description : GenerateDefaultDescription(model);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error generating character description");
                return GenerateDefaultDescription(model);
            }
        }
        
        // Generate a default description if LLM service fails
        private string GenerateDefaultDescription(CharacterCreateViewModel model)
        {
            return $"{model.Name} is a {model.Race} {model.Class} with a {model.Background ?? "mysterious"} background. " +
                   $"As a {model.Alignment ?? "neutral"} character, they embark on adventures seeking glory and fortune. " +
                   $"Their journey has just begun, and many tales are yet to be written.";
        }
        
        // Generate character portrait URL
        private async Task<string> GenerateCharacterPortraitUrlAsync(CharacterCreateViewModel model, Dictionary<string, int> stats)
        {
            try
            {
                // Ensure gender is set
                string gender = !string.IsNullOrEmpty(model.Gender) ? model.Gender : "Male";
                
                // Extract key physical traits from description if available
                string physicalTraits = "";
                if (!string.IsNullOrEmpty(model.Description))
                {
                    // Try to extract physical traits from the description
                    string[] lines = model.Description.Split('\n');
                    foreach (var line in lines.Take(10)) // Look at first 10 lines
                    {
                        if (line.Contains("appearance") || line.Contains("looks") || 
                            line.Contains("hair") || line.Contains("eyes") || 
                            line.Contains("face") || line.Contains("skin"))
                        {
                            physicalTraits = line;
                            break;
                        }
                    }
                }
                
                // Generate portrait using LLM service (will use OpenAI)
                string prompt = $"Fantasy portrait of a {model.Race} {model.Class}, " +
                               $"{(gender == "Female" ? "female" : "male")}, " +
                               $"with {model.Background} background. " +
                               $"Character named {model.Name}. ";
                
                // Add physical traits if available
                if (!string.IsNullOrEmpty(physicalTraits))
                {
                    prompt += $"Physical traits: {physicalTraits}. ";
                }
                
                // Add alignment and other details
                prompt += $"{model.Alignment} alignment. ";
                
                // Add stat-based details
                if (stats["STR"] > 15) prompt += "Muscular build. ";
                if (stats["DEX"] > 15) prompt += "Nimble and agile looking. ";
                if (stats["CON"] > 15) prompt += "Robust and healthy looking. ";
                if (stats["INT"] > 15) prompt += "Intelligent gaze. ";
                if (stats["WIS"] > 15) prompt += "Wise and perceptive expression. ";
                if (stats["CHA"] > 15) prompt += "Very charismatic and attractive. ";
                
                prompt += "D&D style, fantasy artwork, detailed, high quality.";
                
                _logger.LogInformation($"Generating portrait with prompt: {prompt}");
                
                // Use the LLM service to generate an image (always uses OpenAI even if Anthropic is selected for text)
                var portraitUrl = await _llmService.GetGeneratedImageUrlAsync(prompt);
                
                if (!string.IsNullOrEmpty(portraitUrl))
                {
                    return portraitUrl;
                }
                
                return "https://www.dndbeyond.com/avatars/default-avatar.png";
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error generating character portrait URL: {Message}", ex.Message);
                return "https://www.dndbeyond.com/avatars/default-avatar.png";
            }
        }
        
        // Helper method to guess gender from name (very simplified)
        private string DetermineGender(string name)
        {
            // This is a very simplified approach
            return name.EndsWith("a") || name.EndsWith("e") ? "female" : "male";
        }

        // GET: Character/Edit/5
        public async Task<IActionResult> Edit(int id)
        {
            var character = await _characterService.GetCharacterByIdAsync(id);
            if (character == null)
            {
                return NotFound();
            }

            var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
            if (character.UserId != userId && !User.IsInRole("Admin"))
            {
                return Forbid();
            }

            var stats = character.Stats;
            
            var model = new CharacterEditViewModel
            {
                Id = character.Id,
                Name = character.Name,
                Race = character.Race,
                Class = character.Class,
                Level = character.Level,
                Background = character.Background,
                Alignment = character.Alignment,
                Strength = stats.GetValueOrDefault("STR", 10),
                Dexterity = stats.GetValueOrDefault("DEX", 10),
                Constitution = stats.GetValueOrDefault("CON", 10),
                Intelligence = stats.GetValueOrDefault("INT", 10),
                Wisdom = stats.GetValueOrDefault("WIS", 10),
                Charisma = stats.GetValueOrDefault("CHA", 10),
                Description = character.Description,
                Equipment = character.Equipment
            };
            
            // Use default D&D 5e options instead of external data service
            model.AvailableRaces = new List<string> 
            { 
                "Human", "Elf", "Dwarf", "Halfling", "Dragonborn", "Gnome", "Half-Elf", "Half-Orc", "Tiefling"
            };
            
            model.AvailableClasses = new List<string> 
            { 
                "Barbarian", "Bard", "Cleric", "Druid", "Fighter", "Monk", "Paladin", "Ranger", "Rogue", "Sorcerer", "Warlock", "Wizard"
            };
            
            model.AvailableBackgrounds = new List<string> 
            { 
                "Acolyte", "Criminal", "Folk Hero", "Noble", "Sage", "Soldier", "Charlatan", "Entertainer", "Guild Artisan", "Hermit", "Outlander", "Sailor"
            };

            return View(model);
        }

        // POST: Character/Edit/5
        [HttpPost]
        [ValidateAntiForgeryToken]
        public async Task<IActionResult> Edit(int id, CharacterEditViewModel model)
        {
            if (id != model.Id)
            {
                return NotFound();
            }

            if (ModelState.IsValid)
            {
                var character = await _characterService.GetCharacterByIdAsync(id);
                if (character == null)
                {
                    return NotFound();
                }

                var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
                if (character.UserId != userId && !User.IsInRole("Admin"))
                {
                    return Forbid();
                }

                // Create stats dictionary
                var stats = new Dictionary<string, int>
                {
                    { "STR", model.Strength },
                    { "DEX", model.Dexterity },
                    { "CON", model.Constitution },
                    { "INT", model.Intelligence },
                    { "WIS", model.Wisdom },
                    { "CHA", model.Charisma }
                };
                
                character.Name = model.Name;
                character.Race = model.Race;
                character.Class = model.Class;
                character.Level = model.Level;
                character.Background = model.Background;
                character.Alignment = model.Alignment;
                character.StatsJson = JsonSerializer.Serialize(stats);
                character.Description = model.Description;
                character.Equipment = model.Equipment;
                character.UpdatedAt = DateTime.UtcNow;

                await _characterService.UpdateCharacterAsync(character);
                return RedirectToAction(nameof(Details), new { id = character.Id });
            }
            
            // Repopulate dropdown lists if validation failed
            PopulateDropdownLists(model);
            return View(model);
        }

        // GET: Character/Delete/5
        public async Task<IActionResult> Delete(int id)
        {
            var character = await _characterService.GetCharacterByIdAsync(id);
            if (character == null)
            {
                return NotFound();
            }

            var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
            if (character.UserId != userId && !User.IsInRole("Admin"))
            {
                return Forbid();
            }

            return View(character);
        }

        // POST: Character/Delete/5
        [HttpPost, ActionName("Delete")]
        [ValidateAntiForgeryToken]
        public async Task<IActionResult> DeleteConfirmed(int id)
        {
            var character = await _characterService.GetCharacterByIdAsync(id);
            if (character == null)
            {
                return NotFound();
            }

            var userId = _userManager.GetUserId(User) ?? throw new UnauthorizedAccessException("User not found");
            if (character.UserId != userId && !User.IsInRole("Admin"))
            {
                return Forbid();
            }

            await _characterService.DeleteCharacterAsync(id);
            return RedirectToAction(nameof(Index));
        }
    }

    public class CharacterDetailsViewModel
    {
        public Character Character { get; set; } = null!;
        public List<Campaign> Campaigns { get; set; } = new List<Campaign>();
    }

    public class CharacterCreateViewModel
    {
        [Required]
        [StringLength(100, MinimumLength = 2)]
        public string Name { get; set; } = string.Empty;
        
        [Required]
        [StringLength(50)]
        public string Race { get; set; } = string.Empty;
        
        [Required]
        [StringLength(50)]
        public string Class { get; set; } = string.Empty;
        
        [Range(1, 20)]
        public int Level { get; set; } = 1;
        
        [StringLength(50)]
        public string? Background { get; set; } = string.Empty;
        
        [StringLength(50)]
        public string? Alignment { get; set; } = string.Empty;
        
        [Range(3, 18)]
        public int Strength { get; set; } = 10;
        
        [Range(3, 18)]
        public int Dexterity { get; set; } = 10;
        
        [Range(3, 18)]
        public int Constitution { get; set; } = 10;
        
        [Range(3, 18)]
        public int Intelligence { get; set; } = 10;
        
        [Range(3, 18)]
        public int Wisdom { get; set; } = 10;
        
        [Range(3, 18)]
        public int Charisma { get; set; } = 10;
        
        [StringLength(2000)]
        public string? Description { get; set; } = string.Empty;
        
        [StringLength(2000)]
        public string? Equipment { get; set; } = string.Empty;
        
        [StringLength(1000)]
        public string? PortraitUrl { get; set; } = string.Empty;
        
        public int CampaignId { get; set; }
        public string CampaignName { get; set; } = string.Empty;
        
        public List<string> AvailableRaces { get; set; } = new List<string>();
        public List<string> AvailableClasses { get; set; } = new List<string>();
        public List<string> AvailableBackgrounds { get; set; } = new List<string>();
        
        public bool UseRandomStats { get; set; } = false;
        public int PointsRemaining { get; set; } = 27; // Point buy system with 27 points
        
        // Gender property that can be set directly from form
        [StringLength(20)]
        public string Gender { get; set; } = "Male";
        
        // Method to determine gender from name if not explicitly set
        public string DetermineGenderFromName()
        {
            // Simplified approach based on name endings
            return Name.EndsWith("a") || Name.EndsWith("e") ? "Female" : "Male";
        }
    }

    public class CharacterEditViewModel
    {
        public int Id { get; set; }
        
        [Required]
        [StringLength(50)]
        public string Name { get; set; } = string.Empty;
        
        [Required]
        [StringLength(50)]
        public string Race { get; set; } = string.Empty;
        
        [Required]
        [StringLength(50)]
        public string Class { get; set; } = string.Empty;
        
        [Range(1, 20)]
        public int Level { get; set; } = 1;
        
        [StringLength(50)]
        public string? Background { get; set; } = string.Empty;
        
        [StringLength(50)]
        public string? Alignment { get; set; } = string.Empty;
        
        [Range(3, 20)]
        public int Strength { get; set; } = 10;
        
        [Range(3, 20)]
        public int Dexterity { get; set; } = 10;
        
        [Range(3, 20)]
        public int Constitution { get; set; } = 10;
        
        [Range(3, 20)]
        public int Intelligence { get; set; } = 10;
        
        [Range(3, 20)]
        public int Wisdom { get; set; } = 10;
        
        [Range(3, 20)]
        public int Charisma { get; set; } = 10;
        
        [StringLength(2000)]
        public string? Description { get; set; } = string.Empty;
        
        [StringLength(2000)]
        public string? Equipment { get; set; } = string.Empty;
        
        public List<string> AvailableRaces { get; set; } = new List<string>();
        public List<string> AvailableClasses { get; set; } = new List<string>();
        public List<string> AvailableBackgrounds { get; set; } = new List<string>();
    }
} 