# AI PDF Assistant API

A high-performance, modular FastAPI backend service designed to process PDF documents using full-page Optical Character Recognition (OCR) and Google's Gemini Generative AI. The application enables authenticated users to upload PDF materials, perform page-level image rendering and Tesseract OCR, generate structured AI summaries, and generate 10-question multiple-choice quizzes that are persisted in SQLite with secured correct answers.

---

## Key Features

- **User Management & Authentication**: User registration with Argon2 password hashing (`pwdlib`), JWT token issuance, and OAuth2 bearer token protection (`pyjwt`).
- **Protected PDF Document Upload**: Validates PDF extension and `%PDF` magic bytes header, saving uploaded documents with unique UUID filenames in isolated server storage.
- **Full-Page Image Rendering**: Uses PyMuPDF (`pymupdf`) to render every PDF page as a high-resolution 200 DPI image pixmap, ensuring full visual canvas coverage.
- **Tesseract OCR Extraction**: Uses `pytesseract` and `Pillow` to extract text from rendered page images. Handles normal text PDFs, scanned/image PDFs, and mixed pages containing both vector text and embedded images containing text.
- **Text Normalization & Cleaning**: Strips line-level whitespace formatting noise while preserving paragraph boundaries and reading order.
- **Prompt Injection Defense**: Wraps extracted OCR text inside strict boundary delimiters (`--- DOCUMENT CONTENT START ---`) and explicitly instructs Gemini to treat document content purely as untrusted data.
- **AI-Powered Summary Generation**: Integrates Google Gemini AI (`google-genai` / `gemini-2.5-flash`) to generate structured summaries. Features an automated chunking strategy (15,000 chars with 1,000-char overlap) for long documents.
- **AI-Powered Quiz Generation**: Prompts Gemini to generate 10-question multiple-choice quizzes with options A/B/C/D, explanations, and correct answers. Includes strict JSON payload validation.
- **Relational Quiz Persistence**: Persists generated quizzes and individual questions in SQLite using SQLAlchemy 2.x ORM models (`Quiz` and `QuizQuestion`).
- **Secure Answer Protection**: `correct_answer` is stored in the database for future scoring endpoints, but is **intentionally excluded** from public API response schemas.
- **Interactive Documentation**: Auto-generated interactive OpenAPI/Swagger UI (`/docs`) and ReDoc (`/redoc`).
- **Automated Test Coverage**: Complete test suites for OCR extraction, Summary API, and Quiz API using in-memory SQLite and mock AI responses.

---

## Architecture & Pipeline Workflow

```text
Client / Swagger UI
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│                   FastAPI Application                    │
└─────────────────────────────┬────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│         JWT / OAuth2 Authentication & Security           │
└─────────────────────────────┬────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│          Material Lookup & Ownership Check               │
└─────────────────────────────┬────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│             Physical Storage (uploads/*.pdf)             │
└─────────────────────────────┬────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│     PyMuPDF (Page-level 200 DPI Pixmap Image Render)     │
└─────────────────────────────┬────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│            Pillow In-Memory PNG Image Stream             │
└─────────────────────────────┬────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│             Tesseract OCR Engine (pytesseract)           │
└─────────────────────────────┬────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│       Cleaned & Normalized Document Text Stream          │
└─────────────────────────────┬────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│           Google Gemini AI Service (google-genai)        │
│    ├── Prompt Injection Boundary Security                │
│    ├── Long Document Chunking Strategy                   │
│    ├── Summary Generation Service                        │
│    └── Quiz JSON Generation & Payload Validation         │
└─────────────────────────────┬────────────────────────────┘
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
┌──────────────────────────────┐ ┌─────────────────────────┐
│ SQLite DB Persistence        │ │ JSON API Response       │
│ • Quiz (Metadata)            │ │ • SummaryResponse       │
│ • QuizQuestion (+Ans in DB)  │ │ • QuizResponse (No Ans) │
└──────────────────────────────┘ └─────────────────────────┘
```

### Pipeline Responsibilities:
1. **PyMuPDF (`pymupdf`)**: Renders every PDF page into a high-resolution image pixmap canvas.
2. **Pillow (`PIL`)**: Converts raw image pixmap bytes into in-memory image objects for pytesseract.
3. **Tesseract (`pytesseract`)**: Performs Optical Character Recognition on complete page images.
4. **Google Gemini API (`google-genai`)**: Synthesizes clean OCR text into structured AI summaries and validated 10-question multiple-choice quizzes.

