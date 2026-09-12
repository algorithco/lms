"""
LLM Client Implementations - Plug into essays/views.py _sync_grade_essay()
Copy the one you need and update essays/views.py
"""

# =============================================================================
# OPTION 1: OpenAI (GPT-4o, GPT-4o-mini, etc.)
# =============================================================================
def openai_grade_essay(prompt: str, api_key: str, model: str = "gpt-4o-mini") -> str:
    """
    Requires: pip install openai>=1.0.0
    """
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=2000,
        response_format={"type": "json_object"},  # Forces valid JSON
    )
    return response.choices[0].message.content


# =============================================================================
# OPTION 2: Anthropic Claude
# =============================================================================
def claude_grade_essay(prompt: str, api_key: str, model: str = "claude-3-haiku-20240307") -> str:
    """
    Requires: pip install anthropic
    """
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    
    message = client.messages.create(
        model=model,
        max_tokens=2000,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


# =============================================================================
# OPTION 3: Local LLM via Ollama (llama3, mistral, etc.)
# =============================================================================
def ollama_grade_essay(prompt: str, model: str = "llama3", base_url: str = "http://localhost:11434") -> str:
    """
    Requires: pip install ollama
    Ollama must be running locally with model pulled: `ollama pull llama3`
    """
    import ollama
    
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1, "num_predict": 2000},
        format="json",  # Forces JSON output
    )
    return response["message"]["content"]


# =============================================================================
# OPTION 4: Hugging Face Inference API (free tier available)
# =============================================================================
def hf_grade_essay(prompt: str, api_token: str, model: str = "meta-llama/Meta-Llama-3-8B-Instruct") -> str:
    """
    Requires: pip install huggingface_hub
    """
    from huggingface_hub import InferenceClient
    
    client = InferenceClient(token=api_token)
    
    response = client.chat_completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


# =============================================================================
# OPTION 5: Custom HTTP endpoint (your own model server)
# =============================================================================
def custom_http_grade_essay(prompt: str, endpoint: str, api_key: str = None) -> str:
    """
    For self-hosted models (vLLM, TGI, custom FastAPI, etc.)
    Expected endpoint: POST /v1/chat/completions (OpenAI-compatible)
    """
    import requests
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }
    
    response = requests.post(endpoint, json=payload, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


# =============================================================================
# USAGE IN essays/views.py
# =============================================================================
"""
# At top of essays/views.py:
import os
from .llm_clients import openai_grade_essay  # or your chosen client

# Replace _sync_grade_essay function:
def _sync_grade_essay(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")  # or settings.OPENAI_API_KEY
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return openai_grade_essay(prompt, api_key)
"""