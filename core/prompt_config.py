import os


def _load_prompt_from_file(file_path: str) -> str:
    """Loads a prompt from a specified file path."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # Using print for critical startup errors is acceptable.
        # In a more complex app, a pre-config logger could be used.
        print(
            f"CRITICAL ERROR: Prompt file not found at {file_path}. The application may not function correctly."
        )
        return ""  # Return empty string as a fallback.
    except Exception as e:
        print(f"An error occurred while reading {file_path}: {e}")
        return ""


# Define paths to the prompt files relative to this file's location
_current_dir = os.path.dirname(__file__)
_system_instruction_path = os.path.join(_current_dir, "system_instruction.txt")
_style_guide_path = os.path.join(_current_dir, "style_guide.txt")
_schema_report_path = os.path.join(_current_dir, "schema_report.txt")

# Load the prompts from their files
SYSTEM_INSTRUCTION: str = _load_prompt_from_file(_system_instruction_path)
GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI: str = _load_prompt_from_file(_style_guide_path)
SCHEMA_REPORT: str = _load_prompt_from_file(_schema_report_path)

# Backwards-compatible aliases for tests/LLM cache config helpers.
PREDEFINED_STYLE_REFERENCE_TEXT: str = GUIDA_STILE_TERMINOLOGIA_ED_ESEMPI
REPORT_STRUCTURE_PROMPT: str = SCHEMA_REPORT
