using System;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DnDGameMaster.WebApp.Models
{
    public class AICosts
    {
        [Key]
        public int Id { get; set; }

        [Required]
        [StringLength(50)]
        public string Provider { get; set; } = string.Empty;

        [Required]
        [StringLength(100)]
        public string ModelName { get; set; } = string.Empty;

        [Required]
        [StringLength(50)]
        public string OperationType { get; set; } = string.Empty; // 'COMPLETION', 'EMBEDDING', 'IMAGE_GENERATION'

        [Required]
        public int TokensUsed { get; set; } = 0;

        [Required]
        [Column(TypeName = "decimal(10,8)")]
        public decimal CostPerToken { get; set; }

        [Required]
        [Column(TypeName = "decimal(10,6)")]
        public decimal TotalCost { get; set; }

        public int? CampaignId { get; set; }

        public string? UserId { get; set; } = string.Empty;

        [Required]
        public DateTime Date { get; set; } = DateTime.UtcNow.Date;

        [Required]
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

        // Navigation properties
        [ForeignKey("CampaignId")]
        public virtual Campaign? Campaign { get; set; }
    }
} 