import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from services.report_generation_service import generate_docx_variant
from core.models import ReportVersion

@pytest.mark.asyncio
async def test_generate_docx_variant_bn():
    # Mock DB Session
    mock_db = MagicMock()
    
    # Mock Version
    version_id = str(uuid4())
    mock_version = ReportVersion(
        id=version_id,
        case_id=uuid4(),
        organization_id=uuid4(),
        ai_raw_output="Test Content",
        is_final=False
    )
    mock_db.query.return_value.filter.return_value.first.return_value = mock_version

    # Mock Generator (BN)
    with patch("services.docx_generator.create_styled_docx") as mock_create_bn:
        mock_create_bn.return_value = MagicMock() # Stream
        
        # Mock GCS
        with patch("services.report_generation_service.get_storage_client") as mock_gcs:
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            mock_gcs.return_value.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            mock_blob.generate_signed_url.return_value = "https://signed-url.com"

            url = await generate_docx_variant(version_id, "bn", mock_db)
            
            assert url == "https://signed-url.com"
            mock_create_bn.assert_called_once_with("Test Content")
            # Verify blob name contains _BN
            args, _ = mock_bucket.blob.call_args
            assert "_BN.docx" in args[0]

@pytest.mark.asyncio
async def test_generate_docx_variant_salomone():
    # Mock DB Session
    mock_db = MagicMock()
    
    # Mock Version
    version_id = str(uuid4())
    mock_version = ReportVersion(
        id=version_id,
        case_id=uuid4(),
        organization_id=uuid4(),
        ai_raw_output="Test Content",
        is_final=False
    )
    mock_db.query.return_value.filter.return_value.first.return_value = mock_version

    # Ensure module is loaded for patch to work
    from services import docx_generator_salomone

    # Mock Generator (Salomone)
    with patch("services.docx_generator_salomone.create_styled_docx") as mock_create_salomone:
        mock_create_salomone.return_value = MagicMock() # Stream
        
        # Mock GCS
        with patch("services.report_generation_service.get_storage_client") as mock_gcs:
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            mock_gcs.return_value.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            mock_blob.generate_signed_url.return_value = "https://signed-url.com"

            url = await generate_docx_variant(version_id, "salomone", mock_db)
            
            assert url == "https://signed-url.com"
            mock_create_salomone.assert_called_once_with("Test Content")
            # Verify blob name contains _Salomone
            args, _ = mock_bucket.blob.call_args
            assert "_Salomone.docx" in args[0]
