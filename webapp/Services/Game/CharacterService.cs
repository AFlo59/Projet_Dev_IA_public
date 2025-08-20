using DnDGameMaster.WebApp.Data;
using DnDGameMaster.WebApp.Models;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace DnDGameMaster.WebApp.Services.Game
{
    public class CharacterService : ICharacterService
    {
        private readonly ApplicationDbContext _context;
        private readonly ILogger<CharacterService> _logger;

        public CharacterService(ApplicationDbContext context, ILogger<CharacterService> logger)
        {
            _context = context;
            _logger = logger;
        }

        public async Task<List<Character>> GetCharactersForUserAsync(string userId)
        {
            return await _context.Characters
                .Where(c => c.UserId == userId)
                .OrderBy(c => c.Name)
                .ToListAsync();
        }

        public async Task<Character?> GetCharacterByIdAsync(int id)
        {
            return await _context.Characters
                .Include(c => c.User)
                .FirstOrDefaultAsync(c => c.Id == id);
        }

        public async Task<Character> CreateCharacterAsync(Character character)
        {
            _context.Characters.Add(character);
            await _context.SaveChangesAsync();
            return character;
        }

        public async Task UpdateCharacterAsync(Character character)
        {
            _context.Entry(character).State = EntityState.Modified;
            await _context.SaveChangesAsync();
        }

        public async Task DeleteCharacterAsync(int id)
        {
            var character = await _context.Characters.FindAsync(id);
            if (character != null)
            {
                _context.Characters.Remove(character);
                await _context.SaveChangesAsync();
            }
        }

        public async Task<CampaignCharacter> AddCharacterToCampaignAsync(int campaignId, int characterId)
        {
            var existingLink = await _context.CampaignCharacters
                .FirstOrDefaultAsync(cc => cc.CampaignId == campaignId && cc.CharacterId == characterId);

            if (existingLink != null)
            {
                if (!existingLink.IsActive)
                {
                    existingLink.IsActive = true;
                    await _context.SaveChangesAsync();
                }
                return existingLink;
            }

            var campaignCharacter = new CampaignCharacter
            {
                CampaignId = campaignId,
                CharacterId = characterId,
                IsActive = true,
                JoinedAt = DateTime.UtcNow
            };

            _context.CampaignCharacters.Add(campaignCharacter);
            await _context.SaveChangesAsync();
            return campaignCharacter;
        }

        public async Task RemoveCharacterFromCampaignAsync(int campaignId, int characterId)
        {
            var campaignCharacter = await _context.CampaignCharacters
                .FirstOrDefaultAsync(cc => cc.CampaignId == campaignId && cc.CharacterId == characterId);

            if (campaignCharacter != null)
            {
                _context.CampaignCharacters.Remove(campaignCharacter);
                await _context.SaveChangesAsync();
            }
        }

        public async Task<List<Campaign>> GetCharacterCampaignsAsync(int characterId)
        {
            return await _context.CampaignCharacters
                .Where(cc => cc.CharacterId == characterId && cc.Campaign != null)
                .Select(cc => cc.Campaign!)
                .Where(c => c != null)
                .ToListAsync();
        }
    }
} 