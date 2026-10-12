MAX_OUTPUT = 16_000  # max chars returned by any tool

# Deferred MCP tools — MCP tool schemas are hidden until Thrall loads them with mcp_search
PROVIDER_TOOL_LIMIT = 128        # most providers reject a request with more tools than this
MCP_SEARCH_MAX_RESULTS = 8       # tools loaded per mcp_search call
MCP_SESSION_TOOL_CAP = 60        # max MCP tools loaded in one session (least recently used dropped first)
MCP_IDLE_TURNS = 15              # unload an MCP tool after this many user turns without being called
MCP_CATALOG_SAMPLE_TOOLS = 4     # example tool names shown per server in the context catalog
MCP_OVERVIEW_SAMPLE_TOOLS = 12   # tool names shown when mcp_search is given only a server name

# In-task checklist (todo_write)
TODO_MAX_ITEMS = 30              # items beyond this are rejected — split the task instead

CODE_EXTS ={".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java", ".c", ".cpp", ".cs", ".rb", ".sh", ".bash", ".ps1", ".lua", ".php", ".swift", ".kt", ".toml", ".yaml", ".yml", ".json"}
