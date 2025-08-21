using DnDGameMaster.WebApp.Data;
using DnDGameMaster.WebApp.Models;
using DnDGameMaster.WebApp.Services.LLM;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace DnDGameMaster.WebApp.Services.Game
{
    public class CampaignService : ICampaignService
    {
        private readonly ApplicationDbContext _context;
        private readonly ILogger<CampaignService> _logger;
        private readonly ILLMGameMasterService _llmService;

        public CampaignService(ApplicationDbContext context, ILogger<CampaignService> logger, ILLMGameMasterService llmService)
        {
            _context = context;
            _logger = logger;
            _llmService = llmService;
        }

        public async Task<List<Campaign>> GetCampaignsForUserAsync(string userId)
        {
            return await _context.Campaigns
                .Where(c => c.OwnerId == userId || c.CampaignCharacters.Any(cc => cc.Character != null && cc.Character.UserId == userId))
                .ToListAsync();
        }

        public async Task<List<Campaign>> GetPublicCampaignsAsync()
        {
            return await _context.Campaigns
                .Where(c => c.IsPublic)
                .ToListAsync();
        }

        public async Task<Campaign?> GetCampaignByIdAsync(int id)
        {
            return await _context.Campaigns
                .FirstOrDefaultAsync(c => c.Id == id);
        }

        public async Task<Campaign> CreateCampaignAsync(Campaign campaign)
        {
            try
            {
                // Note: Maintenant nous pouvons vérifier l'existence de l'utilisateur car nous avons accès à la table Users dans le même contexte
                if (!string.IsNullOrEmpty(campaign.OwnerId))
                {
                    bool userExists = await _context.Users.AnyAsync(u => u.Id == campaign.OwnerId);
                    if (!userExists)
                    {
                        _logger.LogError($"User with ID {campaign.OwnerId} does not exist in the database.");
                        throw new InvalidOperationException($"User with ID {campaign.OwnerId} does not exist in the database.");
                    }
                }
                
                // Set initial content generation status
                campaign.ContentGenerationStatus = "NotStarted";
                
                _context.Campaigns.Add(campaign);
                await _context.SaveChangesAsync();
                return campaign;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error creating campaign");
                throw;
            }
        }

        public async Task UpdateCampaignAsync(Campaign campaign)
        {
            _context.Entry(campaign).State = EntityState.Modified;
            await _context.SaveChangesAsync();
        }

        public async Task DeleteCampaignAsync(int id)
        {
            var campaign = await _context.Campaigns.FindAsync(id);
            if (campaign != null)
            {
                _context.Campaigns.Remove(campaign);
                await _context.SaveChangesAsync();
            }
        }

        public async Task<bool> IsUserInCampaignAsync(int campaignId, string userId)
        {
            return await _context.CampaignCharacters
                .AnyAsync(cc => cc.CampaignId == campaignId && cc.Character != null && cc.Character.UserId == userId);
        }

        public async Task<bool> IsUserCampaignOwnerAsync(int campaignId, string userId)
        {
            return await _context.Campaigns
                .AnyAsync(c => c.Id == campaignId && c.OwnerId == userId);
        }

        public async Task<List<CampaignCharacter>> GetCampaignCharactersAsync(int campaignId)
        {
            return await _context.CampaignCharacters
                .Where(cc => cc.CampaignId == campaignId)
                .Include(cc => cc.Character)
                .ToListAsync();
        }

        public async Task<List<CampaignSession>> GetCampaignSessionsAsync(int campaignId)
        {
            return await _context.CampaignSessions
                .Where(s => s.CampaignId == campaignId)
                .OrderByDescending(s => s.StartedAt)
                .ToListAsync();
        }

        public async Task<List<CampaignMessage>> GetCampaignMessagesAsync(int campaignId, int? limit = null)
        {
            // Construire la requête de base
            var query = _context.CampaignMessages
                .Where(m => m.CampaignId == campaignId)
                .Include(m => m.Character)
                .OrderByDescending(m => m.CreatedAt);

            // Appliquer la limite si nécessaire et exécuter la requête
            if (limit.HasValue)
            {
                return await query.Take(limit.Value).ToListAsync();
            }
            
            return await query.ToListAsync();
        }

        public async Task<CampaignMessage> AddCampaignMessageAsync(CampaignMessage message)
        {
            _context.CampaignMessages.Add(message);
            await _context.SaveChangesAsync();
            return message;
        }
        
        public async Task<List<CampaignCharacter>> GetUserCharactersInCampaignAsync(int campaignId, string userId)
        {
            return await _context.CampaignCharacters
                .Where(cc => cc.CampaignId == campaignId && cc.Character != null && cc.Character.UserId == userId)
                .Include(cc => cc.Character)
                .ToListAsync();
        }
        
        public async Task AddCharacterToCampaignAsync(int campaignId, int characterId)
        {
            // Check if character is already in campaign
            var existingCharacter = await _context.CampaignCharacters
                .FirstOrDefaultAsync(cc => cc.CampaignId == campaignId && cc.CharacterId == characterId);
            
            if (existingCharacter == null)
            {
                // Create new campaign character association
                var campaignCharacter = new CampaignCharacter
                {
                    CampaignId = campaignId,
                    CharacterId = characterId,
                    IsActive = true,
                    JoinedAt = DateTime.UtcNow
                };
                
                _context.CampaignCharacters.Add(campaignCharacter);
                await _context.SaveChangesAsync();
            }
        }
        
        public async Task<bool> AddUserToCampaignAsync(int campaignId, string userId)
        {
            // Check if campaign exists and is valid for joining
            var campaign = await _context.Campaigns.FindAsync(campaignId);
            if (campaign == null)
            {
                return false;
            }
            
            // Check if user is already in campaign (has characters in the campaign)
            var isUserInCampaign = await IsUserInCampaignAsync(campaignId, userId);
            if (isUserInCampaign)
            {
                return true; // User is already in campaign
            }
            
            // The user will join the campaign when they create their first character
            // So we just return true to indicate the user can join
            return true;
        }
        
        public async Task<List<string>> GetUniquePlayersInCampaignAsync(int campaignId)
        {
            // Get all unique user IDs who have characters in this campaign (excluding the campaign owner)
            var campaign = await _context.Campaigns.FindAsync(campaignId);
            if (campaign == null)
            {
                return new List<string>();
            }
            
            var uniquePlayerIds = await _context.CampaignCharacters
                .Where(cc => cc.CampaignId == campaignId && cc.Character != null)
                .Select(cc => cc.Character!.UserId)
                .Where(userId => userId != campaign.OwnerId) // Exclude campaign owner
                .Distinct()
                .ToListAsync();
            
            return uniquePlayerIds;
        }
        
        public async Task UpdateContentGenerationStatusAsync(int campaignId, string status, string? error = null)
        {
            var campaign = await _context.Campaigns.FindAsync(campaignId);
            if (campaign != null)
            {
                campaign.ContentGenerationStatus = status;
                
                if (status == "InProgress" && !campaign.ContentGenerationStartedAt.HasValue)
                {
                    campaign.ContentGenerationStartedAt = DateTime.UtcNow;
                }
                else if (status == "Completed" || status == "Failed")
                {
                    campaign.ContentGenerationCompletedAt = DateTime.UtcNow;
                }
                
                if (!string.IsNullOrEmpty(error))
                {
                    campaign.ContentGenerationError = error;
                }
                
                await _context.SaveChangesAsync();
            }
        }
        
        public async Task UpdateCharacterGenerationStatusAsync(int campaignId, string status, string? error = null)
        {
            var campaign = await _context.Campaigns.FindAsync(campaignId);
            if (campaign != null)
            {
                campaign.CharacterGenerationStatus = status;
                
                if (status == "InProgress" && !campaign.CharacterGenerationStartedAt.HasValue)
                {
                    campaign.CharacterGenerationStartedAt = DateTime.UtcNow;
                }
                else if (status == "Completed" || status == "Failed")
                {
                    campaign.CharacterGenerationCompletedAt = DateTime.UtcNow;
                }
                
                if (!string.IsNullOrEmpty(error))
                {
                    campaign.CharacterGenerationError = error;
                }
                
                await _context.SaveChangesAsync();
            }
        }
        
        public async Task UpdateCharacterLocationAsync(int campaignId, int characterId, string location)
        {
            var campaignCharacter = await _context.CampaignCharacters
                .FirstOrDefaultAsync(cc => cc.CampaignId == campaignId && cc.CharacterId == characterId);
            
            if (campaignCharacter != null)
            {
                campaignCharacter.CurrentLocation = location;
                await _context.SaveChangesAsync();
            }
        }
        
        public async Task<string?> GetCharacterLocationAsync(int campaignId, int characterId)
        {
            // Force fresh data from database to ensure we get latest updates from GM
            var campaignCharacter = await _context.CampaignCharacters
                .AsNoTracking() // Ensure fresh data from database
                .FirstOrDefaultAsync(cc => cc.CampaignId == campaignId && cc.CharacterId == characterId);
            
            _logger.LogInformation($"🗺️ Retrieved character {characterId} location: '{campaignCharacter?.CurrentLocation}' for campaign {campaignId}");
            return campaignCharacter?.CurrentLocation;
        }
        
        public async Task RefreshCharacterLocationFromDatabaseAsync(int campaignId, int characterId)
        {
            try
            {
                // Force Entity Framework to refresh its view of the database
                await _context.Database.ExecuteSqlRawAsync("SELECT 1"); // Simple query to refresh connection
                
                var campaignCharacter = await _context.CampaignCharacters
                    .AsNoTracking()
                    .FirstOrDefaultAsync(cc => cc.CampaignId == campaignId && cc.CharacterId == characterId);
                
                if (campaignCharacter != null)
                {
                    _logger.LogInformation($"🔄 Refreshed character {characterId} location: '{campaignCharacter.CurrentLocation}' for campaign {campaignId}");
                }
                else
                {
                    _logger.LogWarning($"⚠️ Character {characterId} not found in campaign {campaignId} during refresh");
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"❌ Error refreshing character {characterId} location for campaign {campaignId}");
            }
        }
        
        public async Task InitializeCampaignGameStateAsync(int campaignId)
        {
            try
            {
                _logger.LogInformation($"🎮 Initializing game state for campaign {campaignId}");
                
                var campaign = await _context.Campaigns.FindAsync(campaignId);
                if (campaign == null)
                {
                    _logger.LogWarning($"Campaign {campaignId} not found");
                    return;
                }
                
                // ✅ CORRECTION : webapp ne fait PLUS d'assignation automatique
                // Le LLM GameMaster est SOUVERAIN sur les locations
                _logger.LogInformation($"🎮 Game Master will handle ALL location assignments during campaign start");
                
                // Initialize quest discovery states (passive seulement)
                await InitializeQuestStatesAsync(campaignId);
                
                _logger.LogInformation($"✅ Game state initialization completed for campaign {campaignId}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error initializing game state for campaign {campaignId}");
                throw;
            }
        }
        
        // ✅ SUPPRIMÉ : webapp ne fait PLUS d'assignation automatique de locations
        // Le LLM GameMaster est désormais SEUL RESPONSABLE de ces décisions
        
        // ✅ GetMainTownForCampaignAsync supprimé - Le LLM GameMaster gère les locations
        
        private Task InitializeQuestStatesAsync(int campaignId)
        {
            try
            {
                _logger.LogInformation($"📜 Initializing quest states for campaign {campaignId}");
                
                // This would be handled via the LLM service calls since quests are stored there
                // For now, we just log that this initialization should happen
                _logger.LogInformation($"✅ Quest states initialization noted for campaign {campaignId}");
                return Task.CompletedTask;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error initializing quest states for campaign {campaignId}");
                return Task.FromException(ex);
            }
        }
        
        public async Task<List<object>> GetCurrentLocationDataAsync(int campaignId, int characterId)
        {
            try
            {
                _logger.LogInformation($"🔍 Getting current location data for character {characterId} in campaign {campaignId}");
                
                var currentLocation = await GetCharacterLocationAsync(campaignId, characterId);
                if (string.IsNullOrEmpty(currentLocation))
                {
                    _logger.LogWarning($"⚠️ No current location found for character {characterId} in campaign {campaignId}");
                    return new List<object>();
                }
                
                _logger.LogInformation($"📍 Character {characterId} is currently in: '{currentLocation}'");
                
                // Get location details, NPCs, and discovered quests
                var locationData = new List<object>();
                
                // Add location info
                locationData.Add(new { Type = "Location", Name = currentLocation });
                
                // Get NPCs in this location via LLM service
                if (_llmService != null)
                {
                    try
                    {
                        var npcsResponse = await _llmService.GetCampaignNPCsAsync(campaignId);
                        if (npcsResponse?.NPCs?.Any() == true)
                        {
                            // Améliorer le filtrage des NPCs par localisation
                            var npcsInLocation = npcsResponse.NPCs
                                .Where(npc => 
                                    npc.Status == "Active" && 
                                    (npc.CurrentLocation?.Equals(currentLocation, StringComparison.OrdinalIgnoreCase) == true ||
                                     string.IsNullOrEmpty(npc.CurrentLocation)) // NPCs sans localisation spécifique
                                )
                                .Select(npc => new { 
                                    Type = "NPC", 
                                    npc.Name, 
                                    npc.Description, 
                                    npc.PortraitUrl,
                                    npc.Race,
                                    npc.Class,
                                    npc.Level,
                                    npc.CurrentLocation
                                })
                                .ToList();
                            
                            _logger.LogInformation($"Found {npcsInLocation.Count} NPCs in location '{currentLocation}' for campaign {campaignId}");
                            locationData.AddRange(npcsInLocation);
                        }
                        else
                        {
                            _logger.LogWarning($"No NPCs found for campaign {campaignId}");
                        }
                    }
                    catch (Exception ex)
                    {
                        _logger.LogWarning(ex, $"Could not get NPCs for location {currentLocation}");
                    }
                }
                
                return locationData;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error getting current location data for character {characterId} in campaign {campaignId}");
                return new List<object>();
            }
        }
        
        public async Task<List<object>> GetDiscoveredQuestsAsync(int campaignId, string? questGiver = null)
        {
            try
            {
                if (_llmService != null)
                {
                    // Récupérer les quêtes acceptées par le personnage au lieu de toutes les quêtes
                    var characterQuestsResponse = await _llmService.GetCharacterQuestsAsync(campaignId);
                    if (characterQuestsResponse?.Quests?.Any() == true)
                    {
                        var acceptedQuests = characterQuestsResponse.Quests
                            .Where(q => q.Status == "Active" || q.Status == "InProgress") // Seulement les quêtes actives
                            .Where(q => string.IsNullOrEmpty(questGiver) || q.QuestGiver?.Equals(questGiver, StringComparison.OrdinalIgnoreCase) == true)
                            .Select(q => new 
                            { 
                                Type = "Quest", 
                                q.Title, 
                                q.Description, 
                                q.Status, 
                                q.QuestGiver,
                                q.Difficulty,
                                q.Reward,
                                q.Progress
                            })
                            .ToList<object>();
                        
                        _logger.LogInformation($"Found {acceptedQuests.Count} accepted quests for campaign {campaignId}");
                        return acceptedQuests;
                    }
                    else
                    {
                        _logger.LogInformation($"No accepted quests found for campaign {campaignId}");
                        return new List<object>();
                    }
                }
                
                return new List<object>();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error getting accepted quests for campaign {campaignId}");
                return new List<object>();
            }
        }
        
        public async Task<bool> HandleNPCInteractionAsync(int campaignId, int characterId, string npcName)
        {
            try
            {
                _logger.LogInformation($"🤝 Handling NPC interaction: Character {characterId} with {npcName} in campaign {campaignId}");
                
                var currentLocation = await GetCharacterLocationAsync(campaignId, characterId);
                if (string.IsNullOrEmpty(currentLocation))
                {
                    return false;
                }
                
                // Check if this NPC has quests to give
                if (_llmService != null)
                {
                    var questsResponse = await _llmService.GetCampaignQuestsAsync(campaignId);
                    if (questsResponse?.Quests?.Any() == true)
                    {
                        var npcQuests = questsResponse.Quests
                            .Where(q => q.QuestGiver?.Equals(npcName, StringComparison.OrdinalIgnoreCase) == true && q.Status == "Available")
                            .ToList();
                        
                        if (npcQuests.Any())
                        {
                            // This would trigger quest discovery via the LLM service
                            _logger.LogInformation($"🔍 Found {npcQuests.Count} quests from {npcName} for potential discovery");
                            return true;
                        }
                    }
                }
                
                return false;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error handling NPC interaction for character {characterId} with {npcName}");
                return false;
            }
        }
        
        // ===============================
        // LOCATION SYNCHRONIZATION METHODS
        // ===============================
        
        public async Task<bool> SyncCharacterLocationWithLLMAsync(int campaignId, int characterId, string newLocation)
        {
            try
            {
                _logger.LogInformation($"🔄 Syncing character {characterId} location to {newLocation} with LLM service");
                
                // First update locally
                await UpdateCharacterLocationAsync(campaignId, characterId, newLocation);
                
                // Then sync with llmgamemaster
                if (_llmService != null)
                {
                    var success = await _llmService.UpdateCharacterLocationAsync(campaignId, characterId, newLocation);
                    if (success)
                    {
                        _logger.LogInformation($"✅ Successfully synced character {characterId} location with LLM service");
                        return true;
                    }
                    else
                    {
                        _logger.LogWarning($"⚠️ Failed to sync character {characterId} location with LLM service");
                    }
                }
                
                return false;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error syncing character {characterId} location with LLM service");
                return false;
            }
        }
        
        public async Task<bool> SyncAllCharacterLocationsWithLLMAsync(int campaignId)
        {
            try
            {
                _logger.LogInformation($"🔄 Syncing all character locations for campaign {campaignId} with LLM service");
                
                var campaignCharacters = await _context.CampaignCharacters
                    .Where(cc => cc.CampaignId == campaignId)
                    .Include(cc => cc.Character)
                    .ToListAsync();
                
                if (!campaignCharacters.Any())
                {
                    _logger.LogInformation($"No characters found for campaign {campaignId}");
                    return true;
                }
                
                // Build character locations dictionary
                var characterLocations = new Dictionary<int, string>();
                foreach (var cc in campaignCharacters)
                {
                    if (!string.IsNullOrEmpty(cc.CurrentLocation))
                    {
                        characterLocations[cc.CharacterId] = cc.CurrentLocation;
                    }
                }
                
                if (!characterLocations.Any())
                {
                    _logger.LogInformation($"No character locations to sync for campaign {campaignId}");
                    return true;
                }
                
                // Sync with llmgamemaster
                if (_llmService != null)
                {
                    var success = await _llmService.SyncAllCharacterLocationsAsync(campaignId, characterLocations);
                    if (success)
                    {
                        _logger.LogInformation($"✅ Successfully synced all character locations for campaign {campaignId}");
                        return true;
                    }
                    else
                    {
                        _logger.LogWarning($"⚠️ Failed to sync all character locations for campaign {campaignId}");
                    }
                }
                
                return false;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error syncing all character locations for campaign {campaignId}");
                return false;
            }
        }
        
        public async Task<Dictionary<int, string>> GetCharacterLocationsByIdAsync(int campaignId)
        {
            var characterLocations = await _context.CampaignCharacters
                .Where(cc => cc.CampaignId == campaignId && !string.IsNullOrEmpty(cc.CurrentLocation))
                .ToDictionaryAsync(cc => cc.CharacterId, cc => cc.CurrentLocation!);
            
            return characterLocations;
        }

        // Additional methods for test compatibility
        public async Task<List<Campaign>> GetUserCampaignsAsync(string userId)
        {
            // This is an alias for GetCampaignsForUserAsync for test compatibility
            return await GetCampaignsForUserAsync(userId);
        }

        public async Task<bool> CanUserAccessCampaignAsync(int campaignId, string userId)
        {
            // A user can access a campaign if:
            // 1. They own the campaign, OR
            // 2. They have characters in the campaign, OR  
            // 3. The campaign is public
            var campaign = await _context.Campaigns.FindAsync(campaignId);
            if (campaign == null)
            {
                return false;
            }

            // Check if user is the owner
            if (campaign.OwnerId == userId)
            {
                return true;
            }

            // Check if campaign is public
            if (campaign.IsPublic)
            {
                return true;
            }

            // Check if user has characters in the campaign
            return await IsUserInCampaignAsync(campaignId, userId);
        }
    }
} 