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
from pathlib import Path
from typing import Any

from jmix_cli.core.csv import validate_csv_path


def get_relations_from_csv(csv_path: str, target_entity_name: str) -> list[dict[str, Any]]:
    relations_list: list[dict[str, Any]] = []
    csv_file = Path(csv_path)
    if not csv_file.exists():
        return relations_list
    required = ["source_entity", "relation_type", "target_entity", "field_name", "mandatory"]
    validate_csv_path(csv_path, required)
    with csv_file.open(mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["source_entity"].strip().lower() == target_entity_name.lower():
                rel_dict = {
                    "type": row["relation_type"].strip(),
                    "target": row["target_entity"].strip(),
                    "field": row["field_name"].strip(),
                    "mandatory": row["mandatory"].strip().lower() == "true",
                }
                if "ownership" in (reader.fieldnames or []):
                    rel_dict["ownership"] = row.get("ownership", "").strip()
                relations_list.append(rel_dict)
    return relations_list
