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
from datetime import datetime
from pathlib import Path

from jmix_cli.core.project import PROIECT_PATH, company_path, project_name
from jmix_cli.core.files import write_file, ensure_dir
from jmix_cli.core.logger import get_logger

logger = get_logger("jmix_cli.migrate")


def _add_import_after(content: str, class_name: str) -> str:
    """Add an import for ``class_name`` after the last existing import line.

    If the import already exists, the content is returned unchanged.
    """
    full_import = f"import {class_name};"
    if full_import in content:
        return content
    match = re.search(r'(import [^\n;]+;\n)(?!import)', content)
    if match:
        return content[:match.end()] + full_import + "\n" + content[match.end():]
    match = re.search(r'package [^;]+;\n', content)
    if match:
        return content[:match.end()] + "\n" + full_import + "\n" + content[match.end():]
    return content


def _append_index_entry(match: re.Match, index_entry: str) -> str:
    """Append an @Index entry to an existing @Table indexes array."""
    indexes_content = match.group(1).rstrip()
    closing = match.group(2)
    if indexes_content.rstrip().endswith(","):
        return indexes_content + "\n        " + index_entry + closing
    return indexes_content + ",\n        " + index_entry + closing


def _remove_index_entry(content: str, index_name: str) -> str:
    """Remove an @Index entry from the @Table indexes array.

    Handles first/last/only entry cases (with/without preceding or trailing comma).
    If the indexes array becomes empty, removes the entire indexes = { ... } from @Table.
    """
    escaped = re.escape(index_name)
    pattern = rf"(?:,)?\n[ \t]+@Index\(name\s*=\s*\"{escaped}\".*?\),?"
    new_content = re.sub(pattern, "", content, count=1)
    if re.search(r"indexes\s*=\s*\{\s*\}", new_content):
        new_content = re.sub(r',\s*indexes\s*=\s*\{\s*\}', "", new_content)
    return new_content


def inject_new_fields_into_existing_entity(entity_name: str, new_fields: list[dict[str, Any]]) -> None:
    """Inject new fields into existing Java entity file."""
    entity_path = (
        PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{entity_name}.java"
    )

    if not entity_path.exists():
        return

    content = entity_path.read_text(encoding="utf-8")

    for field in new_fields:
        f_name = field["name"]
        f_type = field["type"]

        if f"private {f_type} {f_name};" in content or f"private {f_type} {f_name} = false;" in content:
            continue

        type_import_map = {
            "BigDecimal": "import java.math.BigDecimal;",
            "LocalDate": "import java.time.LocalDate;",
            "LocalDateTime": "import java.time.LocalDateTime;",
            "OffsetDateTime": "import java.time.OffsetDateTime;",
        }
        type_import = type_import_map.get(f_type)
        if type_import and type_import not in content:
            content = content.replace(
                "import java.util.UUID;",
                f"import java.util.UUID;\n{type_import}",
            )

        validation_anno = ""
        if field["mandatory"]:
            validation_anno = "    @NotNull\n"

        if field["mandatory"]:
            column_annotation = f'    @Column(name = "{f_name.upper()}", nullable = false)\n'
        else:
            column_annotation = f'    @Column(name = "{f_name.upper()}")\n'
        field_declaration = f"    private {f_type} {f_name}{' = false' if f_type.lower() == 'boolean' and field.get('mandatory') else ''};\n\n"

        field_block = f"{validation_anno}{column_annotation}{field_declaration}"

        if field["unique"]:
            table_name = entity_name.upper()
            col_upper = f_name.upper()
            idx_name = f"IDX_{table_name}_UNQ_{col_upper}"
            index_entry = f'@Index(name = "{idx_name}", columnList = "{col_upper}", unique = true)'

            if "import jakarta.persistence.Index;" not in content:
                content = content.replace(
                    "import jakarta.persistence.*;",
                    "import jakarta.persistence.*;\nimport jakarta.persistence.Index;",
                )

            if re.search(r'@Table\([^)]*indexes\s*=\s*\{', content):
                content = re.sub(
                    r'(indexes\s*=\s*\{[^}]*?)(\s*\})',
                    lambda m: _append_index_entry(m, index_entry),
                    content,
                    count=1,
                )
            else:
                content = re.sub(
                    r'@Table\(name\s*=\s*"([^"]+)"\)',
                    lambda m: f'@Table(name = "{m.group(1)}", indexes = {{\n        {index_entry}\n    }})',
                    content,
                    count=1,
                )

        if "    public UUID getId()" in content:
            content = content.replace(
                "    public UUID getId()",
                f"{field_block}    public UUID getId()"
            )

        f_caps = f_name[0].upper() + f_name[1:]
        getter = f"    public {f_type} get{f_caps}() {{\n        return {f_name};\n    }}\n\n"
        setter = f"    public void set{f_caps}({f_type} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

        last_brace = content.rfind("}")
        if last_brace != -1:
            content = content[:last_brace] + getter + setter + content[last_brace:]

    entity_path.write_text(content, encoding="utf-8")
    logger.info(f"✅ Injected new fields into {entity_name}.java")


