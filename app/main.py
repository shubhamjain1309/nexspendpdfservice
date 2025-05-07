from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
from app.pdf_utils import process_pdf

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
    password: str = Form(...)
):
    try:
        content = await file.read()
        result = process_pdf(content, password)
        if result["status"] == "error":
            return JSONResponse(status_code=400, content=result)
        return result
    except Exception as e:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": f"Unable to unlock or parse the PDF: {str(e)}"
        }) 