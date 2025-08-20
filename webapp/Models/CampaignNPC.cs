using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DnDGameMaster.WebApp.Models
{
    public class CampaignNPC
    {
        [Key]
        public int Id { get; set; }
        
        [Required]
        public int CampaignId { get; set; }
        
        [Required]
        [StringLength(100)]
        public string Name { get; set; } = string.Empty;
        
        [Required]
        [StringLength(50)]
        public string Type { get; set; } = "Humanoid"; // Monster, Ally, Neutral, Enemy, Humanoid
        
        [Required]
        [StringLength(50)]
        public string Race { get; set; } = string.Empty;
        
        [StringLength(50)]
        public string? Class { get; set; } = string.Empty;
        
        [Range(1, 30)]
        public int Level { get; set; } = 1;
        
        // Points de vie séparés en max et actuel
        [Range(1, 1000)]
        public int MaxHitPoints { get; set; } = 10;
        
        [Range(0, 1000)]
        public int CurrentHitPoints { get; set; } = 10;
        
        [Range(10, 30)]
        public int ArmorClass { get; set; } = 10;
        
        // Statistiques de base D&D
        [Range(1, 30)]
        public int Strength { get; set; } = 10;
        
        [Range(1, 30)]
        public int Dexterity { get; set; } = 10;
        
        [Range(1, 30)]
        public int Constitution { get; set; } = 10;
        
        [Range(1, 30)]
        public int Intelligence { get; set; } = 10;
        
        [Range(1, 30)]
        public int Wisdom { get; set; } = 10;
        
        [Range(1, 30)]
        public int Charisma { get; set; } = 10;
        
        [StringLength(50)]
        public string? Alignment { get; set; } = string.Empty;
        
        [StringLength(2000)]
        public string? Description { get; set; } = string.Empty;
        
        [StringLength(100)]
        public string? CurrentLocation { get; set; } = string.Empty;
        
        [StringLength(20)]
        public string Status { get; set; } = "Active"; // Active, Dead, Missing, Captured, Fled
        
        [StringLength(500)]
        public string? Notes { get; set; } = string.Empty;
        
        [StringLength(1000)]
        public string? PortraitUrl { get; set; } = string.Empty;
        
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        
        public DateTime? UpdatedAt { get; set; }
        
        // Navigation properties
        [ForeignKey("CampaignId")]
        public virtual Campaign? Campaign { get; set; }
        
        // Propriétés calculées pour les modificateurs
        public int StrengthModifier => (Strength - 10) / 2;
        public int DexterityModifier => (Dexterity - 10) / 2;
        public int ConstitutionModifier => (Constitution - 10) / 2;
        public int IntelligenceModifier => (Intelligence - 10) / 2;
        public int WisdomModifier => (Wisdom - 10) / 2;
        public int CharismaModifier => (Charisma - 10) / 2;
    }
} 