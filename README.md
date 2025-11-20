# AI Insurance Report Generator

An AI-powered web application that helps insurance professionals generate professional, high-quality insurance reports in Italian. The application leverages Google's Gemini 2.5 model to process uploaded documents and produce structured reports that can be reviewed, edited, and downloaded as DOCX files.

## Features

- **Multi-Format Document Support**: Upload images (PNG, JPEG), PDFs, DOCX, XLSX, TXT, and EML files
- **Intelligent Document Processing**: Automatic OCR for images, text extraction from documents, and data extraction from spreadsheets
- **AI-Powered Report Generation**: Uses Gemini 2.5 to generate professional Italian insurance reports based on uploaded documents
- **Report Preview & Editing**: Clean web interface to preview and edit generated reports before download
- **Professional DOCX Export**: Download reports as formatted Word documents with proper styling and structure
- **Admin Panel**: Administrative interface for system monitoring, report management, and configuration
- **Rate Limiting**: Built-in protection against abuse with configurable rate limits
- **Authentication**: Basic HTTP authentication for admin access

## Target Users

- Cargo Surveyors
- Claims Handlers
- Insurance Surveyors
- Legal professionals working with insurance claims
- Any professional requiring standardized insurance reports in Italian

## Prerequisites

- Python 3.10 or higher
- Google Gemini API key
- (Optional) PostgreSQL database for production deployments

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/andreasalomone/perito.git
   cd report-ai
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Create a `.env` file in the root directory with the following variables:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   FLASK_SECRET_KEY=your_secret_key_here
   BASIC_AUTH_USERNAME=admin
   BASIC_AUTH_PASSWORD=your_secure_password
   DATABASE_URL=sqlite:///instance/project.db  # Or PostgreSQL URL for production
   LOG_LEVEL=INFO
   PORT=5000
   ```

## Configuration

Configuration is managed through environment variables and the `core/config.py` file. Key settings include:

- **File Upload Limits**: 
  - Max file size: 25 MB (configurable via `MAX_FILE_SIZE_MB`)
  - Max total upload size: 100 MB (configurable via `MAX_TOTAL_UPLOAD_SIZE_MB`)

- **LLM Settings**:
  - Model: `gemini-2.5-pro`
  - Temperature: 0.5
  - Max tokens: 64000
  - Retry attempts: 3

- **DOCX Generation**:
  - Font: Times New Roman
  - Normal font size: 12pt
  - Heading font size: 12pt
  - Line spacing: 1.5

See `core/config.py` for all available configuration options.

## Usage

### Running the Application

#### Development Mode
```bash
python app.py
```
The application will be available at `http://localhost:5000`

#### Production Mode (with Hypercorn)
```bash
python run_server.py
```

### Database Initialization

Initialize the database schema:
```bash
flask init-db
```

### Using the Application

1. **Upload Documents**: Navigate to the home page and upload one or more documents related to your insurance claim
2. **Generate Report**: The AI will process your documents and generate a draft report in Italian
3. **Review & Edit**: Review the generated report and make any necessary edits in the preview interface
4. **Download**: Download the final report as a DOCX file

### Admin Panel

Access the admin panel at `/admin/login` using your configured credentials. The admin panel provides:
- System monitoring and statistics
- Report history and details
- AI control and configuration
- Template management

## Project Structure

```
report-ai/
├── admin/              # Admin panel routes, templates, and services
├── assets/             # Static assets (logos, favicons)
├── core/               # Core configuration, database, and models
├── docs/               # Documentation and coding guidelines
├── instance/           # Database files (SQLite)
├── scripts/            # Utility scripts
├── static/             # CSS and static files
├── templates/          # HTML templates
├── tests/              # Test suite
├── uploads/            # User-uploaded files (temporary)
├── app.py              # Main Flask application
├── document_processor.py  # Document processing logic
├── docx_generator.py   # DOCX generation logic
├── llm_handler.py      # LLM integration and prompt management
├── run_server.py       # Production server entry point
└── requirements.txt    # Python dependencies
```

## Development

### Code Style

This project follows strict coding guidelines (see `docs/rules/`):
- **SOLID Principles**: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion
- **KISS**: Keep It Simple, Stupid
- **DRY**: Don't Repeat Yourself
- **YAGNI**: You Ain't Gonna Need It
- **Python**: PEP 8 compliance, type hints, docstrings
- **Testing**: Unit tests, integration tests, and E2E tests

### Running Tests

```bash
pytest
```

Run with coverage:
```bash
pytest --cov=. --cov-report=html
```

### Development Dependencies

Install development dependencies:
```bash
pip install -r requirements-dev.txt
```

## Technology Stack

- **Backend**: Flask (async), Hypercorn
- **AI/ML**: Google Gemini 2.5 API
- **Database**: SQLite (development) / PostgreSQL (production)
- **Document Processing**: PyMuPDF, python-docx, openpyxl, Pillow
- **Authentication**: Flask-HTTPAuth
- **Rate Limiting**: Flask-Limiter
- **Configuration**: Pydantic Settings

## API Endpoints

- `GET /` - Home page with document upload interface
- `POST /upload` - Upload documents for processing
- `POST /generate` - Generate report from uploaded documents
- `GET /report/<report_id>` - View generated report
- `POST /report/<report_id>/edit` - Edit report content
- `GET /download/<report_id>` - Download report as DOCX
- `/admin/*` - Admin panel routes

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]

## Support

For issues, questions, or feature requests, please [create an issue](https://github.com/andreasalomone/perito/issues) on GitHub.

## Acknowledgments

Built with Google Gemini 2.5 for intelligent report generation.

