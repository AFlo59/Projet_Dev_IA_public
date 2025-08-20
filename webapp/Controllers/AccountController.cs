using DnDGameMaster.WebApp.Models;
using DnDGameMaster.WebApp.Services;
using DnDGameMaster.WebApp.Services.Email;
using DnDGameMaster.WebApp.Services.Game;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using System.ComponentModel.DataAnnotations;
using System.Threading.Tasks;
using Microsoft.Extensions.Configuration;

namespace DnDGameMaster.WebApp.Controllers
{
    public class AccountController : Controller
    {
        private readonly UserManager<ApplicationUser> _userManager;
        private readonly SignInManager<ApplicationUser> _signInManager;
        private readonly IEmailService _emailService;
        private readonly ILogger<AccountController> _logger;
        private readonly IConfiguration _configuration;
        private readonly ICampaignService _campaignService;
        private readonly ICharacterService _characterService;

        public AccountController(
            UserManager<ApplicationUser> userManager,
            SignInManager<ApplicationUser> signInManager,
            IEmailService emailService,
            ILogger<AccountController> logger,
            IConfiguration configuration,
            ICampaignService campaignService,
            ICharacterService characterService)
        {
            _userManager = userManager;
            _signInManager = signInManager;
            _emailService = emailService;
            _logger = logger;
            _configuration = configuration;
            _campaignService = campaignService;
            _characterService = characterService;
        }

        [HttpGet]
        public IActionResult Register()
        {
            return View();
        }

        [HttpPost]
        public async Task<IActionResult> Register(RegisterViewModel model)
        {
            if (ModelState.IsValid)
            {
                var user = new ApplicationUser
                {
                    UserName = model.Email,
                    Email = model.Email,
                    FirstName = model.FirstName,
                    LastName = model.LastName,
                    EmailConfirmed = true // Confirmer automatiquement l'email
                };

                var result = await _userManager.CreateAsync(user, model.Password);
                if (result.Succeeded)
                {
                    _logger.LogInformation("User created a new account with password.");

                    // Add user to Player role
                    await _userManager.AddToRoleAsync(user, "Player");

                    // Auto-connecter l'utilisateur
                    await _signInManager.SignInAsync(user, isPersistent: false);
                    _logger.LogInformation("User auto-signed in after registration.");

                    // Rediriger vers la page d'accueil au lieu de la confirmation
                    return RedirectToAction("Index", "Home");
                }

                foreach (var error in result.Errors)
                {
                    ModelState.AddModelError(string.Empty, error.Description);
                }
            }

            return View(model);
        }

        [HttpGet]
        public IActionResult RegisterConfirmation()
        {
            return View();
        }

