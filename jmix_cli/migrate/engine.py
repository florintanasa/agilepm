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
from typing import Any

from jmix_cli.utils import COMPANY, PROIECT_PATH, company_path, ensure_dir, project_name, write_file
from jmix_cli.utils import get_logger
from jmix_cli.entity import get_entities_from_csv, get_relations_from_csv

from jmix_cli.migrate.adapters import (
    HSQLDBAdapter,
    get_existing_columns_from_changelogs,
)
from jmix_cli.migrate.diff import (
    _get_fields_from_existing_java,
    _read_entity_fields,
    detect_changed_fields,
    detect_dropped_columns,
    detect_field_metadata_changes,
    detect_missing_columns,
    detect_relation_metadata_changes,
    get_missing_relation_columns,
    get_table_name,
)
from jmix_cli.migrate.changelog import (
    gen_add_column_changelog,
    gen_drop_column_changelog,
    gen_modify_column_changelog,
    gen_rename_column_changelog,
)
from jmix_cli.migrate.java import (
    _remove_fields_from_java,
    _update_java_for_metadata_changes,
    inject_new_fields_into_existing_entity,
)

logger = get_logger("jmix_cli.migrate")


def _apply_relation_field_renames(entity_name: str) -> list[str]:
    """Rename relation fields in Java if the field name in relations.csv
    doesn't match the Java field name.

    For N:1 and 1:1 relations, when the field_name in relations.csv changes
    (e.g., from 'priority' to 'mumu'), this function updates the Java entity
    field name, getter, and setter accordingly. The DB column name (e.g.,
    PRIORITY_ID) stays the same, so no changelog is needed for the rename.

    Returns list of renamed field names (old -> new) for logging.
    """
    from jmix_cli.entity import get_relations_from_csv

    relations = get_relations_from_csv("relations.csv", entity_name)
    if not relations:
        return []

    entity_path = (
        PROIECT_PATH
        / "src"
        / "main"
        / "java"
        / company_path
        / project_name
        / "entity"
        / f"{entity_name}.java"
    )
    if not entity_path.exists():
        return []

    content = entity_path.read_text(encoding="utf-8")
    renamed: list[str] = []

    for rel in relations:
        rel_type = rel["type"].strip().upper()
        if rel_type not in ("N:1", "1:1", "COMPOSITION_1:1"):
            continue
        csv_field = rel["field"].strip()
        tgt_class = rel["target"].strip()

        simple_pattern = rf'@JoinColumn\(name\s*=\s*"(\w+_ID)"[^)]*\)\s*\n(?:    @NotNull\n)?\s*@(ManyToOne|OneToOne)\(fetch = FetchType\.LAZY\)\s*\n\s*private {tgt_class} (\w+);'
        match = re.search(simple_pattern, content)
        if match and match.group(3) != csv_field:
            old_field = match.group(3)
            new_field = csv_field
            old_caps = old_field[0].upper() + old_field[1:]
            new_caps = new_field[0].upper() + new_field[1:]

            content = content.replace(
                f"private {tgt_class} {old_field};",
                f"private {tgt_class} {new_field};",
                1,
            )
            content = content.replace(
                f"public {tgt_class} get{old_caps}()",
                f"public {tgt_class} get{new_caps}()",
                1,
            )
            content = content.replace(
                f"return {old_field};",
                f"return {new_field};",
                1,
            )
            content = content.replace(
                f"public void set{old_caps}({tgt_class} {old_field})",
                f"public void set{new_caps}({tgt_class} {new_field})",
                1,
            )
            content = content.replace(
                f"this.{old_field} = {old_field};",
                f"this.{new_field} = {new_field};",
                1,
            )
            renamed.append(f"{old_field} -> {new_field}")

    if renamed:
        entity_path.write_text(content, encoding="utf-8")
        logger.info(f"✅ Renamed relation fields in {entity_name}.java: {renamed}")

    return renamed


