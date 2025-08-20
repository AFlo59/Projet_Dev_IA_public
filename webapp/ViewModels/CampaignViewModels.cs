using System.ComponentModel.DataAnnotations;
using DnDGameMaster.WebApp.Models;

namespace DnDGameMaster.WebApp.ViewModels
{
    public class CampaignCreateViewModel
    {
        [Required]
        [StringLength(100)]
        public string Name { get; set; } = string.Empty;

        [StringLength(1000)]
        public string? Description { get; set; } = string.Empty;

        [StringLength(500)]
        public string? Settings { get; set; } = string.Empty;

        [Required]
        [StringLength(50)]
        public string Language { get; set; } = "English";

        [Range(1, 20)]
        public int StartingLevel { get; set; } = 1;

        [Range(1, 10)]
        public int MaxPlayers { get; set; } = 4;

        public bool IsPublic { get; set; } = false;
    }

    public class CampaignIndexViewModel
    {
        public List<Campaign> UserCampaigns { get; set; } = new List<Campaign>();
        public List<Campaign> PublicCampaigns { get; set; } = new List<Campaign>();
    }

    public class CampaignDetailsViewModel
    {
        public Campaign Campaign { get; set; } = new Campaign();
        public List<CampaignCharacter> Characters { get; set; } = new List<CampaignCharacter>();
        public List<CampaignSession> Sessions { get; set; } = new List<CampaignSession>();
        public bool IsOwner { get; set; }
        public bool UserInCampaign { get; set; }
        public bool CanEdit { get; set; }
        public bool CanPlay { get; set; }
    }

    public class SendMessageViewModel
    {
        [Required]
        public int CampaignId { get; set; }

        [Required]
        public int CharacterId { get; set; }

        [Required]
        [StringLength(1000)]
        public string Content { get; set; } = string.Empty;
    }
} 