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

from pathlib import Path
from typing import Any

from jmix_cli.core.java import inject_import_if_missing
from jmix_cli.core.project import COMPANY, PROIECT_PATH, company_path, project_name
from jmix_cli.core.logger import get_logger

logger = get_logger("jmix_cli.user")


def _ensure_import(content: str, import_class: str) -> str:
    full_import = f"import {import_class};"
    if full_import in content:
        return content
    return content.replace(
        f"package {COMPANY}.{project_name}.entity;",
        f"package {COMPANY}.{project_name}.entity;\n{full_import}",
    )


def _inject_n1(content: str, rel: dict[str, Any]) -> str:
    f_name = rel["field"]
    tgt_class = rel["target"]
    if f"private {tgt_class} {f_name};" in content:
        return content
    sql_col = f"{f_name.upper()}_ID"
    validation_anno = ""
    if rel["mandatory"]:
        validation_anno = "    @NotNull\n"
        content = _ensure_import(content, "jakarta.validation.constraints.NotNull")
    join_col = f'@JoinColumn(name = "{sql_col}", nullable = false)' if rel["mandatory"] else f'@JoinColumn(name = "{sql_col}")'
    field = f'    {join_col}\n{validation_anno}    @ManyToOne(fetch = FetchType.LAZY)\n    private {tgt_class} {f_name};\n\n'
    caps = f_name[0].upper() + f_name[1:] if len(f_name) > 1 else f_name.upper()
    methods = f"    public {tgt_class} get{caps}() {{\n        return {f_name};\n    }}\n\n"
    methods += f"    public void set{caps}({tgt_class} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"
    last_brace = content.rfind("}")
    if last_brace == -1:
        return content
    return content[:last_brace] + field + methods + content[last_brace:]


def _inject_11(content: str, rel: dict[str, Any]) -> str:
    f_name = rel["field"]
    tgt_class = rel["target"]
    if f"private {tgt_class} {f_name};" in content:
        return content
    sql_col = f"{f_name.upper()}_ID"
    validation_anno = ""
    if rel["mandatory"]:
        validation_anno = "    @NotNull\n"
        content = _ensure_import(content, "jakarta.validation.constraints.NotNull")
    join_col = f'@JoinColumn(name = "{sql_col}", nullable = false)' if rel["mandatory"] else f'@JoinColumn(name = "{sql_col}")'
    field = f'    {join_col}\n{validation_anno}    @OneToOne(fetch = FetchType.LAZY)\n    private {tgt_class} {f_name};\n\n'
    caps = f_name[0].upper() + f_name[1:] if len(f_name) > 1 else f_name.upper()
    methods = f"    public {tgt_class} get{caps}() {{\n        return {f_name};\n    }}\n\n"
    methods += f"    public void set{caps}({tgt_class} {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"
    content = _ensure_import(content, "jakarta.persistence.OneToOne")
    content = _ensure_import(content, "jakarta.persistence.JoinColumn")
    content = _ensure_import(content, "jakarta.persistence.FetchType")
    last_brace = content.rfind("}")
    if last_brace == -1:
        return content
    return content[:last_brace] + field + methods + content[last_brace:]


def _inject_nn(content: str, rel: dict[str, Any]) -> str:
    f_name = rel["field"]
    tgt_class = rel["target"]
    if f"private List<{tgt_class}> {f_name};" in content or f"private Collection<{tgt_class}> {f_name};" in content:
        return content
    ownership = rel.get("ownership", "owning")
    join_table = f"USER_{tgt_class.upper()}_LINK"
    src_fk = "USER_ID"
    tgt_fk = f"{tgt_class.upper()}_ID"
    field = "    @ManyToMany\n"
    field += f'    @JoinTable(name = "{join_table}",\n'
    field += f'            joinColumns = @JoinColumn(name = "{src_fk}"),\n'
    field += f'            inverseJoinColumns = @JoinColumn(name = "{tgt_fk}"))\n'
    field += f"    private List<{tgt_class}> {f_name};\n\n"
    caps = f_name[0].upper() + f_name[1:] if len(f_name) > 1 else f_name.upper()
    methods = f"    public List<{tgt_class}> get{caps}() {{\n        return {f_name};\n    }}\n\n"
    methods += f"    public void set{caps}(List<{tgt_class}> {f_name}) {{\n        this.{f_name} = {f_name};\n    }}\n\n"
    content = _ensure_import(content, "jakarta.persistence.ManyToMany")
    content = _ensure_import(content, "jakarta.persistence.JoinTable")
    content = _ensure_import(content, "jakarta.persistence.JoinColumn")
    content = _ensure_import(content, "java.util.List")
    last_brace = content.rfind("}")
    if last_brace == -1:
        return content
    return content[:last_brace] + field + methods + content[last_brace:]


