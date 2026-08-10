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

from jmix_cli.core.project import PROIECT_PATH, company_path, project_name
from jmix_cli.entity import get_entities_from_csv, get_relations_from_csv
from jmix_cli.entity.traits import get_traits_from_csv
from jmix_cli.migrate.adapters import HSQLDBAdapter, get_existing_columns_from_changelogs


def get_table_name(entity_name: str) -> str:
    """Get the database table name for an entity.

    User entity uses USER_ table (Jmix convention).
    """
    return "USER_" if entity_name == "User" else entity_name.upper()


def map_type_to_sql(java_type: str) -> str:
    """Map Java field type to SQL column type for Liquibase."""
    jt = java_type.lower()
    if jt in ["string", "text"]:
        return "VARCHAR(255)"
    if jt in ["integer", "int"]:
        return "INT"
    if jt in ["long"]:
        return "BIGINT"
    if jt in ["boolean", "bool"]:
        return "BOOLEAN"
    if jt in ["date", "localdate"]:
        return "date"
    if jt in ["datetime", "localdatetime", "offsetdatetime"]:
        return "timestamp with time zone"
    if jt in ["uuid"]:
        return "UUID"
    if jt in ["double"]:
        return "double precision"
    if jt in ["bigdecimal"]:
        return "DECIMAL"
    return "VARCHAR(255)"


def _read_entity_fields(entity_name: str) -> list[dict[str, Any]]:
    """Read entity fields from entities.csv."""
    return get_entities_from_csv("entities.csv", entity_name)


def _read_entity_traits(entity_name: str) -> dict[str, Any]:
    """Read entity traits from traits.csv."""
    return get_traits_from_csv("traits.csv", entity_name)


