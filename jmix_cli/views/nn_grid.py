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

from jmix_cli.core.project import COMPANY, PROIECT_PATH, company_path, project_name
from jmix_cli.core.files import write_file
from jmix_cli.views.user import _java_type_to_datatype
from jmix_cli.entity import get_entities_from_csv


def _infer_inverse_n_n_field(target_class: str, source_class: str) -> str | None:
    entity_path = (
        PROIECT_PATH
        / "src"
        / "main"
        / "java"
        / company_path
        / project_name
        / "entity"
        / f"{target_class}.java"
    )

    if not entity_path.exists():
        return None

    entity_content = entity_path.read_text(encoding="utf-8")

    pattern = rf'private\s+List<{source_class}>\s+(\w+)\s*;\s*\n\s*@ManyToMany\(mappedBy\s*=\s*"[^"]+"\s*\)'
    match = re.search(pattern, entity_content)
    if match:
        return match.group(1)

    pattern2 = rf'private\s+List<{source_class}>\s+(\w+)\s*.\s*@ManyToMany.*mappedBy.*"{source_class.lower()}s?"'
    match2 = re.search(pattern2, entity_content, re.DOTALL)
    if match2:
        return match2.group(1)

    if source_class.lower() == "team":
        return "teams"
    if source_class.lower() == "user":
        return "users"

    return None


def _get_property_columns(entity_name: str) -> list[str]:
    if entity_name.lower() == "user":
        return ["username"]

    entities_path = Path("entities.csv")
    if not entities_path.exists():
        return ["id"]

    columns = []
    fields_list = get_entities_from_csv("entities.csv", entity_name)
    for field in fields_list:
        f_type = field.get("type", "").lower()
        if f_type in ["string", "text"]:
            columns.append(field.get("name", ""))
    return columns if columns else ["id"]


def inject_nn_grid_into_inverse_entity(relations_list: list[dict[str, str]]) -> None:
    for rel in relations_list:
        if rel["type"].strip().upper() != "N:N":
            continue
        source_name = rel.get("source_entity") or ""
        if not source_name:
            continue
        f_name = rel["field"].strip()
        tgt_class = rel["target"].strip()
        tgt_lower = tgt_class.lower()
        ownership = rel.get("ownership", "owning")

        if ownership in ("inverse", "single-owning"):
            continue

        inv_field_name = _infer_inverse_n_n_field(tgt_class, source_name)
        if not inv_field_name:
            continue

        xml_path = (
            PROIECT_PATH
            / "src"
            / "main"
            / "resources"
            / company_path
            / project_name
            / "view"
            / tgt_lower
            / f"{tgt_lower}-detail-view.xml"
        )
        if not xml_path.exists():
            continue
        xml_content = xml_path.read_text(encoding="utf-8")
        grid_id = f"{inv_field_name}DataGrid"
        if f'id="{grid_id}"' in xml_content:
            continue

        column_props = _get_property_columns(source_name)

        container_id = f"{inv_field_name}Dc"
        container_block = f'            <collection id="{container_id}" property="{inv_field_name}"/>\n'

        if ownership == "both-owning":
            container_block_start = "        <vbox>\n"
            container_block_start += f'            <h3 text="msg://{COMPANY}.{project_name}.view.{source_name.lower()}/{source_name.lower()}ListView.title"/>\n'
            buttons_block = '        <hbox id="buttonsPanel" classNames="buttons-panel">\n'
            buttons_block += f'            <button action="{grid_id}.add"/>\n'
            buttons_block += f'            <button action="{grid_id}.exclude"/>\n'
            buttons_block += "        </hbox>\n"
            grid_block = f'            <dataGrid id="{grid_id}" dataContainer="{container_id}"\n                      width="100%" maxHeight="15rem">\n'
            grid_block += "                <actions>\n"
            grid_block += '                    <action id="add" type="list_add"/>\n'
            grid_block += '                    <action id="exclude" type="list_exclude"/>\n'
            grid_block += "                </actions>\n"
            grid_block += "                <columns>\n"
            for col in column_props:
                grid_block += f'                    <column property="{col}"/>\n'
            grid_block += "                </columns>\n"
            grid_block += "            </dataGrid>\n"
            container_block_finish = "        </vbox>\n"
        elif ownership == "owning":
            container_block_start = '        <vbox>\n'
            container_block_start += f'            <h3 text="msg://{COMPANY}.{project_name}.view.{source_name.lower()}/{source_name.lower()}ListView.title"/>\n'
            buttons_block = ""
            grid_block = f'            <dataGrid id="{grid_id}" dataContainer="{container_id}" selectionMode="MULTI">\n'
            grid_block += "                <columns>\n"
            for col in column_props:
                grid_block += f'                    <column property="{col}"/>\n'
            grid_block += "                </columns>\n"
            grid_block += "            </dataGrid>\n"
            container_block_finish = "        </vbox>\n"
        else:
            continue

        if f'id="{tgt_lower}Dc"' in xml_content and "</instance>" in xml_content:
            fetch_plan_property = f'                <property name="{inv_field_name}" fetchPlan="_base"/>\n'
            if '<fetchPlan extends="_base">' in xml_content:
                existing_fp_end = xml_content.find('</fetchPlan>')
                if existing_fp_end != -1:
                    insert_pos = xml_content.rfind('\n', 0, existing_fp_end)
                    xml_content = xml_content[:insert_pos] + '\n' + fetch_plan_property + xml_content[insert_pos + 1:]
                if '<collection id="' + container_id + '"' not in xml_content:
                    fp_end_pos = xml_content.find('</fetchPlan>')
                    if fp_end_pos != -1:
                        after_fp = xml_content.find('\n', fp_end_pos)
                        if after_fp != -1:
                            xml_content = xml_content[:after_fp + 1] + container_block + xml_content[after_fp + 1:]
            else:
                fetch_plan_block = '            <fetchPlan extends="_base">\n' + fetch_plan_property + '            </fetchPlan>\n'
                xml_content = xml_content.replace(
                    f'<loader id="{tgt_lower}Dl"/>',
                    f'{fetch_plan_block}            <loader id="{tgt_lower}Dl"/>\n{container_block}'
                )
            xml_content = xml_content.replace('</instance>\n        </data>', f'        </instance>\n    </data>')
        if "</formLayout>" in xml_content:
            replacement = f"</formLayout>\n{container_block_start}{buttons_block}{grid_block}{container_block_finish}"
            xml_content = xml_content.replace("</formLayout>", replacement)
        write_file(xml_path, xml_content)


