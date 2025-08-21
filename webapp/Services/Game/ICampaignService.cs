using DnDGameMaster.WebApp.Models;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace DnDGameMaster.WebApp.Services.Game
{
    public interface ICampaignService
    {
        Task<List<Campaign>> GetCampaignsForUserAsync(string userId);
        Task<List<Campaign>> GetPublicCampaignsAsync();
        Task<Campaign?> GetCampaignByIdAsync(int id);
        Task<Campaign> CreateCampaignAsync(Campaign campaign);
        Task UpdateCampaignAsync(Campaign campaign);
        Task DeleteCampaignAsync(int id);
        Task<bool> IsUserInCampaignAsync(int campaignId, string userId);
        Task<bool> IsUserCampaignOwnerAsync(int campaignId, string userId);
        Task<List<CampaignCharacter>> GetCampaignCharactersAsync(int campaignId);
        Task<List<CampaignSession>> GetCampaignSessionsAsync(int campaignId);
        Task<List<CampaignMessage>> GetCampaignMessagesAsync(int campaignId, int? limit = null);
        Task<CampaignMessage> AddCampaignMessageAsync(CampaignMessage message);
        Task<List<CampaignCharacter>> GetUserCharactersInCampaignAsync(int campaignId, string userId);
        Task AddCharacterToCampaignAsync(int campaignId, int characterId);
        Task<bool> AddUserToCampaignAsync(int campaignId, string userId);
        Task<List<string>> GetUniquePlayersInCampaignAsync(int campaignId);
        Task UpdateContentGenerationStatusAsync(int campaignId, string status, string? error = null);
        Task UpdateCharacterGenerationStatusAsync(int campaignId, string status, string? error = null);
        Task UpdateCharacterLocationAsync(int campaignId, int characterId, string location);
        Task<string?> GetCharacterLocationAsync(int campaignId, int characterId);
        
        // Additional methods for tests compatibility
        Task<List<Campaign>> GetUserCampaignsAsync(string userId);
        Task<bool> CanUserAccessCampaignAsync(int campaignId, string userId);
        
        // New methods for game state management
        Task InitializeCampaignGameStateAsync(int campaignId);
        // ✅ SUPPRIMÉ : AutoAssignCharacterLocationsAsync et GetMainTownForCampaignAsync
        // Le LLM GameMaster gère maintenant ces responsabilités
        Task<List<object>> GetCurrentLocationDataAsync(int campaignId, int characterId);
        Task<List<object>> GetDiscoveredQuestsAsync(int campaignId, string? questGiver = null);
        Task<bool> HandleNPCInteractionAsync(int campaignId, int characterId, string npcName);
        Task RefreshCharacterLocationFromDatabaseAsync(int campaignId, int characterId);
    }
} 