def _remove_fields_from_java(entity_name: str, fields_to_remove: list[str]) -> None:
    """Remove fields, getters, and setters from an existing Java entity file."""
    entity_path = (
        PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{entity_name}.java"
    )
    if not entity_path.exists():
        return

    content = entity_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    for field_name in fields_to_remove:
        field_type = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("private ") and f" {field_name};" in stripped.lower():
                parts = stripped.replace(";", "").split()
                if len(parts) >= 3:
                    field_type = parts[1]
                break

        if field_type is None:
            continue

        actual_field_name = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("private ") and f" {field_name};" in stripped.lower():
                parts = stripped.replace(";", "").split()
                if len(parts) >= 3:
                    actual_field_name = parts[2]
                break

        if actual_field_name is None:
            continue

        caps = actual_field_name[0].upper() + actual_field_name[1:]

        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("private ") and f" {field_name};" in stripped.lower():
                while new_lines and new_lines[-1].strip().startswith("@"):
                    new_lines.pop()
                if new_lines and new_lines[-1].strip() == "":
                    new_lines.pop()
                continue
            new_lines.append(line)
        lines = new_lines

        content = "\n".join(lines)

        getter = f"    public {field_type} get{caps}() {{\n        return {actual_field_name};\n    }}\n\n"
        content = content.replace(getter, "")

        setter = f"    public void set{caps}({field_type} {actual_field_name}) {{\n        this.{actual_field_name} = {actual_field_name};\n    }}\n\n"
        content = content.replace(setter, "")

        lines = content.splitlines()

    entity_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(f"✅ Removed dropped fields from {entity_name}.java: {fields_to_remove}")


def _update_java_for_metadata_changes(entity_name: str, metadata_changes: list[dict[str, Any]]) -> None:
    """Update Java entity file to reflect metadata changes (mandatory, type, unique).

    For 'nullable' changes: adds/removes @NotNull and updates @Column(nullable=...).
    For 'type' changes: updates the field declaration, getter return type, and
    setter parameter type.
    """
    entity_path = (
        PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{entity_name}.java"
    )
    if not entity_path.exists():
        return

    content = entity_path.read_text(encoding="utf-8")

    for change in metadata_changes:
        field_name = change["name"]
        field_upper = field_name.upper()
        change_type = change["change"]

        if change_type == "nullable":
            new_mandatory = change["new"]
            is_relation = change.get("is_relation", False)

            if is_relation:
                col_name = change["column_name"]
                if new_mandatory:
                    if f'@JoinColumn(name = "{col_name}", nullable = false)' not in content:
                        for ann in ("ManyToOne", "OneToOne"):
                            old = f'@JoinColumn(name = "{col_name}")\n    @{ann}'
                            new = f'@JoinColumn(name = "{col_name}", nullable = false)\n    @NotNull\n    @{ann}'
                            if old in content:
                                content = content.replace(old, new, 1)
                                break
                    if "import jakarta.validation.constraints.NotNull;" not in content:
                        content = _add_import_after(content, "jakarta.validation.constraints.NotNull")
                else:
                    old_join = f'@JoinColumn(name = "{col_name}", nullable = false)\n    @NotNull\n'
                    new_join = f'@JoinColumn(name = "{col_name}")\n'
                    content = content.replace(old_join, new_join)
                    if "@NotNull" not in content:
                        content = re.sub(
                            r'\nimport jakarta\.validation\.constraints\.NotNull;',
                            '',
                            content,
                        )
            else:
                if new_mandatory:
                    old_col = f'@Column(name = "{field_upper}")'
                    new_col = f'@NotNull\n    @Column(name = "{field_upper}", nullable = false)'
                    if old_col in content and f'@Column(name = "{field_upper}", nullable = false)' not in content:
                        content = content.replace(old_col, new_col)
                    if change.get("field_type", "").lower() == "boolean":
                        old_decl = f"private Boolean {field_name};"
                        new_decl = f"private Boolean {field_name} = false;"
                        if old_decl in content and f"private Boolean {field_name} = false;" not in content:
                            content = content.replace(old_decl, new_decl)
                else:
                    old_col = f'@Column(name = "{field_upper}", nullable = false)'
                    new_col = f'@Column(name = "{field_upper}")'
                    content = content.replace(old_col, new_col)

                    pattern = rf'(    @NotNull\n)((?:    @\w+.*\n)*)(    @Column\(name = "{field_upper}"\))'
                    content = re.sub(pattern, r'\2\3', content)

                    if change.get("field_type", "").lower() == "boolean":
                        old_decl = f"private Boolean {field_name} = false;"
                        new_decl = f"private Boolean {field_name};"
                        content = content.replace(old_decl, new_decl)

        elif change_type == "type":
            old_type = change["old"]
            new_type = change["new"]
            content = content.replace(
                f"private {old_type} {field_name};",
                f"private {new_type} {field_name};",
            )
            f_caps = field_name[0].upper() + field_name[1:]
            content = content.replace(
                f"public {old_type} get{f_caps}()",
                f"public {new_type} get{f_caps}()",
            )
            content = content.replace(
                f"public void set{f_caps}({old_type} {field_name})",
                f"public void set{f_caps}({new_type} {field_name})",
            )

        elif change_type == "unique":
            table_name = entity_name.upper()
            index_name = f"IDX_{table_name}_UNQ_{field_upper}"
            index_entry = (
                f'@Index(name = "{index_name}", columnList = "{field_upper}", unique = true)'
            )

            if change["new"]:
                if re.search(r'@Table\([^)]*indexes\s*=\s*\{', content):
                    content = re.sub(
                        r'(indexes\s*=\s*\{[^}]*?)(\s*\})',
                        lambda m: _append_index_entry(m, index_entry),
                        content,
                        count=1,
                    )
                else:
                    content = re.sub(
                        r'@Table\(name\s*=\s*"([^"]+)"\)',
                        lambda m: f'@Table(name = "{m.group(1)}", indexes = {{\n        {index_entry}\n    }})',
                        content,
                        count=1,
                    )
            else:
                content = _remove_index_entry(content, index_name)

    entity_path.write_text(content, encoding="utf-8")
    logger.info(f"✅ Updated Java metadata for {entity_name}.java")
