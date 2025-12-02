from typing import Any, Dict, List, Optional

class ServiceMessage:
    def __init__(self, message: str, type: str):
        self.message = message
        self.type = type

    def __repr__(self):
        return f"<ServiceMessage(type='{self.type}', message='{self.message}')>"

class ServiceResult:
    def __init__(self, success: bool = True):
        self.success = success
        self.messages: List[ServiceMessage] = []
        self.data: Dict[str, Any] = {}

    def add_message(self, message: str, type: str):
        self.messages.append(ServiceMessage(message, type))
    
    def __repr__(self):
        return f"<ServiceResult(success={self.success}, messages={len(self.messages)})>"
