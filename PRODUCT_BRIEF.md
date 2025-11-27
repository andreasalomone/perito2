# Product Brief: AI Insurance Report Generator
**RobotPerizia Report-AI**

Version: 1.0  
Date: November 27, 2025  
Author: Product Team

---

## 1. Executive Summary

**RobotPerizia Report-AI** is an intelligent web application that revolutionizes the insurance reporting workflow for Italian insurance professionals. Leveraging Google's Gemini 2.5 AI model, the application automatically processes multi-format documents (images, PDFs, spreadsheets, emails) and generates professional, comprehensive insurance reports in Italian following industry-standard formats and terminology.

**Key Value Proposition:**
- **Time Savings**: Reduce report generation time from hours to minutes
- **Professional Quality**: Consistent, detailed reports adhering to industry standards
- **Intelligent Processing**: Multi-modal AI handles text, images, and structured data
- **User-Friendly**: Simple upload-generate-edit-download workflow

---

## 2. Product Overview

### 2.1 What is Report-AI?

Report-AI is a specialized document processing and report generation platform built for:
- Cargo Surveyors
- Claims Handlers  
- Insurance Surveyors
- Legal professionals handling insurance claims

The application automates the tedious process of extracting information from claim documents and synthesizing it into professional Italian insurance reports (perizie).

### 2.2 How It Works

```mermaid
graph LR
    A[Upload Documents] --> B[AI Processing]
    B --> C[Extract Information]
    C --> D[Generate Report]
    D --> E[Review & Edit]
    E --> F[Download DOCX]
```

**Core Workflow:**
1. **Upload**: Users upload claim-related documents (photos, PDFs, spreadsheets, emails)
2. **Process**: AI extracts text via OCR, parses structured data, and analyzes images
3. **Generate**: Gemini 2.5 synthesizes a comprehensive Italian insurance report
4. **Review**: Users preview and edit the generated report in a clean interface
5. **Export**: Download professionally formatted DOCX files ready for submission

---

## 3. Current Features & Capabilities

### 3.1 Document Processing

| Feature | Details |
|---------|---------|
| **Supported Formats** | PNG, JPEG, PDF, DOCX, XLSX, TXT, EML |
| **Upload Limits** | 25 MB per file, 100 MB total per report |
| **OCR Processing** | Automatic text extraction from images and scanned PDFs |
| **Vision Analysis** | AI image understanding for photos of damage, documents, etc. |
| **Spreadsheet Parsing** | Extracts tabular data from Excel files |
| **Email Processing** | Parses EML files including attachments |

**Technical Implementation:**
- PyMuPDF for PDF processing
- Pillow for image handling
- openpyxl for Excel parsing
- Custom multi-modal pipeline for Gemini API

### 3.2 AI Report Generation

| Capability | Implementation |
|------------|----------------|
| **AI Model** | Google Gemini 2.5 Pro |
| **Language** | Italian (specialized insurance terminology) |
| **Report Structure** | Based on industry-standard perizia format |
| **Content Quality** | Professional tone, detailed narrative (500+ words per section) |
| **Retry Mechanism** | 3-attempt linear retry with fallback model |
| **Cache System** | Context caching to optimize costs and speed |

**Key Sections Generated:**
- Dati della Spedizione (Shipment Data)
- Dinamica degli Eventi ed Accertamenti (Event Timeline & Findings)
- Computo del Danno (Damage Calculation)
- Cause del Danno (Root Causes)

### 3.3 User Interface

**Main Application:**
- Clean, modern upload interface with drag-and-drop
- Real-time progress tracking with step-by-step logs
- In-browser report preview and editing
- One-click DOCX download with professional formatting

**Admin Dashboard** (`/admin`):
- System monitoring and statistics
- Report history with detailed metrics
- Document processing logs per report
- Token usage and API cost tracking
- AI control panel for configuration
- Template management

### 3.4 Technical Infrastructure

