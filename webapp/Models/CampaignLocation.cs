using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DnDGameMaster.WebApp.Models
{
    public class CampaignLocation
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
        public string Type { get; set; } = "Location"; // City, Town, Village, Dungeon, Forest, Tavern, Shop, Castle, Temple, etc.
        
        [StringLength(2000)]
        public string? Description { get; set; } = string.Empty;
        
        [StringLength(500)]
        public string? ShortDescription { get; set; } = string.Empty; // Brief description for quick reference
        
        public int? ParentLocationId { get; set; } // For nested locations (e.g., tavern inside a city)
        
        public bool IsDiscovered { get; set; } = false; // Whether players have discovered this location
        
        public bool IsAccessible { get; set; } = true; // Whether players can access this location
        
        [StringLength(50)]
        public string? Climate { get; set; } = string.Empty; // Cold, Temperate, Hot, Tropical, etc.
        
        [StringLength(50)]
        public string? Terrain { get; set; } = string.Empty; // Forest, Mountain, Plains, Desert, Swamp, etc.
        
        [StringLength(50)]
        public string? Population { get; set; } = string.Empty; // None, Small, Medium, Large, Huge
        
        [StringLength(1000)]
        public string? Notes { get; set; } = string.Empty;
        
        [StringLength(1000)]
        public string? ImageUrl { get; set; } = string.Empty;
        
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        
        public DateTime? UpdatedAt { get; set; }
        
        // Navigation properties
        [ForeignKey("CampaignId")]
        public virtual Campaign? Campaign { get; set; }
        
        [ForeignKey("ParentLocationId")]
        public virtual CampaignLocation? ParentLocation { get; set; }
        
        public virtual ICollection<CampaignLocation> SubLocations { get; set; } = new List<CampaignLocation>();
        
        public virtual ICollection<CampaignQuest> Quests { get; set; } = new List<CampaignQuest>();
    }
} 