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
import re
from pathlib import Path
from typing import Any

from jmix_cli.core.constants import ISO_LANG_NAMES
from jmix_cli.core.files import append_unique, replace_entity_messages
from jmix_cli.core.logger import get_logger
from jmix_cli.core.project import COMPANY, PROIECT_PATH, company_path, project_name
from jmix_cli.core.csv import validate_csv_path
from jmix_cli.i18n.translator import ask_ollama_translation

logger = get_logger("jmix_cli.i18n")


def update_messages_entity(
    project_dir: str, base_package: str, entity_name: str, traits_list: list[str], relations_list: list[dict[str, Any]] = []
) -> None:
    n = entity_name.strip()
    logger.info(
        f"Generating dynamic parametric localization messages for exact entity {n}..."
    )

    project_root = Path(project_dir)
    app_properties_path = project_root / "src" / "main" / "resources" / "application.properties"
    available_locales = ["en"]
    if app_properties_path.exists():
        with app_properties_path.open(encoding="utf-8") as f:
            for line in f:
                if "jmix.core.available-locales" in line:
                    match = re.search(r"jmix\.core\.available-locales\s*=\s*(.*)", line)
                    if match:
                        available_locales = [
                            loc.strip()
                            for loc in match.group(1).split(",")
                            if loc.strip()
                        ]

    package_path_slashes = base_package.replace(".", "/")
    base_path = project_root / "src" / "main" / "resources" / package_path_slashes

    entity_traits = {
        "versioned": False,
        "audit_of_creation": False,
        "audit_of_modification": False,
        "soft_delete": False,
    }
    traits_csv_path = project_root / "traits.csv"
    if traits_csv_path.exists():
        validate_csv_path("traits.csv", ["entity_name", "versioned", "audit_of_creation", "audit_of_modification", "soft_delete"])
        with traits_csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("entity_name", "").strip() == n:
                    entity_traits["versioned"] = (
                        row.get("versioned", "").strip().lower() == "true"
                    )
                    entity_traits["audit_of_creation"] = (
                        row.get("audit_of_creation", "").strip().lower() == "true"
                    )
                    entity_traits["audit_of_modification"] = (
                        row.get("audit_of_modification", "").strip().lower() == "true"
                    )
                    entity_traits["soft_delete"] = (
                        row.get("soft_delete", "").strip().lower() == "true"
                    )

    spaced_title = "".join([" " + c if c.isupper() else c for c in n]).strip().lower()
    readable_title_en = spaced_title.capitalize()
    plural_title_en = (
        readable_title_en
        if readable_title_en.endswith("s")
        else f"{readable_title_en}s"
    )

    for locale in available_locales:
        if locale == "en":
            target_path = base_path / "messages_en.properties"
            lang_name = "English"
            primary_iso = "en"
        else:
            target_path = base_path / f"messages_{locale}.properties"
            primary_iso = locale.split("_")[0].lower()
            lang_name = ISO_LANG_NAMES.get(primary_iso, locale)

        target_lines = []
        target_lines.append(f"{base_package}.entity/{n}={n}")
        target_lines.append(f"{base_package}.entity/{n}.id=Id")

        if entity_traits["versioned"]:
            v_text = "Version" if locale == "en" else "Versiune"
            target_lines.append(f"{base_package}.entity/{n}.version={v_text}")
        if entity_traits["audit_of_creation"]:
            cb = "Created by" if locale == "en" else "Creat de"
            cd = "Created date" if locale == "en" else "Data creării"
            target_lines.append(f"{base_package}.entity/{n}.createdBy={cb}")
            target_lines.append(f"{base_package}.entity/{n}.createdDate={cd}")
        if entity_traits["audit_of_modification"]:
            mb = "Last modified by" if locale == "en" else "Modificat de"
            md = "Last modified date" if locale == "en" else "Data modificării"
            target_lines.append(f"{base_package}.entity/{n}.lastModifiedBy={mb}")
            target_lines.append(f"{base_package}.entity/{n}.lastModifiedDate={md}")
        if entity_traits["soft_delete"]:
            db = "Deleted by" if locale == "en" else "Șters de"
            dd = "Deleted date" if locale == "en" else "Data ștergerii"
            target_lines.append(f"{base_package}.entity/{n}.deletedBy={db}")
            target_lines.append(f"{base_package}.entity/{n}.deletedDate={dd}")

        for trait in traits_list:
            spaced_name = (
                "".join([" " + c if c.isupper() else c for c in trait]).strip().lower()
            )
            readable_en = spaced_name.capitalize()
            if locale == "en":
                target_lines.append(f"{base_package}.entity/{n}.{trait}={readable_en}")
                target_lines.append(
                    f"{base_package}.view.{n.lower()}/{n.lower()}DetailView.{trait}Field={readable_en}"
                )
                target_lines.append(
                    f"{base_package}.view.{n.lower()}/{n.lower()}ListView.{trait}Column={readable_en}"
                )
                target_lines.append(
                    f"{base_package}.view.{n.lower()}/{n.lower()}ListView.dataGrid.{trait}={readable_en}"
                )
            else:
                traducere_lang = ask_ollama_translation(readable_en, lang_name)
                target_lines.append(
                    f"{base_package}.entity/{n}.{trait}={traducere_lang}"
                )
                target_lines.append(
                    f"{base_package}.view.{n.lower()}/{n.lower()}DetailView.{trait}Field={traducere_lang}"
                )
                target_lines.append(
                    f"{base_package}.view.{n.lower()}/{n.lower()}ListView.{trait}Column={traducere_lang}"
                )
                target_lines.append(
                    f"{base_package}.view.{n.lower()}/{n.lower()}ListView.dataGrid.{trait}={traducere_lang}"
                )

        if locale == "en":
            target_lines.append(
                f"{base_package}.view.{n.lower()}/{n.lower()}ListView.title={plural_title_en}"
            )
            target_lines.append(
                f"{base_package}.view.{n.lower()}/{n.lower()}DetailView.title={readable_title_en} Details"
            )
            target_lines.append(f"{base_package}/menu.{n}.list={plural_title_en}")
        else:
            traducere_title_list = ask_ollama_translation(plural_title_en, lang_name)
            if not traducere_title_list or len(traducere_title_list) > 50:
                traducere_title_list = (
                    f"Lista {spaced_title}" if primary_iso == "ro" else plural_title_en
                )
            traducere_title_detail = ask_ollama_translation(
                readable_title_en, lang_name
            )
            if not traducere_title_detail or len(traducere_title_detail) > 50:
                traducere_title_detail = (
                    f"Detalii {spaced_title}"
                    if primary_iso == "ro"
                    else f"{readable_title_en} Details"
                )
            target_lines.append(
                f"{base_package}.view.{n.lower()}/{n.lower()}ListView.title={traducere_title_list}"
            )
            target_lines.append(
                f"{base_package}.view.{n.lower()}/{n.lower()}DetailView.title={traducere_title_detail}"
            )
            target_lines.append(f"{base_package}/menu.{n}.list={traducere_title_list}")

        for rel in relations_list:
            f_name = rel["field"]
            spaced_name = (
                "".join([" " + c if c.isupper() else c for c in f_name]).strip().lower()
            )
            readable_en = spaced_name.capitalize()
            if locale == "en":
                target_lines.append(
                    f"{base_package}.entity/{n}.{f_name}={readable_en}"
                )
            else:
                translate_label_relation = ask_ollama_translation(readable_en, lang_name)
                target_lines.append(
                    f"{base_package}.entity/{n}.{f_name}={translate_label_relation}"
                )

        for rel in relations_list:
            if rel["type"] == "COMPOSITION_1:N":
                tgt_lower = rel["target"].lower()
                f_name = rel["field"]
                readable_title_en = f_name.capitalize()
                if locale == "en":
                    target_lines.append(
                        f"{base_package}.view.{tgt_lower}/{tgt_lower}DetailView.{f_name}={readable_title_en}"
                    )
                else:
                    translate_label_composition = ask_ollama_translation(
                        readable_title_en, lang_name
                    )
                    target_lines.append(
                        f"{base_package}.view.{tgt_lower}/{tgt_lower}DetailView.{f_name}={translate_label_composition}"
                    )

        entity_lines = [
            line for line in target_lines
            if line.startswith(f"{base_package}.entity/{n}.") or line.startswith(f"{base_package}.entity/{n}=")
        ]
        other_lines = [line for line in target_lines if not line.startswith(f"{base_package}.entity/{n}.") and not line.startswith(f"{base_package}.entity/{n}=")]
        
        replace_entity_messages(str(target_path), base_package, n, entity_lines)
        if other_lines:
            append_unique(str(target_path), other_lines)
        if locale == "en":
            replace_entity_messages(str(base_path / "messages.properties"), base_package, n, entity_lines)
            if other_lines:
                append_unique(str(base_path / "messages.properties"), other_lines)

    logger.info(
        f"✨ Parametric localization layout for entity '{n}' successfully compiled across available locales!"
    )
    from jmix_cli.i18n.cache import _persist_cache
    _persist_cache()