| Component | Technology |
|-----------|-----------|
| **Backend** | Flask (async), Python 3.10+ |
| **Task Queue** | Celery with Redis |
| **Database** | PostgreSQL (production), SQLite (dev) |
| **AI Integration** | Google Gemini API |
| **Document Export** | python-docx with custom styling |
| **Authentication** | Flask-HTTPAuth (Basic Auth) |
| **Rate Limiting** | Flask-Limiter |
| **Monitoring** | Prometheus metrics |
| **Deployment** | Docker, Render platform |

### 3.5 Data & Analytics

**Report Tracking (ReportLog Model):**
- Unique report ID with timestamp
- Status (processing, success, error)
- Generation time in seconds
- API cost in USD
- Token usage breakdown (prompt, candidates, cached, total)
- Real-time progress logs
- LLM raw response and final edited text

**Document Tracking (DocumentLog Model):**
- Original filename and file type
- File size in bytes
- Extraction status per document
- Extraction method (text vs vision)
- Extracted content length
- Error messages for debugging

---

## 4. User Personas

### Persona 1: **Carlo - Cargo Surveyor**
**Demographics:** 45 years old, 15 years experience in cargo surveying  
**Technical Skills:** Moderate (comfortable with web apps, not a developer)  
**Pain Points:**
- Spends 3-4 hours writing each perizia manually
- Repetitive data entry from shipping documents
- Needs consistent terminology and formatting
- Tight deadlines from insurance companies

**Goals:**
- Generate first draft in under 10 minutes
- Maintain professional quality and detail
- Focus time on analysis, not typing

### Persona 2: **Sofia - Claims Handler**
**Demographics:** 32 years old, works for a mid-size insurance company  
**Technical Skills:** High (uses multiple industry tools daily)  
**Pain Points:**
- Handles 20-30 claims simultaneously
- Needs to produce standardized reports quickly
- Struggles with handwritten notes and poor-quality photos
- Requires audit trail for compliance

**Goals:**
- Batch process multiple claims efficiently
- Ensure all required sections are complete
- Download reports ready for legal review

### Persona 3: **Marco - Legal Professional**
**Demographics:** 50 years old, represents claimants in insurance disputes  
**Technical Skills:** Low (prefers simple, intuitive tools)  
**Pain Points:**
- Receives documents in various formats from clients
- Needs detailed technical analysis for court
- Limited time to prepare extensive documentation

**Goals:**
- Transform client evidence into professional reports
- Include photos and damage calculations automatically
- Present credible, well-formatted documentation in court

---

## 5. Key User Flows

### 5.1 First-Time User Report Generation

1. User lands on homepage (`/`)
2. Reads brief instructions on supported formats
3. Clicks upload area or drags documents
4. Uploads 5-10 files (photos, CMR, invoice Excel)
5. Clicks "Generate Report"
6. Sees real-time progress:
   - "Analisi file: IMG_1234.jpg"
   - "Testo estratto da fattura.xlsx (2341 caratteri)"
   - "Generazione report con AI in corso..."
7. After 30-90 seconds, sees "Report generato con successo"
8. Reviews generated report, makes minor edits
9. Clicks "Download Report"
10. Receives DOCX file with Salomone & Associati branding

### 5.2 Admin Monitoring Flow

1. Admin logs in at `/admin/login` with credentials
2. Views dashboard with key metrics:
   - Reports generated today: 47
   - Success rate: 94%
   - Average generation time: 38s
   - Total API cost today: $12.34
3. Clicks on recent report to see details
4. Reviews 8 uploaded documents with extraction methods
5. Checks token usage: 45K prompt, 15K response, 30K cached
6. Reads full LLM raw response for quality check
7. Notes one document failed extraction, investigates error

---

## 6. Technical Architecture Highlights

### 6.1 Asynchronous Processing

**Challenge:** Document processing and AI generation can take 30-120 seconds  
**Solution:** Celery task queue with Redis broker

```python
# User uploads → immediate response with report_id
# Background task processes files asynchronously
@celery_app.task(bind=True)
def generate_report_task(report_id, file_paths, ...):
    # Process documents
    # Call LLM API
    # Update database with results
```

**User Experience:** Non-blocking UI with real-time progress updates via status polling

