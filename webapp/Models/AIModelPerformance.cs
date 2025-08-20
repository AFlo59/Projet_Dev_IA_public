using System;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DnDGameMaster.WebApp.Models
{
    public class AIModelPerformance
    {
        [Key]
        public int Id { get; set; }

        [Required]
        [StringLength(100)]
        public string ModelName { get; set; } = string.Empty;

        [Required]
        [StringLength(50)]
        public string Provider { get; set; } = string.Empty;

        [Required]
        public int AverageResponseTime { get; set; }

        [Required]
        [Column(TypeName = "decimal(5,2)")]
        public decimal SuccessRate { get; set; }

        [Required]
        [Column(TypeName = "decimal(5,2)")]
        public decimal ErrorRate { get; set; }

        [Required]
        public int TotalRequests { get; set; } = 0;

        [Required]
        public int TotalErrors { get; set; } = 0;

        [Required]
        public DateTime Date { get; set; } = DateTime.UtcNow.Date;

        [Required]
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

        public DateTime? UpdatedAt { get; set; }
    }
} 