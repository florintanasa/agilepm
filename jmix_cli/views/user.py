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
from pathlib import Path
from typing import Any

from jmix_cli.core.project import COMPANY, PROIECT_PATH, company_path, project_name
from jmix_cli.core.files import write_file
from jmix_cli.entity import get_entities_from_csv


def inject_list_ui_into_existing_user(relations_list: list[dict[str, Any]], fields_list: list[dict[str, Any]] | None = None) -> None:
    xml_path = (
        PROIECT_PATH
        / "src"
        / "main"
        / "resources"
        / company_path
        / project_name
        / "view"
        / "user"
        / "user-list-view.xml"
    )
    if not xml_path.exists():
        return
    xml_content = xml_path.read_text(encoding="utf-8")
    modified = False
    user_standard_fields = {"username", "firstName", "lastName", "email", "active", "timeZoneId"}
    valid_fields = {f["name"] for f in fields_list} if fields_list else set()
    for match in re.finditer(r'<column property="([^"]+)"/>', xml_content):
        col_name = match.group(1)
        if col_name not in valid_fields and col_name not in user_standard_fields:
            xml_content = xml_content.replace(f'<column property="{col_name}"/>\n', '')
            modified = True
    if fields_list:
        for field in fields_list:
            f_name = field["name"]
            if f'name="{f_name}"' not in xml_content and "</columns>" in xml_content:
                ui_column = f'    <column property="{f_name}"/>\n'
                xml_content = xml_content.replace(
                    "</columns>", f"{ui_column}            </columns>"
                )
                modified = True
    for rel in relations_list:
        rel_type = rel["type"].strip().upper()
        if rel_type not in {"N:1", "1:1", "N:N"}:
            continue
        f_name = rel["field"]
        if (
            f'name="{f_name}"' not in xml_content
            and ('<fetchPlan extends="_base">' in xml_content or '<fetchPlan extends="_base"/>' in xml_content)
        ):
            fp_prop = f'                <property name="{f_name}" fetchPlan="_base"/>'
            if '<fetchPlan extends="_base"/>' in xml_content:
                xml_content = xml_content.replace(
                    '<fetchPlan extends="_base"/>',
                    f'<fetchPlan extends="_base">\n{fp_prop}\n            </fetchPlan>',
                )
            else:
                xml_content = xml_content.replace(
                    '<fetchPlan extends="_base">',
                    f'<fetchPlan extends="_base">\n{fp_prop}',
                )
            modified = True
        if rel_type in {"N:1", "1:1"} and (
            f'property="{f_name}"' not in xml_content
            and "</columns>" in xml_content
        ):
            ui_column = f'                <column property="{f_name}"/>\n'
            closing_idx = xml_content.rfind('</columns>')
            if closing_idx != -1:
                xml_content = xml_content[:closing_idx] + ui_column + xml_content[closing_idx:]
            modified = True
    if modified:
        write_file(xml_path, xml_content)