---

## Technology Stack

| Technology | Requirement / Version | Role & Purpose |
| :--- | :--- | :--- |
| **Python** | `^3.11` | Primary programming language |
| **FastAPI** | `>=0.110.0` | High-performance ASGI Web Framework |
| **Uvicorn** | `>=0.28.0` | Lightning-fast ASGI Server |
| **SQLAlchemy** | `>=2.0.28` | Relational ORM & Database abstraction |
| **SQLite** | Built-in | Embedded relational database engine (`ai_pdf_assistant.db`) |
| **Pydantic** | `>=2.6.4` | Data validation, settings loading, and schema serialization |
| **Pydantic Settings** | `>=2.2.1` | Environment variable management |
| **PyMuPDF** | `>=1.24.0` | High-speed PDF page rendering engine (`get_pixmap`) |
| **Tesseract OCR / pytesseract** | `>=0.3.10` | Optical Character Recognition engine & Python wrapper |
| **Pillow** | `>=10.0.0` | In-memory image processing library for pytesseract |
| **Google Gemini API** | `>=0.1.0` | Generative AI SDK (`google-genai` / `gemini-2.5-flash`) |
| **PyJWT** | `>=2.8.0` | JSON Web Token encoding and decoding |
| **pwdlib[argon2]** | `>=0.2.0` | Secure password hashing using Argon2 algorithm |
| **python-multipart** | `>=0.0.12` | Multipart form-data handling for file uploads |

---

## Project Structure

```text
ai-pdf-assistant/
│
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app initialization, lifespan, & health endpoint
│   ├── database.py          # SQLAlchemy 2.x engine, SessionLocal, Base, & get_db
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # Settings management via Pydantic BaseSettings
│   │   └── security.py      # Argon2 password hashing, JWT logic, & get_current_user
│   │
│   ├── models/              # SQLAlchemy 2.x database ORM models
│   │   ├── __init__.py
│   │   ├── user.py          # User model (id, username, email, password_hash)
│   │   ├── material.py      # Material model (id, user_id, filename, file_path)
│   │   └── quiz.py          # Quiz & QuizQuestion ORM models
│   │
│   ├── schemas/             # Pydantic validation & response schemas
│   │   ├── __init__.py
│   │   ├── user.py          # User registration & response schemas
│   │   ├── token.py         # JWT Token response schemas
│   │   ├── material.py      # Material response schema
│   │   ├── summary.py       # SummaryResponse schema
│   │   └── quiz.py          # QuizResponse schema (hides correct_answer)
│   │
│   ├── routers/             # FastAPI APIRouter handlers
│   │   ├── __init__.py
│   │   ├── users.py         # POST /users (User registration)
│   │   ├── auth.py          # POST /auth/login (JWT authentication)
│   │   └── materials.py     # Upload, Summary, & Quiz routes
│   │
│   └── services/            # Business logic & external AI services
│       ├── __init__.py
│       ├── pdf_service.py   # PyMuPDF rendering + Tesseract OCR extraction
│       ├── gemini_service.py# Gemini AI client, chunking, & prompt execution
│       ├── summary_service.py # Summary service orchestrator
│       └── quiz_service.py  # Quiz generation, payload validation, & DB persistence
│
├── uploads/                 # Storage directory for uploaded PDF files
├── tests/                   # Automated unit & integration test suites
│   ├── __init__.py
│   ├── test_pdf_service.py  # Page-level OCR service test suite
│   ├── test_summary_api.py  # Summary API endpoint test suite
│   └── test_quiz_api.py     # Quiz API endpoint test suite
│
├── .env                     # Local environment variables (git-ignored)
├── .env.example             # Template configuration file
├── .gitignore               # Git repository ignore rules
├── requirements.txt         # Python package dependencies
└── README.md                # Project documentation
```

---

## API Endpoints Reference

| Method | Endpoint | Authentication | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Public | Application health-check endpoint |
| `POST` | `/users` | Public | Register a new user account |
| `POST` | `/auth/login` | Public | Authenticate user credentials and receive JWT access token |
| `POST` | `/materials/upload` | Bearer JWT | Upload a PDF document and record material metadata |
| `POST` | `/materials/{id}/summary` | Bearer JWT | Render PDF pages, run Tesseract OCR, and generate AI summary |
| `POST` | `/materials/{id}/quiz` | Bearer JWT | Render PDF, run OCR, generate 10-question MCQ quiz, & persist in SQLite |
| `GET` | `/docs` | Public | Auto-generated interactive Swagger UI documentation |
| `GET` | `/redoc` | Public | Auto-generated ReDoc interactive documentation |

