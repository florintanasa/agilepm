import csv
import os
import re
from pathlib import Path

PROIECT_PATH = Path.cwd()


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
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file is empty: {csv_path}")
        missing = set(required_columns) - set(reader.fieldnames)
        if missing:
            raise ValueError(
                f"CSV file {csv_path} is missing required columns: {missing}"
            )
        return list(reader)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


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
