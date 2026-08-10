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
from datetime import datetime
from pathlib import Path

from jmix_cli.core.files import write_file
from jmix_cli.core.java import inject_import_if_missing
from jmix_cli.core.project import COMPANY, PROIECT_PATH, company_path, project_name


def inject_composition_1n(name: str, rel: dict[str, str]) -> None:
    src_class = name
    tgt_class = rel["target"]
    f_name = rel["field"]

    first_char_lower = tgt_class[0].lower()
    remaining_chars = tgt_class[1:]
    mapped_by_prop = first_char_lower + remaining_chars

    src_file_path = PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{src_class}.java"
    if src_file_path.exists():
        java_src_content = src_file_path.read_text(encoding="utf-8")
        sql_fk_col = f"{mapped_by_prop.upper()}_ID"
        mandatory_val = rel.get("mandatory", False)
        if f"private {tgt_class} {mapped_by_prop};" not in java_src_content:
            not_null_anno = "    @NotNull\n" if mandatory_val else ""
            nullable_attr = ", nullable = false" if mandatory_val else ""
            n1_field = f'    @ManyToOne(fetch = FetchType.LAZY)\n    @JoinColumn(name = "{sql_fk_col}"{nullable_attr})\n{not_null_anno}    private {tgt_class} {mapped_by_prop};\n\n'
            n1_caps = mapped_by_prop[0].upper() + mapped_by_prop[1:]
            n1_methods = f"    public {tgt_class} get{n1_caps}() {{\n        return {mapped_by_prop};\n    }}\n\n"
            n1_methods += f"    public void set{n1_caps}({tgt_class} {mapped_by_prop}) {{\n        this.{mapped_by_prop} = {mapped_by_prop};\n    }}\n\n"
            src_last_brace = java_src_content.rfind("}")
            if src_last_brace != -1:
                java_src_content = (
                    java_src_content[:src_last_brace]
                    + n1_field
                    + n1_methods
                    + java_src_content[src_last_brace:]
                )
                java_src_content = inject_import_if_missing(java_src_content, "jakarta.persistence.ManyToOne")
                java_src_content = inject_import_if_missing(java_src_content, "jakarta.persistence.JoinColumn")
                java_src_content = inject_import_if_missing(java_src_content, "jakarta.persistence.FetchType")
                if mandatory_val:
                    java_src_content = inject_import_if_missing(java_src_content, "jakarta.validation.constraints.NotNull")
                src_file_path.write_text(java_src_content, encoding="utf-8")
        else:
            _update_mandatory_annotations(src_file_path, java_src_content, tgt_class, mapped_by_prop, sql_fk_col, mandatory_val)

    src_table = "USER_" if src_class == "User" else src_class.upper()
    col_name = f"{mapped_by_prop.upper()}_ID"
    try:
        from jmix_cli.migrate import get_existing_columns_from_changelogs
        existing_cols = get_existing_columns_from_changelogs(src_table)
        if col_name not in existing_cols:
            from jmix_cli.liquibase import gen_liquibase_relations_changelog
            synthetic_rel = [{
                "type": "N:1",
                "target": tgt_class,
                "field": mapped_by_prop,
                "mandatory": rel.get("mandatory", False),
                "ownership": "",
            }]
            gen_liquibase_relations_changelog(src_class, synthetic_rel)
    except ImportError:
        pass

    tgt_file_path = PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{tgt_class}.java"
    if not tgt_file_path.exists():
        return
    java_tgt_content = tgt_file_path.read_text(encoding="utf-8")
    if (
        f"private List<{src_class}> {f_name};" in java_tgt_content
        or f"private {src_class} {f_name};" in java_tgt_content
    ):
        return

    new_field = ""
    new_methods = ""
    f_caps = f_name[0].upper() + f_name[1:]
    mapped_by_prop_for_tgt = "user" if tgt_class.lower() == "user" else tgt_class.lower() + tgt_class[1:]

    if rel["type"] == "COMPOSITION_1:N":
        first_char_lower = tgt_class[0].lower()
        remaining_chars = tgt_class[1:]
        mapped_by_prop_for_tgt = first_char_lower + remaining_chars
        new_field = f'    @Composition\n    @OnDelete(DeletePolicy.CASCADE)\n    @OneToMany(mappedBy = "{mapped_by_prop_for_tgt}")\n    private List<{src_class}> {f_name};\n\n'
        new_methods = f"    public List<{src_class}> get{f_caps}() {{\n        return {f_name};\n    }}\n\n"
        new_methods += f"    public void set{f_caps}(List<{src_class}> {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"
        if "import java.util.List;" not in java_tgt_content:
            package_end_idx = java_tgt_content.find(";")
            if package_end_idx != -1:
                java_tgt_content = (
                    java_tgt_content[: package_end_idx + 1]
                    + "\nimport java.util.List;"
                    + java_tgt_content[package_end_idx + 1 :]
                )

    if "import io.jmix.core.metamodel.annotation.Composition;" not in java_tgt_content:
        java_tgt_content = java_tgt_content.replace(
            f"package {COMPANY}.{project_name}.entity;",
            f"package {COMPANY}.{project_name}.entity;\nimport io.jmix.core.metamodel.annotation.Composition;\nimport io.jmix.core.entity.annotation.OnDelete;\nimport io.jmix.core.DeletePolicy;\nimport jakarta.persistence.OneToOne;\nimport jakarta.persistence.JoinColumn;\nimport jakarta.persistence.FetchType;",
        )

    if "    public UUID getId()" in java_tgt_content:
        old_anchor = "    public UUID getId()"
        replacement = "    " + new_field + "    public UUID getId()"
        java_tgt_content = java_tgt_content.replace(old_anchor, replacement)
    elif "    public final UUID getId()" in java_tgt_content:
        old_anchor = "    public final UUID getId()"
        replacement = "    " + new_field + "    public final UUID getId()"
        java_tgt_content = java_tgt_content.replace(old_anchor, replacement)

    last_brace_index = java_tgt_content.rfind("}")
    if last_brace_index != -1:
        java_tgt_content = (
            java_tgt_content[:last_brace_index]
            + "\n"
            + new_methods
            + java_tgt_content[last_brace_index:]
        )
    tgt_file_path.write_text(java_tgt_content, encoding="utf-8")


