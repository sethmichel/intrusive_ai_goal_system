import secrets

from fastapi import Header, HTTPException

from config import get_config

'''
Static bearer token auth (the "~10 lines of code" option from v1_design.md).
Every endpoint requires "Authorization: Bearer <api_token>". The token is a
random secret you generate once and paste into each client's config -- it is
NOT the AI key, which never leaves the server.
'''


def require_token(authorization: str = Header(default="")):
    expected = get_config()["api_token"]
    if not expected:
        raise HTTPException(500, "server has no api_token configured; set it in config.json")
    provided = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(401, "bad or missing bearer token")
