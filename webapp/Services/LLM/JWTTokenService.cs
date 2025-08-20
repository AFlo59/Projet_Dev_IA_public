using System;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Identity;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Microsoft.IdentityModel.Tokens;
using DnDGameMaster.WebApp.Models;

namespace DnDGameMaster.WebApp.Services.LLM
{
    /// <summary>
    /// Service pour générer des tokens JWT compatibles avec l'API LLM GameMaster
    /// </summary>
    public class JWTTokenService : IJWTTokenService
    {
        private readonly IConfiguration _configuration;
        private readonly UserManager<ApplicationUser> _userManager;
        private readonly ILogger<JWTTokenService> _logger;
        
        public JWTTokenService(
            IConfiguration configuration,
            UserManager<ApplicationUser> userManager,
            ILogger<JWTTokenService> logger)
        {
            _configuration = configuration;
            _userManager = userManager;
            _logger = logger;
        }
        
        public Task<string?> GenerateTokenAsync(ApplicationUser user)
        {
            try
            {
                var secretKey = _configuration["LLM_JWT_SECRET_KEY"] ?? 
                               _configuration["JWT_SECRET_KEY"] ?? 
                               "your-very-secure-secret-key-change-this-in-production";
                
                var expirationHours = int.Parse(_configuration["LLM_JWT_EXPIRATION_HOURS"] ?? "24");
                
                if (string.IsNullOrEmpty(secretKey) || secretKey.Length < 32)
                {
                    _logger.LogError("JWT secret key is missing or too short. Please configure LLM_JWT_SECRET_KEY");
                    return Task.FromResult<string?>(null);
                }
                
                var tokenHandler = new JwtSecurityTokenHandler();
                var key = Encoding.UTF8.GetBytes(secretKey);
                
                var tokenDescriptor = new SecurityTokenDescriptor
                {
                    Subject = new ClaimsIdentity(new[]
                    {
                        new Claim("user_id", user.Id),
                        new Claim("email", user.Email ?? string.Empty),
                        new Claim("username", user.UserName ?? string.Empty),
                        new Claim("type", "access")
                    }),
                    Expires = DateTime.UtcNow.AddHours(expirationHours),
                    IssuedAt = DateTime.UtcNow,
                    SigningCredentials = new SigningCredentials(
                        new SymmetricSecurityKey(key), 
                        SecurityAlgorithms.HmacSha256Signature)
                };
                
                var token = tokenHandler.CreateToken(tokenDescriptor);
                var tokenString = tokenHandler.WriteToken(token);
                
                _logger.LogInformation($"JWT token generated successfully for user {user.Email}");
                return Task.FromResult<string?>(tokenString);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error generating JWT token for user {user.Email}");
                return Task.FromResult<string?>(null);
            }
        }
        
        public async Task<string?> GenerateTokenByUserIdAsync(string userId)
        {
            try
            {
                var user = await _userManager.FindByIdAsync(userId);
                if (user == null)
                {
                    _logger.LogWarning($"User with ID {userId} not found");
                    return null;
                }
                
                return await GenerateTokenAsync(user);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error generating JWT token for user ID {userId}");
                return null;
            }
        }
        
        public bool ValidateToken(string token)
        {
            try
            {
                var secretKey = _configuration["LLM_JWT_SECRET_KEY"] ?? 
                               _configuration["JWT_SECRET_KEY"] ?? 
                               "your-very-secure-secret-key-change-this-in-production";
                
                var tokenHandler = new JwtSecurityTokenHandler();
                var key = Encoding.UTF8.GetBytes(secretKey);
                
                tokenHandler.ValidateToken(token, new TokenValidationParameters
                {
                    ValidateIssuerSigningKey = true,
                    IssuerSigningKey = new SymmetricSecurityKey(key),
                    ValidateIssuer = false,
                    ValidateAudience = false,
                    ClockSkew = TimeSpan.Zero
                }, out SecurityToken validatedToken);
                
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogDebug(ex, "Token validation failed");
                return false;
            }
        }
    }
}
