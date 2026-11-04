"""Fireline: AI indoor/outdoor coordination harness for firefighters.

Modules
-------
- fireline.models      shared pydantic data contracts (every module imports from here)
- fireline.llm         Ollama/Llama JSON-mode client with validation + retries
- fireline.triage      radio audio/text -> transcript -> structured triage -> priority queue
- fireline.worldmodel  spatial state store: responders, victim estimates, indoor/outdoor fusion
- fireline.briefer     per-responder briefing agent + TTS for hands-free audio
- fireline.server      FastAPI + WebSocket hub, command dashboard, clip-on responder view
"""

__version__ = "0.1.0"