def _inject_inverse_for_relation(source_name: str, rel: dict[str, Any]) -> None:
    tgt_class = rel["target"]
    f_name = rel["field"]
    r_type = rel["type"].upper()
    if r_type not in {"1:1", "N:N"}:
        return
    tgt_file_path = (
        PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / f"{tgt_class}.java"
    )
    if not tgt_file_path.exists():
        return
    java_tgt_content = tgt_file_path.read_text(encoding="utf-8")
    if r_type == "1:1":
        inv_field_name = "user"
        if f"private User {inv_field_name};" in java_tgt_content:
            return
        logger.info(f"   -> Injecting inverse 1:1 in {tgt_class}")
        inv_field = f'    @OneToOne(fetch = FetchType.LAZY, mappedBy = "{f_name}")\n    private User {inv_field_name};\n\n'
        inv_caps = inv_field_name[0].upper() + inv_field_name[1:]
        inv_methods = f"    public User get{inv_caps}() {{\n        return {inv_field_name};\n    }}\n\n"
        inv_methods += f"    public void set{inv_caps}(User {inv_field_name}) {{\n        this.{inv_field_name} = {inv_field_name};\n    }}\n\n"
        java_tgt_content = _ensure_import(java_tgt_content, "jakarta.persistence.OneToOne")
        java_tgt_content = _ensure_import(java_tgt_content, "jakarta.persistence.FetchType")
        last_brace = java_tgt_content.rfind("}")
        if last_brace == -1:
            return
        java_tgt_content = java_tgt_content[:last_brace] + inv_field + inv_methods + java_tgt_content[last_brace:]
        tgt_file_path.write_text(java_tgt_content, encoding="utf-8")
    elif r_type == "N:N":
        ownership = rel.get("ownership", "owning")
        inv_field_name = source_name.lower() + "s" if not source_name.endswith("s") else source_name.lower()
        check = f"private List<{source_name}> {inv_field_name};"
        if check in java_tgt_content:
            return
        logger.info(f"   -> Injecting inverse N:N in {tgt_class}")
        if ownership in ("owning", "single-owning"):
            inv_field = f'    @ManyToMany(mappedBy = "{f_name}")\n    private List<{source_name}> {inv_field_name};\n\n'
        elif ownership == "both-owning":
            join_table = f"{source_name.upper()}_{tgt_class.upper()}_LINK"
            src_fk = f"{tgt_class.upper()}_ID"
            tgt_fk = f"{source_name.upper()}_ID"
            inv_field = f'    @ManyToMany\n'
            inv_field += f'    @JoinTable(name = "{join_table}",\n'
            inv_field += f'            joinColumns = @JoinColumn(name = "{src_fk}"),\n'
            inv_field += f'            inverseJoinColumns = @JoinColumn(name = "{tgt_fk}"))\n'
            inv_field += f'    private List<{source_name}> {inv_field_name};\n\n'
        else:
            join_table = f"USER_{tgt_class.upper()}_LINK"
            inv_field = f'    @ManyToMany\n'
            inv_field += f'    @JoinTable(name = "{join_table}",\n'
            inv_field += f'            joinColumns = @JoinColumn(name = "{tgt_class.upper()}_ID"),\n'
            inv_field += f'            inverseJoinColumns = @JoinColumn(name = "USER_ID"))\n'
            inv_field += f'    private List<{source_name}> {inv_field_name};\n\n'
        inv_caps = inv_field_name[0].upper() + inv_field_name[1:]
        inv_methods = f"    public List<{source_name}> get{inv_caps}() {{\n        return {inv_field_name};\n    }}\n\n"
        inv_methods += f"    public void set{inv_caps}(List<{source_name}> {inv_field_name}) {{\n        this.{inv_field_name} = {inv_field_name};\n    }}\n\n"
        java_tgt_content = _ensure_import(java_tgt_content, "jakarta.persistence.ManyToMany")
        if ownership != "owning":
            java_tgt_content = _ensure_import(java_tgt_content, "jakarta.persistence.JoinTable")
            java_tgt_content = _ensure_import(java_tgt_content, "jakarta.persistence.JoinColumn")
        java_tgt_content = _ensure_import(java_tgt_content, "java.util.List")
        last_brace = java_tgt_content.rfind("}")
        if last_brace == -1:
            return
        java_tgt_content = java_tgt_content[:last_brace] + inv_field + inv_methods + java_tgt_content[last_brace:]
        tgt_file_path.write_text(java_tgt_content, encoding="utf-8")


def inject_relations_into_existing_user(source_name: str, relations_list: list[dict[str, Any]]) -> None:
    user_java_path = (
        PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "entity" / "User.java"
    )
    if not user_java_path.exists():
        logger.debug("[DEBUG] User.java not found")
        return
    content = user_java_path.read_text(encoding="utf-8")
    modified = False
    for rel in relations_list:
        r_type = rel["type"].upper()
        if r_type not in {"N:1", "1:1", "N:N"}:
            continue
        f_name = rel["field"]
        tgt_class = rel["target"]
        already_present = f"private {tgt_class} {f_name};" in content or f"private List<{tgt_class}> {f_name};" in content
        if not already_present:
            logger.info(f"   -> Injecting relation {r_type} '{f_name}' in User.java")
        if r_type == "N:1":
            content = _inject_n1(content, rel)
        elif r_type == "1:1":
            content = _inject_11(content, rel)
        elif r_type == "N:N":
            content = _inject_nn(content, rel)
        _inject_inverse_for_relation(source_name, rel)
        modified = True
    if modified:
        user_java_path.write_text(content, encoding="utf-8")
        logger.info("✨ [Java] User.java has been updated with the new relationships!")
