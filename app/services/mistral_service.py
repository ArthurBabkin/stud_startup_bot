from mistralai import Mistral
import os
from app.config import config
import logging
from pdfplumber import open as pdf_open

# Настройка логирования
logger = logging.getLogger(__name__)

async def extract_text_with_mistral_ocr(file_path: str) -> str:
    """
    Extract text from a PDF file using Mistral's OCR capabilities
    
    Args:
        file_path: Path to the PDF file
    
    Returns:
        Extracted text as a string
    """
    
    # Получаем список API ключей из конфигурации
    api_keys = config.mistral_api_keys
    
    # Если список пуст, логируем и переходим сразу к использованию pdfplumber
    if not api_keys:
        logger.warning("No Mistral API keys configured, falling back to pdfplumber.")
        return extract_text_with_pdfplumber(file_path)
    
    # Пробуем каждый ключ по очереди
    for api_key in api_keys:
        try:
            # Инициализируем клиент с текущим ключом
            client = Mistral(api_key=api_key)
            
            logger.info(f"Trying to process PDF with Mistral OCR using key: {api_key[:5]}...")
            
            # Upload the PDF file
            uploaded_pdf = client.files.upload(
                file={
                    "file_name": os.path.basename(file_path),
                    "content": open(file_path, "rb"),
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
            # Если это последний ключ в списке, переходим к pdfplumber
            if api_key == api_keys[-1]:
                logger.warning("All Mistral OCR API keys failed, falling back to pdfplumber.")
                return extract_text_with_pdfplumber(file_path)
            
            # Если это не последний ключ, пробуем следующий
            logger.info("Trying next Mistral OCR API key...")
            continue

def extract_text_with_pdfplumber(file_path: str) -> str:
    """
    Извлекает текст из PDF файла с помощью pdfplumber (старый метод)
    
    Args:
        file_path: Путь к PDF файлу
    
    Returns:
        Извлеченный текст в виде строки
    """
    logger.info("Using pdfplumber for text extraction")
    try:
        with pdf_open(file_path) as pdf:
            text = ''
            for page in pdf.pages:
                text += page.extract_text() or ''  # Защита от None
        return text
    except Exception as e:
        logger.error(f"Error with pdfplumber: {str(e)}")
        return "" 