using Mailjet.Client;
using Mailjet.Client.Resources;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json.Linq;
using System.Threading.Tasks;

namespace DnDGameMaster.WebApp.Services.Email
{
    public class MailjetEmailService : IEmailService
    {
        private readonly IConfiguration _configuration;
        private readonly ILogger<MailjetEmailService> _logger;
        
        public MailjetEmailService(IConfiguration configuration, ILogger<MailjetEmailService> logger)
        {
            _configuration = configuration;
            _logger = logger;
        }

        public async System.Threading.Tasks.Task SendEmailAsync(string to, string subject, string htmlMessage)
        {
            try
            {
                var apiKey = _configuration["MAILJET_API_KEY"];
                var secretKey = _configuration["MAILJET_SECRET_KEY"];
                var fromEmail = _configuration["MAILJET_FROM_EMAIL"] ?? "etudessup59230@gmail.fr";
                var fromName = _configuration["MAILJET_FROM_NAME"] ?? "D&D GameMaster";
                
                var client = new MailjetClient(apiKey, secretKey);

                // Construire le message avec l'API Mailjet
                var request = new MailjetRequest
                {
                    Resource = Send.Resource
                }
                .Property(Send.Messages, new JArray {
                    new JObject {
                        {"From", new JObject {
                            {"Email", fromEmail},
                            {"Name", fromName}
                        }},
                        {"To", new JArray {
                            new JObject {
                                {"Email", to}
                            }
                        }},
                        {"Subject", subject},
                        {"HTMLPart", htmlMessage}
                    }
                });

                // Envoyer l'email
                var response = await client.PostAsync(request);
                
                // Vérifier le statut de la réponse (2xx = succès)
                if (response.IsSuccessStatusCode)
                {
                    _logger.LogInformation($"Email sent to {to} with subject: {subject}");
                }
                else
                {
                    _logger.LogError($"Failed to send email to {to}. Status: {response.StatusCode}");
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error sending email to {to}");
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