def _read_all_relations() -> list[dict[str, Any]]:
    """Read all relations from relations.csv with full source/target info.

    Unlike get_relations_from_csv (which filters by source entity), this
    returns every row so callers can also check relations where the entity
    is the *target*.
    """
    relations_list: list[dict[str, Any]] = []
    csv_file = Path("relations.csv")
    if not csv_file.exists():
        return relations_list
    with csv_file.open(mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rel_dict: dict[str, Any] = {
                "source": row["source_entity"].strip(),
                "type": row["relation_type"].strip(),
                "target": row["target_entity"].strip(),
                "field": row["field_name"].strip(),
                "mandatory": row["mandatory"].strip().lower() == "true",
            }
            if "ownership" in (reader.fieldnames or []):
                rel_dict["ownership"] = row.get("ownership", "").strip()
            relations_list.append(rel_dict)
    return relations_list


def _get_relation_field_names(entity_name: str) -> set[str]:
    """Get field names from relations.csv for the given entity (as source or target).

    For N:1, 1:1 relations: the forward field is on the *source* entity.
    For COMPOSITION_1:1: ``_finalize_composition_relationships`` injects the
    forward field (``{field}``, type = target) into the *source* entity, and
    ``_inject_composition_into_parent`` may inject the inverse field
    (``{source_entity_camelCase}``) into the *source* entity.  When the entity
    is the *target* of a COMPOSITION_1:1, the
    """
    relations = get_relations_from_csv("relations.csv", entity_name)
    field_names: set[str] = set()
    for rel in relations:
        rel_type = rel["type"]
        field = rel["field"]
        if rel_type in ("N:1", "1:1"):
            field_names.add(field.upper())
        elif rel_type == "COMPOSITION_1:1":
            field_names.add(field.upper())
            inv_field = entity_name[0].lower() + entity_name[1:]
            field_names.add(inv_field.upper())
        elif rel_type == "COMPOSITION_1:N":
            tgt_class = rel["target"]
            mapped_by_prop = tgt_class[0].lower() + tgt_class[1:]
            field_names.add(mapped_by_prop.upper())

    for rel in _read_all_relations():
        if rel["target"].upper() != entity_name.upper():
            continue
        if rel["type"] == "COMPOSITION_1:1":
            field_names.add(rel["field"].upper())
            inv_field = rel["source"][0].lower() + rel["source"][1:]
            field_names.add(inv_field.upper())

    return field_names


def _get_relation_column_names(entity_name: str) -> set[str]:
    """Get FK column names from relations.csv for the given entity (as source).

    For N:1, 1:1, and COMPOSITION_1:1 relations where the entity is the
    *source*: ``_finalize_composition_relationships`` injects
    ``@JoinColumn(name = "{field}_ID")`` into the source entity, so the FK
    column ``{field}_ID`` lives on the source entity's table.

    When the entity is the *target* of a COMPOSITION_1:1, the FK column is on
    the *source* entity's table, so nothing is added for the target.

    Al
    """
    relations = get_relations_from_csv("relations.csv", entity_name)
    column_names: set[str] = set()
    for rel in relations:
        rel_type = rel["type"]
        field = rel["field"].upper()
        if rel_type in ("N:1", "1:1", "COMPOSITION_1:1"):
            column_names.add(f"{field}_ID")

    entity_path = (
        PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{entity_name}.java"
    )
    if entity_path.exists():
        content = entity_path.read_text(encoding="utf-8")
        for match in re.finditer(r'@JoinColumn\(name\s*=\s*"([^"]+)"', content):
            column_names.add(match.group(1).upper())

    return column_names


def detect_missing_columns(entity_name: str, db_adapter: DatabaseAdapter) -> list[dict[str, Any]]:
    """Detect columns that exist in entity but not in database or existing changelogs."""
    table_name = get_table_name(entity_name)
    entity_fields = _read_entity_fields(entity_name)

    db_columns = db_adapter.get_columns(table_name)
    changelog_columns = get_existing_columns_from_changelogs(table_name)

    existing_columns = db_columns | changelog_columns

    missing = []
    for field in entity_fields:
        sql_col = field["name"].upper()
        if sql_col not in existing_columns:
            missing.append(field)

    return missing


def detect_missing_relations(entity_name: str) -> list[dict[str, Any]]:
    """Check if entity has relations defined but missing changelog entries.

    For N:N both-owning, we need to check if inverse relation also has changelog.
    """
    relations_list = get_relations_from_csv("relations.csv", entity_name)
    missing_rels = []

    for rel in relations_list:
        rel_type = rel["type"]
        tgt = rel["target"].upper()
        field = rel["field"].upper()

        if rel_type == "N:1":
            fk_col = f"{field}_ID"
            if fk_col not in get_existing_columns_from_changelogs(entity_name.upper()):
                missing_rels.append(rel)
        elif rel_type == "N:N":
            ownership = rel.get("ownership", "owning")
            if ownership == "both-owning":
                inv_field_name = entity_name.lower() + ("s" if not entity_name.endswith("s") else "")
                inv_columns = get_existing_columns_from_changelogs(tgt)
                if f"{inv_field_name.upper()}" not in str(inv_columns):
                    missing_rels.append(rel)

    return missing_rels


def get_missing_relation_columns(entity_name: str, db_adapter: DatabaseAdapter) -> list[dict[str, Any]]:
    """Get relation FK columns that are missing from the database/changelog.

    For N:1, 1:1, and COMPOSITION_1:1 relations where the entity is the
    *source*, the FK column ``{field}_ID`` should exist in the entity's table.
    This function returns column definitions for those FK columns that are
    missing from both the database and existing changelogs.

    Returns list of dicts with ``name``, ``type``, and ``mandatory`` keys
    suitable for ``gen_add_column_changelog``.
    """
    table_name = get_table_name(entity_name)
    db_columns = db_adapter.get_columns(table_name)
    changelog_columns = get_existing_columns_from_changelogs(table_name)
    existing_columns = db_columns | changelog_columns

    relations = get_relations_from_csv("relations.csv", entity_name)
    relation_cols = _get_relation_column_names(entity_name)

    missing = []
    for rel in relations:
        rel_type = rel["type"]
        field = rel["field"].upper()
        if rel_type in ("N:1", "1:1", "COMPOSITION_1:1"):
            fk_col = f"{field}_ID"
            if fk_col in relation_cols and fk_col not in existing_columns:
                missing.append({
                    "name": fk_col,
                    "type": "UUID",
                    "mandatory": rel.get("mandatory", False),
                    "unique": False,
                })

    return missing


def detect_changed_fields(entity_name: str) -> tuple[list[dict[str, Any]], list[str], list[tuple[str, str]]]:
    """Detect dropped, added, and renamed fields for an entity.

    Returns:
        added_fields: fields in entities.csv but missing from existing Java
        dropped_fields: fields in existing Java but missing from entities.csv
        renamed_fields: list of (old_name, new_name) where a likely rename was detected
    """
    csv_fields = _read_entity_fields(entity_name)
    csv_by_name = {f["name"].upper(): f for f in csv_fields}
    java_fields = _get_fields_from_existing_java(entity_name)
    java_by_name = {f["name"].upper(): f for f in java_fields}

    relation_field_names = _get_relation_field_names(entity_name)

    dropped = []
    for f in java_fields:
        if f["name"].upper() not in csv_by_name and f["name"].upper() not in relation_field_names:
            dropped.append(f["name"])

    added = []
    for f in csv_fields:
        if f["name"].upper() not in java_by_name:
            added.append(f)

    renamed: list[tuple[str, str]] = []
    unmatched_dropped = []
    unmatched_added = []
    for dropped_name in dropped:
        match = None
        for added_field in added:
            if added_field["type"] == next(
                (f["type"] for f in java_fields if f["name"].upper() == dropped_name.upper()),
                None,
            ) and _names_are_similar(dropped_name, added_field["name"]):
                match = added_field
                break
        if match:
            renamed.append((dropped_name, match["name"]))
        else:
            unmatched_dropped.append(dropped_name)

    unmatched_added = [f["name"] for f in added if f["name"].upper() not in [n.upper() for _, n in renamed]]

    return unmatched_added, unmatched_dropped, renamed


def detect_field_metadata_changes(entity_name: str) -> list[dict[str, Any]]:
    """Detect type/mandatory/unique changes for existing fields."""
    csv_fields = _read_entity_fields(entity_name)
    java_fields = _get_fields_from_existing_java(entity_name)
    java_by_name = {f["name"].upper(): f for f in java_fields}

    changes: list[dict[str, Any]] = []
    for csv_field in csv_fields:
        upper_name = csv_field["name"].upper()
        if upper_name not in java_by_name:
            continue
        java_field = java_by_name[upper_name]
        if csv_field["type"] != java_field["type"]:
            changes.append(
                {
                    "name": csv_field["name"],
                    "change": "type",
                    "old": java_field["type"],
                    "new": csv_field["type"],
                }
            )
        if csv_field["mandatory"] != java_field["mandatory"]:
            changes.append(
                {
                    "name": csv_field["name"],
                    "change": "nullable",
                    "old": java_field["mandatory"],
                    "new": csv_field["mandatory"],
                    "field_type": csv_field["type"],
                }
            )
        if csv_field["unique"] != java_field["unique"]:
            changes.append(
                {
                    "name": csv_field["name"],
                    "change": "unique",
                    "old": java_field["unique"],
                    "new": csv_field["unique"],
                }
            )
    return changes


def detect_relation_metadata_changes(entity_name: str) -> list[dict[str, Any]]:
    """Detect mandatory (nullable) changes for relation fields defined in relations.csv.

    Only N:1 and 1:1 relations are checked — these generate a single-valued
    field with a ``@JoinColumn`` FK column in the Java entity.  The detection
    compares the ``mandatory`` flag from ``relations.csv`` against the presence
    of ``@NotNull`` directly above the ``@JoinColumn`` / ``@ManyToOne`` /
    ``@OneToOne`` annotation block in the existing Java file.

    Each returned change dict uses the FK column name from ``@JoinColumn``.
    """
    relations = get_relations_from_csv("relations.csv", entity_name)
    if not relations:
        return []

    entity_path = (
        PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{entity_name}.java"
    )
    if not entity_path.exists():
        return []

    content = entity_path.read_text(encoding="utf-8")

    changes: list[dict[str, Any]] = []
    for rel in relations:
        rel_type = rel["type"].strip().upper()
        if rel_type not in ("N:1", "1:1", "COMPOSITION_1:1"):
            continue
        f_name = rel["field"]
        csv_col_name = f"{f_name.upper()}_ID"

        field_pattern = (
            r'(@JoinColumn\(name\s*=\s*"(\w+_ID)"[^)]*\)\s*\n'
            r'(?:    @NotNull\n)?\s*'
            r'@(?:ManyToOne|OneToOne)\(fetch = FetchType\.LAZY\)\s*\n    )'
            f'private {rel["target"]} {f_name};'
        )
        join_match = re.search(field_pattern, content)
        if join_match:
            col_name = join_match.group(2)
        else:
            col_name = csv_col_name

        pattern = (
            rf'    @JoinColumn\(name\s*=\s*"' + col_name + r'"(?:,\s*nullable\s*=\s*false)?\)\s*\n'
            r'(    @NotNull\n)?'
            r'    @(ManyToOne|OneToOne)'
        )
        match = re.search(pattern, content)
        if match is None or match.group(1) is None:
            pattern_pre = (
                r'    @NotNull\n'
                rf'    @JoinColumn\(name\s*=\s*"' + col_name + r'"(?:,\s*nullable\s*=\s*false)?\)\s*\n'
                r'    @(ManyToOne|OneToOne)'
            )
            match_pre = re.search(pattern_pre, content)
            if match_pre:
                java_mandatory = True
            elif match:
                java_mandatory = bool(match.group(1))
            else:
                java_mandatory = False
        else:
            java_mandatory = True

        csv_mandatory = rel.get("mandatory", False)

        if java_mandatory != csv_mandatory:
            changes.append(
                {
                    "name": col_name.lower(),
                    "column_name": col_name,
                    "field_name": f_name,
                    "change": "nullable",
                    "old": java_mandatory,
                    "new": csv_mandatory,
                    "is_relation": True,
                }
            )

    return changes


def _names_are_similar(name1: str, name2: str) -> bool:
    """Check if two field names are similar enough to be considered a rename.

    Uses common prefix length as a heuristic — fields must share at least
    3 characters in a common prefix to be considered a rename. This prevents
    false-positive renames between unrelated fields of the same type
    (e.g. companyName -> address).
    """
    if not name1 or not name2:
        return False
    min_len = min(len(name1), len(name2))
    common_prefix_len = 0
    for i in range(min_len):
        if name1[i].lower() == name2[i].lower():
            common_prefix_len += 1
        else:
            break
    return common_prefix_len >= 3


def _get_fields_from_existing_java(entity_name: str) -> list[dict[str, Any]]:
    """Extract business field metadata from an existing Java entity file."""
    entity_path = (
        PROIECT_PATH
        / "src" / "main" / "java" / company_path / project_name / "entity"
        / f"{entity_name}.java"
    )
    fields: list[dict[str, Any]] = []
    if not entity_path.exists():
        return fields

    content = entity_path.read_text(encoding="utf-8")
    unique_columns = _get_unique_columns_from_java(content)
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("private "):
            continue
        if "<" in stripped:
            continue

        declaration = stripped.strip(";")
        parts = declaration.split()
        if len(parts) >= 2:
            f_type = parts[1]
            f_name = parts[2].strip(";")
            if f_name in (
                "id", "version", "createdBy", "createdDate",
                "lastModifiedBy", "lastModifiedDate",
                "deletedBy", "deletedDate",
            ):
                continue
            block_start = idx - 1
            while block_start >= 0 and not lines[block_start].strip().startswith("private "):
                block_start -= 1
            block_start += 1
            block = "\n".join(lines[block_start:idx])
            mandatory = "@NotNull" in block
            fields.append(
                {
                    "name": f_name,
                    "type": f_type,
                    "mandatory": mandatory,
                    "unique": f_name.upper() in unique_columns,
                }
            )

    return fields


def _get_unique_columns_from_java(content: str) -> set[str]:
    """Extract column names that have a unique constraint from the @Table annotation.

    Parses @Index entries with unique=true and returns the column names
    (uppercased) from their columnList attribute.
    """
    unique_columns: set[str] = set()
    for match in re.finditer(r'@Index\s*\(([^)]*)\)', content, re.DOTALL):
        index_body = match.group(1)
        if re.search(r'unique\s*=\s*true', index_body):
            col_match = re.search(r'columnList\s*=\s*"([^"]+)"', index_body)
            if col_match:
                for col in col_match.group(1).split(','):
                    unique_columns.add(col.strip().upper())
    return unique_columns


def detect_dropped_columns(entity_name: str, db_adapter: DatabaseAdapter) -> list[str]:
    table_name = get_table_name(entity_name)
    entity_fields = _read_entity_fields(entity_name)
    db_columns = db_adapter.get_columns(table_name)
    changelog_columns = get_existing_columns_from_changelogs(table_name)

    entity_columns = {f["name"].upper() for f in entity_fields}
    system_cols = {"ID", "VERSION", "CREATED_BY", "CREATED_DATE", "LAST_MODIFIED_BY", "LAST_MODIFIED_DATE", "DELETED_BY", "DELETED_DATE"}
    relation_cols = _get_relation_column_names(entity_name)

    already_dropped = _get_already_dropped_columns(table_name)

    all_existing = db_columns | changelog_columns
    dropped = [
        col for col in all_existing
        if col not in entity_columns
        and col not in system_cols
        and col not in relation_cols
        and col not in already_dropped
    ]
    return dropped


def _get_already_dropped_columns(table_name: str) -> set[str]:
    """Get columns that have already been dropped by previous drop changelogs.

    Parses all changelog XML files for dropColumn changesets targeting the
    given table, so we don't repeatedly try to drop the same column.
    """
    changelog_dir = (
        PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name / "liquibase" / "changelog"
    )
    dropped: set[str] = set()
    if not changelog_dir.exists():
        return dropped

    for xml_file in changelog_dir.rglob("*.xml"):
        try:
            content = xml_file.read_text(encoding="utf-8")
        except OSError:
            continue
        if f"tableName=\"{table_name}\"" not in content:
            continue
        for match in re.finditer(
            r'<dropColumn[^>]*tableName="' + re.escape(table_name) + r'"[^>]*>',
            content,
        ):
            tag = match.group(0)
            col_match = re.search(r'columnName="([^"]+)"', tag)
            if col_match:
                dropped.add(col_match.group(1).upper())
    return dropped
