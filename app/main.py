from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
from app.pdf_utils import process_pdf
from app.investment_pdf_utils import process_investment_pdf

app = FastAPI()

# Get the current directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Mount the static directory
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Allow CORS for all origins (customize as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))

@app.post("/extract")
async def extract_pdf(
    file: UploadFile = File(...),
    password: str = Form(...),
    bank: str = Form(...),
    document_type: str = Form(...)
):
    try:
        content = await file.read()
        result = process_pdf(content, password, bank, document_type)
        print("Returning result from /extract:", result)
        if result["status"] == "error":
            return JSONResponse(status_code=400, content=result)
        return result
    except Exception as e:
        print(f"Exception in /extract endpoint: {e}")
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": f"Unable to unlock or parse the PDF: {str(e)}"
        })

@app.post("/extract-investment")
async def extract_investment_pdf(
    file: UploadFile = File(...),
    password: str = Form(...),
    statement_type: str = Form(...),
    institution: str = Form(None),
    bank: str = Form(None)
):
    """Extract holdings & transactions from investment statement PDFs."""
    try:
        content = await file.read()
        # Use institution if provided, else fallback to bank
        institution_val = institution or bank
        if not institution_val:
            return JSONResponse(status_code=400, content={
                "status": "error",
                "message": "Missing institution or bank for investment statement."
            })
        result = process_investment_pdf(content, password, statement_type, institution_val)
        if result.get("status") == "error":
            return JSONResponse(status_code=400, content=result)
        return result
    except Exception as e:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": f"Unable to process the PDF: {str(e)}"
        }) 