namespace DnDGameMaster.WebApp.Services.Email
{
    public interface IEmailService
    {
        Task SendEmailAsync(string to, string subject, string htmlMessage);
        Task SendEmailConfirmationAsync(string to, string userName, string confirmationLink);
        Task SendPasswordResetAsync(string to, string userName, string resetLink);
        Task SendWelcomeEmailAsync(string to, string userName);
    }
} 