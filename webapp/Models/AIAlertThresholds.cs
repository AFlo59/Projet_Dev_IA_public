using System;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DnDGameMaster.WebApp.Models
{
    public class AIAlertThresholds
    {
        [Key]
        public int Id { get; set; }

        [Required]
        [StringLength(100)]
        public string MetricName { get; set; } = string.Empty;

        [Required]
        [StringLength(20)]
        public string ThresholdType { get; set; } = string.Empty; // 'MIN', 'MAX', 'AVERAGE'

        [Required]
        [Column(TypeName = "decimal(10,4)")]
        public decimal ThresholdValue { get; set; }

        [Required]
        [StringLength(20)]
        public string AlertLevel { get; set; } = "WARNING";

        [Required]
        public bool IsActive { get; set; } = true;

        public string? Description { get; set; } = string.Empty;

        [Required]
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

        public DateTime? UpdatedAt { get; set; }
    }
} 