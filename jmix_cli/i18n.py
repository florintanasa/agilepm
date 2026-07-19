import csv
import http.client
import json
import os
import re
from typing import Any

from jmix_cli.utils import COMPANY, PROIECT_PATH, append_unique, company_path, project_name


def ask_ollama_translation(text_to_translate: str, target_language_name: str) -> str:
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
            return translated_text if translated_text else text_to_translate
    except Exception as e:
        print(f"[-] Ollama translation warning: {e}. Falling back to English.")
    return text_to_translate


def update_messages_entity(
    project_dir: str, base_package: str, entity_name: str, traits_list: list[str], relations_list: list[dict[str, Any]] = []
) -> None:
    n = entity_name.strip()
    print(
        f"Generating dynamic parametric localization messages for exact entity {n}..."
    )

    app_properties_path = project_dir + "/src/main/resources/application.properties"
    available_locales = ["en"]
    if os.path.exists(app_properties_path):
        with open(app_properties_path, "r", encoding="utf-8") as f:
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
    base_path = project_dir + f"/src/main/resources/{package_path_slashes}"

    entity_traits = {
        "versioned": False,
        "audit_of_creation": False,
        "audit_of_modification": False,
        "soft_delete": False,
    }
    traits_csv_path = project_dir + "/traits.csv"
    if os.path.exists(traits_csv_path):
        with open(traits_csv_path, mode="r", encoding="utf-8") as f:
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
            target_path = base_path + "/messages_en.properties"
            lang_name = "English"
            primary_iso = "en"
        else:
            target_path = base_path + f"/messages_{locale}.properties"
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

        append_unique(target_path, target_lines)
        if locale == "en":
            append_unique(base_path + "/messages.properties", target_lines)

    print(
        f"✨ Parametric localization layout for entity '{n}' successfully compiled across available locales!"
    )
