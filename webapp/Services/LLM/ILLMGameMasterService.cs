using System.Threading.Tasks;

namespace DnDGameMaster.WebApp.Services.LLM
{
    public interface ILLMGameMasterService
    {
        /// <summary>
        /// Start a new campaign session with the AI Game Master
        /// </summary>
        Task<GameMasterResponse> StartCampaignAsync(int campaignId, int sessionId, int characterId, string playerName);

        /// <summary>
        /// Send a message to the AI Game Master and get a response
        /// </summary>
        Task<GameMasterResponse> SendMessageAsync(int campaignId, int sessionId, int characterId, string message, bool isSystemMessage = false);

        /// <summary>
        /// End the current session and get a summary
        /// </summary>
        Task<GameMasterResponse> EndSessionAsync(int campaignId, int sessionId);

        /// <summary>
        /// Generate a narrative response for a specific context
        /// </summary>
        Task<GameMasterResponse> GenerateNarrativeResponseAsync(int campaignId, string message, string userId, int? characterId = null);
        
        /// <summary>
        /// Generate narrative response (generic method for tests)
        /// </summary>
        Task<GameMasterResponse> GenerateNarrativeAsync(int campaignId, string message, string userId, int? characterId = null);
        
        /// <summary>
        /// Generate character description
        /// </summary>
        Task<GameMasterResponse> GenerateCharacterDescriptionAsync(string characterName, string characterClass, string characterRace, string background, string language);
        
        /// <summary>
        /// Get campaign metrics for monitoring
        /// </summary>
        Task<CampaignMetricsResponse> GetCampaignMetricsAsync(int campaignId);
        
        /// <summary>
        /// Get all campaign elements (NPCs, Locations, Quests) from the LLM GameMaster
        /// </summary>
        Task<CampaignElementsResponse> GetCampaignElementsAsync(int campaignId);

        /// <summary>
        /// Get the status of image generation for a campaign
        /// </summary>
        Task<ImageStatusResponse> GetImageStatusAsync(int campaignId);

        /// <summary>
        /// Generate missing images for all elements in a campaign
        /// </summary>
        Task<ImageGenerationResponse> GenerateMissingImagesAsync(int campaignId);

        /// <summary>
        /// Generate image for a specific element
        /// </summary>
        Task<ImageGenerationResponse> GenerateElementImageAsync(int campaignId, string elementType, int elementId);
        
        /// <summary>
        /// Generate campaign content (locations, NPCs, quests) in background
        /// </summary>
        Task<ContentGenerationResponse> GenerateCampaignContentAsync(int campaignId);
        
        /// <summary>
        /// Get the status of campaign content generation
        /// </summary>
        Task<ContentGenerationStatusResponse> GetContentGenerationStatusAsync(int campaignId);
        
        /// <summary>
        /// Get campaign NPCs from the LLM GameMaster
        /// </summary>
        Task<CampaignNPCsResponse> GetCampaignNPCsAsync(int campaignId);
        
        /// <summary>
        /// Get campaign locations from the LLM GameMaster
        /// </summary>
        Task<CampaignLocationsResponse> GetCampaignLocationsAsync(int campaignId);
        
        /// <summary>
        /// Get campaign quests from the LLM GameMaster
        /// </summary>
        Task<CampaignQuestsResponse> GetCampaignQuestsAsync(int campaignId);
        
        /// <summary>
        /// Get character quests (accepted quests) from the LLM GameMaster
        /// </summary>
        Task<CampaignQuestsResponse> GetCharacterQuestsAsync(int campaignId);
        
        /// <summary>
        /// Update character location in the LLM GameMaster
        /// </summary>
        Task<bool> UpdateCharacterLocationAsync(int campaignId, int characterId, string location);
        
        /// <summary>
        /// Sync all character locations with the LLM GameMaster
        /// </summary>
        Task<bool> SyncAllCharacterLocationsAsync(int campaignId, Dictionary<int, string> characterLocations);
        
        /// <summary>
        /// Get character location from the LLM GameMaster
        /// </summary>
        Task<CharacterLocationResponse> GetCharacterLocationAsync(int campaignId, int characterId);
    }

    public class CampaignMetricsResponse
    {
        public bool Success { get; set; }
        public int CampaignId { get; set; }
        public int TotalMessages { get; set; }
        public int TotalSessions { get; set; }
        public int ActivePlayers { get; set; }
        public double AverageSessionLength { get; set; }
        public string Message { get; set; } = string.Empty;
    }

    public class ImageStatusResponse
    {
        public bool Success { get; set; }
        public int CampaignId { get; set; }
        public ImageStatus Status { get; set; } = new ImageStatus();
        public string Message { get; set; } = string.Empty;
    }

    public class ImageStatus
    {
        public ElementImageStatus NPCs { get; set; } = new ElementImageStatus();
        public ElementImageStatus Locations { get; set; } = new ElementImageStatus();
        public int BackgroundThreads { get; set; }
    }

    public class ElementImageStatus
    {
        public int Total { get; set; }
        public int WithImages { get; set; }
        public int MissingImages { get; set; }
    }

    public class ImageGenerationResponse
    {
        public bool Success { get; set; }
        public int CampaignId { get; set; }
        public string ElementType { get; set; } = string.Empty;
        public int ElementId { get; set; }
        public string ImageUrl { get; set; } = string.Empty;
        public string Message { get; set; } = string.Empty;
        public string Status { get; set; } = string.Empty;
    }
    
    public class ContentGenerationResponse
    {
        public bool Success { get; set; }
        public int CampaignId { get; set; }
        public string Message { get; set; } = string.Empty;
        public string Status { get; set; } = string.Empty;
    }
    
    public class ContentGenerationStatusResponse
    {
        public bool Success { get; set; }
        public int CampaignId { get; set; }
        public string Status { get; set; } = string.Empty;
        public string? Error { get; set; }
        public DateTime? StartedAt { get; set; }
        public DateTime? CompletedAt { get; set; }
    }
    
    public class CampaignNPCsResponse
    {
        public bool Success { get; set; }
        public List<CampaignNPCDto> NPCs { get; set; } = new List<CampaignNPCDto>();
    }
    
    public class CampaignLocationsResponse
    {
        public bool Success { get; set; }
        public List<CampaignLocationDto> Locations { get; set; } = new List<CampaignLocationDto>();
    }
    
    public class CampaignQuestsResponse
    {
        public bool Success { get; set; }
        public List<CampaignQuestDto> Quests { get; set; } = new List<CampaignQuestDto>();
    }
    
    public class CharacterLocationResponse
    {
        public bool Success { get; set; }
        public int CharacterId { get; set; }
        public string CurrentLocation { get; set; } = string.Empty;
        public string CharacterName { get; set; } = string.Empty;
    }
    

} 