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

import logging
from datetime import datetime
from pathlib import Path

from jmix_cli.core.files import write_file
from jmix_cli.core.java import inject_import_if_missing
from jmix_cli.core.project import COMPANY, PROIECT_PATH, company_path, project_name

logger = logging.getLogger(__name__)


def inject_composition_11(name: str, rel: dict[str, str]) -> None:
    src_class = name
    tgt_class = rel["target"]
    f_name = rel["field"]

    tgt_file_path = PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{tgt_class}.java"
    if not tgt_file_path.exists():
        return
    java_tgt_content = tgt_file_path.read_text(encoding="utf-8")
    if (
        f"private List<{src_class}> {f_name};" in java_tgt_content
        or f"private {src_class} {f_name};" in java_tgt_content
    ):
        return

    logger.info(f" 🔗 Injection of @Composition ({rel['type']}) into the class: {tgt_class}")
    new_field = ""
    new_methods = ""
    f_caps = f_name[0].upper() + f_name[1:]
    mapped_by_prop = "user" if tgt_class.lower() == "user" else tgt_class.lower() + tgt_class[1:]

    sql_fk_col = f"{f_name.upper()}_ID"
    new_field = f'@Composition\n    @JoinColumn(name = "{sql_fk_col}")\n    @OneToOne(fetch = FetchType.LAZY)\n    private {src_class} {f_name};\n\n'
    new_methods = f"    public {src_class} get{f_caps}() {{\n        return {f_name};\n    }}\n\n    public void set{f_caps}({src_class} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"

    src_file_path = PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{src_class}.java"
    if src_file_path.exists():
        java_src_content = src_file_path.read_text(encoding="utf-8")
        inv_field_name = name[0].lower() + name[1:]
        if f"private {name} {inv_field_name};" not in java_src_content:
            inv_field = f'    @OneToOne(fetch = FetchType.LAZY, mappedBy = "{f_name}")\n    private {name} {inv_field_name};\n\n'
            inv_caps = inv_field_name[0].upper() + inv_field_name[1:]
            inv_methods = f"    public {name} get{inv_caps}() {{\n        return {inv_field_name};\n    }}\n\n"
            inv_methods += f"    public void set{inv_caps}({name} {inv_field_name}) {{\n        this.{inv_field_name} = {inv_field_name};\n    }}\n\n"
            src_last_brace = java_src_content.rfind("}")
            if src_last_brace != -1:
                java_src_content = (
                    java_src_content[:src_last_brace]
                    + inv_field
                    + inv_methods
                    + java_src_content[src_last_brace:]
                )
                if "import jakarta.persistence.OneToOne;" not in java_src_content:
                    java_src_content = java_src_content.replace(
                        f"package {COMPANY}.{project_name}.entity;",
                        f"package {COMPANY}.{project_name}.entity;\nimport jakarta.persistence.OneToOne;\nimport jakarta.persistence.FetchType;",
                    )
                src_file_path.write_text(java_src_content, encoding="utf-8")

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

    stable_fk_id = f"{src_class.lower()}-add-fk-{f_name}"
    fk_changelog = f"""<?xml version="1.0" encoding="UTF-8" ?>
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
                      http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-latest.xsd"
    objectQuotingStrategy="QUOTE_ONLY_RESERVED_WORDS"
>
    <changeSet id="{stable_fk_id}" author="{project_name}">
        <addForeignKeyConstraint baseTableName="{src_class.upper()}"
                                  baseColumnNames="{f_name.upper()}_ID"
                                  constraintName="FK_{src_class.upper()}_ON_{f_name}"
                                  referencedTableName="{tgt_class.upper()}"
                                  referencedColumnNames="ID"/>
    </changeSet>
</databaseChangeLog>
"""
    current_year = datetime.now().strftime("%Y")
    current_month = datetime.now().strftime("%m")
    fk_dir = PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name / "liquibase" / "changelog" / current_year / current_month
    fk_dir.mkdir(parents=True, exist_ok=True)
    existing_fk = list(fk_dir.glob(f"*-03-fk-{src_class.lower()}.xml"))
    if not existing_fk:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        fk_file = fk_dir / f"{timestamp}-03-fk-{src_class.lower()}.xml"
        fk_file.write_text(fk_changelog, encoding="utf-8")
