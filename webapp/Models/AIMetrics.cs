using System;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DnDGameMaster.WebApp.Models
{
    public class AIMetrics
    {
        [Key]
        public int Id { get; set; }

        [Required]
        [StringLength(100)]
        public string MetricName { get; set; } = string.Empty;

        [Required]
        [Column(TypeName = "decimal(10,4)")]
        public decimal MetricValue { get; set; }

        [StringLength(20)]
        public string? MetricUnit { get; set; } = string.Empty;

        [StringLength(100)]
        public string? ModelName { get; set; } = string.Empty;

        [StringLength(50)]
        public string? Provider { get; set; } = string.Empty;

        public int? CampaignId { get; set; }

        public string? UserId { get; set; } = string.Empty;

        [Required]
        public DateTime Timestamp { get; set; } = DateTime.UtcNow;

        [Column(TypeName = "jsonb")]
        public string? Metadata { get; set; } = string.Empty;

        // Navigation properties
        [ForeignKey("CampaignId")]
        public virtual Campaign? Campaign { get; set; }
    }
} 