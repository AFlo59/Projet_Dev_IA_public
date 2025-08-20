using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DnDGameMaster.WebApp.Models
{
    public class CampaignQuest
    {
        [Key]
        public int Id { get; set; }
        
        [Required]
        public int CampaignId { get; set; }
        
        [Required]
        [StringLength(200)]
        public string Title { get; set; } = string.Empty;
        
        [StringLength(2000)]
        public string? Description { get; set; } = string.Empty;
        
        [StringLength(500)]
        public string? ShortDescription { get; set; } = string.Empty; // Brief description for quick reference
        
        [Required]
        [StringLength(50)]
        public string Type { get; set; } = "Side"; // Main, Side, Optional, Personal, Faction
        
        [Required]
        [StringLength(50)]
        public string Status { get; set; } = "Available"; // Available, Active, Completed, Failed, Abandoned
        
        [StringLength(500)]
        public string? Reward { get; set; } = string.Empty;
        
        [StringLength(500)]
        public string? Requirements { get; set; } = string.Empty; // What is needed to start or complete
        
        [Range(1, 20)]
        public int? RequiredLevel { get; set; }
        
        public int? LocationId { get; set; } // Where the quest takes place or starts
        
        [StringLength(100)]
        public string? QuestGiver { get; set; } = string.Empty; // Who gave the quest
        
        [StringLength(50)]
        public string? Difficulty { get; set; } = string.Empty; // Easy, Medium, Hard, Legendary
        
        [StringLength(1000)]
        public string? Notes { get; set; } = string.Empty;
        
        [StringLength(1000)]
        public string? Progress { get; set; } = string.Empty; // Current progress notes
        
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        
        public DateTime? UpdatedAt { get; set; }
        
        public DateTime? CompletedAt { get; set; }
        
        // Navigation properties
        [ForeignKey("CampaignId")]
        public virtual Campaign? Campaign { get; set; }
        
        [ForeignKey("LocationId")]
        public virtual CampaignLocation? Location { get; set; }
    }
} 