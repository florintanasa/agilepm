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
import http.client
import json
import re
from pathlib import Path
from typing import Any

from jmix_cli.utils import get_logger
from jmix_cli.exceptions import ConfigurationError, GenerationError
from jmix_cli.utils import COMPANY, PROIECT_PATH, append_unique, company_path, project_name, validate_csv_path

logger = get_logger("jmix_cli.i18n")

_CACHE_FILE = Path(".ollama_translation_cache.json")
_translation_cache: dict[str, str] = {}
_cache_loaded = False


def _load_cache() -> None:
    global _cache_loaded, _translation_cache
    if _cache_loaded:
        return
    if _CACHE_FILE.exists():
        try:
            _translation_cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            _translation_cache = {}
    _cache_loaded = True


def _persist_cache() -> None:
    try:
        _CACHE_FILE.write_text(
            json.dumps(_translation_cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def _cache_key(text: str, target_language_name: str) -> str:
    return f"{target_language_name}:{text}"


def ask_ollama_translation(text_to_translate: str, target_language_name: str) -> str:
    _load_cache()
    key = _cache_key(text_to_translate, target_language_name)
    if key in _translation_cache:
        return _translation_cache[key]

    prompt = (
        f"Translate the following software UI label from English into {target_language_name}. "
        f"Return ONLY the translated string, without quotes, explanations, or introductory text. "
        f"Label: {text_to_translate}"
    )
    try:
        connection = http.client.HTTPConnection("localhost", 11434, timeout=10)
        payload = json.dumps(
            {"model": "translategemma:4b", "prompt": prompt, "stream": False}
        )
        headers = {"Content-Type": "application/json"}
        connection.request("POST", "/api/generate", payload, headers)
        response = connection.getresponse()
        if response.status == 200:
            data = json.loads(response.read().decode("utf-8"))
            translated_text = data.get("response", "").strip()
            translated_text = translated_text.replace('"', "").replace("'", "")
            result = translated_text if translated_text else text_to_translate
            _translation_cache[key] = result
            return result
    except (ConnectionError, TimeoutError, http.client.HTTPException, json.JSONDecodeError) as e:
        logger.error(f"[-] Ollama translation warning: {e}. Falling back to English.")
    return text_to_translate


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
            iso_lang_names = {
                "ar": "Arabic",
                "ckb": "Central Kurdish",
                "de": "German",
                "el": "Greek",
                "es": "Spanish",
                "fr": "French",
                "it": "Italian",
                "nl": "Dutch",
                "pt": "Brazilian Portuguese",
                "ro": "Romanian",
                "ru": "Russian",
                "tr": "Turkish",
                "zh": "Simplified Chinese",
            }
            primary_iso = locale.split("_")[0].lower()
            lang_name = iso_lang_names.get(primary_iso, locale)

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

        append_unique(str(target_path), target_lines)
        if locale == "en":
            append_unique(str(base_path / "messages.properties"), target_lines)

    logger.info(
        f"✨ Parametric localization layout for entity '{n}' successfully compiled across available locales!"
    )
    _persist_cache()
