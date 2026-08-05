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
from pathlib import Path
from typing import Any

from jmix_cli.core.project import COMPANY, PROIECT_PATH, company_path, project_name
from jmix_cli.core.files import write_file
from jmix_cli.core.logger import get_logger
from jmix_cli.core.csv import validate_csv_path
from jmix_cli.exceptions import ConfigurationError

logger = get_logger("jmix_cli.security")


def gen_jmix_resource_roles_from_csv() -> None:
    roles_file = Path("roles.csv")
    if not roles_file.exists():
        raise ConfigurationError("roles.csv configuration file not found.")

    validate_csv_path("roles.csv", ["name", "code", "entity_name", "ui_list", "ui_detail", "create", "read", "update", "delete"])

    roles_data: dict[str, dict[str, Any]] = {}
    with roles_file.open(mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r_code = row["code"].strip()
            if r_code not in roles_data:
                roles_data[r_code] = {"name": row["name"].strip(), "code": r_code, "policies": []}
            roles_data[r_code]["policies"].append(row)

    for r_code, r_info in roles_data.items():
        role_name = r_info["name"]
        raw_class_name = "".join([part.capitalize() for part in r_code.split("-")])
        class_name = raw_class_name if raw_class_name.endswith("Role") else raw_class_name + "Role"

        logger.info(f"[*] Compiling Jmix ResourceRole: '{role_name}' -> {class_name}.java")

        java_imports = {
            "import io.jmix.security.model.SecurityScope;",
            "import io.jmix.security.role.annotation.ResourceRole;",
            "import io.jmix.security.role.annotation.EntityPolicy;",
            "import io.jmix.security.model.EntityPolicyAction;",
            "import io.jmix.security.role.annotation.EntityAttributePolicy;",
            "import io.jmix.security.model.EntityAttributePolicyAction;",
            "import io.jmix.securityflowui.role.annotation.ViewPolicy;",
            "import io.jmix.securityflowui.role.annotation.MenuPolicy;",
        }

        java_policies_body = ""
        for policy in r_info["policies"]:
            ent_name = policy["entity_name"].strip()
            java_imports.add(f"import {COMPANY}.{project_name}.entity.{ent_name};")

            view_ids = []
            menu_ids = []
            if policy["ui_list"].strip().lower() == "true":
                view_ids.append(f'"{ent_name}.list"')
                menu_ids.append(f'"{ent_name}.list"')
            if policy["ui_detail"].strip().lower() == "true":
                view_ids.append(f'"{ent_name}.detail"')

            view_policy_annotation = ""
            if view_ids:
                ids_str = ", ".join(view_ids)
                view_policy_annotation = f"    @ViewPolicy(viewIds = {{{ids_str}}})\n"

            menu_policy_annotation = ""
            if menu_ids:
                m_ids_str = ", ".join(menu_ids)
                menu_policy_annotation = f"    @MenuPolicy(menuIds = {{{m_ids_str}}})\n"

            crud_actions = []
            if policy["create"].strip().lower() == "true":
                crud_actions.append("EntityPolicyAction.CREATE")
            if policy["read"].strip().lower() == "true":
                crud_actions.append("EntityPolicyAction.READ")
            if policy["update"].strip().lower() == "true":
                crud_actions.append("EntityPolicyAction.UPDATE")
            if policy["delete"].strip().lower() == "true":
                crud_actions.append("EntityPolicyAction.DELETE")

            entity_policy_annotation = ""
            if crud_actions:
                actions_str = ", ".join(crud_actions)
                entity_policy_annotation = f"    @EntityPolicy(entityClass = {ent_name}.class, actions = {{{actions_str}}})\n"

            attr_action = "EntityAttributePolicyAction.VIEW"
            if "EntityPolicyAction.CREATE" in crud_actions or "EntityPolicyAction.UPDATE" in crud_actions:
                attr_action = "EntityAttributePolicyAction.MODIFY"

            attribute_policy_annotation = f'    @EntityAttributePolicy(entityClass = {ent_name}.class, attributes = "*", action = {attr_action})\n'

            method_name = ent_name[0].lower() + ent_name[1:] + "Policies"
            java_policies_body += f"{view_policy_annotation}{menu_policy_annotation}{entity_policy_annotation}{attribute_policy_annotation}    void {method_name}();\n\n"

        imports_block = "\n".join(sorted(list(java_imports)))
        java_content = f"""package {COMPANY}.{project_name}.security;

{imports_block}

@ResourceRole(name = "{role_name}", code = "{r_code}", scope = SecurityScope.UI)
public interface {class_name} {{

{java_policies_body}}}
"""

        target_dir = PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "security"
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"{class_name}.java"
        write_file(file_path, java_content)
