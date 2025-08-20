using System.Net;
using System.Net.Mail;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;

namespace DnDGameMaster.WebApp.Services.Email
{
    public class BrevoSmtpEmailService : IEmailService
    {
        private readonly IConfiguration _configuration;
        private readonly ILogger<BrevoSmtpEmailService> _logger;
        
        public BrevoSmtpEmailService(IConfiguration configuration, ILogger<BrevoSmtpEmailService> logger)
        {
            _configuration = configuration;
            _logger = logger;
        }

        public async System.Threading.Tasks.Task SendEmailAsync(string to, string subject, string htmlMessage)
        {
            try
            {
                // Configuration SMTP Brevo
                var smtpServer = "smtp-relay.brevo.com";
                var smtpPort = 587;
                var smtpUsername = "8dd239001@smtp-brevo.com";
                var smtpPassword = "aHFRxC7XgqwKtPTJ"; // Mot de passe SMTP (clé secrète)
                
                var fromEmail = _configuration["BREVO_FROM_EMAIL"] ?? "etudessup59230@gmail.com";
                var fromName = _configuration["BREVO_FROM_NAME"] ?? "D&D GameMaster";

                // Créer le message
                var message = new MailMessage
                {
                    From = new MailAddress(fromEmail, fromName),
                    Subject = subject,
                    Body = htmlMessage,
                    IsBodyHtml = true
                };
                
                message.To.Add(new MailAddress(to));

                // Créer le client SMTP
                using (var client = new SmtpClient(smtpServer, smtpPort))
                {
                    client.UseDefaultCredentials = false;
                    client.Credentials = new NetworkCredential(smtpUsername, smtpPassword);
                    client.EnableSsl = true;
                    
                    await client.SendMailAsync(message);
                    _logger.LogInformation($"Email sent via SMTP to {to} with subject: {subject}");
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error sending email via SMTP to {to}");
                throw; // Rethrow pour permettre la gestion dans le contrôleur
            }
        }

        public async System.Threading.Tasks.Task SendEmailConfirmationAsync(string to, string userName, string confirmationLink)
        {
            var subject = "Confirm your email for D&D GameMaster";
            var htmlContent = $@"
                <html>
                <body>
                    <h1>Welcome to D&D GameMaster, {userName}!</h1>
                    <p>Please confirm your email address by clicking the link below:</p>
                    <p><a href='{confirmationLink}'>Confirm Email</a></p>
                    <p>If you did not create an account, you can ignore this email.</p>
                    <p>Thank you,<br>D&D GameMaster Team</p>
                </body>
                </html>";
                
            await SendEmailAsync(to, subject, htmlContent);
        }

        public async System.Threading.Tasks.Task SendPasswordResetAsync(string to, string userName, string resetLink)
        {
            var subject = "Reset your D&D GameMaster password";
            var htmlContent = $@"
                <html>
                <body>
                    <h1>Hello, {userName}!</h1>
                    <p>You requested a password reset for your D&D GameMaster account.</p>
                    <p>Please click the link below to reset your password:</p>
                    <p><a href='{resetLink}'>Reset Password</a></p>
                    <p>If you did not request a password reset, you can ignore this email.</p>
                    <p>Thank you,<br>D&D GameMaster Team</p>
                </body>
                </html>";
                
            await SendEmailAsync(to, subject, htmlContent);
        }

        public async System.Threading.Tasks.Task SendWelcomeEmailAsync(string to, string userName)
        {
            var subject = "Welcome to D&D GameMaster!";
            var htmlContent = $@"
                <html>
                <body>
                    <h1>Welcome, {userName}!</h1>
                    <p>Thank you for joining D&D GameMaster. Your account has been successfully created and activated.</p>
                    <p>You can now create campaigns, build characters, and start your adventures with our AI-powered Game Master.</p>
                    <p>Happy gaming!</p>
                    <p>The D&D GameMaster Team</p>
                </body>
                </html>";
                
            await SendEmailAsync(to, subject, htmlContent);
        }
    }
} 