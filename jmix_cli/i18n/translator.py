# -
# Copyright (c) 2026 Florin Tanasă <florin.tanasa@gmail.com>
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# -

import http.client
import json
from pathlib import Path

from jmix_cli.core.config import get_ollama_endpoint, get_ollama_model
from jmix_cli.core.logger import get_logger
from jmix_cli.i18n import cache as _i18n_cache

logger = get_logger("jmix_cli.i18n")


def ask_ollama_translation(text_to_translate: str, target_language_name: str) -> str:
    _i18n_cache._load_cache()
    key = _i18n_cache._cache_key(text_to_translate, target_language_name)
    if key in _i18n_cache._translation_cache:
        return _i18n_cache._translation_cache[key]

    host, port = get_ollama_endpoint()
    model = get_ollama_model()
    prompt = (
        f"Translate the following software UI label from English into {target_language_name}. "
        f"Return ONLY the translated string, without quotes, explanations, or introductory text. "
        f"Label: {text_to_translate}"
    )
    try:
        connection = http.client.HTTPConnection(host, port, timeout=10)
        payload = json.dumps(
            {"model": model, "prompt": prompt, "stream": False}
        )
        headers = {"Content-Type": "application/json"}
        connection.request("POST", "/api/generate", payload, headers)
        response = connection.getresponse()
        if response.status == 200:
            data = json.loads(response.read().decode("utf-8"))
            translated_text = data.get("response", "").strip()
            translated_text = translated_text.replace('"', "").replace("'", "")
            result = translated_text if translated_text else text_to_translate
            _i18n_cache._translation_cache[key] = result
            _i18n_cache._persist_cache()
            return result
    except (ConnectionError, TimeoutError, http.client.HTTPException, json.JSONDecodeError) as e:
        logger.error(f"[-] Ollama translation warning: {e}. Falling back to English.")
    return text_to_translate
