"""OpenAI GPT-4 integration for AarogyaAI."""

import logging
import os
from typing import Dict, List

from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logger = logging.getLogger(__name__)

PAYMENT_PLACEHOLDER = "<PAYMENT_LINK>"

SYSTEM_PROMPT_TEMPLATE = f"""
You are an AI health assistant named AarogyaAI on a web chat interface for a primary care service in India.
Your goal is to follow this workflow with each user:

1. Greet and ask for consent to proceed.
   - If user says yes → collect basic info.
   - If user says no → politely exit.

2. Ask for:
   - Name
   - Age
   - Gender
   - PIN code

3. Ask what they are experiencing (symptoms, diet, wellness, urgent issue).

4. Ask structured follow-up questions.
   Use their previous answers for context.

5. If red flags → recommend doctor consult.

6. If consult is accepted, respond with a short sentence
   containing the token {PAYMENT_PLACEHOLDER}. Do not
   include any other link text. The backend will
   replace this token with an actual Razorpay link.

Always say:
**This is not a diagnosis. Consult a doctor if unsure.**
Respond in short, clear format in {{language}}.
"""

async def generate_response(messages: List[Dict[str, str]], language: str = "English") -> str:
    """Call OpenAI's API and return the assistant's reply."""
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(language=language)
    chat_messages = [{"role": "system", "content": system_prompt}] + messages
    try:
        resp = await client.chat.completions.create(
            model="gpt-4",
            messages=chat_messages,
            temperature=0.6,
            timeout=10,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.exception("OpenAI request failed: %s", exc)
        return "Sorry, I couldn't process that right now. Please try after some time."