def migrate_entity(entity_name: str, mode: str = "prompt") -> None:
    """Generate incremental Liquibase migrations for an entity.

    Args:
        entity_name: Name of the entity to migrate
        mode: 'prompt' (ask for confirmation on drop), 'force' (apply all), 'dry-run' (no write), 'quiet' (only log on changes)
    """
    from jmix_cli.i18n import update_messages_entity

    db_adapter = HSQLDBAdapter()
    messages_need_update = False

    relation_renames = _apply_relation_field_renames(entity_name)

    added_fields, dropped_from_csv, renamed_fields = detect_changed_fields(entity_name)

    if renamed_fields or added_fields or relation_renames:
        messages_need_update = True

    if entity_name == "User":
        user_standard_fields = {
            "username", "password", "firstname", "lastname",
            "email", "active", "timezoneid", "userprofile",
        }
        dropped_from_csv = [f for f in dropped_from_csv if f.lower() not in user_standard_fields]

    if dropped_from_csv:
        messages_need_update = True

    metadata_changes = detect_field_metadata_changes(entity_name)
    metadata_changes.extend(detect_relation_metadata_changes(entity_name))

    renamed_old_names = {old for old, _ in renamed_fields}
    renamed_new_names = {new for _, new in renamed_fields}

    all_missing = detect_missing_columns(entity_name, db_adapter)
    missing_fields = [f for f in all_missing if f["name"] not in renamed_new_names]

    table_name = get_table_name(entity_name)

    changelog_cols = get_existing_columns_from_changelogs(table_name)
    added_fields = [
        name for name in added_fields
        if name.upper() not in changelog_cols
    ]

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    if renamed_fields:
        entity_path = (
            PROIECT_PATH
            / "src"
            / "main"
            / "java"
            / company_path
            / project_name
            / "entity"
            / f"{entity_name}.java"
        )
        if entity_path.exists():
            java_content = entity_path.read_text(encoding="utf-8")
            csv_fields = _read_entity_fields(entity_name)
            for old_name, new_name in renamed_fields:
                field_type = next(f["type"] for f in csv_fields if f["name"] == new_name)
                old_caps = old_name[0].upper() + old_name[1:]
                new_caps = new_name[0].upper() + new_name[1:]
                java_content = java_content.replace(
                    f"private {field_type} {old_name};",
                    f"private {field_type} {new_name};",
                )
                java_content = java_content.replace(
                    f"return {old_name};",
                    f"return {new_name};",
                )
                java_content = java_content.replace(
                    f"public {field_type} get{old_caps}()",
                    f"public {field_type} get{new_caps}()",
                )
                java_content = java_content.replace(
                    f"public void set{old_caps}({field_type} {old_name})",
                    f"public void set{new_caps}({field_type} {new_name})",
                )
                java_content = java_content.replace(
                    f"this.{old_name} = {old_name};",
                    f"this.{new_name} = {new_name};",
                )
                java_content = java_content.replace(
                    f"this.{old_name}",
                    f"this.{new_name}",
                )
                entity_path.write_text(java_content, encoding="utf-8")
                logger.info(f"✅ Renamed field in Java: {old_name} -> {new_name}")

    if missing_fields:
        if mode != "quiet":
            logger.info(f"Injecting {len(missing_fields)} new fields into {entity_name}.java...")
        inject_new_fields_into_existing_entity(entity_name, missing_fields)

    csv_fields = _read_entity_fields(entity_name)
    java_fields = _get_fields_from_existing_java(entity_name)
    java_field_names = {f["name"].upper() for f in java_fields}
    re_added_fields = [
        f for f in csv_fields
        if f["name"].upper() not in java_field_names
        and f["name"].upper() in changelog_cols
    ]
    if re_added_fields:
        if mode != "quiet":
            logger.info(f"Injecting {len(re_added_fields)} re-added fields into {entity_name}.java...")
        inject_new_fields_into_existing_entity(entity_name, re_added_fields)

    dropped_columns = detect_dropped_columns(entity_name, db_adapter)

    csv_fields_by_name = {f["name"].lower(): f for f in _read_entity_fields(entity_name)}
    added_field_dicts = [
        csv_fields_by_name[name.lower()]
        for name in added_fields
        if name.lower() in csv_fields_by_name
    ]

    missing_relation_cols = get_missing_relation_columns(entity_name, db_adapter)

    if missing_fields or added_field_dicts or missing_relation_cols:
        new_fields = missing_fields + added_field_dicts + missing_relation_cols
        seen_names: set[str] = set()
        new_fields = [
            f for f in new_fields
            if f["name"].upper() not in seen_names
            and not seen_names.add(f["name"].upper())
        ]
        content = gen_add_column_changelog(entity_name, new_fields)
        target_dir = (
            PROIECT_PATH
            / "src"
            / "main"
            / "resources"
            / company_path
            / project_name
            / "liquibase"
            / "changelog"
            / datetime.now().strftime("%Y")
            / datetime.now().strftime("%m")
        )
        ensure_dir(str(target_dir))
        filename = target_dir / f"{timestamp}-alter-{table_name}-addField.xml"

        if mode != "quiet":
            logger.info(f"Generating incremental migration for {entity_name}: add columns {new_fields}")
        if mode != "dry-run":
            write_file(filename, content)
            if mode != "quiet":
                logger.info(f"✨ Created incremental changelog: {filename}")
        else:
            logger.info(f"[dry-run] Would create: {filename}")

    if renamed_fields:
        rename_content = gen_rename_column_changelog(entity_name, renamed_fields)
        if rename_content:
            target_dir = (
                PROIECT_PATH
                / "src"
                / "main"
                / "resources"
                / company_path
                / project_name
                / "liquibase"
                / "changelog"
                / datetime.now().strftime("%Y")
                / datetime.now().strftime("%m")
            )
            ensure_dir(str(target_dir))
            filename = target_dir / f"{timestamp}-alter-{table_name}-renameField.xml"
            if mode != "dry-run":
                write_file(filename, rename_content)
                if mode != "quiet":
                    logger.info(f"✨ Created rename changelog: {filename}")
            else:
                logger.info(f"[dry-run] Would create: {filename}")

    if metadata_changes:
        for change in metadata_changes:
            if (
                change.get("is_relation", False)
                and change["change"] == "nullable"
                and change.get("new") is True
            ):
                col = change["column_name"]
                tbl = table_name
                logger.warning(
                    f"⚠️  {entity_name}.{change['field_name']} → {tbl}.{col} "
                    f"is becoming NOT NULL. If existing DB rows have NULL in "
                    f"{col}, the Liquibase 'addNotNullConstraint' will fail. "
                    f"Either: (1) rm -rf .jmix/hsqldb/ then restart app, "
                    f"or (2) manually UPDATE {tbl} SET {col} = '<valid UUID>' "
                    f"WHERE {col} IS NULL before restarting."
                )
        changes_content = gen_modify_column_changelog(entity_name, metadata_changes)
        if changes_content:
            target_dir = (
                PROIECT_PATH
                / "src"
                / "main"
                / "resources"
                / company_path
                / project_name
                / "liquibase"
                / "changelog"
                / datetime.now().strftime("%Y")
                / datetime.now().strftime("%m")
            )
            ensure_dir(str(target_dir))
            filename = target_dir / f"{timestamp}-alter-{table_name}-modifyField.xml"
            if mode != "dry-run":
                write_file(filename, changes_content)
                if mode != "quiet":
                    logger.info(f"✨ Created modify changelog: {filename}")
            else:
                logger.info(f"[dry-run] Would create: {filename}")

    if metadata_changes and mode != "dry-run":
        _update_java_for_metadata_changes(entity_name, metadata_changes)

    user_standard_cols = set()
    if entity_name == "User":
        user_standard_cols = {
            "USERNAME", "PASSWORD", "FIRST_NAME", "LAST_NAME",
            "EMAIL", "ACTIVE", "TIME_ZONE_ID",
            "FIRSTNAME", "LASTNAME", "TIMEZONEID", "USERPROFILE",
        }
    dropped_upper = {name.upper() for name in dropped_columns}
    all_dropped = [
        name for name in dropped_columns
        if name.upper() not in user_standard_cols
    ] + [
        name for name in dropped_from_csv
        if name.upper() not in dropped_upper
        and name.upper() not in user_standard_cols
        and name not in renamed_old_names
    ]
    if all_dropped:
        if mode == "prompt":
            response = input(f"⚠️  Warning: Columns {all_dropped} will be DROPPED from {table_name} (data loss!). Continue? [y/N]: ")
            if response.lower() != "y":
                logger.info("Skipped dropping columns.")
                return

        if mode != "dry-run":
            _remove_fields_from_java(entity_name, [name.lower() for name in all_dropped])

        if mode != "dry-run":
            content = gen_drop_column_changelog(entity_name, all_dropped)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            target_dir = (
                PROIECT_PATH
                / "src"
                / "main"
                / "resources"
                / company_path
                / project_name
                / "liquibase"
                / "changelog"
                / datetime.now().strftime("%Y")
                / datetime.now().strftime("%m")
            )
            ensure_dir(str(target_dir))
            filename = target_dir / f"{timestamp}-alter-{table_name}-dropField.xml"

            logger.info(f"Generating incremental migration for {entity_name}: drop columns {all_dropped}")
            write_file(filename, content)
            logger.info(f"⚠️ Created DROP changelog (data will be lost!): {filename}")

    if messages_need_update and mode != "dry-run" and mode != "quiet" and entity_name != "User":
        relations_list = get_relations_from_csv("relations.csv", entity_name)
        csv_fields = _read_entity_fields(entity_name)
        all_field_names = [f["name"] for f in csv_fields]
        relation_field_names = [rel["field"] for rel in relations_list]
        all_field_names = list(set(all_field_names + relation_field_names))
        update_messages_entity(str(PROIECT_PATH), f"{COMPANY}.{project_name}", entity_name, all_field_names, relations_list)


def migrate_all_entities(mode: str = "prompt") -> None:
    """Run migration for all entities defined in entities.csv."""
    from jmix_cli.entity import get_sorted_entities_by_dependency

    entities = get_sorted_entities_by_dependency()

    if not entities:
        logger.info("[migrate] No entities found in entities.csv")
        return

    logger.info(f"[*] Running incremental migration for {len(entities)} entities...")

    for entity in entities:
        logger.info(f"\n   → Migrating: {entity}")
        migrate_entity(entity, mode)

    logger.info("\n✅ Incremental migration completed!")
