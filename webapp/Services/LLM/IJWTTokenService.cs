using System.Threading.Tasks;
using DnDGameMaster.WebApp.Models;

namespace DnDGameMaster.WebApp.Services.LLM
{
    /// <summary>
    /// Service pour générer des tokens JWT pour l'API LLM GameMaster
    /// </summary>
    public interface IJWTTokenService
    {
        /// <summary>
        /// Génère un token JWT pour l'utilisateur connecté
        /// </summary>
        /// <param name="user">Utilisateur pour lequel générer le token</param>
        /// <returns>Token JWT ou null si erreur</returns>
        Task<string?> GenerateTokenAsync(ApplicationUser user);
        
        /// <summary>
        /// Génère un token JWT à partir de l'ID utilisateur
        /// </summary>
        /// <param name="userId">ID de l'utilisateur</param>
        /// <returns>Token JWT ou null si erreur</returns>
        Task<string?> GenerateTokenByUserIdAsync(string userId);
        
        /// <summary>
        /// Valide un token JWT (optionnel pour debugging)
        /// </summary>
        /// <param name="token">Token à valider</param>
        /// <returns>True si valide</returns>
        bool ValidateToken(string token);
    }
}
