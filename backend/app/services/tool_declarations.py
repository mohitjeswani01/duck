"""Function declarations for the three file tools, in the format the
google-genai SDK expects for manual tool definitions (confirmed against
https://googleapis.github.io/python-genai/ — FunctionDeclaration takes a
plain JSON Schema dict via `parameters_json_schema`, not the older
`types.Schema` object). Phase 3's conversation engine plugs these straight
into `GenerateContentConfig(tools=[TOOLS])` and dispatches by name to the
matching function in app.services.file_tools.
"""
from google.genai import types

LIST_FILES_DECLARATION = types.FunctionDeclaration(
    name="list_files",
    description=(
        "List files in the connected repo, optionally filtered by a directory path "
        "or glob pattern (e.g. 'src/', 'src/**/*.ts'). Returns file paths and sizes."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Optional directory prefix or glob pattern. Omit to list all files.",
            },
        },
    },
)

READ_FILE_DECLARATION = types.FunctionDeclaration(
    name="read_file",
    description=(
        "Read a file from the connected repo, with line numbers on every line. "
        "If no line range is given and the file is long, only the first few hundred "
        "lines are returned along with the total line count."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to the repo root."},
            "start_line": {"type": "integer", "description": "Optional 1-indexed first line to return."},
            "end_line": {"type": "integer", "description": "Optional 1-indexed last line to return."},
        },
        "required": ["path"],
    },
)

SEARCH_CODE_DECLARATION = types.FunctionDeclaration(
    name="search_code",
    description=(
        "Search the connected repo's files for a literal string or regular expression. "
        "Returns matching lines with file path, line number, and surrounding context."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Literal string or regular expression to search for."},
            "file_pattern": {
                "type": "string",
                "description": "Optional directory prefix or glob pattern to restrict which files are searched.",
            },
            "is_regex": {
                "type": "boolean",
                "description": "Whether `query` should be treated as a regular expression. Defaults to false (literal substring search).",
            },
        },
        "required": ["query"],
    },
)

FILE_TOOLS = types.Tool(
    function_declarations=[LIST_FILES_DECLARATION, READ_FILE_DECLARATION, SEARCH_CODE_DECLARATION]
)
