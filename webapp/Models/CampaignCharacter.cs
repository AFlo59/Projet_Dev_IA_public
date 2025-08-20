using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DnDGameMaster.WebApp.Models
{
    public class CampaignCharacter
    {
        [Key]
        public int Id { get; set; }
        
        [Required]
        public int CampaignId { get; set; }
        
        [Required]
        public int CharacterId { get; set; }
        
        public bool IsActive { get; set; } = true;
        
        // New field for character's current location
        [StringLength(100)]
        public string? CurrentLocation { get; set; } = string.Empty;
        
        public DateTime JoinedAt { get; set; } = DateTime.UtcNow;
        
        // Navigation properties
        [ForeignKey("CampaignId")]
        public virtual Campaign? Campaign { get; set; }
        
        [ForeignKey("CharacterId")]
        public virtual Character? Character { get; set; }
    }
} 