---

## Authentication & Authorization

1. **User Registration (`POST /users`)**: Accepts `username`, `email`, and `password`. Passwords are hashed using the Argon2 algorithm via `pwdlib`.
2. **User Login (`POST /auth/login`)**: Accepts OAuth2 form-data (`username`, `password`). Returns a signed JWT access token (`access_token`, `token_type: bearer`).
3. **Route Protection**: Endpoints require the `Authorization: Bearer <access_token>` header. The `get_current_user` dependency decodes the JWT signature, verifies expiration, and injects the authenticated `User` ORM instance.
4. **Resource Ownership Enforcement**: Endpoints `/materials/{id}/summary` and `/materials/{id}/quiz` verify that `material.user_id == current_user.id`. Access attempts by unauthorized users return an explicit `403 Forbidden` response.

---

## PDF Upload & Physical Storage

- **Endpoint**: `POST /materials/upload`
- **Validation**: Accepts multipart `UploadFile`. Validates both `.pdf` file extension and `%PDF` magic bytes header.
- **Physical Storage**: PDF files are assigned a unique 32-character hex UUID (`uploads/<uuid>.pdf`) and saved in the `uploads/` directory on disk.
- **Database Recording**: Inserts a `Material` record storing `filename`, `file_path`, `user_id`, and `created_at` timestamp.

---

## OCR Pipeline Architecture

The application uses **full-page OCR** to guarantee complete text extraction across all document formats:

```text
PDF Document Page
      │
      ▼
PyMuPDF (fitz) renders complete page at 200 DPI → Image Pixmap Buffer
      │
      ▼
Pillow converts Pixmap PNG bytes → In-Memory PIL Image
      │
      ▼
pytesseract executes Tesseract OCR on full page image
      │
      ▼
Raw OCR Text → clean_extracted_text() whitespace normalization
```

### Key Capabilities:
- **Full Canvas Coverage**: Renders the complete page canvas as an image rather than relying on embedded text objects.
- **Handles Mixed Content**: Processes normal text PDFs, scanned/image PDFs, and mixed pages containing both selectable vector text and embedded images with text.
- **Text Cleaning**: Standardizes carriage returns (`\r\n` $\rightarrow$ `\n`), collapses multi-spaces/tabs, and preserves paragraph breaks (`\n\n`).

