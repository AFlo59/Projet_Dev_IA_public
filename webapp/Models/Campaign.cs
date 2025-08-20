using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DnDGameMaster.WebApp.Models
{
    public class Campaign
    {
        [Key]
        public int Id { get; set; }
        
        [Required]
        [StringLength(100)]
        public string Name { get; set; } = string.Empty;

        [Required]
        [StringLength(50)]
        public string Language { get; set; } = "English";
        
        [StringLength(1000)]
        public string? Description { get; set; } = string.Empty;
        
        [StringLength(500)]
        public string? Settings { get; set; } = string.Empty; // Changed to plural for multiple settings
        
        [Range(1, 20)]
        public int StartingLevel { get; set; } = 1;
        
        [Range(1, 10)]
        public int MaxPlayers { get; set; } = 5;
        
        public bool IsPublic { get; set; } = false;
        
        [StringLength(20)]
        public string Status { get; set; } = "Active"; // Active, Completed, Paused
        
        // New fields for content generation
        [StringLength(20)]
        public string ContentGenerationStatus { get; set; } = "NotStarted"; // NotStarted, InProgress, Completed, Failed, ImagesInProgress, ImagesCompleted
        
        public DateTime? ContentGenerationStartedAt { get; set; }
        
        public DateTime? ContentGenerationCompletedAt { get; set; }
        
        [StringLength(1000)]
        public string? ContentGenerationError { get; set; } = string.Empty;
        
        // New fields for character generation tracking
        [StringLength(20)]
        public string CharacterGenerationStatus { get; set; } = "NotStarted"; // NotStarted, InProgress, Completed, Failed
        
        public DateTime? CharacterGenerationStartedAt { get; set; }
        
        public DateTime? CharacterGenerationCompletedAt { get; set; }
        
        [StringLength(1000)]
        public string? CharacterGenerationError { get; set; } = string.Empty;
        
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        
        public DateTime? UpdatedAt { get; set; }
        
        public string OwnerId { get; set; } = string.Empty;
        
        [ForeignKey("OwnerId")]
        public virtual ApplicationUser? Owner { get; set; }
        
        // Navigation properties
        public virtual ICollection<CampaignCharacter> CampaignCharacters { get; set; } = new List<CampaignCharacter>();
        public virtual ICollection<CampaignSession> Sessions { get; set; } = new List<CampaignSession>();
        public virtual ICollection<CampaignMessage> Messages { get; set; } = new List<CampaignMessage>();
    }
} 