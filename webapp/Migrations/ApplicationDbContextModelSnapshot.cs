using DnDGameMaster.WebApp.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Storage.ValueConversion;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

namespace DnDGameMaster.WebApp.Migrations
{
    [DbContext(typeof(ApplicationDbContext))]
    partial class ApplicationDbContextModelSnapshot : ModelSnapshot
    {
        protected override void BuildModel(ModelBuilder modelBuilder)
        {
#pragma warning disable 612, 618
            modelBuilder
                .HasAnnotation("ProductVersion", "6.0.16")
                .HasAnnotation("Relational:MaxIdentifierLength", 63);

            NpgsqlModelBuilderExtensions.UseIdentityByDefaultColumns(modelBuilder);

            // Campaign entity configuration
            modelBuilder.Entity("DnDGameMaster.WebApp.Models.Campaign", b =>
            {
                b.Property<int>("Id")
                    .ValueGeneratedOnAdd()
                    .HasColumnType("integer");

                NpgsqlPropertyBuilderExtensions.UseIdentityByDefaultColumn(b.Property<int>("Id"));

                b.Property<DateTime>("CreatedAt")
                    .HasColumnType("timestamp with time zone");

                b.Property<string>("Description")
                    .HasMaxLength(1000)
                    .HasColumnType("character varying(1000)");

                b.Property<bool>("IsPublic")
                    .HasColumnType("boolean");
                    
                b.Property<string>("Language")
                    .IsRequired()
                    .HasMaxLength(50)
                    .HasColumnType("character varying(50)");

                b.Property<int>("MaxPlayers")
                    .HasColumnType("integer");

                b.Property<string>("Name")
                    .IsRequired()
                    .HasMaxLength(100)
                    .HasColumnType("character varying(100)");

                b.Property<string>("OwnerId")
                    .IsRequired()
                    .HasColumnType("text");

                b.Property<string>("Settings")
                    .HasMaxLength(500)
                    .HasColumnType("character varying(500)");

                b.Property<int>("StartingLevel")
                    .HasColumnType("integer");

                b.Property<string>("Status")
                    .IsRequired()
                    .HasMaxLength(20)
                    .HasColumnType("character varying(20)");

                b.Property<DateTime?>("UpdatedAt")
                    .HasColumnType("timestamp with time zone");

                // Content generation fields
                b.Property<string>("ContentGenerationStatus")
                    .IsRequired()
                    .HasMaxLength(20)
                    .HasColumnType("character varying(20)");

                b.Property<DateTime?>("ContentGenerationStartedAt")
                    .HasColumnType("timestamp with time zone");

                b.Property<DateTime?>("ContentGenerationCompletedAt")
                    .HasColumnType("timestamp with time zone");

                b.Property<string>("ContentGenerationError")
                    .HasMaxLength(1000)
                    .HasColumnType("character varying(1000)");

                b.HasKey("Id");

                b.HasIndex("OwnerId");

                b.ToTable("Campaigns");
            });
            
            // Character entity configuration
            modelBuilder.Entity("DnDGameMaster.WebApp.Models.Character", b =>
            {
                b.Property<int>("Id")
                    .ValueGeneratedOnAdd()
                    .HasColumnType("integer");

                NpgsqlPropertyBuilderExtensions.UseIdentityByDefaultColumn(b.Property<int>("Id"));

                b.Property<string>("Alignment")
                    .HasMaxLength(20)
                    .HasColumnType("character varying(20)");

                b.Property<string>("Background")
                    .HasMaxLength(50)
                    .HasColumnType("character varying(50)");

                b.Property<int>("Charisma")
                    .HasColumnType("integer");

                b.Property<string>("Class")
                    .IsRequired()
                    .HasMaxLength(50)
                    .HasColumnType("character varying(50)");

                b.Property<int>("Constitution")
                    .HasColumnType("integer");

                b.Property<DateTime>("CreatedAt")
                    .HasColumnType("timestamp with time zone");

                b.Property<string>("Description")
                    .HasColumnType("text");

                b.Property<int>("Dexterity")
                    .HasColumnType("integer");

                b.Property<string>("Equipment")
                    .HasColumnType("text");

                b.Property<int>("Intelligence")
                    .HasColumnType("integer");

                b.Property<int>("Level")
                    .HasColumnType("integer");

                b.Property<string>("Name")
                    .IsRequired()
                    .HasMaxLength(100)
                    .HasColumnType("character varying(100)");

                b.Property<string>("PortraitUrl")
                    .HasColumnType("text");

                b.Property<string>("Race")
                    .IsRequired()
                    .HasMaxLength(50)
                    .HasColumnType("character varying(50)");

                b.Property<int>("Strength")
                    .HasColumnType("integer");

                b.Property<DateTime?>("UpdatedAt")
                    .HasColumnType("timestamp with time zone");

                b.Property<string>("UserId")
                    .IsRequired()
                    .HasColumnType("text");

                b.HasKey("Id");

                b.HasIndex("UserId");

                b.ToTable("Characters");
            });

            // CampaignCharacter entity configuration
            modelBuilder.Entity("DnDGameMaster.WebApp.Models.CampaignCharacter", b =>
            {
                b.Property<int>("Id")
                    .ValueGeneratedOnAdd()
                    .HasColumnType("integer");

                NpgsqlPropertyBuilderExtensions.UseIdentityByDefaultColumn(b.Property<int>("Id"));

                b.Property<int>("CampaignId")
                    .HasColumnType("integer");

                b.Property<int>("CharacterId")
                    .HasColumnType("integer");

                b.Property<string>("CurrentLocation")
                    .HasMaxLength(100)
                    .HasColumnType("character varying(100)");

                b.Property<bool>("IsActive")
                    .HasColumnType("boolean");

                b.Property<DateTime>("JoinedAt")
                    .HasColumnType("timestamp with time zone");

                b.HasKey("Id");

                b.HasIndex("CampaignId");

                b.HasIndex("CharacterId");

                b.HasIndex("CampaignId", "CharacterId")
                    .IsUnique();

                b.ToTable("CampaignCharacters");
            });

            // CampaignSession entity configuration
            modelBuilder.Entity("DnDGameMaster.WebApp.Models.CampaignSession", b =>
            {
                b.Property<int>("Id")
                    .ValueGeneratedOnAdd()
                    .HasColumnType("integer");

                NpgsqlPropertyBuilderExtensions.UseIdentityByDefaultColumn(b.Property<int>("Id"));

                b.Property<int>("CampaignId")
                    .HasColumnType("integer");

                b.Property<string>("Description")
                    .HasColumnType("text");

                b.Property<DateTime?>("EndedAt")
                    .HasColumnType("timestamp with time zone");

                b.Property<string>("Name")
                    .HasMaxLength(100)
                    .HasColumnType("character varying(100)");

                b.Property<DateTime>("StartedAt")
                    .HasColumnType("timestamp with time zone");

                b.Property<string>("Status")
                    .HasMaxLength(20)
                    .HasColumnType("character varying(20)");

                b.Property<string>("Summary")
                    .HasColumnType("text");

                b.HasKey("Id");

                b.HasIndex("CampaignId");

                b.ToTable("CampaignSessions");
            });

            // CampaignMessage entity configuration
            modelBuilder.Entity("DnDGameMaster.WebApp.Models.CampaignMessage", b =>
            {
                b.Property<int>("Id")
                    .ValueGeneratedOnAdd()
                    .HasColumnType("integer");

                NpgsqlPropertyBuilderExtensions.UseIdentityByDefaultColumn(b.Property<int>("Id"));

                b.Property<int>("CampaignId")
                    .HasColumnType("integer");

                b.Property<int?>("CharacterId")
                    .HasColumnType("integer");

                b.Property<string>("Content")
                    .IsRequired()
                    .HasColumnType("text");

                b.Property<string>("MessageType")
                    .IsRequired()
                    .HasMaxLength(20)
                    .HasColumnType("character varying(20)");

                b.Property<int?>("SessionId")
                    .HasColumnType("integer");

                b.Property<DateTime>("SentAt")
                    .HasColumnType("timestamp with time zone");

                b.Property<string>("UserId")
                    .HasColumnType("text");

                b.HasKey("Id");

                b.HasIndex("CampaignId");

                b.HasIndex("CharacterId");

                b.HasIndex("SessionId");

                b.ToTable("CampaignMessages");
            });

            // ApplicationUser entity configuration
            modelBuilder.Entity("DnDGameMaster.WebApp.Models.ApplicationUser", b =>
            {
                b.Property<string>("Id")
                    .HasColumnType("text");

                b.Property<int>("AccessFailedCount")
                    .HasColumnType("integer");

                b.Property<string>("ConcurrencyStamp")
                    .IsConcurrencyToken()
                    .HasColumnType("text");

                b.Property<DateTime>("Created")
                    .HasColumnType("timestamp with time zone");

                b.Property<string>("Email")
                    .HasMaxLength(256)
                    .HasColumnType("character varying(256)");

                b.Property<bool>("EmailConfirmed")
                    .HasColumnType("boolean");

                b.Property<string>("FirstName")
                    .HasMaxLength(50)
                    .HasColumnType("character varying(50)");

                b.Property<DateTime?>("LastActive")
                    .HasColumnType("timestamp with time zone");

                b.Property<string>("LastName")
                    .HasMaxLength(50)
                    .HasColumnType("character varying(50)");

                b.Property<bool>("LockoutEnabled")
                    .HasColumnType("boolean");

                b.Property<DateTimeOffset?>("LockoutEnd")
                    .HasColumnType("timestamp with time zone");

                b.Property<string>("NormalizedEmail")
                    .HasMaxLength(256)
                    .HasColumnType("character varying(256)");

                b.Property<string>("NormalizedUserName")
                    .HasMaxLength(256)
                    .HasColumnType("character varying(256)");

                b.Property<string>("PasswordHash")
                    .HasColumnType("text");

                b.Property<string>("PhoneNumber")
                    .HasColumnType("text");

                b.Property<bool>("PhoneNumberConfirmed")
                    .HasColumnType("boolean");

                b.Property<string>("SecurityStamp")
                    .HasColumnType("text");

                b.Property<bool>("TwoFactorEnabled")
                    .HasColumnType("boolean");

                b.Property<string>("UserName")
                    .HasMaxLength(256)
                    .HasColumnType("character varying(256)");

                b.HasKey("Id");

                b.HasIndex("NormalizedEmail")
                    .IsUnique()
                    .HasDatabaseName("EmailIndex");

                b.HasIndex("NormalizedUserName")
                    .IsUnique()
                    .HasDatabaseName("UserNameIndex");

                b.ToTable("AspNetUsers");
            });

            // IdentityRole entity configuration
            modelBuilder.Entity("Microsoft.AspNetCore.Identity.IdentityRole", b =>
            {
                b.Property<string>("Id")
                    .HasColumnType("text");

                b.Property<string>("ConcurrencyStamp")
                    .IsConcurrencyToken()
                    .HasColumnType("text");

                b.Property<string>("Name")
                    .HasMaxLength(256)
                    .HasColumnType("character varying(256)");

                b.Property<string>("NormalizedName")
                    .HasMaxLength(256)
                    .HasColumnType("character varying(256)");

                b.HasKey("Id");

                b.HasIndex("NormalizedName")
                    .IsUnique()
                    .HasDatabaseName("RoleNameIndex");

                b.ToTable("AspNetRoles");
            });

            // IdentityUserClaim entity configuration
            modelBuilder.Entity("Microsoft.AspNetCore.Identity.IdentityUserClaim<string>", b =>
            {
                b.Property<int>("Id")
                    .ValueGeneratedOnAdd()
                    .HasColumnType("integer");

                NpgsqlPropertyBuilderExtensions.UseIdentityByDefaultColumn(b.Property<int>("Id"));

                b.Property<string>("ClaimType")
                    .HasColumnType("text");

                b.Property<string>("ClaimValue")
                    .HasColumnType("text");

                b.Property<string>("UserId")
                    .IsRequired()
                    .HasColumnType("text");

                b.HasKey("Id");

                b.HasIndex("UserId");

                b.ToTable("AspNetUserClaims");
            });

            // IdentityUserLogin entity configuration
            modelBuilder.Entity("Microsoft.AspNetCore.Identity.IdentityUserLogin<string>", b =>
            {
                b.Property<string>("LoginProvider")
                    .HasColumnType("text");

                b.Property<string>("ProviderKey")
                    .HasColumnType("text");

                b.Property<string>("ProviderDisplayName")
                    .HasColumnType("text");

                b.Property<string>("UserId")
                    .IsRequired()
                    .HasColumnType("text");

                b.HasKey("LoginProvider", "ProviderKey");

                b.HasIndex("UserId");

                b.ToTable("AspNetUserLogins");
            });

            // IdentityUserRole entity configuration
            modelBuilder.Entity("Microsoft.AspNetCore.Identity.IdentityUserRole<string>", b =>
            {
                b.Property<string>("UserId")
                    .HasColumnType("text");

                b.Property<string>("RoleId")
                    .HasColumnType("text");

                b.HasKey("UserId", "RoleId");

                b.HasIndex("RoleId");

                b.ToTable("AspNetUserRoles");
            });

            // IdentityUserToken entity configuration
            modelBuilder.Entity("Microsoft.AspNetCore.Identity.IdentityUserToken<string>", b =>
            {
                b.Property<string>("UserId")
                    .HasColumnType("text");

                b.Property<string>("LoginProvider")
                    .HasColumnType("text");

                b.Property<string>("Name")
                    .HasColumnType("text");

                b.Property<string>("Value")
                    .HasColumnType("text");

                b.HasKey("UserId", "LoginProvider", "Name");

                b.ToTable("AspNetUserTokens");
            });

            // IdentityRoleClaim entity configuration
            modelBuilder.Entity("Microsoft.AspNetCore.Identity.IdentityRoleClaim<string>", b =>
            {
                b.Property<int>("Id")
                    .ValueGeneratedOnAdd()
                    .HasColumnType("integer");

                NpgsqlPropertyBuilderExtensions.UseIdentityByDefaultColumn(b.Property<int>("Id"));

                b.Property<string>("ClaimType")
                    .HasColumnType("text");

                b.Property<string>("ClaimValue")
                    .HasColumnType("text");

                b.Property<string>("RoleId")
                    .IsRequired()
                    .HasColumnType("text");

                b.HasKey("Id");

                b.HasIndex("RoleId");

                b.ToTable("AspNetRoleClaims");
            });

            // Relationships
            modelBuilder.Entity("DnDGameMaster.WebApp.Models.Campaign", b =>
            {
                b.HasOne("DnDGameMaster.WebApp.Models.ApplicationUser", "Owner")
                    .WithMany()
                    .HasForeignKey("OwnerId")
                    .OnDelete(DeleteBehavior.Cascade)
                    .IsRequired();
            });

            modelBuilder.Entity("DnDGameMaster.WebApp.Models.Character", b =>
            {
                b.HasOne("DnDGameMaster.WebApp.Models.ApplicationUser", "User")
                    .WithMany()
                    .HasForeignKey("UserId")
                    .OnDelete(DeleteBehavior.Cascade)
                    .IsRequired();
            });

            modelBuilder.Entity("DnDGameMaster.WebApp.Models.CampaignCharacter", b =>
            {
                b.HasOne("DnDGameMaster.WebApp.Models.Campaign", "Campaign")
                    .WithMany("CampaignCharacters")
                    .HasForeignKey("CampaignId")
                    .OnDelete(DeleteBehavior.Cascade)
                    .IsRequired();

                b.HasOne("DnDGameMaster.WebApp.Models.Character", "Character")
                    .WithMany("CampaignCharacters")
                    .HasForeignKey("CharacterId")
                    .OnDelete(DeleteBehavior.Cascade)
                    .IsRequired();
            });

            modelBuilder.Entity("DnDGameMaster.WebApp.Models.CampaignSession", b =>
            {
                b.HasOne("DnDGameMaster.WebApp.Models.Campaign", "Campaign")
                    .WithMany("Sessions")
                    .HasForeignKey("CampaignId")
                    .OnDelete(DeleteBehavior.Cascade)
                    .IsRequired();
            });

            modelBuilder.Entity("DnDGameMaster.WebApp.Models.CampaignMessage", b =>
            {
                b.HasOne("DnDGameMaster.WebApp.Models.Campaign", "Campaign")
                    .WithMany("Messages")
                    .HasForeignKey("CampaignId")
                    .OnDelete(DeleteBehavior.Cascade)
                    .IsRequired();

                b.HasOne("DnDGameMaster.WebApp.Models.Character", "Character")
                    .WithMany()
                    .HasForeignKey("CharacterId");

                b.HasOne("DnDGameMaster.WebApp.Models.CampaignSession", "Session")
                    .WithMany()
                    .HasForeignKey("SessionId");
            });

            modelBuilder.Entity("Microsoft.AspNetCore.Identity.IdentityUserClaim<string>", b =>
            {
                b.HasOne("DnDGameMaster.WebApp.Models.ApplicationUser", null)
                    .WithMany()
                    .HasForeignKey("UserId")
                    .OnDelete(DeleteBehavior.Cascade)
                    .IsRequired();
            });

            modelBuilder.Entity("Microsoft.AspNetCore.Identity.IdentityUserLogin<string>", b =>
            {
                b.HasOne("DnDGameMaster.WebApp.Models.ApplicationUser", null)
                    .WithMany()
                    .HasForeignKey("UserId")
                    .OnDelete(DeleteBehavior.Cascade)
                    .IsRequired();
            });

            modelBuilder.Entity("Microsoft.AspNetCore.Identity.IdentityUserRole<string>", b =>
            {
                b.HasOne("Microsoft.AspNetCore.Identity.IdentityRole", null)
                    .WithMany()
                    .HasForeignKey("RoleId")
                    .OnDelete(DeleteBehavior.Cascade)
                    .IsRequired();

                b.HasOne("DnDGameMaster.WebApp.Models.ApplicationUser", null)
                    .WithMany()
                    .HasForeignKey("UserId")
                    .OnDelete(DeleteBehavior.Cascade)
                    .IsRequired();
            });

            modelBuilder.Entity("Microsoft.AspNetCore.Identity.IdentityUserToken<string>", b =>
            {
                b.HasOne("DnDGameMaster.WebApp.Models.ApplicationUser", null)
                    .WithMany()
                    .HasForeignKey("UserId")
                    .OnDelete(DeleteBehavior.Cascade)
                    .IsRequired();
            });

            modelBuilder.Entity("Microsoft.AspNetCore.Identity.IdentityRoleClaim<string>", b =>
            {
                b.HasOne("Microsoft.AspNetCore.Identity.IdentityRole", null)
                    .WithMany()
                    .HasForeignKey("RoleId")
                    .OnDelete(DeleteBehavior.Cascade)
                    .IsRequired();
            });
#pragma warning restore 612, 618
        }
    }
} 