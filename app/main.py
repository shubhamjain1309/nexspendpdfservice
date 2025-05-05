from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.pdf_utils import process_pdf

app = FastAPI()

# Allow CORS for all origins (customize as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    except Exception:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Unable to unlock or parse the PDF."
        }) 