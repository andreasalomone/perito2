from enum import Enum

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"

class CaseStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"

class ExtractionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
    PROCESSING = "PROCESSING"
    PENDING = "PENDING"
