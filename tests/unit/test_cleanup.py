"""
Unit tests for file cleanup service.
"""
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCleanupService:
    """Tests for the file cleanup service."""

    def test_get_old_directories_empty_folder(self, tmp_path):
        """Test get_old_directories with an empty upload folder."""
        from services.cleanup import get_old_directories
        
        with patch('services.cleanup.settings') as mock_settings:
            mock_settings.UPLOAD_FOLDER = str(tmp_path)
            
            old_dirs = get_old_directories(days=1)
            
            assert old_dirs == []

    def test_get_old_directories_recent_files(self, tmp_path):
        """Test that recent directories are not flagged for cleanup."""
        from services.cleanup import get_old_directories
        
        # Create a recent directory
        recent_dir = tmp_path / "recent_upload"
        recent_dir.mkdir()
        
        with patch('services.cleanup.settings') as mock_settings:
            mock_settings.UPLOAD_FOLDER = str(tmp_path)
            
            old_dirs = get_old_directories(days=1)
            
            assert old_dirs == []

    def test_get_old_directories_old_files(self, tmp_path):
        """Test that old directories are correctly identified."""
        from services.cleanup import get_old_directories
        
        # Create an old directory
        old_dir = tmp_path / "old_upload"
        old_dir.mkdir()
        
        # Set modification time to 2 days ago
        two_days_ago = datetime.now() - timedelta(days=2)
        os.utime(old_dir, (two_days_ago.timestamp(), two_days_ago.timestamp()))
        
        with patch('services.cleanup.settings') as mock_settings:
            mock_settings.UPLOAD_FOLDER = str(tmp_path)
            
            old_dirs = get_old_directories(days=1)
            
            assert len(old_dirs) == 1
            assert old_dirs[0].name == "old_upload"

    def test_get_old_directories_mixed(self, tmp_path):
        """Test with both old and recent directories."""
        from services.cleanup import get_old_directories
        
        # Create old directory
        old_dir = tmp_path / "old_upload"
        old_dir.mkdir()
        two_days_ago = datetime.now() - timedelta(days=2)
        os.utime(old_dir, (two_days_ago.timestamp(), two_days_ago.timestamp()))
        
        # Create recent directory
        recent_dir = tmp_path / "recent_upload"
        recent_dir.mkdir()
        
        with patch('services.cleanup.settings') as mock_settings:
            mock_settings.UPLOAD_FOLDER = str(tmp_path)
            
            old_dirs = get_old_directories(days=1)
            
            assert len(old_dirs) == 1
            assert old_dirs[0].name == "old_upload"

    def test_get_old_directories_nonexistent_folder(self):
        """Test behavior when upload folder doesn't exist."""
        from services.cleanup import get_old_directories
        
        with patch('services.cleanup.settings') as mock_settings:
            mock_settings.UPLOAD_FOLDER = "/nonexistent/path"
            
            old_dirs = get_old_directories(days=1)
            
            assert old_dirs == []

    def test_cleanup_old_uploads_success(self, tmp_path):
        """Test successful cleanup of old directories."""
        from services.cleanup import cleanup_old_uploads
        
        # Create old directory with a file
        old_dir = tmp_path / "old_upload"
        old_dir.mkdir()
        test_file = old_dir / "test.txt"
        test_file.write_text("test content")
        
        # Set modification time to 2 days ago
        two_days_ago = datetime.now() - timedelta(days=2)
        os.utime(old_dir, (two_days_ago.timestamp(), two_days_ago.timestamp()))
        
        with patch('services.cleanup.settings') as mock_settings:
            mock_settings.UPLOAD_FOLDER = str(tmp_path)
            
            stats = cleanup_old_uploads(days=1)
            
            assert stats['directories_found'] == 1
            assert stats['directories_deleted'] == 1
            assert stats['directories_failed'] == 0
            assert stats['bytes_freed'] > 0
            assert not old_dir.exists()

    def test_cleanup_old_uploads_no_old_files(self, tmp_path):
        """Test cleanup when there are no old files."""
        from services.cleanup import cleanup_old_uploads
        
        # Create only recent directory
        recent_dir = tmp_path / "recent_upload"
        recent_dir.mkdir()
        
        with patch('services.cleanup.settings') as mock_settings:
            mock_settings.UPLOAD_FOLDER = str(tmp_path)
            
            stats = cleanup_old_uploads(days=1)
            
            assert stats['directories_found'] == 0
            assert stats['directories_deleted'] == 0
            assert stats['bytes_freed'] == 0
            assert recent_dir.exists()

    def test_cleanup_old_uploads_partial_failure(self, tmp_path):
        """Test cleanup with some directories failing to delete."""
        from services.cleanup import cleanup_old_uploads
        
        # Create old directories
        old_dir1 = tmp_path / "old_upload_1"
        old_dir1.mkdir()
        old_dir2 = tmp_path / "old_upload_2"
        old_dir2.mkdir()
        
        two_days_ago = datetime.now() - timedelta(days=2)
        os.utime(old_dir1, (two_days_ago.timestamp(), two_days_ago.timestamp()))
        os.utime(old_dir2, (two_days_ago.timestamp(), two_days_ago.timestamp()))
        
        with patch('services.cleanup.settings') as mock_settings:
            mock_settings.UPLOAD_FOLDER = str(tmp_path)
            
            # Mock shutil.rmtree to fail on second directory
            original_rmtree = __import__('shutil').rmtree
            call_count = [0]
            
            def mock_rmtree(path):
                call_count[0] += 1
                if call_count[0] == 2:
                    raise PermissionError("Mock permission error")
                original_rmtree(path)
            
            with patch('shutil.rmtree', side_effect=mock_rmtree):
                stats = cleanup_old_uploads(days=1)
                
                assert stats['directories_found'] == 2
                assert stats['directories_deleted'] == 1
                assert stats['directories_failed'] == 1
                assert len(stats['errors']) == 1

    def test_cleanup_old_uploads_calculates_size(self, tmp_path):
        """Test that cleanup correctly calculates freed space."""
        from services.cleanup import cleanup_old_uploads
        
        # Create old directory with multiple files
        old_dir = tmp_path / "old_upload"
        old_dir.mkdir()
        
        file1 = old_dir / "file1.txt"
        file1.write_text("A" * 1000)
        
        file2 = old_dir / "file2.txt"
        file2.write_text("B" * 2000)
        
        two_days_ago = datetime.now() - timedelta(days=2)
        os.utime(old_dir, (two_days_ago.timestamp(), two_days_ago.timestamp()))
        
        with patch('services.cleanup.settings') as mock_settings:
            mock_settings.UPLOAD_FOLDER = str(tmp_path)
            
            stats = cleanup_old_uploads(days=1)
            
            assert stats['bytes_freed'] == 3000

    def test_cleanup_custom_days_threshold(self, tmp_path):
        """Test cleanup with custom days threshold."""
        from services.cleanup import get_old_directories
        
        # Create directory that's 3 days old
        old_dir = tmp_path / "three_day_old"
        old_dir.mkdir()
        three_days_ago = datetime.now() - timedelta(days=3)
        os.utime(old_dir, (three_days_ago.timestamp(), three_days_ago.timestamp()))
        
        with patch('services.cleanup.settings') as mock_settings:
            mock_settings.UPLOAD_FOLDER = str(tmp_path)
            
            # Should not be found with days=5 threshold
            old_dirs = get_old_directories(days=5)
            assert len(old_dirs) == 0
            
            # Should be found with days=2 threshold
            old_dirs = get_old_directories(days=2)
            assert len(old_dirs) == 1
