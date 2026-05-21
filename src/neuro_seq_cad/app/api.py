from __future__ import annotations


def create_app():
    try:
        from fastapi import FastAPI  # type: ignore
    except Exception as exc:
        raise RuntimeError("Install the optional api dependencies to use FastAPI") from exc
    app = FastAPI(title="HS-CAD Image to CAD Draft API")
    return app