def inject_nn_datagrid_into_source_entity(relations_list: list[dict[str, str]]) -> None:
    for rel in relations_list:
        if rel["type"].strip().upper() != "N:N":
            continue
        ownership = rel.get("ownership", "owning")
        if ownership != "both-owning":
            continue

        source_name = rel.get("source_entity") or ""
        if not source_name:
            continue
        f_name = rel["field"].strip()
        tgt_class = rel["target"].strip()

        source_lower = source_name.lower()

        xml_path = (
            PROIECT_PATH
            / "src"
            / "main"
            / "resources"
            / company_path
            / project_name
            / "view"
            / source_lower
            / f"{source_lower}-detail-view.xml"
        )
        if not xml_path.exists():
            continue

        xml_content = xml_path.read_text(encoding="utf-8")

        grid_id = f"{f_name}DataGrid"
        if f'id="{grid_id}"' in xml_content:
            continue

        picker_id = f"{f_name}Field"
        if f'id="{picker_id}"' in xml_content:
            picker_pattern = f'<multiSelectComboBoxPicker id="{picker_id}"[^>]*>.*?</multiSelectComboBoxPicker>'
            xml_content = re.sub(picker_pattern, '', xml_content, flags=re.DOTALL)

        old_inside1 = f'<loader id="{source_lower}Dl"/>\n        </instance>'
        old_inside2 = '<loader/>\n        </instance>'
        new_inside = f'<loader/>\n            <collection id="{f_name}Dc" property="{f_name}"/>\n        </instance>'
        if old_inside1 in xml_content and f'class="{COMPANY}.{project_name}.entity.{tgt_class}"' in xml_content:
            xml_content = xml_content.replace(old_inside1, new_inside)
            old_outside = f'\n        <collection id="{f_name}Dc" class="{COMPANY}.{project_name}.entity.{tgt_class}">.*?</collection>'
            xml_content = re.sub(old_outside, '', xml_content, flags=re.DOTALL)
        elif old_inside2 in xml_content and f'class="{COMPANY}.{project_name}.entity.{tgt_class}"' in xml_content:
            xml_content = xml_content.replace(old_inside2, new_inside)
            old_outside = f'<collection id="{tgt_class[0].lower() + tgt_class[1:]}sDc" class="{COMPANY}.{project_name}.entity.{tgt_class}">.*?</collection>'
            xml_content = re.sub(old_outside, '', xml_content, flags=re.DOTALL)

        column_props = _get_property_columns(tgt_class)

        container_block_start = '        <vbox>\n'
        container_block_start += f'            <h3 text="msg://{COMPANY}.{project_name}.view.{tgt_class.lower()}/{tgt_class.lower()}ListView.title"/>\n'
        buttons_block = '        <hbox id="buttonsPanel" classNames="buttons-panel">\n'
        buttons_block += f'            <button action="{grid_id}.add"/>\n'
        buttons_block += f'            <button action="{grid_id}.exclude"/>\n'
        buttons_block += "        </hbox>\n"
        grid_block = f'            <dataGrid id="{grid_id}" dataContainer="{f_name}Dc"\n                      width="100%" maxHeight="15rem">\n'
        grid_block += "                <actions>\n"
        grid_block += '                    <action id="add" type="list_add"/>\n'
        grid_block += '                    <action id="exclude" type="list_exclude"/>\n'
        grid_block += "                </actions>\n"
        grid_block += "                <columns>\n"
        for col in column_props:
            grid_block += f'                    <column property="{col}"/>\n'
        grid_block += "                </columns>\n"
        grid_block += "            </dataGrid>\n"
        container_block_finish = "        </vbox>\n"

        if "</formLayout>" in xml_content:
            replacement = f"</formLayout>\n{container_block_start}{buttons_block}{grid_block}{container_block_finish}"
            xml_content = xml_content.replace("</formLayout>", replacement)
        write_file(xml_path, xml_content)
