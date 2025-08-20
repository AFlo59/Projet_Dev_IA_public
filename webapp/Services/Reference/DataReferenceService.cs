using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace DnDGameMaster.WebApp.Services.Reference
{
    public class DataReferenceService : IDataReferenceService
    {
        private readonly HttpClient _httpClient;
        private readonly IConfiguration _configuration;
        private readonly ILogger<DataReferenceService> _logger;
        private string? _authToken;
        
        public DataReferenceService(HttpClient httpClient, IConfiguration configuration, ILogger<DataReferenceService> logger)
        {
            _httpClient = httpClient;
            _configuration = configuration;
            _logger = logger;
        }
        
        public async Task<string> GetAuthTokenAsync()
        {
            if (!string.IsNullOrEmpty(_authToken))
            {
                return _authToken;
            }
            
            var tokenRequest = new
            {
                username = "api_user",
                password = "dnd_api_password"
            };
            
            var response = await _httpClient.PostAsJsonAsync("/token", tokenRequest);
            
            if (response.IsSuccessStatusCode)
            {
                var tokenResponse = await response.Content.ReadFromJsonAsync<Dictionary<string, string>>();
                if (tokenResponse != null && tokenResponse.TryGetValue("access_token", out var token))
                {
                    _authToken = token;
                    return token;
                }
            }
            
            throw new Exception("Failed to obtain authorization token from DataReference API");
        }
        
        private async Task AuthenticateRequestAsync()
        {
            var token = await GetAuthTokenAsync();
            _httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
        }
        
        public async Task<List<string>> GetSchemasAsync()
        {
            await AuthenticateRequestAsync();
            
            var response = await _httpClient.GetAsync("/schemas");
            response.EnsureSuccessStatusCode();
            
            return await response.Content.ReadFromJsonAsync<List<string>>() ?? new List<string>();
        }
        
        public async Task<List<string>> GetTablesInSchemaAsync(string schema)
        {
            await AuthenticateRequestAsync();
            
            var response = await _httpClient.GetAsync($"/schemas/{schema}/tables");
            response.EnsureSuccessStatusCode();
            
            return await response.Content.ReadFromJsonAsync<List<string>>() ?? new List<string>();
        }
        
        public async Task<List<Dictionary<string, object>>> GetTableDataAsync(string schema, string table, int limit = 100, int offset = 0)
        {
            await AuthenticateRequestAsync();
            
            var response = await _httpClient.GetAsync($"/{schema}/{table}?limit={limit}&offset={offset}");
            response.EnsureSuccessStatusCode();
            
            var content = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<List<Dictionary<string, object>>>(content, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            }) ?? new List<Dictionary<string, object>>();
        }
        
        public async Task<List<Dictionary<string, object>>> SearchTableDataAsync(string schema, string table, string query, string? fields = null, int limit = 100)
        {
            await AuthenticateRequestAsync();
            
            var url = $"/{schema}/{table}/search?query={Uri.EscapeDataString(query)}&limit={limit}";
            if (!string.IsNullOrEmpty(fields))
            {
                url += $"&fields={Uri.EscapeDataString(fields)}";
            }
            
            var response = await _httpClient.GetAsync(url);
            response.EnsureSuccessStatusCode();
            
            var content = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<List<Dictionary<string, object>>>(content, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            }) ?? new List<Dictionary<string, object>>();
        }
        
        public async Task<Dictionary<string, object>> GetItemByIdAsync(string schema, string table, int id)
        {
            await AuthenticateRequestAsync();
            
            var response = await _httpClient.GetAsync($"/{schema}/{table}/{id}");
            response.EnsureSuccessStatusCode();
            
            var content = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<Dictionary<string, object>>(content, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            }) ?? new Dictionary<string, object>();
        }
    }
} 