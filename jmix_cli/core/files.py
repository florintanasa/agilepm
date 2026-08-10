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
import os
from pathlib import Path


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
    new_keys = {}
    for line in new_lines:
        if "=" in line:
            key = line.split("=")[0].strip()
            new_keys[key] = line

    result = []
    seen_keys = set()
    first_entity_idx = None
    last_entity_idx = None
    for i, line in enumerate(existing_lines):
        if line.startswith(prefix + ".") or line.startswith(prefix + "="):
            key = line.split("=")[0].strip()
            if first_entity_idx is None:
                first_entity_idx = i
            if key in new_keys:
                result.append(new_keys[key])
                seen_keys.add(key)
                last_entity_idx = len(result) - 1
            else:
                result.append(line)
                last_entity_idx = len(result) - 1
        else:
            result.append(line)

    for key, line in new_keys.items():
        if key not in seen_keys:
            if last_entity_idx is not None:
                result.insert(last_entity_idx + 1, line)
                last_entity_idx += 1
            else:
                result.append(line)

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(result) + "\n", encoding="utf-8")


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


def update_checkbox_required_state_property() -> None:
    csv_path = Path("entities.csv")
    has_mandatory_boolean = False
    if csv_path.exists():
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["field_type"].strip().lower() in ("boolean", "bool") and row["mandatory"].strip().lower() == "true":
                    has_mandatory_boolean = True
                    break

    app_props_path = Path("src/main/resources/application.properties")
    if not app_props_path.exists():
        return

    content = app_props_path.read_text(encoding="utf-8")
    prop_line = "jmix.ui.component.checkbox-required-state-initialization-enabled=false\n"

    if has_mandatory_boolean:
        if "jmix.ui.component.checkbox.required-state-initialization-enabled" not in content:
            content = content.replace(
                "jmix.ui.composite-menu=true\n",
                f"jmix.ui.composite-menu=true\n{prop_line}",
            )
            app_props_path.write_text(content, encoding="utf-8")
    else:
        lines = content.splitlines()
        new_lines = [
            line for line in lines
            if not line.strip().startswith("jmix.ui.component.checkbox-required-state-initialization-enabled")
            and not line.strip().startswith("jmix.ui.component.checkbox.required-state-initialization-enabled")
        ]
        new_content = "\n".join(new_lines)
        if not new_content.endswith("\n"):
            new_content += "\n"
        app_props_path.write_text(new_content, encoding="utf-8")