def inject_detail_ui_into_existing_user(relations_list: list[dict[str, Any]], fields_list: list[dict[str, Any]] | None = None) -> None:
    xml_path = (
        PROIECT_PATH
        / "src"
        / "main"
        / "resources"
        / company_path
        / project_name
        / "view"
        / "user"
        / "user-detail-view.xml"
    )
    if not xml_path.exists():
        return
    xml_content = xml_path.read_text(encoding="utf-8")
    accumulated_containers = ""
    accumulated_form_components = ""
    modified = False
    user_standard_fields = {"username", "firstName", "lastName", "email", "active", "timeZoneId"}
    valid_fields = {f["name"] for f in fields_list} if fields_list else set()
    for match in re.finditer(r'<textField id="([^"]+)Field" property="([^"]+)"(?:\s+datatype="[^"]*")?/>', xml_content):
        component_id = match.group(1)
        prop_name = match.group(2)
        if prop_name not in valid_fields and prop_name not in user_standard_fields:
            xml_content = re.sub(
                rf'<textField id="{component_id}Field" property="{prop_name}"(?:\s+datatype="[^"]*")?/>\n',
                '',
                xml_content,
            )
            modified = True
    if fields_list:
        for field in fields_list:
            f_name = field["name"]
            component_id = f"{f_name}Field"
            if (
                f'id="{component_id}"' not in xml_content
                and f'id="{component_id}"' not in accumulated_form_components
            ):
                dt = _java_type_to_datatype(field.get("type", ""))
                if dt:
                    ui_block = f'            <textField id="{component_id}" property="{f_name}" datatype="{dt}"/>\n'
                else:
                    ui_block = f'            <textField id="{component_id}" property="{f_name}"/>\n'
                accumulated_form_components += ui_block
                modified = True
    for rel in relations_list:
        rel_type = rel["type"].strip().upper()
        if rel_type not in {"N:1", "1:1", "N:N"}:
            continue
        f_name = rel["field"].strip()
        tgt_class = rel["target"].strip()
        tgt_lower = tgt_class.lower()
        container_id = f"{tgt_lower}sDc"
        if (
            f'id="{container_id}"' not in xml_content
            and f'id="{container_id}"' not in accumulated_containers
        ):
            c_block = f'        <collection id="{container_id}" class="{COMPANY}.{project_name}.entity.{tgt_class}">\n'
            c_block += '            <fetchPlan extends="_base"/>\n'
            c_block += f'            <loader id="{tgt_lower}sDl">\n'
            c_block += "                <query>\n"
            c_block += f"                    <![CDATA[select e from {tgt_class} e]]>\n"
            c_block += "                </query>\n"
            c_block += "            </loader>\n"
            c_block += "        </collection>\n"
            accumulated_containers += c_block
            modified = True
        component_id = f"{f_name}Field"
        if (
            f'id="{component_id}"' not in xml_content
            and f'id="{component_id}"' not in accumulated_form_components
        ):
            if rel_type == "N:N":
                ui_block = f'            <multiSelectComboBoxPicker id="{component_id}" property="{f_name}" itemsContainer="{container_id}">\n'
            else:
                ui_block = f'            <entityComboBox id="{component_id}" property="{f_name}" itemsContainer="{container_id}">\n'
            ui_block += "                <actions>\n"
            ui_block += '                    <action id="entityLookupAction" type="entity_lookup"/>\n'
            ui_block += '                    <action id="entityOpenAction" type="entity_open"/>\n'
            ui_block += '                    <action id="entityClearAction" type="entity_clear"/>\n'
            ui_block += "                </actions>\n"
            if rel_type == "N:N":
                ui_block += "            </multiSelectComboBoxPicker>\n"
            else:
                ui_block += "            </entityComboBox>\n"
            accumulated_form_components += ui_block
            modified = True

    fetch_plan_props = ""
    for rel in relations_list:
        rel_type = rel["type"].strip().upper()
        if rel_type not in {"N:1", "1:1", "N:N"}:
            continue
        f_name = rel["field"].strip()
        fetch_plan_props += f"                <property name=\"{f_name}\" fetchPlan=\"_base\"/>\n"
    if fetch_plan_props and 'id="userDc"' in xml_content:
        instance_fp_pattern = r'(<instance id="userDc"[^>]*>\s*)<fetchPlan extends="_base"/>(\s*<loader/>)'
        replacement = r'\1<fetchPlan extends="_base">\n' + fetch_plan_props + r'            </fetchPlan>\n\2'
        if re.search(instance_fp_pattern, xml_content):
            xml_content = re.sub(instance_fp_pattern, replacement, xml_content, count=1)
            modified = True
        else:
            instance_fp_pattern2 = r'(<instance id="userDc"[^>]*>\s*<fetchPlan extends="_base">)(.*?)(</fetchPlan>)(\s*<loader/>)'
            match = re.search(instance_fp_pattern2, xml_content, re.DOTALL)
            if match:
                existing_props = match.group(2)
                new_props = []
                for prop_line in fetch_plan_props.strip().split('\n'):
                    prop_name = prop_line.split('name="')[1].split('"')[0] if 'name="' in prop_line else None
                    if prop_name and f'name="{prop_name}"' not in existing_props:
                        new_props.append(prop_line)
                if new_props:
                    new_fp = match.group(1) + existing_props.rstrip() + '\n' + '\n'.join(new_props) + match.group(3)
                    xml_content = xml_content.replace(match.group(0), new_fp + match.group(4), 1)
                    modified = True
    if modified:
        if accumulated_containers and "</data>" in xml_content:
            xml_content = xml_content.replace(
                "</data>", f"{accumulated_containers}    </data>"
            )
        if accumulated_form_components and "</formLayout>" in xml_content:
            xml_content = xml_content.replace(
                "</formLayout>", f"{accumulated_form_components}        </formLayout>"
            )
        write_file(xml_path, xml_content)


_FIELD_TYPE_TO_DATATYPE = {
    "int": "int",
    "integer": "int",
    "long": "long",
    "double": "double",
    "bigdecimal": "decimal",
    "decimal": "decimal",
    "float": "decimal",
    "short": "int",
    "biginteger": "decimal",
}


def _java_type_to_datatype(f_type: str) -> str | None:
    return _FIELD_TYPE_TO_DATATYPE.get(f_type.lower())
