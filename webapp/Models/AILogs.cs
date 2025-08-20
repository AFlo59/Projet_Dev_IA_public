using System;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DnDGameMaster.WebApp.Models
{
    public class AILogs
    {
        [Key]
        public int Id { get; set; }

        [Required]
        [StringLength(20)]
        public string LogLevel { get; set; } = "INFO";

        [Required]
        public string LogMessage { get; set; } = string.Empty;

        [StringLength(50)]
        public string? LogCategory { get; set; } = string.Empty;

        [StringLength(100)]
        public string? ModelName { get; set; } = string.Empty;

        [StringLength(50)]
        public string? Provider { get; set; } = string.Empty;

        public int? CampaignId { get; set; }

        public string? UserId { get; set; } = string.Empty;

        [StringLength(100)]
        public string? RequestId { get; set; } = string.Empty;

        public int? ResponseTime { get; set; }

        public int? TokensUsed { get; set; }

        [Column(TypeName = "decimal(10,6)")]
        public decimal? Cost { get; set; }

        [Required]
        public DateTime Timestamp { get; set; } = DateTime.UtcNow;

        public string? StackTrace { get; set; } = string.Empty;

        [Column(TypeName = "jsonb")]
        public string? Metadata { get; set; } = string.Empty;

        // Navigation properties
        [ForeignKey("CampaignId")]
        public virtual Campaign? Campaign { get; set; }
    }
} 