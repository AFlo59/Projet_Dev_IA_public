using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using System.Text.Json;

namespace DnDGameMaster.WebApp.Models
{
    public class Character
    {
        [Key]
        public int Id { get; set; }
        
        [Required]
        [StringLength(100)]
        public string Name { get; set; } = string.Empty;
        
        [Required]
        [StringLength(50)]
        public string Race { get; set; } = string.Empty;
        
        [StringLength(20)]
        public string? Gender { get; set; } = string.Empty;
        
        [Required]
        [StringLength(50)]
        public string Class { get; set; } = string.Empty;
        
        [Range(1, 20)]
        public int Level { get; set; } = 1;
        
        [StringLength(50)]
        public string? Background { get; set; } = string.Empty;
        
        [StringLength(50)]
        public string? Alignment { get; set; } = string.Empty;
        
        [Range(3, 20)]
        public int Strength { get; set; } = 10;
        
        [Range(3, 20)]
        public int Dexterity { get; set; } = 10;
        
        [Range(3, 20)]
        public int Constitution { get; set; } = 10;
        
        [Range(3, 20)]
        public int Intelligence { get; set; } = 10;
        
        [Range(3, 20)]
        public int Wisdom { get; set; } = 10;
        
        [Range(3, 20)]
        public int Charisma { get; set; } = 10;
        
        // Pour compatibilité avec le code existant
        [NotMapped]
        public string StatsJson
        {
            get => JsonSerializer.Serialize(new Dictionary<string, int>
            {
                { "STR", Strength },
                { "DEX", Dexterity },
                { "CON", Constitution },
                { "INT", Intelligence },
                { "WIS", Wisdom },
                { "CHA", Charisma }
            });
            set
            {
                var stats = JsonSerializer.Deserialize<Dictionary<string, int>>(value) ?? new Dictionary<string, int>();
                if (stats.TryGetValue("STR", out int str)) Strength = str;
                if (stats.TryGetValue("DEX", out int dex)) Dexterity = dex;
                if (stats.TryGetValue("CON", out int con)) Constitution = con;
                if (stats.TryGetValue("INT", out int intel)) Intelligence = intel;
                if (stats.TryGetValue("WIS", out int wis)) Wisdom = wis;
                if (stats.TryGetValue("CHA", out int cha)) Charisma = cha;
            }
        }
        
        [NotMapped]
        public Dictionary<string, int> Stats
        {
            get => new Dictionary<string, int>
            {
                { "STR", Strength },
                { "DEX", Dexterity },
                { "CON", Constitution },
                { "INT", Intelligence },
                { "WIS", Wisdom },
                { "CHA", Charisma }
            };
            set
            {
                if (value.TryGetValue("STR", out int str)) Strength = str;
                if (value.TryGetValue("DEX", out int dex)) Dexterity = dex;
                if (value.TryGetValue("CON", out int con)) Constitution = con;
                if (value.TryGetValue("INT", out int intel)) Intelligence = intel;
                if (value.TryGetValue("WIS", out int wis)) Wisdom = wis;
                if (value.TryGetValue("CHA", out int cha)) Charisma = cha;
            }
        }
        
        [StringLength(2000)]
        public string? Equipment { get; set; } = string.Empty;
        
        [StringLength(2000)]
        public string? Description { get; set; } = string.Empty;
        
        [StringLength(1000)]
        public string? PhysicalAppearance { get; set; } = string.Empty; // Extracted from description for portrait generation
        
        [StringLength(1000)]
        public string? PortraitUrl { get; set; } = string.Empty;
        
        [Required]
        public string UserId { get; set; } = string.Empty;
        
        [ForeignKey("UserId")]
        public virtual ApplicationUser? User { get; set; }
        
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        
        public DateTime? UpdatedAt { get; set; }
        
        // Navigation properties
        public virtual ICollection<CampaignCharacter> CampaignCharacters { get; set; } = new List<CampaignCharacter>();
    }
} 