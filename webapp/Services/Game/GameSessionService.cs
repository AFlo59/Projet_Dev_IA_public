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
    public class GameSessionService : IGameSessionService
    {
        private readonly ApplicationDbContext _context;
        private readonly ILogger<GameSessionService> _logger;

        public GameSessionService(ApplicationDbContext context, ILogger<GameSessionService> logger)
        {
            _context = context;
            _logger = logger;
        }

        public async Task<List<CampaignSession>> GetSessionsForCampaignAsync(int campaignId)
        {
            return await _context.CampaignSessions
                .Where(s => s.CampaignId == campaignId)
                .OrderByDescending(s => s.StartedAt)
                .ToListAsync();
        }

        public async Task<CampaignSession?> GetSessionByIdAsync(int id)
        {
            return await _context.CampaignSessions
                .Include(s => s.Campaign)
                .FirstOrDefaultAsync(s => s.Id == id);
        }

        public async Task<CampaignSession> CreateSessionAsync(CampaignSession session)
        {
            _context.CampaignSessions.Add(session);
            await _context.SaveChangesAsync();
            return session;
        }

        public async Task UpdateSessionAsync(CampaignSession session)
        {
            _context.Entry(session).State = EntityState.Modified;
            await _context.SaveChangesAsync();
        }

        public async Task DeleteSessionAsync(int id)
        {
            var session = await _context.CampaignSessions.FindAsync(id);
            if (session != null)
            {
                _context.CampaignSessions.Remove(session);
                await _context.SaveChangesAsync();
            }
        }

        public async Task<CampaignSession> StartSessionAsync(int campaignId, string sessionName)
        {
            var session = new CampaignSession
            {
                CampaignId = campaignId,
                Name = sessionName,
                Status = "Active",
                StartedAt = DateTime.UtcNow
            };

            _context.CampaignSessions.Add(session);
            await _context.SaveChangesAsync();
            return session;
        }

        public async Task<CampaignSession> EndSessionAsync(int sessionId, string summary)
        {
            var session = await _context.CampaignSessions.FindAsync(sessionId);
            if (session == null)
            {
                throw new KeyNotFoundException($"Session with ID {sessionId} not found");
            }

            session.Status = "Completed";
            session.EndedAt = DateTime.UtcNow;
            session.Summary = summary;

            _context.Entry(session).State = EntityState.Modified;
            await _context.SaveChangesAsync();
            return session;
        }
        
        public async Task<CampaignSession> GetOrCreateCurrentSessionAsync(int campaignId)
        {
            // Try to get the active session for this campaign
            var activeSession = await _context.CampaignSessions
                .Where(s => s.CampaignId == campaignId && s.Status == "Active" && !s.EndedAt.HasValue)
                .OrderByDescending(s => s.StartedAt)
                .FirstOrDefaultAsync();
                
            if (activeSession != null)
            {
                return activeSession;
            }
            
            // If no active session exists, create a new one
            var campaign = await _context.Campaigns.FindAsync(campaignId);
            if (campaign == null)
            {
                throw new KeyNotFoundException($"Campaign with ID {campaignId} not found");
            }
            
            var sessionCount = await _context.CampaignSessions.CountAsync(s => s.CampaignId == campaignId);
            
            var newSession = new CampaignSession
            {
                CampaignId = campaignId,
                Name = $"Session {sessionCount + 1}",
                Status = "Active",
                StartedAt = DateTime.UtcNow,
                // StartedAt is already set to DateTime.UtcNow
            };
            
            _context.CampaignSessions.Add(newSession);
            await _context.SaveChangesAsync();
            
            return newSession;
        }
        
        public async Task<List<CampaignMessage>> GetSessionMessagesAsync(int sessionId)
        {
            return await _context.CampaignMessages
                .Where(m => m.SessionId == sessionId)
                .Include(m => m.Character)
                .OrderBy(m => m.CreatedAt)
                .ToListAsync();
        }
        
        public async Task<CampaignMessage> AddMessageAsync(CampaignMessage message)
        {
            _context.CampaignMessages.Add(message);
            await _context.SaveChangesAsync();
            return message;
        }
        
        /// <summary>
        /// Atomically checks if a session has any messages and creates an initialization message if none exist.
        /// This prevents race conditions when multiple requests try to initialize the same session.
        /// </summary>
        /// <param name="sessionId">The session ID to check</param>
        /// <param name="initializationMessage">The initialization message to create if no messages exist</param>
        /// <returns>True if the initialization message was created, false if messages already existed</returns>
        public async Task<bool> TryCreateInitializationMessageAsync(int sessionId, CampaignMessage initializationMessage)
        {
            using var transaction = await _context.Database.BeginTransactionAsync();
            
            try
            {
                // Check if any messages exist for this session
                var messageCount = await _context.CampaignMessages
                    .Where(m => m.SessionId == sessionId)
                    .CountAsync();
                
                if (messageCount == 0)
                {
                    // No messages exist, create the initialization message
                    _context.CampaignMessages.Add(initializationMessage);
                    await _context.SaveChangesAsync();
                    await transaction.CommitAsync();
                    _logger.LogInformation($"Created initialization message for session {sessionId}");
                    return true;
                }
                else
                {
                    // Messages already exist, don't create another initialization message
                    await transaction.RollbackAsync();
                    _logger.LogInformation($"Session {sessionId} already has {messageCount} messages, skipping initialization");
                    return false;
                }
            }
            catch (Exception ex)
            {
                await transaction.RollbackAsync();
                _logger.LogError(ex, $"Error creating initialization message for session {sessionId}");
                throw;
            }
        }
    }
} 