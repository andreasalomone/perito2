"""LLM services package for report generation."""

# Re-export the submodules for backward-compatible imports like:
#   from app.services.llm import cache_service
#   cache_service.get_or_create_prompt_cache(client)
#
# Also re-export the singleton from prompt_builder_service
from app.services.llm import (
    cache_service as cache_service,
    file_upload_service as file_upload_service,
    generation_service as generation_service,
    response_parser_service as response_parser_service,
)
from app.services.llm.prompt_builder_service import (
    prompt_builder_service,
    PromptBuilderService,
)

__all__ = [
    "cache_service",
    "file_upload_service",
    "generation_service",
    "prompt_builder_service",
    "response_parser_service",
    "PromptBuilderService",
]
