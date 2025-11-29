import pytest
from unittest import mock

def test_view_prompts(client, app):
    """Verify admin can view prompts."""
    # Mock prompt_manager.get_all_prompts
    with mock.patch('admin.services.prompt_manager.get_all_prompts') as mock_get_all:
        mock_get_all.return_value = {"system_instruction": "You are a helpful assistant."}
        
        response = client.get('/admin/ai-control')
        assert response.status_code == 200
        assert b"system_instruction" in response.data or b"System Instruction" in response.data
        assert b"You are a helpful assistant." in response.data

def test_update_prompt(client, app):
    """Verify admin can update a prompt."""
    with mock.patch('admin.services.prompt_manager.update_prompt_content') as mock_update:
        mock_update.return_value = ("Prompt updated successfully.", True)
        
        data = {
            "prompt_name": "system_prompt",
            "content": "New content"
        }
        response = client.post('/admin/ai-control', data=data, follow_redirects=True)
        
        assert response.status_code == 200
        assert b"Prompt updated successfully" in response.data
        mock_update.assert_called_with("system_prompt", "New content")