        [HttpGet]
        public async Task<IActionResult> ConfirmEmail(string userId, string code)
        {
            if (userId == null || code == null)
            {
                return RedirectToAction("EmailError");
            }

            var user = await _userManager.FindByIdAsync(userId);
            if (user == null)
            {
                return RedirectToAction("EmailError");
            }

            var result = await _userManager.ConfirmEmailAsync(user, code);
            if (result.Succeeded)
            {
                // Make sure we have a non-null userName
                var userName = user.FirstName ?? "User";
                
                // Send welcome email
                try
                {
                    if (!string.IsNullOrEmpty(user.Email))
                    {
                        await _emailService.SendWelcomeEmailAsync(user.Email, userName);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Failed to send welcome email to {Email}", user.Email);
                    // Continue anyway since the account is confirmed
                }
                return View("ConfirmEmail");
            }
            else
            {
                return View("EmailError");
            }
        }

        [HttpGet]
        public IActionResult Login(string? returnUrl = null)
        {
            ViewData["ReturnUrl"] = returnUrl;
            return View();
        }

        [HttpPost]
        public async Task<IActionResult> Login(LoginViewModel model, string? returnUrl = null)
        {
            ViewData["ReturnUrl"] = returnUrl;

            if (ModelState.IsValid)
            {
                // Auto-confirmer l'utilisateur si nécessaire
                var user = await _userManager.FindByEmailAsync(model.Email);
                if (user != null && !await _userManager.IsEmailConfirmedAsync(user))
                {
                    // Activer automatiquement le compte
                    user.EmailConfirmed = true;
                    await _userManager.UpdateAsync(user);
                    _logger.LogInformation("User account auto-confirmed during login: {Email}", model.Email);
                }
                
                var result = await _signInManager.PasswordSignInAsync(model.Email, model.Password, model.RememberMe, lockoutOnFailure: true);
                if (result.Succeeded)
                {
                    _logger.LogInformation("User logged in.");
                    return RedirectToLocal(returnUrl);
                }
                if (result.RequiresTwoFactor)
                {
                    // Pour l'instant, nous ne supportons pas 2FA
                    ModelState.AddModelError(string.Empty, "Two-factor authentication is not supported yet.");
                    return View(model);
                }
                if (result.IsLockedOut)
                {
                    _logger.LogWarning("User account locked out.");
                    return RedirectToAction(nameof(Lockout));
                }
                else
                {
                    ModelState.AddModelError(string.Empty, "Invalid login attempt. Please check your email and password.");
                    return View(model);
                }
            }

            return View(model);
        }

        [HttpGet]
        public async Task<IActionResult> ResendConfirmationEmail(string email)
        {
            if (string.IsNullOrEmpty(email))
            {
                return RedirectToAction(nameof(Login));
            }

            var user = await _userManager.FindByEmailAsync(email);
            if (user == null)
            {
                // Don't reveal that the user does not exist
                TempData["EmailResent"] = true;
                return RedirectToAction(nameof(RegisterConfirmation));
            }

            if (await _userManager.IsEmailConfirmedAsync(user))
            {
                // Account already confirmed
                return RedirectToAction(nameof(Login));
            }

            // Generate confirmation code
            var code = await _userManager.GenerateEmailConfirmationTokenAsync(user);
            var callbackUrl = Url.Action(
                "ConfirmEmail",
                "Account",
                new { userId = user.Id, code = code },
                protocol: HttpContext.Request.Scheme);
                
            callbackUrl = callbackUrl ?? string.Empty;
            
            // Make sure we have a non-null userName
            var userName = user.FirstName ?? "User";
            
            // Store email in TempData for potential future resends
            TempData["UserEmail"] = email;

            // Send confirmation email
            try
            {
                await _emailService.SendEmailConfirmationAsync(email, userName, callbackUrl);
                _logger.LogInformation("Confirmation email resent to {Email}", email);
                TempData["EmailResent"] = true;
            }
            catch (Exception ex)
            {
                // If email sending fails, auto-confirm the account in development environment
                _logger.LogWarning(ex, "Email resending failed. Auto-confirming account in development mode.");
                await _userManager.ConfirmEmailAsync(user, code);
                TempData["AutoConfirmed"] = true;
            }

            return RedirectToAction(nameof(RegisterConfirmation));
        }

        [HttpGet]
        public IActionResult ForgotPassword()
        {
            return View();
        }

        [HttpPost]
        public async Task<IActionResult> ForgotPassword(ForgotPasswordViewModel model)
        {
            if (ModelState.IsValid)
            {
                var user = await _userManager.FindByEmailAsync(model.Email);
                if (user == null || !(await _userManager.IsEmailConfirmedAsync(user)))
                {
                    // Don't reveal that the user does not exist or is not confirmed
                    return RedirectToAction(nameof(ForgotPasswordConfirmation));
                }

                // Generate password reset token
                string code = await _userManager.GeneratePasswordResetTokenAsync(user);
                var callbackUrl = Url.Action(
                    "ResetPassword",
                    "Account",
                    new { userId = user.Id, code = code },
                    protocol: HttpContext.Request.Scheme);
                    
                // S'assurer que l'URL n'est pas null
                callbackUrl = callbackUrl ?? string.Empty;

                // Send password reset email
                await _emailService.SendPasswordResetAsync(model.Email, user.FirstName ?? "User", callbackUrl);

                return RedirectToAction(nameof(ForgotPasswordConfirmation));
            }

            return View(model);
        }

        [HttpGet]
        public IActionResult ForgotPasswordConfirmation()
        {
            return View();
        }

        [HttpGet]
        public IActionResult ResetPassword(string? code = null)
        {
            if (code == null)
            {
                return BadRequest("A code must be supplied for password reset.");
            }
            else
            {
                var model = new ResetPasswordViewModel { Code = code };
                return View(model);
            }
        }

        [HttpPost]
        public async Task<IActionResult> ResetPassword(ResetPasswordViewModel model)
        {
            if (!ModelState.IsValid)
            {
                return View(model);
            }

            var user = await _userManager.FindByEmailAsync(model.Email);
            if (user == null)
            {
                // Don't reveal that the user does not exist
                return RedirectToAction(nameof(ResetPasswordConfirmation));
            }

            var result = await _userManager.ResetPasswordAsync(user, model.Code, model.Password);
            if (result.Succeeded)
            {
                return RedirectToAction(nameof(ResetPasswordConfirmation));
            }

            foreach (var error in result.Errors)
            {
                ModelState.AddModelError(string.Empty, error.Description);
            }

            return View();
        }

        [HttpGet]
        public IActionResult ResetPasswordConfirmation()
        {
            return View();
        }

        [HttpGet]
        public IActionResult Lockout()
        {
            return View();
        }

        [HttpPost]
        [Authorize]
        public async Task<IActionResult> Logout()
        {
            await _signInManager.SignOutAsync();
            _logger.LogInformation("User logged out.");
            return RedirectToAction(nameof(HomeController.Index), "Home");
        }

        [HttpGet]
        [Authorize]
        public async Task<IActionResult> Profile()
        {
            var user = await _userManager.GetUserAsync(User);
            if (user == null)
            {
                return NotFound();
            }

                            var model = new ProfileViewModel
                {
                    Email = user.Email ?? string.Empty,
                    FirstName = user.FirstName ?? string.Empty,
                    LastName = user.LastName ?? string.Empty
                };

            return View(model);
        }

        [HttpPost]
        [Authorize]
        public async Task<IActionResult> Profile(ProfileViewModel model)
        {
            if (!ModelState.IsValid)
            {
                return View(model);
            }

            var user = await _userManager.GetUserAsync(User);
            if (user == null)
            {
                return NotFound();
            }

            user.FirstName = model.FirstName ?? string.Empty;
            user.LastName = model.LastName ?? string.Empty;

            var result = await _userManager.UpdateAsync(user);
            if (!result.Succeeded)
            {
                foreach (var error in result.Errors)
                {
                    ModelState.AddModelError(string.Empty, error.Description);
                }
                return View(model);
            }

            TempData["StatusMessage"] = "Your profile has been updated";
            return RedirectToAction(nameof(Profile));
        }

        [HttpPost]
        [Authorize]
        public async Task<IActionResult> ChangePassword([FromForm] ChangePasswordViewModel model)
        {
            try
            {
                var user = await _userManager.GetUserAsync(User);
                if (user == null)
                {
                    return Json(new { success = false, errors = new[] { "User not found" } });
                }

                if (string.IsNullOrEmpty(model.CurrentPassword) || string.IsNullOrEmpty(model.NewPassword))
                {
                    return Json(new { success = false, errors = new[] { "Current password and new password are required" } });
                }

                if (model.NewPassword != model.ConfirmPassword)
                {
                    return Json(new { success = false, errors = new[] { "New password and confirmation password do not match" } });
                }

                if (model.NewPassword.Length < 6)
                {
                    return Json(new { success = false, errors = new[] { "Password must be at least 6 characters long" } });
                }

                var result = await _userManager.ChangePasswordAsync(user, model.CurrentPassword, model.NewPassword);
                if (result.Succeeded)
                {
                    _logger.LogInformation("User changed their password successfully.");
                    await _signInManager.RefreshSignInAsync(user);
                    return Json(new { success = true, message = "Password changed successfully" });
                }

                var errors = result.Errors.Select(x => x.Description).ToList();
                return Json(new { success = false, errors = errors });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error changing password");
                return Json(new { success = false, errors = new[] { "An error occurred while changing the password" } });
            }
        }

        [HttpGet]
        [Authorize]
        public async Task<IActionResult> GetUserStatistics()
        {
            try
            {
                var user = await _userManager.GetUserAsync(User);
                if (user == null)
                {
                    return Json(new { success = false, message = "User not found" });
                }

                // Get campaign count (owned by user)
                var campaignCount = await GetUserCampaignCountAsync(user.Id);
                
                // Get character count (created by user)
                var characterCount = await GetUserCharacterCountAsync(user.Id);

                return Json(new { 
                    success = true, 
                    campaignCount = campaignCount,
                    characterCount = characterCount,
                    memberSince = user.Created
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting user statistics");
                return Json(new { success = false, message = "Error loading statistics" });
            }
        }

        private async Task<int> GetUserCampaignCountAsync(string userId)
        {
            var campaigns = await _campaignService.GetCampaignsForUserAsync(userId);
            return campaigns.Count;
        }

        private async Task<int> GetUserCharacterCountAsync(string userId)
        {
            var characters = await _characterService.GetCharactersForUserAsync(userId);
            return characters.Count;
        }

        private IActionResult RedirectToLocal(string? returnUrl)
        {
            if (!string.IsNullOrEmpty(returnUrl) && Url.IsLocalUrl(returnUrl))
            {
                return Redirect(returnUrl);
            }
            else
            {
                return RedirectToAction(nameof(HomeController.Index), "Home");
            }
        }
    }

    public class RegisterViewModel
    {
        [Required]
        [EmailAddress]
        [Display(Name = "Email")]
        public string Email { get; set; } = string.Empty;

        [Required]
        [StringLength(100, ErrorMessage = "The {0} must be at least {2} and at max {1} characters long.", MinimumLength = 6)]
        [DataType(DataType.Password)]
        [Display(Name = "Password")]
        public string Password { get; set; } = string.Empty;

        [DataType(DataType.Password)]
        [Display(Name = "Confirm password")]
        [Compare("Password", ErrorMessage = "The password and confirmation password do not match.")]
        public string ConfirmPassword { get; set; } = string.Empty;

        [Required]
        [StringLength(50)]
        [Display(Name = "First Name")]
        public string FirstName { get; set; } = string.Empty;

        [Required]
        [StringLength(50)]
        [Display(Name = "Last Name")]
        public string LastName { get; set; } = string.Empty;
    }

    public class LoginViewModel
    {
        [Required]
        [EmailAddress]
        public string Email { get; set; } = string.Empty;

        [Required]
        [DataType(DataType.Password)]
        public string Password { get; set; } = string.Empty;

        [Display(Name = "Remember me?")]
        public bool RememberMe { get; set; }
    }

    public class ForgotPasswordViewModel
    {
        [Required]
        [EmailAddress]
        public string Email { get; set; } = string.Empty;
    }

    public class ResetPasswordViewModel
    {
        [Required]
        [EmailAddress]
        public string Email { get; set; } = string.Empty;

        [Required]
        [StringLength(100, ErrorMessage = "The {0} must be at least {2} and at max {1} characters long.", MinimumLength = 6)]
        [DataType(DataType.Password)]
        public string Password { get; set; } = string.Empty;

        [DataType(DataType.Password)]
        [Display(Name = "Confirm password")]
        [Compare("Password", ErrorMessage = "The password and confirmation password do not match.")]
        public string ConfirmPassword { get; set; } = string.Empty;

        public string Code { get; set; } = string.Empty;
    }

    public class ProfileViewModel
    {
        [Required]
        [EmailAddress]
        [Display(Name = "Email")]
        public string Email { get; set; } = string.Empty;

        [Required]
        [StringLength(50)]
        [Display(Name = "First Name")]
        public string FirstName { get; set; } = string.Empty;

        [Required]
        [StringLength(50)]
        [Display(Name = "Last Name")]
        public string LastName { get; set; } = string.Empty;
    }

    public class ChangePasswordViewModel
    {
        [Required]
        [DataType(DataType.Password)]
        [Display(Name = "Current Password")]
        public string CurrentPassword { get; set; } = string.Empty;

        [Required]
        [StringLength(100, ErrorMessage = "The {0} must be at least {2} and at max {1} characters long.", MinimumLength = 6)]
        [DataType(DataType.Password)]
        [Display(Name = "New Password")]
        public string NewPassword { get; set; } = string.Empty;

        [Required]
        [DataType(DataType.Password)]
        [Display(Name = "Confirm New Password")]
        [Compare("NewPassword", ErrorMessage = "The new password and confirmation password do not match.")]
        public string ConfirmPassword { get; set; } = string.Empty;
    }
} 