### 6.2 Multi-Modal LLM Integration

**Challenge:** Handle both text and images in a single report  
**Solution:** Unified processing pipeline with vision support

- **Text Entries:** Extracted content from PDFs, DOCX, TXT, XLSX
- **Vision Entries:** Images sent to Gemini with vision capabilities
- **Combined Prompt:** Both types merged into single API call

### 6.3 Cost Optimization

**Challenge:** Gemini API costs can accumulate with large documents  
**Solution:** Context caching and intelligent retry logic

1. **First Attempt:** Use context cache (if available)
2. **On Cache Error:** Retry without cache
3. **On Overload:** Retry with exponential backoff
4. **Final Fallback:** Use alternate model (Gemini 2.5 Flash)

**Result:** Significant cost savings via cached content tokens (billed at 1/10 rate)

### 6.4 Robust Error Handling

**Production-Hardened Features:**
- Linear retry logic for LLM failures (3 attempts)
- Graceful degradation (cache → no cache → fallback model)
- Per-document error tracking (some docs can fail without blocking report)
- Comprehensive logging with Prometheus metrics
- Token limit truncation to prevent API rejections

---

## 7. Current Pain Points & Known Issues

### 7.1 User Experience Challenges

| Issue | Impact | Severity |
|-------|--------|----------|
| **No user accounts** | Reports are session-based only, no history | Medium |
| **Single report at a time** | Users can't queue multiple reports | Medium |
| **Limited editing** | Basic textarea, no rich formatting tools | Low |
| **No collaborative features** | Can't share reports with colleagues | Medium |
| **Mobile experience** | Not optimized for phones/tablets | Low-Medium |

### 7.2 Technical Limitations

| Issue | Impact | Severity |
|-------|--------|----------|
| **Token limit handling** | Very large documents may get truncated | Medium |
| **Long processing times** | Complex reports take 60-120s, user waits | Medium |
| **No batch processing** | Must upload one report at a time | Medium |
| **File size constraints** | 25 MB per file may be too small for high-res photos | Low |
| **Email attachment depth** | Nested EML attachments not fully supported | Low |

### 7.3 Admin & Monitoring Gaps

| Issue | Impact | Severity |
|-------|--------|----------|
| **No user analytics** | Can't track which users generate most reports | Low |
| **Limited template customization** | Report format is hardcoded | Medium |
| **No A/B testing** | Can't experiment with different prompts | Low |
| **Alert system missing** | No notifications for high error rates | Low |

---

## 8. Opportunities for Enhancement

### 8.1 UX Improvements (High Priority)

#### **1. User Account System**
**Problem:** No way to access previously generated reports  
**Opportunity:**
- User registration and login
- Personal dashboard with report history
- "Regenerate" button for past reports
- Export history tracking

**Impact:** Increases user retention, enables SaaS model

#### **2. Real-Time Collaboration**
**Problem:** Solo workflow, no team features  
**Opportunity:**
- Share reports with colleagues via link
- Comment and annotation system
- Review/approval workflow
- Role-based access (surveyor, reviewer, admin)

**Impact:** Unlocks enterprise adoption

#### **3. Enhanced Editing Interface**
**Problem:** Basic textarea is limiting  
**Opportunity:**
- Rich text editor with formatting preservation
- AI-assisted rewriting of specific sections
- Grammar and style suggestions (Italian-specific)
- Template section reordering via drag-and-drop
- Inline image insertion

**Impact:** Higher quality final reports, less external editing

#### **4. Mobile-Optimized Experience**
**Problem:** Desktop-only design  
**Opportunity:**
- Responsive UI for tablets
- Photo upload directly from mobile camera
- Simplified mobile workflow for field surveyors
- PWA (Progressive Web App) for offline capabilities

**Impact:** Use in field during inspections

#### **5. Batch Upload & Processing**
**Problem:** One report at a time  
**Opportunity:**
- Upload folder of documents, auto-sort by claim
- Parallel report generation (queue system UI)
- Bulk export to ZIP file
- Scheduled report generation (e.g., nightly)

**Impact:** 10x throughput for high-volume users

