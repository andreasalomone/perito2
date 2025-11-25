from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class ServiceMessage:
    message: str
    category: str = "info"  # 'success', 'info', 'warning', 'error'


@dataclass
class ServiceResult:
    success: bool
    data: Any = None
    messages: List[ServiceMessage] = field(default_factory=list)

    def add_message(self, message: str, category: str = "info"):
        self.messages.append(ServiceMessage(message, category))
