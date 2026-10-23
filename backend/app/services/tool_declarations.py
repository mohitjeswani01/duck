"""Function declarations for all seven tools Gemini can call during a
session: the three Phase 2 file tools, plus Phase 3's four control tools
that drive the phase state machine.

Format note (discovered the hard way in Phase 3): the installed
google-genai==1.3.0 does NOT support the `parameters_json_schema` plain-dict
field that the *current* SDK docs describe — that's a newer SDK feature.
This pinned version only accepts `parameters=types.Schema(...)`, which does
accept plain nested dicts (pydantic coerces them), but with JSON-Schema-style
keys swapped for this SDK's conventions: `"type"` values are the *uppercase*
`types.Type` names (`"OBJECT"`, `"STRING"`, `"INTEGER"`, `"BOOLEAN"`,
`"ARRAY"`), and array constraints are snake_case (`min_items`/`max_items`,
not `minItems`/`maxItems`). Re-verify against the installed version's actual
fields (`types.FunctionDeclaration.model_fields`) rather than trusting docs
when touching this file again — the API has changed across SDK versions.
"""
from google.genai import types

LIST_FILES_DECLARATION = types.FunctionDeclaration(
    name="list_files",
    description=(
        "List files in the connected repo, optionally filtered by a directory path "
        "or glob pattern (e.g. 'src/', 'src/**/*.ts'). Returns file paths and sizes."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "pattern": {
                "type": "STRING",
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
    parameters={
        "type": "OBJECT",
        "properties": {
            "path": {"type": "STRING", "description": "File path relative to the repo root."},
            "start_line": {"type": "INTEGER", "description": "Optional 1-indexed first line to return."},
            "end_line": {"type": "INTEGER", "description": "Optional 1-indexed last line to return."},
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
    parameters={
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "Literal string or regular expression to search for."},
            "file_pattern": {
                "type": "STRING",
                "description": "Optional directory prefix or glob pattern to restrict which files are searched.",
            },
            "is_regex": {
                "type": "BOOLEAN",
                "description": "Whether `query` should be treated as a regular expression. Defaults to false (literal substring search).",
            },
        },
        "required": ["query"],
    },
)

FILE_TOOLS = types.Tool(
    function_declarations=[LIST_FILES_DECLARATION, READ_FILE_DECLARATION, SEARCH_CODE_DECLARATION]
)

# --- Control tools (Phase 3) -------------------------------------------------
# These let Gemini drive the phase state machine through typed calls instead of
# parsed free text. The backend enforces which of these are legal in the
# session's current phase (see app/services/control_tools.py); an illegal call
# gets a clear error back as the tool result so Gemini can correct itself.

ASK_QUESTIONS_DECLARATION = types.FunctionDeclaration(
    name="ask_questions",
    description=(
        "Ask the user 1-3 focused clarifying questions, after you've already looked at "
        "relevant code. This pauses the conversation until the user replies. Capped at "
        "two rounds per session, so don't call this for things you could check yourself "
        "by reading more code."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "questions": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "min_items": 1,
                "max_items": 3,
                "description": "1 to 3 specific questions, each referencing what you found in the code.",
            },
        },
        "required": ["questions"],
    },
)

STATE_HYPOTHESIS_DECLARATION = types.FunctionDeclaration(
    name="state_hypothesis",
    description=(
        "State your theory of the root cause, with evidence, before proposing any fix. "
        "If confidence is 'low', this pauses so the user can confirm it matches what "
        "they're seeing before you continue."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "description": {
                "type": "STRING",
                "description": "A clear, specific statement of the suspected root cause.",
            },
            "evidence": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "file_path": {"type": "STRING"},
                        "line_number": {"type": "INTEGER"},
                        "note": {"type": "STRING", "description": "What this line shows and why it matters."},
                    },
                    "required": ["file_path", "line_number", "note"],
                },
                "min_items": 1,
                "description": "At least one concrete piece of evidence from code you've actually read.",
            },
            "confidence": {
                "type": "STRING",
                "enum": ["low", "medium", "high"],
                "description": "Your honest confidence this is the actual root cause.",
            },
        },
        "required": ["description", "evidence", "confidence"],
    },
)

PROPOSE_FIX_DECLARATION = types.FunctionDeclaration(
    name="propose_fix",
    description=(
        "Propose a fix as precise line replacements — never write a diff yourself. The "
        "backend reads the real file content and builds the actual diff from the lines "
        "you specify, so line numbers are always correct. Include one entry per file if "
        "the fix spans multiple files."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "changes": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "file_path": {"type": "STRING"},
                        "start_line": {"type": "INTEGER", "description": "1-indexed, inclusive."},
                        "end_line": {"type": "INTEGER", "description": "1-indexed, inclusive."},
                        "new_code": {
                            "type": "STRING",
                            "description": "The exact replacement text for lines start_line through end_line.",
                        },
                    },
                    "required": ["file_path", "start_line", "end_line", "new_code"],
                },
                "min_items": 1,
            },
            "explanation": {
                "type": "STRING",
                "description": "Why this change fixes the root cause you identified.",
            },
        },
        "required": ["changes", "explanation"],
    },
)

MARK_RESOLVED_DECLARATION = types.FunctionDeclaration(
    name="mark_resolved",
    description=(
        "Close out the session after the user has confirmed the fix actually works. "
        "This becomes the session's bug-journal entry."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "resolution_summary": {
                "type": "STRING",
                "description": "A short summary of what was wrong and how it was fixed.",
            },
            "root_cause": {"type": "STRING", "description": "The underlying root cause, stated plainly."},
            "tags": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "max_items": 5,
                "description": "A few short tags for the bug journal (e.g. 'auth', 'off-by-one', 'react-hooks').",
            },
        },
        "required": ["resolution_summary", "root_cause", "tags"],
    },
)

CONTROL_TOOLS = types.Tool(
    function_declarations=[
        ASK_QUESTIONS_DECLARATION,
        STATE_HYPOTHESIS_DECLARATION,
        PROPOSE_FIX_DECLARATION,
        MARK_RESOLVED_DECLARATION,
    ]
)

# Everything Gemini can call during a session, bundled for GenerateContentConfig(tools=[ALL_TOOLS]).
ALL_TOOLS = types.Tool(
    function_declarations=[
        LIST_FILES_DECLARATION,
        READ_FILE_DECLARATION,
        SEARCH_CODE_DECLARATION,
        ASK_QUESTIONS_DECLARATION,
        STATE_HYPOTHESIS_DECLARATION,
        PROPOSE_FIX_DECLARATION,
        MARK_RESOLVED_DECLARATION,
    ]
)

FILE_TOOL_NAMES = {"list_files", "read_file", "search_code"}
CONTROL_TOOL_NAMES = {"ask_questions", "state_hypothesis", "propose_fix", "mark_resolved"}
