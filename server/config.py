import json
import os

'''
Server config. Copy config.example.json -> config.json (gitignored) and fill it in.
The Gemma/Gemini API key lives ONLY here, on the server -- clients never see it
(see v1_design.md "Authentication issues").
'''

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("ACCOUNTABILITY_CONFIG", os.path.join(BASE_DIR, "config.json"))

DEFAULTS = {
    "db_path": os.path.join(BASE_DIR, "accountability.db"),
    # random token clients must send as "Authorization: Bearer <token>".
    # generate one with:  python -c "import secrets; print(secrets.token_urlsafe(32))"
    "api_token": "",
    # key from https://aistudio.google.com -- Gemma models are served through the Gemini API
    "gemma_api_key": "",
    "gemma_model": "gemma-4-26b-a4b-it",
    "host": "",
    "port": 8734,
}

_config = None


def get_config():
    global _config
    if _config is None:
        cfg = dict(DEFAULTS)
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                cfg.update(json.load(f))
        _config = cfg
    return _config
