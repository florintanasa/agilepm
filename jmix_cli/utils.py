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

import csv
import logging
import os
import re
import sys
from pathlib import Path

from jmix_cli.exceptions import InvalidCsvError

PROIECT_PATH = Path.cwd()


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


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


PROJECT = get_project_name()
project_name = (PROJECT or "").lower()
COMPANY = get_company_name() or ""
company_path = COMPANY.replace(".", "/")


def to_camel_case_lower(text: str) -> str:
    if not text:
        return ""
    text_clean = text.strip()
    return text_clean[0].lower() + text_clean[1:]


def inject_import_if_missing(java_content: str, import_class: str) -> str:
    full_import = f"import {import_class};"
    if full_import in java_content:
        return java_content
    return java_content.replace(
        f"package {COMPANY}.{project_name}.entity;",
        f"package {COMPANY}.{project_name}.entity;\n{full_import}",
    )


def validate_csv_path(csv_path: str, required_columns: list[str]) -> list[dict]:
    if not os.path.exists(csv_path):
        raise InvalidCsvError(csv_path)
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise InvalidCsvError(csv_path, message=f"CSV file is empty: {csv_path}")
        missing = set(required_columns) - set(reader.fieldnames)
        if missing:
            raise InvalidCsvError(csv_path, missing_columns=sorted(list(missing)))
        return list(reader)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_file(path: str | Path, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)


def replace_entity_messages(file_path: str, base_package: str, entity_name: str, new_lines: list[str]) -> None:
    p = Path(file_path)
    existing_lines = []
    if p.exists():
        existing_lines = p.read_text(encoding="utf-8").splitlines()

    prefix = f"{base_package}.entity/{entity_name}"
    filtered = [line for line in existing_lines if not line.startswith(prefix + ".") and line.strip()]

    if not filtered or not filtered[-1].strip():
        pass
    else:
        if filtered[-1].strip():
            filtered.append("")

    for line in new_lines:
        if line not in filtered:
            filtered.append(line)

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(filtered) + "\n", encoding="utf-8")


def append_unique(file_path: str, lines_to_add: list[str]) -> None:
    existing_content = ""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            existing_content = f.read()

    with open(file_path, "a", encoding="utf-8") as f:
        if existing_content and not existing_content.endswith("\n"):
            f.write("\n")

        header_written = False
        for line in lines_to_add:
            if "=" not in line:
                continue
            key = line.split("=")[0].strip()
            if f"{key}=" not in existing_content:
                if not header_written:
                    f.write(
                        f"\n# Automated localization properties bundle layout for entity: {key.split('/')[-1] if '/' in key else key}\n"
                    )
                    header_written = True
                f.write(line + "\n")
