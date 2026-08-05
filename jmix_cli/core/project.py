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

import re
from pathlib import Path


def get_project_name(settings_path: Path = Path("settings.gradle")) -> str | None:
    if not settings_path.exists():
        return None
    text = settings_path.read_text(encoding="utf-8")
    m = re.search(r"""rootProject\.name\s*=\s*(['"])(.*?)\1""", text)
    return m.group(2) if m else None


def get_company_name(build_path: Path = Path("build.gradle")) -> str | None:
    if not build_path.exists():
        return None
    text = build_path.read_text(encoding="utf-8")
    m = re.search(r"""group\s*=\s*(['"])(.*?)\1""", text)
    return m.group(2) if m else None


PROIECT_PATH = Path.cwd()
PROJECT = get_project_name()
project_name = (PROJECT or "").lower()
COMPANY = get_company_name() or ""
company_path = COMPANY.replace(".", "/")
