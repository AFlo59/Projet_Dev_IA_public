using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using System;

namespace DnDGameMaster.WebApp.Models
{
    public class CampaignMessage
    {
        [Key]
        public int Id { get; set; }
        
        [Required]
        public int CampaignId { get; set; }
        
        [Required]
        [StringLength(20)]
        public string MessageType { get; set; } = "user"; // user, ai, system
        
        [Required]
        [StringLength(5000)]
        public string Content { get; set; } = string.Empty;
        
        public string? UserId { get; set; } = string.Empty;
        
        public int? CharacterId { get; set; }
        
        // Map the database column SentAt to this property
        [Column("SentAt")]
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        
        // Add a SentAt property that maps to the same column but allows direct access
        [NotMapped]
        public DateTime SentAt 
        { 
            get { return CreatedAt; } 
            set { CreatedAt = value; } 
        }
        
        public int? SessionId { get; set; }
        
        // Additional properties for test compatibility
        [NotMapped]
        public string UserInput 
        { 
            get { return MessageType == "user" ? Content : string.Empty; } 
            set { if (MessageType == "user") Content = value; } 
        }
        
        [NotMapped]
        public string AIResponse 
        { 
            get { return MessageType == "ai" || MessageType == "gm" ? Content : string.Empty; } 
            set { if (MessageType == "ai" || MessageType == "gm") Content = value; } 
        }
        
        // Navigation properties
        [ForeignKey("CampaignId")]
        public virtual Campaign? Campaign { get; set; }
        
        [ForeignKey("UserId")]
        public virtual ApplicationUser? User { get; set; }
        
        [ForeignKey("CharacterId")]
        public virtual Character? Character { get; set; }
        
        [ForeignKey("SessionId")]
        public virtual CampaignSession? Session { get; set; }
    }
} 