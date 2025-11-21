"""
File cleanup service for removing orphaned uploads.

This module provides scheduled cleanup of old files in the uploads directory
that may have been left behind due to worker crashes or other failures.
"""

import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from core.celery_app import celery_app
from core.config import settings

logger = logging.getLogger(__name__)


def get_old_directories(days: int = 1) -> List[Path]:
    """
    Find directories in upload folder older than specified days.

    Args:
        days: Age threshold in days (default: 1)

    Returns:
        List of Path objects for directories older than threshold
    """
    upload_path = Path(settings.UPLOAD_FOLDER)

    if not upload_path.exists():
        logger.warning(f"Upload folder does not exist: {upload_path}")
        return []

    threshold = datetime.now() - timedelta(days=days)
    old_dirs = []

    for item in upload_path.iterdir():
        if item.is_dir():
            try:
                # Get directory modification time
                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                if mtime < threshold:
                    old_dirs.append(item)
            except (OSError, ValueError) as e:
                logger.warning(f"Could not check directory {item}: {e}")

    return old_dirs


@celery_app.task(name="services.cleanup.cleanup_old_uploads")
def cleanup_old_uploads(days: int = 1) -> dict:
    """
    Celery task to clean up old upload directories.

    This task is scheduled to run periodically via Celery Beat and removes
    directories from the uploads folder that are older than the specified
    number of days.

    Args:
        days: Delete directories older than this many days (default: 1)

    Returns:
        Dict with cleanup statistics
    """
    logger.info(f"Starting cleanup of uploads older than {days} day(s)")

    stats = {
        "directories_found": 0,
        "directories_deleted": 0,
        "directories_failed": 0,
        "bytes_freed": 0,
        "errors": [],
    }

    try:
        old_dirs = get_old_directories(days)
        stats["directories_found"] = len(old_dirs)

        for dir_path in old_dirs:
            try:
                # Calculate directory size before deletion
                total_size = sum(
                    f.stat().st_size for f in dir_path.rglob("*") if f.is_file()
                )

                # Delete the directory
                shutil.rmtree(dir_path)

                stats["directories_deleted"] += 1
                stats["bytes_freed"] += total_size

                logger.info(
                    f"Deleted old directory: {dir_path.name} "
                    f"({total_size / 1024 / 1024:.2f} MB)"
                )

            except Exception as e:
                stats["directories_failed"] += 1
                error_msg = f"Failed to delete {dir_path}: {str(e)}"
                stats["errors"].append(error_msg)
                logger.error(error_msg)

        # Log summary
        logger.info(
            f"Cleanup completed: {stats['directories_deleted']} deleted, "
            f"{stats['directories_failed']} failed, "
            f"{stats['bytes_freed'] / 1024 / 1024:.2f} MB freed"
        )

    except Exception as e:
        error_msg = f"Cleanup task failed: {str(e)}"
        stats["errors"].append(error_msg)
        logger.error(error_msg, exc_info=True)

    return stats
