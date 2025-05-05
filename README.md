# PDF Statement Extraction Microservice

A standalone FastAPI service to unlock, extract, and parse password-protected bank/credit card statements (PDF) and return structured JSON.

## Features
- Accepts PDF + password via POST
- Unlocks PDF (pikepdf)
- Extracts text (pdfplumber)
- Parses transactions (basic regex, extendable)
- Returns JSON with account info and transactions
- In-memory only, no file persistence
- CORS enabled

## API Spec

### POST `/extract`
- **Content-Type:** `multipart/form-data`
- **Body:**
  - `file`: PDF file (required)
  - `password`: PDF password (required)

#### Success Response
```
{
  "status": "success",
  "data": {
    "account_holder": "John Doe",
    "account_number": "XXXX-1234",
    "transactions": [
      {
        "date": "2025-05-01",
        "description": "AMAZON PURCHASE",
        "amount": "-₹1,500.00",
        "balance": "₹23,000.00"
      }
    ]
  }
}
```

#### Error Response
```
{
  "status": "error",
  "message": "Unable to unlock or parse the PDF."
}
```

## Setup & Local Development

```bash
cd pdf_service
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Docker Deployment

Build and run:
```bash
docker build -t pdf-service .
docker run -p 8000:8000 pdf-service
```

## Node.js Integration Example

```js
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

async function extractPdf(filePath, password) {
  const form = new FormData();
  form.append('file', fs.createReadStream(filePath));
  form.append('password', password);

  const response = await axios.post('http://localhost:8000/extract', form, {
    headers: form.getHeaders(),
    timeout: 60000
  });
  return response.data;
}
```

## Extending
- Add more parsers in `app/parsers/`
- Switch parser in `pdf_utils.py` based on bank detection

## Security
- No files are written to disk
- No file content is logged
- Add token auth as needed (see FastAPI docs)

## Hosting
- Suitable for Render.com, Railway.app, Fly.io, etc.
- HTTPS should be handled at infra level
- Service can auto-sleep when idle 