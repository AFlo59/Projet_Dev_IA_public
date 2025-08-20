using DnDGameMaster.WebApp.Models;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace DnDGameMaster.WebApp.Services.Game
{
    public interface ICharacterService
    {
        Task<List<Character>> GetCharactersForUserAsync(string userId);
        Task<Character?> GetCharacterByIdAsync(int id);
        Task<Character> CreateCharacterAsync(Character character);
        Task UpdateCharacterAsync(Character character);
        Task DeleteCharacterAsync(int id);
        Task<CampaignCharacter> AddCharacterToCampaignAsync(int campaignId, int characterId);
        Task RemoveCharacterFromCampaignAsync(int campaignId, int characterId);
        Task<List<Campaign>> GetCharacterCampaignsAsync(int characterId);
    }
} 