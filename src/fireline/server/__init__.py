"""Fireline web server: FastAPI app, WebSocket hub and the per-report pipeline.

    from fireline.server.pipeline import Pipeline
    from fireline.server.hub import Hub
    from fireline.server.app import create_app, app

Run: ``fireline-server`` (or ``python -m fireline.server.app``) — binds FIRELINE_HOST:FIRELINE_PORT.
"""