### 8.2 AI & Intelligence Features (Medium Priority)

#### **6. Multi-Language Support**
**Problem:** Italian only  
**Opportunity:**
- English, German, French report generation
- Auto-detect document language
- Bilingual reports (e.g., Italian + English)

**Impact:** International market expansion

#### **7. Smart Document Classification**
**Problem:** All documents treated equally  
**Opportunity:**
- Auto-identify document types (invoice, CMR, photo, policy)
- Extract structured data (policy numbers, dates, amounts)
- Pre-fill report sections based on document type
- Highlight missing critical documents

**Impact:** Better report quality, faster processing

#### **8. Damage Cost Prediction**
**Problem:** Manual cost estimation  
**Opportunity:**
- Train model on historical claims data
- Auto-suggest repair costs based on damage photos
- Compare against market rates
- Flag unusually high/low estimates

**Impact:** More accurate damage quantification

#### **9. Quality Scoring**
**Problem:** No automated quality check  
**Opportunity:**
- AI scores report completeness (0-100)
- Flags missing required sections
- Identifies contradictions in narrative
- Suggests areas needing more detail

**Impact:** Reduce revision cycles

#### **10. Voice Dictation**
**Problem:** Typing-heavy workflow  
**Opportunity:**
- Voice-to-text for field notes
- Dictate edits directly into report
- Italian speech recognition optimized for technical terms

**Impact:** Faster data entry in field

### 8.3 Integration & Workflow (Medium Priority)

#### **11. Insurance System Integration**
**Problem:** Standalone tool  
**Opportunity:**
- API for third-party claims management systems
- Auto-export to carrier portals
- Import claims data via API
- Webhook notifications on report completion

**Impact:** Seamless workflow integration

#### **12. Email & Notification System**
**Problem:** Must manually check for completion  
**Opportunity:**
- Email notification when report ready
- SMS alerts for mobile users
- Scheduled report summaries (weekly digest)
- Error alerts for failed generations

**Impact:** Proactive user engagement

#### **13. Cloud Storage Integration**
**Problem:** Manual file downloads  
**Opportunity:**
- Auto-save to Google Drive / Dropbox
- Import documents directly from cloud storage
- Version history in cloud
- Shared team folders

**Impact:** Better document management

### 8.4 Analytics & Business Intelligence (Low Priority)

#### **14. Advanced Analytics Dashboard**
**Problem:** Basic metrics only  
**Opportunity:**
- Cost per report trends
- Processing time by document type
- User adoption metrics
- Report quality scores over time
- Custom date range reports

**Impact:** Better business decisions

#### **15. Template Marketplace**
**Problem:** One standard template  
**Opportunity:**
- Multiple perizia templates (cargo, auto, property)
- User-created custom templates
- Marketplace for sharing templates
- Template versioning and rollback

**Impact:** Serve diverse insurance sectors

---

## 9. Feature Prioritization Framework

### Priority Matrix

| Feature | User Impact | Development Effort | Priority Score |
|---------|-------------|-------------------|----------------|
| User Accounts | High | Medium | **9/10** |
| Enhanced Editing | High | Medium | **8/10** |
| Batch Processing | High | Medium | **8/10** |
| Mobile Optimization | Medium | High | **7/10** |
| Smart Classification | High | High | **7/10** |
| Collaboration | Medium | Medium | **6/10** |
| Multi-Language | Medium | Medium | **6/10** |
| Damage Prediction | Medium | High | **5/10** |
| Cloud Integration | Low | Low | **5/10** |
| Voice Dictation | Low | Medium | **4/10** |

### Recommended Roadmap

**Q1 2026: Foundation**
- User account system
- Report history dashboard
- Enhanced text editor

**Q2 2026: Efficiency**
- Batch upload/processing
- Mobile-responsive UI
- Email notifications

**Q3 2026: Intelligence**
- Smart document classification
- Auto-fill from extracted data
- Quality scoring

**Q4 2026: Collaboration**
- Team sharing features
- Review/approval workflow
- Template customization

---

## 10. Competitive Differentiation

