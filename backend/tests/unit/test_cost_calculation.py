
import pytest
from unittest import mock
from core.config import settings
from services.llm.generation_service import calculate_cost

class MockUsageMetadata:
    def __init__(self, prompt_token_count, candidates_token_count):
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count

def test_calculate_cost_tier_1():
    """Test cost calculation for Tier 1 (<= 200k tokens)."""
    # Input: 100k tokens, Output: 50k tokens
    usage = MockUsageMetadata(100_000, 50_000)
    
    expected_input_cost = (100_000 / 1_000_000) * settings.PRICE_INPUT_TIER_1
    expected_output_cost = (50_000 / 1_000_000) * settings.PRICE_OUTPUT_TIER_1
    expected_total = expected_input_cost + expected_output_cost
    
    assert calculate_cost(usage) == pytest.approx(expected_total)

def test_calculate_cost_tier_2():
    """Test cost calculation for Tier 2 (> 200k tokens)."""
    # Input: 300k tokens, Output: 50k tokens
    usage = MockUsageMetadata(300_000, 50_000)
    
    expected_input_cost = (300_000 / 1_000_000) * settings.PRICE_INPUT_TIER_2
    expected_output_cost = (50_000 / 1_000_000) * settings.PRICE_OUTPUT_TIER_2
    expected_total = expected_input_cost + expected_output_cost
    
    assert calculate_cost(usage) == pytest.approx(expected_total)

def test_calculate_cost_no_metadata():
    """Test cost calculation with no metadata."""
    assert calculate_cost(None) == 0.0

def test_calculate_cost_empty_metadata():
    """Test cost calculation with empty metadata."""
    usage = MockUsageMetadata(0, 0)
    assert calculate_cost(usage) == 0.0
