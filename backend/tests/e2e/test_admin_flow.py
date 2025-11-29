import pytest
from core.models import ReportLog, ReportStatus
from services import db_service

def test_admin_dashboard_access(client):
    """Verify admin dashboard is accessible."""
    response = client.get('/admin')
    assert response.status_code == 200
    assert b"Dashboard" in response.data

def test_admin_reports_list(client, app):
    """Verify reports list page shows reports."""
    # Seed a report
    with app.app_context():
        report = db_service.create_initial_report_log()
        db_service.update_report_status(report.id, ReportStatus.SUCCESS, final_report_text="Test Report")
        report_id = report.id

    response = client.get('/admin/reports')
    assert response.status_code == 200
    assert str(report_id).encode() in response.data

def test_admin_report_detail(client, app):
    """Verify report detail page loads."""
    # Seed a report
    with app.app_context():
        report = db_service.create_initial_report_log()
        db_service.update_report_status(
            report.id, 
            ReportStatus.SUCCESS, 
            final_report_text="Test Report Detail",
            llm_raw_response="Test Report Detail"
        )
        report_id = report.id

    response = client.get(f'/admin/reports/{report_id}')
    assert response.status_code == 200
    assert b"Test Report Detail" in response.data