> [!NOTE]
> **System Requirement for Tesseract OCR**:  
> Standard text processing requires the Tesseract OCR engine binary installed on the operating system:
> - **Windows**: Download installer from [UB-Mannheim Tesseract Wiki](https://github.com/UB-Mannheim/tesseract/wiki). Ensure `tesseract.exe` is in system `PATH` or set `TESSERACT_CMD`.
> - **Linux (Ubuntu/Debian)**: `sudo apt-get install tesseract-ocr`
> - **macOS**: `brew install tesseract`

---

## AI Summary Generation (`POST /materials/{id}/summary`)

1. **Flow**: Validates JWT authentication $\rightarrow$ checks material existence and ownership $\rightarrow$ verifies physical PDF file $\rightarrow$ runs PyMuPDF + Tesseract OCR $\rightarrow$ validates text presence ($\ge 15$ alnum chars) $\rightarrow$ calls Gemini API $\rightarrow$ returns `SummaryResponse`.
2. **Prompt Injection Defense**: Encloses OCR text inside strict boundary delimiters (`--- DOCUMENT CONTENT START ---`) and explicitly instructs Gemini that text within boundaries is strictly untrusted data.
3. **Long Document Chunking**: If OCR text exceeds 15,000 characters, `chunk_text()` splits content into overlapping chunks (1,000-char overlap). Chunks are summarized sequentially and consolidated into a cohesive final summary.

### Example Response:
```json
{
  "material_id": 1,
  "summary": "This document covers FastAPI, SQLAlchemy 2.x ORM architecture, full-page Tesseract OCR rendering, and Gemini AI integration...",
  "source": "ocr"
}
```

---

## AI Quiz Generation (`POST /materials/{id}/quiz`)

1. **Flow**: Authenticates request $\rightarrow$ checks ownership $\rightarrow$ extracts OCR text $\rightarrow$ calls Gemini API for JSON payload $\rightarrow$ validates JSON payload structure $\rightarrow$ persists `Quiz` and `QuizQuestion` records in SQLite $\rightarrow$ returns public `QuizResponse`.
2. **Question Structure**: Generates 10 multiple-choice questions with 4 options (A, B, C, D), correct answer, and explanation.
3. **JSON Payload Validation**: `validate_and_clean_quiz_payload()` enforces root `"questions"` list, option presence, correct answer choice in `("A", "B", "C", "D")`, and removes duplicates.
4. **Security Protection of Correct Answers**: `correct_answer` is saved in the SQLite `quiz_questions` table for future answer submission endpoints, but is **intentionally omitted** from `QuestionResponse` / `QuizResponse` public API output.

### Example Response (`POST /materials/{id}/quiz`):
```json
{
  "quiz_id": 1,
  "material_id": 5,
  "total_questions": 10,
  "created_at": "2026-09-30T16:15:00Z",
  "questions": [
    {
      "id": 1,
      "question_order": 1,
      "question": "What is the primary role of PyMuPDF in the OCR pipeline?",
      "options": {
        "A": "Extracting plain text directly",
        "B": "Rendering PDF pages into high-resolution image pixmaps",
        "C": "Managing database session locks",
        "D": "Signing JWT tokens"
      },
      "explanation": "PyMuPDF is used exclusively to render complete PDF pages as 200 DPI image pixmaps for Tesseract OCR."
    }
  ]
}
```

---

## Database Models & Schema

The application uses an SQLite database (`ai_pdf_assistant.db`) managed via SQLAlchemy 2.x ORM models:

- **`User`**: `id`, `username`, `email`, `password_hash`, `created_at`.
- **`Material`**: `id`, `user_id` (FK $\rightarrow$ `users.id`), `filename`, `file_path`, `created_at`.
- **`Quiz`**: `id`, `material_id` (FK $\rightarrow$ `materials.id`), `user_id` (FK $\rightarrow$ `users.id`), `total_questions`, `created_at`.
- **`QuizQuestion`**: `id`, `quiz_id` (FK $\rightarrow$ `quizzes.id`), `question_order`, `question_text`, `option_a`, `option_b`, `option_c`, `option_d`, `correct_answer`, `explanation`.

---

## Environment Variables Configuration

Copy `.env.example` to `.env` and fill in your configuration:

```bash
cp .env.example .env
```

### Safe Environment Template (`.env.example`):
```env
PROJECT_NAME="AI PDF Assistant API"
PROJECT_VERSION="0.1.0"

# Database Configuration (SQLite default)
DATABASE_URL="sqlite:///./ai_pdf_assistant.db"

# JWT Security Configuration
SECRET_KEY="your-secret-key-change-this-in-production"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Gemini API Configuration
GEMINI_API_KEY="your-gemini-api-key-here"
```

---

## Setup & Local Installation

### 1. Create Virtual Environment
**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Development Server
```bash
uvicorn app.main:app --reload
```
The application will start at `http://127.0.0.1:8000`.

---

## Testing & Verification

### Automated Test Suites
Run the automated test suites using the virtual environment Python interpreter:

```powershell
# Run OCR Service Test Suite
.\venv\Scripts\python.exe -m tests.test_pdf_service

# Run Summary API Test Suite
.\venv\Scripts\python.exe -m tests.test_summary_api

# Run Quiz API Test Suite
.\venv\Scripts\python.exe -m tests.test_quiz_api
```

### Interactive Swagger UI Testing Walkthrough
1. Start the server: `uvicorn app.main:app --reload`
2. Open Swagger UI at `http://127.0.0.1:8000/docs`.
3. Register a user via `POST /users` (`username`, `email`, `password`).
4. Log in via `POST /auth/login` to obtain your `access_token`.
5. Click **Authorize** (top right) and enter `Bearer <access_token>`.
6. Upload a PDF via `POST /materials/upload` and copy the returned material `id`.
7. Execute `POST /materials/{id}/summary` to view the generated AI summary.
8. Execute `POST /materials/{id}/quiz` to generate and persist the 10-question MCQ quiz.
9. Query SQLite to verify database persistence of correct answers:
   ```powershell
   sqlite3 ai_pdf_assistant.db "SELECT id, quiz_id, question_order, correct_answer FROM quiz_questions;"
   ```
