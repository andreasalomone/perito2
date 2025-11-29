import os
from typing import Dict, Optional, Tuple


class PromptManager:
    """
    Manages reading and writing of prompt files.
    Acts as the single source of truth for prompt locations and content.
    """

    def __init__(self):
        self._current_dir = os.path.dirname(__file__)
        self.PROMPT_FILES = {
            "system_instruction": os.path.join(
                self._current_dir, "system_instruction.txt"
            ),
            "style_guide": os.path.join(self._current_dir, "style_guide.txt"),
            "schema_report": os.path.join(self._current_dir, "schema_report.txt"),
        }

    def get_prompt_path(self, prompt_name: str) -> Optional[str]:
        """Returns the file path for a given prompt name."""
        return self.PROMPT_FILES.get(prompt_name)

    def get_prompt_content(self, prompt_name: str) -> Tuple[str, bool]:
        """
        Reads the content of a specific prompt file.
        Returns: (content, success)
        """
        file_path = self.get_prompt_path(prompt_name)
        if not file_path:
            return f"Error: Prompt file for '{prompt_name}' not configured.", False

        if not os.path.exists(file_path):
            return (
                f"Error: Prompt file for '{prompt_name}' not found at {file_path}.",
                False,
            )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read(), True
        except Exception as e:
            return f"Error reading file: {e}", False

    def update_prompt_content(self, prompt_name: str, content: str) -> Tuple[str, bool]:
        """
        Writes new content to a specific prompt file.
        Returns: (message, success)
        """
        file_path = self.get_prompt_path(prompt_name)
        if not file_path:
            return f"Error: Prompt file for '{prompt_name}' not configured.", False

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            friendly_name = prompt_name.replace("_", " ").capitalize()
            return f"{friendly_name} prompt updated successfully.", True
        except Exception as e:
            return f"Error writing to file: {e}", False

    def get_all_prompts(self) -> Dict[str, str]:
        """
        Reads the content of all configured prompt files.
        Returns: Dict[prompt_name, content]
        """
        all_prompts = {}
        for name in self.PROMPT_FILES:
            content, success = self.get_prompt_content(name)
            all_prompts[name] = content
        return all_prompts


# Global instance
prompt_manager = PromptManager()


# Helper function for backward compatibility and module-level loading
def _load_prompt_from_file(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error loading prompt from {file_path}: {e}")
        return ""


# Load the prompts from their files (Module-level constants for app usage)
# These are loaded once at startup.
# If dynamic updates are needed during runtime without restart,
# the app should use prompt_manager.get_prompt_content() instead.
SYSTEM_INSTRUCTION: str = _load_prompt_from_file(
    prompt_manager.get_prompt_path("system_instruction")
)
GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI: str = _load_prompt_from_file(
    prompt_manager.get_prompt_path("style_guide")
)
SCHEMA_REPORT: str = _load_prompt_from_file(
    prompt_manager.get_prompt_path("schema_report")
)

# Backwards-compatible aliases
PREDEFINED_STYLE_REFERENCE_TEXT: str = GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI
REPORT_STRUCTURE_PROMPT: str = SCHEMA_REPORT
