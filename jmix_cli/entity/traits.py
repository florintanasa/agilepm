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

from jmix_cli.core.csv import validate_csv_path


def get_traits_from_csv(csv_path: str, target_entity_name: str) -> dict[str, str]:
    traits = {
        "versioned": True,
        "audit_of_creation": True,
        "audit_of_modification": True,
        "soft_delete": False,
    }
    csv_file = Path(csv_path)
    if not csv_file.exists():
        return traits
    validate_csv_path(csv_path, ["entity_name", "versioned", "audit_of_creation", "audit_of_modification", "soft_delete"])
    with csv_file.open(mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["entity_name"].strip().lower() == target_entity_name.lower():
                traits["versioned"] = row["versioned"].strip().lower() == "true"
                traits["audit_of_creation"] = (
                    row["audit_of_creation"].strip().lower() == "true"
                )
                traits["audit_of_modification"] = (
                    row["audit_of_modification"].strip().lower() == "true"
                )
                traits["soft_delete"] = row["soft_delete"].strip().lower() == "true"
                break
    return traits
