using System.Collections.Generic;
using System.Threading.Tasks;

namespace DnDGameMaster.WebApp.Services.Reference
{
    public interface IDataReferenceService
    {
        Task<string> GetAuthTokenAsync();
        Task<List<string>> GetSchemasAsync();
        Task<List<string>> GetTablesInSchemaAsync(string schema);
        Task<List<Dictionary<string, object>>> GetTableDataAsync(string schema, string table, int limit = 100, int offset = 0);
        Task<List<Dictionary<string, object>>> SearchTableDataAsync(string schema, string table, string query, string? fields = null, int limit = 100);
        Task<Dictionary<string, object>> GetItemByIdAsync(string schema, string table, int id);
    }
} 