### What Makes Report-AI Unique?

| Feature | Report-AI | Traditional Tools | Competitors |
|---------|-----------|------------------|-------------|
| **AI-Powered** | ✅ Gemini 2.5 | ❌ Manual | ⚠️ Basic templates |
| **Multi-Modal** | ✅ Text + Vision | ⚠️ Text only | ✅ Some support |
| **Italian Specialized** | ✅ Insurance jargon | ❌ Generic | ❌ Generic |
| **Real-Time Progress** | ✅ Live updates | ❌ Black box | ⚠️ Basic status |
| **Professional DOCX** | ✅ Styled export | ⚠️ Basic format | ✅ Yes |
| **Cost Tracking** | ✅ Per-report costs | ❌ N/A | ❌ Usually hidden |
| **Open Architecture** | ✅ API-first | ❌ Closed | ⚠️ Limited APIs |

**Key Strengths:**
1. Purpose-built for Italian insurance reporting
2. Handles messy real-world documents (photos, handwritten notes, etc.)
3. Transparent AI processing with full audit trail
4. Self-hosted option for data privacy compliance

---

## 11. Success Metrics & KPIs

### Current Metrics (Baseline)

| Metric | Current Value | Target |
|--------|--------------|--------|
| **Adoption** | | |
| Active users | Unknown (no accounts) | 100 in 6 months |
| Reports/week | N/A | 200 |
| **Quality** | | |
| Success rate | ~94% (from logs) | 98% |
| Avg generation time | 38s | <30s |
| **User Satisfaction** | | |
| Task completion | ~85% (estimated) | 95% |
| Editing time | Unknown | <5 min avg |
| **Business** | | |
| API cost/report | $0.15-0.30 | <$0.20 |
| Revenue/user | $0 (free) | $50/month |

### Proposed New Metrics

**User Engagement:**
- Daily/Weekly/Monthly active users (DAU/WAU/MAU)
- Report generation frequency per user
- Premium feature adoption rate
- User retention (30/60/90 day)

**Product Quality:**
- Report edit rate (% of reports edited before download)
- Average edits per report
- Report abandonment rate
- AI quality score (internal metric)

**Business Health:**
- Customer acquisition cost (CAC)
- Lifetime value (LTV)
- Monthly recurring revenue (MRR)
- Net Promoter Score (NPS)

---

## 12. Technical Debt & Refactoring Needs

### Code Quality Initiatives

1. **Increase Test Coverage**
   - Current: ~10% for llm_handler.py
   - Target: 80%+ for critical paths
   - Add E2E tests for full workflow

2. **API Documentation**
   - Generate OpenAPI/Swagger docs
   - Create developer portal
   - Add code examples

3. **Performance Optimization**
   - Database query optimization
   - Redis caching for status checks
   - CDN for static assets

4. **Security Hardening**
   - OWASP Top 10 audit
   - Penetration testing
   - Data encryption at rest

---

## 13. Go-To-Market Considerations

### Pricing Strategy Ideas

**Freemium Model:**
- Free: 5 reports/month, watermarked
- Pro: $29/month, unlimited, custom branding
- Enterprise: $199/month, team features, API access

**Pay-Per-Report:**
- $2 per report (simple)
- $5 per report (complex, 10+ documents)
- Volume discounts (100+ reports)

### Target Markets

1. **Individual Surveyors** (Freelancers)
   - Price-sensitive, value time savings
   - Marketing: SEO, industry forums, LinkedIn

2. **Small Surveying Firms** (3-10 people)
   - Need team collaboration
   - Marketing: Direct outreach, trade shows

3. **Insurance Companies** (In-house claims)
   - High volume, compliance requirements
   - Marketing: Enterprise sales, RFPs

4. **Legal Firms** (Specializing in insurance)
   - Occasional use, high quality needs
   - Marketing: Legal directories, referrals

---

## 14. Regulatory & Compliance

### Data Privacy (GDPR)

**Current Status:**
- Data stored in PostgreSQL (potentially personal info)
- No explicit user consent flow
- No data retention policy documented

