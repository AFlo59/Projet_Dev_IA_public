using DnDGameMaster.WebApp.Models;
using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore;

namespace DnDGameMaster.WebApp.Data
{
    public class ApplicationDbContext : IdentityDbContext<ApplicationUser>
    {
        public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options)
            : base(options)
        {
        }

        public DbSet<Campaign> Campaigns { get; set; } = null!;
        public DbSet<Character> Characters { get; set; } = null!;
        public DbSet<CampaignCharacter> CampaignCharacters { get; set; } = null!;
        public DbSet<CampaignSession> CampaignSessions { get; set; } = null!;
        public DbSet<CampaignMessage> CampaignMessages { get; set; } = null!;
        public DbSet<CampaignNPC> CampaignNPCs { get; set; } = null!;
        public DbSet<CampaignLocation> CampaignLocations { get; set; } = null!;
        public DbSet<CampaignQuest> CampaignQuests { get; set; } = null!;
        
        // Monitoring IA tables
        public DbSet<AIMetrics> AIMetrics { get; set; } = null!;
        public DbSet<AILogs> AILogs { get; set; } = null!;
        public DbSet<AIAlerts> AIAlerts { get; set; } = null!;
        public DbSet<AIAlertThresholds> AIAlertThresholds { get; set; } = null!;
        public DbSet<AICosts> AICosts { get; set; } = null!;
        public DbSet<AIModelPerformance> AIModelPerformance { get; set; } = null!;

        protected override void OnModelCreating(ModelBuilder builder)
        {
            base.OnModelCreating(builder);

            // Configure relationships
            builder.Entity<CampaignCharacter>()
                .HasOne(cc => cc.Campaign)
                .WithMany(c => c.CampaignCharacters)
                .HasForeignKey(cc => cc.CampaignId)
                .OnDelete(DeleteBehavior.Cascade);

            builder.Entity<CampaignCharacter>()
                .HasOne(cc => cc.Character)
                .WithMany(c => c.CampaignCharacters)
                .HasForeignKey(cc => cc.CharacterId)
                .OnDelete(DeleteBehavior.Cascade);

            builder.Entity<CampaignSession>()
                .HasOne(s => s.Campaign)
                .WithMany(c => c.Sessions)
                .HasForeignKey(s => s.CampaignId)
                .OnDelete(DeleteBehavior.Cascade);

            builder.Entity<CampaignMessage>()
                .HasOne(m => m.Campaign)
                .WithMany(c => c.Messages)
                .HasForeignKey(m => m.CampaignId)
                .OnDelete(DeleteBehavior.Cascade);

            // Message can have a character (optional)
            builder.Entity<CampaignMessage>()
                .HasOne(m => m.Character)
                .WithMany()
                .HasForeignKey(m => m.CharacterId)
                .IsRequired(false)
                .OnDelete(DeleteBehavior.SetNull);

            // Configure CampaignNPC relationships
            builder.Entity<CampaignNPC>()
                .HasOne(n => n.Campaign)
                .WithMany()
                .HasForeignKey(n => n.CampaignId)
                .OnDelete(DeleteBehavior.Cascade);

            // Configure CampaignLocation relationships
            builder.Entity<CampaignLocation>()
                .HasOne(l => l.Campaign)
                .WithMany()
                .HasForeignKey(l => l.CampaignId)
                .OnDelete(DeleteBehavior.Cascade);

            // Self-referencing relationship for parent location
            builder.Entity<CampaignLocation>()
                .HasOne(l => l.ParentLocation)
                .WithMany(l => l.SubLocations)
                .HasForeignKey(l => l.ParentLocationId)
                .IsRequired(false)
                .OnDelete(DeleteBehavior.SetNull);

            // Configure CampaignQuest relationships
            builder.Entity<CampaignQuest>()
                .HasOne(q => q.Campaign)
                .WithMany()
                .HasForeignKey(q => q.CampaignId)
                .OnDelete(DeleteBehavior.Cascade);

            builder.Entity<CampaignQuest>()
                .HasOne(q => q.Location)
                .WithMany(l => l.Quests)
                .HasForeignKey(q => q.LocationId)
                .IsRequired(false)
                .OnDelete(DeleteBehavior.SetNull);
        }
    }
} 