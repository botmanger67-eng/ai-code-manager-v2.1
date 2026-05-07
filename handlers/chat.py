import os
import json
import logging
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Configuration – sourced from environment variables with sensible defaults
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.getenv(
    "DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions"
)
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
REQUEST_TIMEOUT = int(os.getenv("DEEPSEEK_REQUEST_TIMEOUT", "60"))

# System prompts for different tasks
PLAN_SYSTEM_PROMPT = """
You are an expert software architect. Given a project description, output a detailed JSON plan.
The JSON must have the following structure:
{
    "project_name": "...",
    "description": "...",
    "architecture": "...",
    "files": [
        {
            "path": "relative/file/path",
            "description": "What this file does",
            "dependencies": ["other/file/path", ...]
        }
    ],
    "technologies": ["tech1", ...]
}
Do not include any explanation. Only output valid JSON.
"""

CODE_SYSTEM_PROMPT = """
You are a senior software engineer. Generate production-ready code for the requested file.
Follow these rules:
- Use modern Python 3.11+ with type hints.
- Include docstrings and inline comments where necessary.
- Follow best practices (PEP8, SOLID, etc.).
- If the file is part of a larger project, adhere to the provided context.
- Output the code inside a single markdown code block, e.g., ```python ... ```.
Do not include any extra text outside the markdown block.
"""


def _call_deepseek(prompt: str, system_prompt: str, max_retries: int = 3) -> Optional[str]:
    """
    Send a chat completion request to DeepSeek API and return the response content.
    Implements simple retry logic on transient failures.
    """
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,  # low temperature for deterministic outputs
        "max_tokens": 8192,
    }

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Calling DeepSeek API (attempt {attempt}/{max_retries})")
            response = requests.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.debug(f"DeepSeek raw response: {content[:200]}...")
            return content
        except requests.exceptions.RequestException as e:
            logger.warning(f"DeepSeek API error on attempt {attempt}: {e}")
            if attempt == max_retries:
                logger.error(f"All {max_retries} attempts to DeepSeek failed")
                return None
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"Invalid response format from DeepSeek: {e}")
            return None
    return None


def analyze_project_plan(message: str) -> dict:
    """
    Analyze a project description and return a structured JSON plan.

    Args:
        message: The user's project description.

    Returns:
        A dictionary representing the project plan (as defined by PLAN_SYSTEM_PROMPT).
        Returns an empty dict if parsing fails or API call fails.
    """
    logger.info(f"Analyzing project plan for message: {message[:100]}...")
    raw_response = _call_deepseek(message, PLAN_SYSTEM_PROMPT)

    if raw_response is None:
        logger.error("No response from DeepSeek for plan generation")
        return {}

    # Attempt to extract JSON from the response (may include markdown fences)
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to parse the entire response as JSON
        json_str = raw_response.strip()

    try:
        plan = json.loads(json_str)
        if not isinstance(plan, dict):
            raise ValueError("Parsed JSON is not an object")
        logger.info(f"Successfully parsed plan for project: {plan.get('project_name', 'unknown')}")
        return plan
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse plan JSON: {e}")
        logger.debug(f"Raw response: {raw_response}")
        return {}


def generate_file_code(filename: str, description: str, context: str) -> str:
    """
    Generate production code for a single file based on its description and project context.

    Args:
        filename: The relative path of the file (e.g., 'src/app.py').
        description: A description of what the file should do.
        context: Existing code or architectural context to guide generation.

    Returns:
        The generated code as a string. Returns an empty string on failure.
    """
    prompt = (
        f"Generate code for the file: {filename}\n\n"
        f"Description: {description}\n\n"
        f"Project context:\n{context}"
    )
    logger.info(f"Generating code for {filename}")
    raw_response = _call_deepseek(prompt, CODE_SYSTEM_PROMPT)

    if raw_response is None:
        logger.error(f"No response from DeepSeek for file {filename}")
        return ""

    code = extract_code_from_response(raw_response)
    if code is None:
        logger.warning(f"Could not extract code from DeepSeek response for {filename}")
        # Fallback: return raw response, user may need to clean up
        return raw_response
    return code


def extract_code_from_response(response: str) -> Optional[str]:
    """
    Extract code from a DeepSeek response wrapped in a markdown code block.

    Args:
        response: The raw response string from DeepSeek.

    Returns:
        The extracted code content if a code block is found, otherwise None.
    """
    # Match a code block with or without a language specifier
    # e.g., ```python\ncode\n``` or ```\ncode\n```
    pattern = r"```(?:\w+)?\n(.*?)```"
    match = re.search(pattern, response, re.DOTALL)
    if match:
        code = match.group(1).strip()
        logger.debug(f"Extracted code of length {len(code)}")
        return code
    # If no markdown block, assume the entire response is code
    logger.debug("No markdown code block found, returning entire response")
    return None