using DnDGameMaster.WebApp.Models;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace DnDGameMaster.WebApp.Services.Game
{
    public interface IGameSessionService
    {
        Task<List<CampaignSession>> GetSessionsForCampaignAsync(int campaignId);
        Task<CampaignSession?> GetSessionByIdAsync(int id);
        Task<CampaignSession> CreateSessionAsync(CampaignSession session);
        Task UpdateSessionAsync(CampaignSession session);
        Task DeleteSessionAsync(int id);
        Task<CampaignSession> StartSessionAsync(int campaignId, string sessionName);
        Task<CampaignSession> EndSessionAsync(int sessionId, string summary);
        Task<CampaignSession> GetOrCreateCurrentSessionAsync(int campaignId);
        Task<List<CampaignMessage>> GetSessionMessagesAsync(int sessionId);
        Task<CampaignMessage> AddMessageAsync(CampaignMessage message);
        Task<bool> TryCreateInitializationMessageAsync(int sessionId, CampaignMessage initializationMessage);
    }
} 