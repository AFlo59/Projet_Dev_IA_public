using System;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DnDGameMaster.WebApp.Models
{
    public class AIAlerts
    {
        [Key]
        public int Id { get; set; }

        [Required]
        [StringLength(50)]
        public string AlertType { get; set; } = string.Empty;

        [Required]
        [StringLength(20)]
        public string AlertLevel { get; set; } = "WARNING";

        [Required]
        public string AlertMessage { get; set; } = string.Empty;

        [StringLength(200)]
        public string? AlertTitle { get; set; } = string.Empty;

        [Required]
        public bool IsResolved { get; set; } = false;

        public DateTime? ResolvedAt { get; set; }

        public string? ResolvedBy { get; set; } = string.Empty;

        public int? CampaignId { get; set; }

        public string? UserId { get; set; } = string.Empty;

        [Required]
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

        public DateTime? UpdatedAt { get; set; }

        [Column(TypeName = "jsonb")]
        public string? Metadata { get; set; } = string.Empty;

        // Navigation properties
        [ForeignKey("CampaignId")]
        public virtual Campaign? Campaign { get; set; }
    }
} 