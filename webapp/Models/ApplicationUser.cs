using Microsoft.AspNetCore.Identity;
using System.ComponentModel.DataAnnotations;

namespace DnDGameMaster.WebApp.Models
{
    public class ApplicationUser : IdentityUser
    {
        [PersonalData]
        [StringLength(50)]
        public string? FirstName { get; set; } = string.Empty;
        
        [PersonalData]
        [StringLength(50)]
        public string? LastName { get; set; } = string.Empty;
        
        [PersonalData]
        public DateTime Created { get; set; } = DateTime.UtcNow;
        
        [PersonalData]
        public DateTime? LastActive { get; set; }
        
        // Navigation property
        public virtual ICollection<Campaign> OwnedCampaigns { get; set; } = new List<Campaign>();
        public virtual ICollection<Character> Characters { get; set; } = new List<Character>();
    }
} 