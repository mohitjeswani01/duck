import enum


class SessionStatus(str, enum.Enum):
    active = "active"
    resolved = "resolved"
    abandoned = "abandoned"


class SessionPhase(str, enum.Enum):
    listening = "listening"
    clarifying = "clarifying"
    investigating = "investigating"
    hypothesis = "hypothesis"
    fix_proposed = "fix_proposed"
    resolved = "resolved"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
