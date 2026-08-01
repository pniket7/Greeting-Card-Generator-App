"""
Gemini client helpers for the greeting-card notes prototype.
"""

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

DEFAULT_MODEL = "gemini-3-flash-preview"


def get_google_api_key():
    """
    Resolve GOOGLE_API_KEY from environment variables or Streamlit secrets.

    Priority:
    1. Environment variable GOOGLE_API_KEY (local .env / host env)
    2. Streamlit secrets GOOGLE_API_KEY (Streamlit Community Cloud)

    :return: The API key string, or None if not found.
    """
    # Prefer environment variable first (local .env and most hosts)
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        return api_key

    # Fall back to Streamlit secrets for Streamlit Community Cloud
    try:
        import streamlit as st

        if hasattr(st, "secrets") and "GOOGLE_API_KEY" in st.secrets:
            return st.secrets["GOOGLE_API_KEY"]
    except Exception:
        pass

    return None


def get_client():
    """
    Create a Gemini client using GOOGLE_API_KEY from env or Streamlit secrets.

    :return: A google.genai Client instance.
    """
    # Read API key from env or Streamlit secrets
    api_key = get_google_api_key()
    if not api_key:
        raise ValueError(
            "Missing GOOGLE_API_KEY. Set it in your project .env file "
            "or in Streamlit secrets (GOOGLE_API_KEY = \"...\")."
        )

    # Initialize the Gemini client
    return genai.Client(api_key=api_key)


def generate_text(prompt, model=DEFAULT_MODEL, temperature=0.7, max_output_tokens=4096):
    """
    Generate text from Gemini for a given prompt.

    :param prompt: The prompt text to send to the model.
    :param model: The Gemini model name to use.
    :param temperature: Sampling temperature for generation.
    :param max_output_tokens: Maximum number of output tokens.
    :return: The generated text response as a string.
    """
    # Initialize the Gemini client
    client = get_client()

    # Run the generation call
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ),
    )

    # Extract response text
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini returned an empty response.")

    return text.strip()


def has_api_key():
    """
    Check whether GOOGLE_API_KEY is available via env or Streamlit secrets.

    :return: True if the key is present, otherwise False.
    """
    return bool(get_google_api_key())
