import contextlib
import logging
import os
import shutil
import tempfile
from typing import Dict, Optional


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
            # Early Analysis feature prompts
            "document_analysis": os.path.join(
                self._current_dir, "document_analysis_prompt.txt"
            ),
            "preliminary_report": os.path.join(
                self._current_dir, "preliminary_report_prompt.txt"
            ),
        }

    def get_prompt_path(self, prompt_name: str) -> Optional[str]:
        """Returns the file path for a given prompt name."""
        return self.PROMPT_FILES.get(prompt_name)

    def get_prompt_content(self, prompt_name: str) -> str:
        """
        Reads the content of a specific prompt file.
        Returns: content matching the prompt_name.
        Raises:
            ValueError: If the prompt is not configured.
            FileNotFoundError: If the prompt file does not exist.
            IOError: If there is an error reading the file.
        """
        file_path = self.get_prompt_path(prompt_name)
        if not file_path:
            raise ValueError(f"Error: Prompt file for '{prompt_name}' not configured.")

        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"Error: Prompt file for '{prompt_name}' not found at {file_path}."
            )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            raise IOError(f"Error reading file: {e}") from e

    def update_prompt_content(self, prompt_name: str, content: str) -> str:
        """
        Writes new content to a specific prompt file.
        Returns: Success message.
        Raises:
            ValueError: If the prompt is not configured.
            IOError: If there is an error writing to the file.
        """
        file_path = self.get_prompt_path(prompt_name)
        if not file_path:
            raise ValueError(f"Error: Prompt file for '{prompt_name}' not configured.")

        tmp_path = None
        try:
            # Create a temporary file in the same directory to ensure atomic move
            dir_name = os.path.dirname(file_path)
            with tempfile.NamedTemporaryFile(
                "w", dir=dir_name, delete=False, encoding="utf-8"
            ) as tmp_file:
                # Capture path immediately for cleanup in case write fails
                tmp_path = tmp_file.name
                tmp_file.write(content)
                tmp_file.flush()
                # Ensure data is written to disk
                os.fsync(tmp_file.fileno())

            # Copy permissions if target exists
            if os.path.exists(file_path):
                with contextlib.suppress(OSError):
                    shutil.copymode(file_path, tmp_path)
            # Atomic replace
            os.replace(tmp_path, file_path)

            friendly_name = prompt_name.replace("_", " ").capitalize()
            return f"{friendly_name} prompt updated successfully."
        except Exception as e:
            # Clean up temp file if it exists and wasn't moved
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception as cleanup_exc:
                    logging.warning(
                        f"Failed to clean up temporary file '{tmp_path}': {cleanup_exc}"
                    )
            raise IOError(f"Error writing to file: {e}") from e

    def get_all_prompts(self) -> Dict[str, str]:
        """
        Reads the content of all configured prompt files.
        Returns: Dict[prompt_name, content]
        Raises: RuntimeError if any prompt fails to load.
        """
        all_prompts = {}
        errors = []
        for name in self.PROMPT_FILES:
            try:
                content = self.get_prompt_content(name)
                all_prompts[name] = content
            except Exception as e:
                errors.append(f"{name}: {e}")

        if errors:
            raise RuntimeError(f"Failed to load prompts: {'; '.join(errors)}")

        return all_prompts


# Global instance
prompt_manager = PromptManager()


# Load the prompts from their files (Module-level constants for app usage)
# These are loaded once at startup.
# If dynamic updates are needed during runtime without restart,
# the app should use prompt_manager.get_prompt_content() instead.
try:
    SYSTEM_INSTRUCTION: str = prompt_manager.get_prompt_content("system_instruction")
except Exception as e:
    logging.getLogger(__name__).error(f"Error loading system_instruction: {e}")
    SYSTEM_INSTRUCTION = ""

try:
    GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI: str = prompt_manager.get_prompt_content(
        "style_guide"
    )
except Exception as e:
    logging.getLogger(__name__).error(f"Error loading style_guide: {e}")
    GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI = ""

try:
    SCHEMA_REPORT: str = prompt_manager.get_prompt_content("schema_report")
except Exception as e:
    logging.getLogger(__name__).error(f"Error loading schema_report: {e}")
    SCHEMA_REPORT = ""

# Backwards-compatible aliases
PREDEFINED_STYLE_REFERENCE_TEXT: str = GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI
REPORT_STRUCTURE_PROMPT: str = SCHEMA_REPORT
