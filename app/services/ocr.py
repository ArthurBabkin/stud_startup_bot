from mistralai.client import MistralClient
import os
from app.config import config
import logging
from pdfplumber import open as pdf_open

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def extract_text_with_mistral_ocr(file_path: str) -> str:
    """
    Extract text from a PDF file using Mistral's OCR capabilities

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted text as a string
    """

    # Get the list of API keys from config
    api_keys = config.mistral_api_keys

    # If the list is empty, log and immediately fall back to pdfplumber
    if not api_keys:
        logger.warning("No Mistral API keys configured, falling back to pdfplumber.")
        return extract_text_with_pdfplumber(file_path)

    # Try each API key in order
    for api_key in api_keys:
        try:
            # Initialize the client with the current key
            client = MistralClient(api_key=api_key)

            logger.info(f"Trying to process PDF with Mistral OCR using key: {api_key[:5]}...")

            # Upload the PDF file
            with open(file_path, "rb") as f:
                uploaded_pdf = client.files.upload(
                    file={
                        "file_name": os.path.basename(file_path),
                        "content": f,
                    },
                    purpose="ocr"
                )

            # Get the signed URL
            signed_url = client.files.get_signed_url(file_id=uploaded_pdf.id)

            # Process the document using OCR
            ocr_response = client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": signed_url.url,
                }
            )

            # Extract text from all pages and combine
            all_text = ""
            if ocr_response.pages and len(ocr_response.pages) > 0:
                for page in ocr_response.pages:
                    all_text += page.markdown + "\n\n"

            logger.info(f"Successfully processed PDF with Mistral OCR using key: {api_key[:5]}")
            return all_text.strip()

        except Exception as e:
            logger.error(f"Error with Mistral OCR key {api_key[:5]}: {str(e)}")
            # If this is the last key in the list, fall back to pdfplumber
            if api_key == api_keys[-1]:
                logger.warning("All Mistral OCR API keys failed, falling back to pdfplumber.")
                return extract_text_with_pdfplumber(file_path)

            # If not the last key, try the next one
            logger.info("Trying next Mistral OCR API key...")
            continue

def extract_text_with_pdfplumber(file_path: str) -> str:
    """
    Extracts text from a PDF file using pdfplumber (legacy method)

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted text as a string
    """
    logger.info("Using pdfplumber for text extraction")
    try:
        with pdf_open(file_path) as pdf:
            text = ''
            for page in pdf.pages:
                text += page.extract_text() or ''  # Protect against None
        return text
    except Exception as e:
        logger.error(f"Error with pdfplumber: {str(e)}")
        return ""