def _update_mandatory_annotations(
    src_file_path: Path, java_src_content: str, tgt_class: str,
    mapped_by_prop: str, sql_fk_col: str, mandatory_val: bool,
) -> None:
    old_no_notnull = (
        f'    @ManyToOne(fetch = FetchType.LAZY)\n'
        f'    @JoinColumn(name = "{sql_fk_col}")\n'
        f'    private {tgt_class} {mapped_by_prop};'
    )
    new_with_notnull = (
        f'    @ManyToOne(fetch = FetchType.LAZY)\n'
        f'    @JoinColumn(name = "{sql_fk_col}", nullable = false)\n'
        f'    @NotNull\n'
        f'    private {tgt_class} {mapped_by_prop};'
    )
    old_with_notnull = (
        f'    @ManyToOne(fetch = FetchType.LAZY)\n'
        f'    @JoinColumn(name = "{sql_fk_col}", nullable = false)\n'
        f'    @NotNull\n'
        f'    private {tgt_class} {mapped_by_prop};'
    )
    new_no_notnull = (
        f'    @ManyToOne(fetch = FetchType.LAZY)\n'
        f'    @JoinColumn(name = "{sql_fk_col}")\n'
        f'    private {tgt_class} {mapped_by_prop};'
    )

    if mandatory_val and old_no_notnull in java_src_content:
        java_src_content = java_src_content.replace(old_no_notnull, new_with_notnull, 1)
        java_src_content = inject_import_if_missing(java_src_content, "jakarta.validation.constraints.NotNull")
        _generate_nullable_changelog(src_file_path, tgt_class, mapped_by_prop, sql_fk_col, True)
    elif not mandatory_val and old_with_notnull in java_src_content:
        java_src_content = java_src_content.replace(old_with_notnull, new_no_notnull, 1)
        _generate_nullable_changelog(src_file_path, tgt_class, mapped_by_prop, sql_fk_col, False)
        src_file_path.write_text(java_src_content, encoding="utf-8")


def _generate_nullable_changelog(
    src_file_path: Path, tgt_class: str, mapped_by_prop: str,
    sql_fk_col: str, make_not_null: bool,
) -> None:
    src_table = "USER_" if src_file_path.stem == "User" else src_file_path.stem.upper()
    if make_not_null:
        change_tag = "addNotNull"
        change_xml = (
            f'        <addNotNullConstraint tableName="{src_table}" '
            f'columnName="{sql_fk_col}"/>\n'
        )
    else:
        change_tag = "dropNotNull"
        change_xml = (
            f'        <dropNotNullConstraint tableName="{src_table}" '
            f'columnName="{sql_fk_col}"/>\n'
        )
    changeset_id = f"{src_table.lower()}-{sql_fk_col}-{change_tag}-nullable"
    year = datetime.now().strftime("%Y")
    month = datetime.now().strftime("%m")
    fk_dir = PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name / "liquibase" / "changelog" / year / month
    fk_dir.mkdir(parents=True, exist_ok=True)
    for existing in fk_dir.glob(f"*{change_tag}*{src_table.lower()}*.xml"):
        if changeset_id in existing.read_text(encoding="utf-8"):
            return

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    changelog_file = fk_dir / f"{timestamp}-04-{change_tag}-{src_table.lower()}.xml"
    changelog_content = f"""<?xml version="1.0" encoding="UTF-8" ?>
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
                      http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-latest.xsd"
    objectQuotingStrategy="QUOTE_ONLY_RESERVED_WORDS"
>
    <changeSet id="{changeset_id}" author="{project_name}">
{change_xml}    </changeSet>
</databaseChangeLog>
"""
    changelog_file.write_text(changelog_content, encoding="utf-8")
