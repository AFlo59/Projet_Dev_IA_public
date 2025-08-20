using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DnDGameMaster.WebApp.Models
{
    public class CampaignSession
    {
        [Key]
        public int Id { get; set; }
        
        [Required]
        public int CampaignId { get; set; }
        
        [Required]
        [StringLength(100)]
        public string Name { get; set; } = string.Empty;
        
        [StringLength(2000)]
        public string? Description { get; set; } = string.Empty;
        
        [StringLength(20)]
        public string Status { get; set; } = "Scheduled"; // Scheduled, Active, Completed
        
        public DateTime StartedAt { get; set; } = DateTime.UtcNow;
        
        public DateTime? EndedAt { get; set; }
        
        [StringLength(5000)]
        public string? Summary { get; set; } = string.Empty;
        
        // Navigation properties
        [ForeignKey("CampaignId")]
        public virtual Campaign? Campaign { get; set; }
    }
} 