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

import json
import threading
from pathlib import Path

_CACHE_FILE = Path(".ollama_translation_cache.json")
_cache_lock = threading.Lock()
_translation_cache: dict[str, str] = {}
_cache_loaded = False


def _load_cache() -> None:
    global _cache_loaded, _translation_cache
    if _cache_loaded:
        return
    with _cache_lock:
        if _cache_loaded:
            return
        if _CACHE_FILE.exists():
            try:
                _translation_cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                _translation_cache = {}
        _cache_loaded = True


def _persist_cache() -> None:
    with _cache_lock:
        try:
            _CACHE_FILE.write_text(
                json.dumps(_translation_cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass


def _cache_key(text: str, target_language_name: str) -> str:
    return f"{target_language_name}:{text}"
