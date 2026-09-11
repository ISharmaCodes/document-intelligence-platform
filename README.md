# Intelligent Document Extraction, Validation & API Platform

An AI-powered document intelligence platform that extracts structured information from invoices and financial statements, validates financial calculations deterministically, stores the latest processed results, and exposes them through a REST API and web dashboard.

Built as an AI Engineer internship technical case study.

---

## Live Demo

**Frontend / Application:**  
https://document-intelligence-platform-rllz.onrender.com/

**Backend API:**  
https://document-intelligence-platform-rllz.onrender.com/api/v1/

**Swagger / OpenAPI:**  
https://document-intelligence-platform-rllz.onrender.com/docs

**Health Check:**  
https://document-intelligence-platform-rllz.onrender.com/api/v1/health

> The application is deployed as a Dockerized FastAPI service on Render.

---

## Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Objectives](#objectives)
- [Supported Documents](#supported-documents)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Document Processing Workflow](#document-processing-workflow)
- [AI and Extraction Approach](#ai-and-extraction-approach)
- [Financial Validation Engine](#financial-validation-engine)
- [API](#api)
- [Database and Persistence](#database-and-persistence)
- [Frontend](#frontend)
- [Project Structure](#project-structure)
- [Technology Stack](#technology-stack)
- [Testing](#testing)
- [Deployment](#deployment)
- [Local Setup](#local-setup)
- [Environment Variables](#environment-variables)
- [Design Decisions](#design-decisions)
- [Limitations](#limitations)
- [Future Improvements](#future-improvements)
- [AI / Tool Usage Declaration](#ai--tool-usage-declaration)
- [Conclusion](#conclusion)

---

## Overview

The Intelligent Document Extraction, Validation & API Platform is designed to process financial documents and invoices and convert their contents into structured, machine-readable data.

The platform supports four document categories:

1. Invoice
2. Balance Sheet
3. Profit & Loss
4. Cash Flow Statement

The user explicitly selects the document type before uploading the file. Automatic document classification is intentionally outside the scope of this case study.

The system accepts PDF, JPG and PNG files, validates them before AI processing, extracts document content using native PDF text extraction and vision-based AI where required, validates the extracted structure using Pydantic schemas, performs deterministic financial calculations using Python, persists the latest result in SQLite, and presents the result through a web dashboard and REST API.

---

## Problem Statement

Financial documents contain large amounts of semi-structured information including:

- Headers
- Dates
- Parties
- Currency information
- Financial line items
- Comparative-period values
- Invoice tables
- Taxes
- Discounts
- Totals
- Cash flow components

Traditional manual extraction is time-consuming and difficult to scale.

The goal of this project is to build a lightweight document intelligence platform that can:

- Read financial documents and invoices
- Extract meaningful information into structured JSON
- Preserve tables and line items
- Handle scanned/image-based documents
- Detect missing or unreadable values
- Independently validate financial calculations
- Persist processing results
- Expose the functionality through a clean REST API
- Provide a usable frontend for demonstration

---

## Objectives

The primary objectives are:

- Build a reliable document validation layer.
- Support PDF, JPG and PNG inputs.
- Support documents of up to three pages.
- Extract all meaningful visible information rather than only a small set of fixed fields.
- Support both native PDFs and scanned/image-based documents.
- Use structured schemas for consistent AI output.
- Preserve comparative-period values for financial statements.
- Perform deterministic financial validations outside the LLM.
- Store the latest processing result by document name.
- Provide REST API endpoints for processing and retrieval.
- Provide an interactive frontend dashboard.
- Deploy the application as a publicly accessible service.

---

## Supported Documents

### 1. Invoice

The platform extracts invoice information including:

- Invoice number
- Invoice date
- Vendor / seller
- Customer / buyer
- Currency
- Subtotal
- Tax
- Discount
- Total amount
- Line items
- Quantity
- Unit price
- Line total
- Additional visible invoice information

### 2. Balance Sheet

The platform extracts:

- Statement name
- Entity information
- Reporting periods
- Currency
- Unit multiplier
- Assets
- Liabilities
- Equity
- Individual financial line items
- Comparative-period values
- Reported totals

### 3. Profit & Loss

The platform extracts:

- Statement name
- Entity information
- Reporting periods
- Currency
- Unit multiplier
- Income line items
- Expense line items
- Revenue
- Cost-related values
- Operating expenses
- Operating profit
- Tax
- Net profit
- Comparative-period values
- Reported totals

### 4. Cash Flow Statement

The platform extracts:

- Statement name
- Entity information
- Reporting periods
- Currency
- Unit multiplier
- Operating activities
- Investing activities
- Financing activities
- Opening cash
- Net change in cash
- Closing cash
- Comparative-period values
- Individual cash-flow line items

---

## Key Features

### Document Validation

Before extraction, uploaded files are checked for:

- Supported file type
- File readability
- Empty/corrupted files
- PDF page count
- Basic file integrity
- Maximum file size

Invalid documents fail gracefully before AI extraction is attempted.

### Structured AI Extraction

The AI extraction layer converts document contents into structured data using document-specific schemas.

The system does not rely on hardcoded document templates.

### Scanned Document Support

Native PDF text is used when sufficient text is available.

For image-based/scanned documents, PDF pages are rendered and processed using a vision-capable LLM.

### Table and Line-Item Extraction

Invoice line items and financial statement rows are represented as structured arrays, allowing variable document layouts and changing financial line items.

### Missing Value Handling

If a field is missing or unreadable, the system returns `null` instead of inventing a value.

### Financial Validation

Financial calculations are performed independently using deterministic Python logic rather than asking the LLM to perform the final validation.

### Persistence

Processed results are stored in SQLite and can be retrieved through the API and frontend dashboard.

### REST API

The platform exposes endpoints for:

- Processing documents
- Retrieving a document
- Listing processed documents
- Health monitoring

### Swagger Documentation

FastAPI automatically provides interactive OpenAPI documentation through `/docs`.

---

# System Architecture

```text
                         +----------------------+
                         |        User          |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |   HTML/CSS/JS UI     |
                         |    Web Dashboard     |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |    FastAPI Backend   |
                         +----------+-----------+
                                    |
                 +------------------+------------------+
                 |                                     |
                 v                                     v
       +-------------------+                 +----------------------+
       | File Validation   |                 | Document Processing  |
       +-------------------+                 +----------+-----------+
                 |                                      |
                 |                         +------------+------------+
                 |                         |                         |
                 |                         v                         v
                 |                +----------------+       +----------------+
                 |                | Native PDF     |       | Vision-capable |
                 |                | Text Extraction|       | LLM Extraction |
                 |                +----------------+       +----------------+
                 |                         |                         |
                 |                         +------------+------------+
                 |                                      |
                 |                                      v
                 |                           +----------------------+
                 |                           | Pydantic Structured  |
                 |                           | Output Validation    |
                 |                           +----------+-----------+
                 |                                      |
                 |                                      v
                 |                           +----------------------+
                 |                           | Financial Validation |
                 |                           |   Python Engine      |
                 |                           +----------+-----------+
                 |                                      |
                 +--------------------------------------+
                                                        |
                                                        v
                                             +----------------------+
                                             |    SQLite Database   |
                                             +----------+-----------+
                                                        |
                                                        v
                                             +----------------------+
                                             | Structured API Result|
                                             +----------------------+
``` 

# Processing Workflow

1. User selects the document type.
2. User uploads a PDF, JPG or PNG.
3. The file is validated before AI processing.
4. PDF files are checked for usable native text.
5. Native text is used when sufficient text is available.
6. Image-based pages are rendered and processed using the vision-capable LLM.
7. The extracted response is parsed and validated against Pydantic schemas.
8. Financial calculations are independently validated using deterministic Python logic.
9. The latest result is stored in SQLite using the document name.
10. The API returns the structured processing result.
11. The frontend displays extracted information, validation results and raw JSON.


# AI and Document Processing
## LLM

The project uses:

### Qwen Qwen3.6 27B

The model is accessed through the Groq API and is used for structured document extraction and vision-based processing of image-based pages.

The implementation uses JSON output mode and validates the returned structure using Pydantic.

## PDF Processing

PDF processing follows a native-text-first approach:

Native PDF text is extracted when sufficient text is available.
Image-based/scanned pages are rendered for vision processing.
Multi-page documents are processed as a single logical document.

## OCR / Vision

For scanned documents and invoice images, the vision-capable LLM is used to read the document content.

No document-specific template parser or hardcoded invoice layout is used.

## Structured Extraction

The extraction layer uses document-specific schemas for:

Invoices
Balance Sheets
Profit & Loss statements
Cash Flow statements

Tables and line items are represented as structured arrays rather than fixed template-specific fields.

Values that are missing or unreadable are returned as null rather than being invented.

## Financial Validation

Financial validation is performed separately from AI extraction using deterministic Python calculations.

### Invoice

Examples of validation checks:

Quantity × Unit Price ≈ Line Total
Subtotal + Tax − Discount ≈ Grand Total
Applicable cash/change reconciliation
Rounding and tax-inclusive structures are handled where applicable

### Balance Sheet

Examples:

Assets ≈ Liabilities + Equity
Individual components are compared against reported totals
Comparative periods are validated independently

### Profit & Loss

Examples:

Income components vs Total Income
Expense components vs Total Expenditure
Total Income − Total Expenditure ≈ Net Profit
Minority interest reconciliation where applicable
Comparative periods are validated independently

### Cash Flow

Examples:

Operating + Investing + Financing + applicable adjustments ≈ Net Change
Opening Cash + Net Change ≈ Closing Cash
Comparative periods are validated independently

Validation results include:

Formula
Operands
Calculated value
Reported value
Variance
Tolerance
Period
Status
Reason


# API
## Process Document
POST /api/v1/documents/process

Accepts a document and selected document type.

## Get Document
GET /api/v1/documents/{document_name}

Returns the latest stored result for a document.

## List Documents
GET /api/v1/documents/

Returns processed documents for the dashboard.

## Health Check
GET /api/v1/health

Returns the application health status.

## Swagger / OpenAPI

Interactive API documentation is available through:

/docs
### Example Response Structure

```json
{
  "document_name": "sample_invoice.jpg",
  "document_type": "invoice",
  "file_validation": {
    "status": "PASSED",
    "issues": []
  },
  "extracted_data": {},
  "financial_validations": [],
  "processing_status": "SUCCESS",
  "processing_metadata": {
    "processed_at": "...",
    "ocr_used": true,
    "model_used": "qwen/qwen3.6-27b",
    "page_count": 1,
    "duration_ms": 2500
  }
}
```

# Database and Persistence

The application uses SQLite for persistence.

The latest processing result is stored by document name. Reprocessing the same document name updates the stored result rather than creating a separate version history.

The database stores:

Document name
Document type
Processing status
File validation result
Extracted structured data
Financial validation results
Processing metadata
Processing timestamp

# Frontend

The frontend is implemented using:

HTML
CSS
Vanilla JavaScript

The dashboard provides:

Document type selection
File upload
Processing action
Processing status
Recent processed documents
Extracted key-value information
Invoice line items
Financial validation results
Processing metadata
Raw JSON output
API health status

# Testing

The project includes automated tests covering core application behavior.

Manual testing was performed for:

Invoice extraction
Scanned/image-based financial documents
Native-text financial documents
Financial validation failures
Unsupported file validation
API retrieval of persisted results

Representative test scenarios include:

A scanned Balance Sheet
A Profit & Loss statement
A Cash Flow statement
A difficult invoice image
An invoice containing a financial validation failure
An unsupported file type

# Project Structure
document-intelligence-platform/
│
├── app/
│   ├── api/
│   ├── db/
│   ├── models/
│   ├── services/
│   └── main.py
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── tests/
│
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md

# Local Setup

## 1. Clone the repository
git clone https://github.com/ISharmaCodes/document-intelligence-platform.git
cd document-intelligence-platform
## 2. Create a virtual environment
python -m venv .venv

Activate it on Windows:

.venv\Scripts\activate
## 3. Install dependencies
pip install -r requirements.txt
## 4. Configure environment variables

Create a .env file based on .env.example.

GROQ_API_KEY=your_api_key_here
LLM_MODEL_NAME=qwen/qwen3.6-27b

Do not commit .env or API keys to GitHub.

## 5. Run the application
uvicorn app.main:app --reload

The application will be available locally through the configured host and port.

Swagger documentation:

/docs

# Docker

Build the Docker image:

docker build -t document-intelligence-platform .

Run the container:

docker run -p 10000:10000 --env-file .env document-intelligence-platform

# Deployment

The application is deployed as a Dockerized FastAPI service.

The same service provides:

REST API
Swagger/OpenAPI documentation
Static frontend
Health endpoint

## Deployment Environment
Docker
FastAPI
Uvicorn
Render
SQLite
Groq API

## Deployment Note

The current deployment uses SQLite on a free hosting environment. The free hosting filesystem may be ephemeral, so SQLite persistence should be replaced with a managed persistent database such as PostgreSQL for a production deployment.

# Security
API credentials are stored through environment variables.
.env is excluded from Git.
Uploaded files are validated before processing.
Unsupported and invalid files are rejected gracefully.
No API keys or secrets are stored in source code.

# Limitations

This is an internship case-study MVP rather than a production document-processing platform.

Current limitations include:

SQLite is used instead of a managed production database.
Processing is synchronous.
The application does not automatically classify document types.
Extraction quality depends on document readability and model output.
Free-tier LLM/API limits may affect processing availability.
Complex handwritten or heavily distorted documents may produce incomplete fields.
The deployment environment may have ephemeral filesystem storage.

# Future Improvements

Possible production improvements include:

PostgreSQL or another managed persistent database
Background/asynchronous document processing
Queue-based processing for higher throughput
Dedicated OCR/document parsing service
Improved observability and structured logging
Authentication and authorization
File/object storage
Confidence scoring with explainable signals
More extensive automated evaluation against labelled datasets
Retry and rate-limit handling for external AI services

# AI / Tool Usage Declaration

AI assistants were used during development for:

Architecture planning
Code generation and refinement
Debugging
Schema design
Prompt development
Documentation
Test development

The final application logic, integration, validation rules and project decisions were reviewed and adapted for the case-study requirements.

# License

This project was developed as part of an AI Engineer internship technical case study. 