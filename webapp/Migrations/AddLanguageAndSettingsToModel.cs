using Microsoft.EntityFrameworkCore.Migrations;

namespace DnDGameMaster.WebApp.Migrations
{
    [Migration("20250611000001_AddLanguageAndSettingsToModel")]
    public partial class AddLanguageAndSettingsToModel : Migration
    {
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // Add Language column to Campaigns
            migrationBuilder.AddColumn<string>(
                name: "Language",
                table: "Campaigns",
                type: "character varying(50)",
                maxLength: 50,
                nullable: false,
                defaultValue: "English");

            // Rename Setting column to Settings and change its max length
            migrationBuilder.RenameColumn(
                name: "Setting",
                table: "Campaigns",
                newName: "Settings");

            migrationBuilder.AlterColumn<string>(
                name: "Settings",
                table: "Campaigns",
                type: "character varying(500)",
                maxLength: 500,
                nullable: true,
                oldClrType: typeof(string),
                oldType: "character varying(50)",
                oldMaxLength: 50,
                oldNullable: true);
        }

        protected override void Down(MigrationBuilder migrationBuilder)
        {
            // Revert Settings column back to Setting and change max length back
            migrationBuilder.RenameColumn(
                name: "Settings",
                table: "Campaigns",
                newName: "Setting");

            migrationBuilder.AlterColumn<string>(
                name: "Setting",
                table: "Campaigns",
                type: "character varying(50)",
                maxLength: 50,
                nullable: true,
                oldClrType: typeof(string),
                oldType: "character varying(500)",
                oldMaxLength: 500,
                oldNullable: true);

            // Remove Language column
            migrationBuilder.DropColumn(
                name: "Language",
                table: "Campaigns");
        }
    }
} 