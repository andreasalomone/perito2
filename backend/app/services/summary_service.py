"""
Summary Service
===============
Generates AI report summaries using a low-cost Gemini model (gemini-2.5-flash-lite).
"""

import logging
from typing import Optional

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = """Sei un assistente esperto nella sintesi di documenti tecnici.

Analizza la seguente perizia assicurativa e genera un **riassunto professionale e conciso** in italiano.

Il riassunto deve:
- Essere in formato **Markdown**
- Includere le sezioni più rilevanti (dati generali, dinamica del sinistro, danni accertati, conclusioni)
- Essere chiaro e facile da leggere
- Essere lungo circa 200-400 parole

---

**PERIZIA DA RIASSUMERE:**

{report_text}

---

**RIASSUNTO (in Markdown):**
"""


async def generate_summary(report_text: str) -> Optional[str]:
    """
    Generates a markdown summary of the report using gemini-2.5-flash-lite.
    
    Args:
        report_text: The raw AI-generated report text
        
    Returns:
        A concise markdown summary in Italian, or None if generation fails
    """
    if not report_text or len(report_text.strip()) < 100:
        logger.warning("Report text too short for summarization")
        return None
    
    try:
        # Initialize client
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        # Build prompt
        prompt = SUMMARY_PROMPT.format(report_text=report_text[:50000])  # Limit input size
        
        # Generate with configurable summary model
        response = await client.aio.models.generate_content(
            model=settings.LLM_SUMMARY_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,  # Lower temperature for more focused summaries
                max_output_tokens=2000,
            )
        )
        
        # Extract text
        if response and response.text:
            summary = response.text.strip()
            logger.info(f"Summary generated successfully ({len(summary)} chars)")
            return summary
        else:
            logger.warning("Empty response from summary model")
            return None
            
    except Exception as e:
        logger.error(f"Summary generation failed: {e}", exc_info=True)
        return None
