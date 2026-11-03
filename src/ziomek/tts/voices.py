"""The voices a participant can be given."""

# The names PocketTTS knows. The API, the MCP resource and the roster all read this one list,
# so the count cannot drift apart between them.
VOICES: tuple[str, ...] = (
    "cosette",
    "marius",
    "javert",
    "alba",
    "jean",
    "anna",
    "vera",
    "fantine",
    "charles",
    "paul",
    "eponine",
    "azelma",
    "george",
    "mary",
    "jane",
    "michael",
    "eve",
    "bill_boerst",
    "peter_yearsley",
    "stuart_bell",
    "caro_davy",
    "giovanni",
    "lola",
    "juergen",
    "rafael",
    "estelle",
)

DEFAULT_VOICE = VOICES[0]