**Needed Enhancements:**
- Cookie consent banner
- Privacy policy and terms of service
- Data export for users (GDPR right to access)
- Data deletion (GDPR right to be forgotten)
- DPA (Data Processing Agreement) for enterprise

### Document Security

**Current Measures:**
- HTTPS in production
- Basic authentication for admin
- Temporary file cleanup after processing

**Recommended Additions:**
- End-to-end encryption for uploads
- Document access logs
- Two-factor authentication (2FA)
- Role-based access control (RBAC)
- SOC 2 Type II certification (for enterprise)

---

## 15. Appendix: Technical Specifications

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Home page upload form |
| POST | `/upload` | Upload files, create report |
| GET | `/report/<id>` | View generated report |
| GET | `/report/status/<id>` | Check generation status (AJAX) |
| GET | `/download_report/<id>` | Download DOCX |
| POST | `/report/<id>/edit` | Save edited content |
| GET | `/admin/login` | Admin authentication |
| GET | `/admin/dashboard` | Admin panel |
| GET | `/admin/report_detail/<id>` | Detailed report view |

### Database Schema

**report_log** (Main report tracking)
- `id` (PK, UUID)
- `created_at` (timestamp)
- `status` (enum: processing/success/error)
- `generation_time_seconds` (float)
- `api_cost_usd` (float)
- `error_message` (text)
- `progress_logs` (JSON array)
- `current_step` (string)
- `prompt_token_count`, `candidates_token_count`, `total_token_count`, `cached_content_token_count` (integers)
- `llm_raw_response` (text)
- `final_report_text` (text)

**document_log** (Individual document tracking)
- `id` (PK, UUID)
- `report_id` (FK)
- `original_filename` (string)
- `stored_filepath` (string)
- `file_size_bytes` (integer)
- `extraction_status` (enum: processing/success/error/skipped)
- `extracted_content_length` (integer)
- `error_message` (text)
- `file_type` (string)
- `extraction_method` (string: text/vision)

### Environment Configuration

**Required Variables:**
- `GEMINI_API_KEY` - Google AI API key
- `FLASK_SECRET_KEY` - Session encryption
- `BASIC_AUTH_USERNAME`, `BASIC_AUTH_PASSWORD` - Admin credentials
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection for Celery

**Optional:**
- `MAX_FILE_SIZE_MB` (default: 25)
- `MAX_TOTAL_UPLOAD_SIZE_MB` (default: 100)
- `LLM_TEMPERATURE` (default: 0.5)
- `LLM_MAX_OUTPUT_TOKENS` (default: 64000)
- `LOG_LEVEL` (default: INFO)

---

## 16. Conclusion & Next Steps

### Summary

RobotPerizia Report-AI is a production-ready AI-powered solution that successfully automates insurance report generation. The product demonstrates strong technical foundations:
- Robust multi-modal document processing
- Intelligent LLM integration with cost optimization
- Professional-grade output quality
- Real-time progress tracking
- Comprehensive admin monitoring

### Immediate Next Steps for Product Team

1. **Gather User Feedback**
   - Interview 5-10 active users
   - Identify biggest pain points
   - Validate prioritization matrix

2. **Define MVP for User Accounts**
   - Design login/registration flow
   - Plan database schema changes
   - Create implementation plan

3. **Prototype Enhanced Editor**
   - Evaluate rich text editor libraries
   - Design section-based editing UI
   - Test with users

4. **Business Model Research**
   - Survey pricing willingness
   - Analyze competitor pricing
   - Build financial model

5. **Roadmap Alignment**
   - Present this brief to stakeholders
   - Finalize Q1 2026 priorities
   - Assign feature owners

### Questions for Discussion

1. What is the target customer segment for the next 6 months?
2. Should we build user accounts before or after mobile optimization?
3. What is the acceptable API cost per report for a sustainable business?
4. Do we want to remain Italian-only or expand language support?
5. Self-hosted vs SaaS: which deployment model to prioritize?

---

**Document Version:** 1.0  
**Last Updated:** November 27, 2025  
**Contact:** Product Team - RobotPerizia

---
