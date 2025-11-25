import pytest
from admin.services import get_dashboard_stats, get_paginated_documents
from core.models import DocumentLog, ExtractionStatus, ReportLog, ReportStatus
from core.database import db

def test_get_dashboard_stats(app, client):
    """Test that dashboard stats are calculated correctly."""
    with app.app_context():
        # Create some dummy data
        report1 = ReportLog(status=ReportStatus.SUCCESS, api_cost_usd=0.05, generation_time_seconds=10.0)
        report2 = ReportLog(status=ReportStatus.ERROR)
        db.session.add_all([report1, report2])
        db.session.commit()

        doc1 = DocumentLog(report_id=report1.id, original_filename="doc1.pdf", stored_filepath="path/to/doc1.pdf", file_size_bytes=1024, extraction_status=ExtractionStatus.SUCCESS)
        doc2 = DocumentLog(report_id=report1.id, original_filename="doc2.pdf", stored_filepath="path/to/doc2.pdf", file_size_bytes=2048, extraction_status=ExtractionStatus.ERROR)
        db.session.add_all([doc1, doc2])
        db.session.commit()

        stats = get_dashboard_stats()

        assert stats["reports_generated"] == 1
        assert stats["processing_errors"] == 1
        assert stats["api_cost_monthly_est"] == "$0.05"
        assert stats["avg_generation_time_secs"] == "10s"
        assert stats["total_documents"] == 2
        assert stats["extraction_success_rate"] == "50.0%"

def test_get_paginated_documents(app, client):
    """Test that documents are paginated correctly."""
    with app.app_context():
        # Create a report and some documents
        report = ReportLog(status=ReportStatus.SUCCESS)
        db.session.add(report)
        db.session.commit()

        docs = []
        for i in range(25):
            docs.append(DocumentLog(report_id=report.id, original_filename=f"doc{i}.pdf", stored_filepath=f"path/to/doc{i}.pdf", file_size_bytes=1024))
        db.session.add_all(docs)
        db.session.commit()

        # Test first page
        pagination = get_paginated_documents(page=1, per_page=10)
        assert len(pagination.items) == 10
        assert pagination.total == 25
        assert pagination.pages == 3

        # Test last page
        pagination = get_paginated_documents(page=3, per_page=10)
        assert len(pagination.items) == 5
