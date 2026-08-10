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
import re
from typing import Any

from jmix_cli.core.project import COMPANY, PROIECT_PATH, company_path, project_name
from jmix_cli.core.files import write_file
from jmix_cli.entity import get_entities_from_csv


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


def _cleanup_view_xml(xml_content: str) -> str:
    content = xml_content
    content = re.sub(
        r'(<instance[^>]*>\s*<fetchPlan extends="_base">)(.*?)(</fetchPlan>\s*<fetchPlan extends="_base">)(.*?)(</fetchPlan>)',
        r'\1\2\4\5',
        content,
        flags=re.DOTALL,
    )
    first_instance_end = content.find('</instance>')
    data_end = content.find('</data>')
    if first_instance_end != -1 and data_end != -1 and data_end > first_instance_end:
        between = content[first_instance_end:data_end + len('</data>')]
        orphaned_close_pattern = re.compile(
            r'^(.*?)</instance>\n        ((?:<collection[^>]*>\s*<fetchPlan[^>]*/>\s*<loader[^>]*>\s*<query>\s*<!\[CDATA\[.*?\]\]>\s*</query>\s*</loader>\s*</collection>\s*)+)(</instance>\n\s*</data>)',
            re.DOTALL,
        )
        m_check = orphaned_close_pattern.search(between)
        if m_check:
            print(f'DEBUG: Found orphaned instance in view, fixing...')
        def move_orphaned_collections_inside_instance(m: re.Match) -> str:
            return m.group(1) + m.group(2) + "        </instance>\n    </data>"
        fixed_between = orphaned_close_pattern.sub(move_orphaned_collections_inside_instance, between)
        if fixed_between != between:
            content = content[:first_instance_end] + fixed_between + content[data_end + len('</data>'):]
    return content


def gen_detail_view_from_csv(
    name: str, fields_list: list[dict[str, Any]], relations_list: list[dict[str, Any]] = []
) -> None:
    lower_name = name.lower()

    xml_form_components = ""
    for field in fields_list:
        f_name = field["name"]
        f_type = field["type"].lower()
        if f_type in ["boolean", "bool"]:
            xml_form_components += (
                f'            <checkbox id="{f_name}Field" property="{f_name}"/>\n'
            )
        elif f_type in ["date", "localdate", "datetime", "localdatetime"]:
            xml_form_components += (
                f'            <datePicker id="{f_name}Field" property="{f_name}"/>\n'
            )
        else:
            dt = _java_type_to_datatype(f_type)
            if dt:
                xml_form_components += (
                    f'            <textField id="{f_name}Field" property="{f_name}" datatype="{dt}"/>\n'
                )
            else:
                xml_form_components += (
                    f'            <textField id="{f_name}Field" property="{f_name}"/>\n'
                )

    xml_relation_data_containers = ""
    relation_properties = []
    created_targets: set[str] = set()
    for rel in relations_list:
        if (
            rel["type"] == "N:1"
            or rel["type"] == "1:1"
            or rel["type"] == "COMPOSITION_1:1"
        ):
            f_name = rel["field"]
            tgt_class = rel["target"]
            tgt_lower = tgt_class.lower()
            relation_properties.append(f_name)
            xml_relation_data_containers += f'        <collection id="{tgt_lower}sDc" class="{COMPANY}.{project_name}.entity.{tgt_class}">\n'
            xml_relation_data_containers += '            <fetchPlan extends="_base"/>\n'
            xml_relation_data_containers += (
                f'            <loader id="{tgt_lower}sDl">\n'
            )
            xml_relation_data_containers += "                <query>\n"
            xml_relation_data_containers += (
                f"                   <![CDATA[select e from {tgt_class} e]]>\n"
            )
            xml_relation_data_containers += "                </query>\n"
            xml_relation_data_containers += "            </loader>\n"
            xml_relation_data_containers += "        </collection>\n"
            xml_form_components += f'            <entityComboBox id="{f_name}Field" property="{f_name}" itemsContainer="{tgt_lower}sDc" label="msg://{COMPANY}.{project_name}.entity/{name}.{f_name}">\n'
            xml_form_components += "                <actions>\n"
            xml_form_components += '                    <action id="entityLookupAction" type="entity_lookup"/>\n'
            xml_form_components += '                    <action id="entityOpenAction" type="entity_open"/>\n'
            xml_form_components += '                    <action id="entityClearAction" type="entity_clear"/>\n'
            xml_form_components += "                </actions>\n"
            xml_form_components += "            </entityComboBox>\n"
        elif rel["type"] == "N:N":
            f_name = rel["field"]
            tgt_class = rel["target"]
            tgt_lower = tgt_class.lower()
            has_direct_relation = any(
                r["type"] in ("N:1", "1:1") and r["target"] == tgt_class
                for r in relations_list
            )
            if not has_direct_relation and tgt_class not in created_targets:
                relation_properties.append(f_name)
                xml_relation_data_containers += f'        <collection id="{tgt_lower}sDc" class="{COMPANY}.{project_name}.entity.{tgt_class}">\n'
                xml_relation_data_containers += '            <fetchPlan extends="_base"/>\n'
                xml_relation_data_containers += (
                    f'            <loader id="{tgt_lower}sDl">\n'
                )
                xml_relation_data_containers += "                <query>\n"
                xml_relation_data_containers += (
                    f"                   <![CDATA[select e from {tgt_class} e]]>\n"
                )
                xml_relation_data_containers += "                </query>\n"
                xml_relation_data_containers += "            </loader>\n"
                xml_relation_data_containers += "        </collection>\n"
                created_targets.add(tgt_class)
            if not has_direct_relation:
                xml_form_components += f'            <multiSelectComboBoxPicker id="{f_name}Field" property="{f_name}" itemsContainer="{tgt_lower}sDc">\n'
                xml_form_components += "                <actions>\n"
                xml_form_components += '                    <action id="entityLookupAction" type="entity_lookup"/>\n'
                xml_form_components += '                    <action id="entityOpenAction" type="entity_open"/>\n'
                xml_form_components += '                    <action id="entityClearAction" type="entity_clear"/>\n'
                xml_form_components += "                </actions>\n"
                xml_form_components += "            </multiSelectComboBoxPicker>\n"
        elif rel["type"] == "COMPOSITION_1:N":
            parent_field_name = rel["target"][0].lower() + rel["target"][1:]
            parent_class = rel["target"]
            parent_lower = parent_class.lower()
            has_direct_relation = any(
                r["type"] in ("N:1", "1:1") and r["target"] == rel["target"]
                for r in relations_list
            )
            if not has_direct_relation:
                relation_properties.append(parent_field_name)
                xml_relation_data_containers += f'        <collection id="{parent_lower}sDc" class="{COMPANY}.{project_name}.entity.{parent_class}">\n'
                xml_relation_data_containers += '            <fetchPlan extends="_base"/>\n'
                xml_relation_data_containers += (
                    f'            <loader id="{parent_lower}sDl">\n'
                )
                xml_relation_data_containers += "                <query>\n"
                xml_relation_data_containers += (
                    f"                   <![CDATA[select e from {parent_class} e]]>\n"
                )
                xml_relation_data_containers += "                </query>\n"
                xml_relation_data_containers += "            </loader>\n"
                xml_relation_data_containers += "        </collection>\n"
                xml_form_components += f'            <entityComboBox id="{parent_field_name}Field" property="{parent_field_name}" itemsContainer="{parent_lower}sDc" label="msg://{COMPANY}.{project_name}.entity/{name}.{parent_field_name}">\n'
                xml_form_components += "                <actions>\n"
                xml_form_components += '                    <action id="entityLookupAction" type="entity_lookup"/>\n'
                xml_form_components += '                    <action id="entityOpenAction" type="entity_open"/>\n'
                xml_form_components += '                    <action id="entityClearAction" type="entity_clear"/>\n'
                xml_form_components += "                </actions>\n"
                xml_form_components += "            </entityComboBox>\n"

            f_name = rel["field"]
            parent_view_path = (
                PROIECT_PATH
                / "src" / "main" / "resources"
                / company_path / project_name / "view"
                / parent_lower / f"{parent_lower}-detail-view.xml"
            )
            if parent_view_path.exists():
                parent_xml = parent_view_path.read_text(encoding="utf-8")
                grid_id = f"{f_name}DataGrid"
                if f'id="{grid_id}"' not in parent_xml:
                    container_block = f'    <collection id="{f_name}Dc" property="{f_name}"/>\n'
                if f'id="{parent_lower}Dc"' in parent_xml:
                    orphaned_instance = f"\n        </instance>"
                    if orphaned_instance in parent_xml:
                        parent_xml = parent_xml.replace(
                            orphaned_instance, f"{container_block}    </instance>", 1
                        )
                    elif "</instance>" in parent_xml:
                        parent_xml = parent_xml.replace(
                            "</instance>", f"{container_block}    </instance>", 1
                        )

                    child_fields = get_entities_from_csv("entities.csv", name)
                    columns = ""
                    if child_fields:
                        for c_field in child_fields:
                            columns += f'                <column property="{c_field["name"]}"/>\n'
                    else:
                        columns = '                <column property="id"/>\n'

                    composition_grid = (
                        f'        <h3 text="msg://{parent_lower}DetailView.{f_name}"/>\n'
                    )
                    composition_grid += f'        <hbox id="{f_name}ButtonsPanel" classNames="buttons-panel">\n'
                    composition_grid += f'            <button id="{f_name}AddBtn" action="{grid_id}.add"/>\n'
                    composition_grid += f'            <button id="{f_name}ExcludeBtn" action="{grid_id}.exclude"/>\n'
                    composition_grid += "        </hbox>\n"
                    composition_grid += f'        <dataGrid id="{grid_id}" width="100%" minHeight="15em" dataContainer="{f_name}Dc">\n'
                    composition_grid += "            <actions>\n"
                    composition_grid += '                <action id="add" type="list_add"/>\n'
                    composition_grid += '                <action id="exclude" type="list_exclude"/>\n'
                    composition_grid += "            </actions>\n"
                    composition_grid += "            <columns>\n"
                    composition_grid += columns
                    composition_grid += "            </columns>\n"
                    composition_grid += "        </dataGrid>\n"

                    if "</formLayout>" in parent_xml:
                        parent_xml = parent_xml.replace(
                            "</formLayout>", f"</formLayout>\n{composition_grid}"
                        )
                    parent_view_path.write_text(parent_xml, encoding="utf-8")

    inverse_composition_rels = []
    inverse_composition_1n_fields = []
    relations_csv_path = Path("relations.csv")
    if relations_csv_path.exists():
        import csv as _csv
        with relations_csv_path.open(mode="r", encoding="utf-8") as _f:
            _reader = _csv.DictReader(_f)
            for _row in _reader:
                if _row["target_entity"].strip().lower() == name.lower():
                    r_type = _row["relation_type"].strip().upper()
                    if r_type == "COMPOSITION_1:1":
                        src_class = _row["source_entity"].strip()
                        inv_field_name = src_class[0].lower() + src_class[1:]
                        inverse_composition_rels.append({
                            "type": _row["relation_type"].strip(),
                            "target": src_class,
                            "field": inv_field_name,
                            "mandatory": _row["mandatory"].strip().lower() == "true",
                        })
                    elif r_type == "COMPOSITION_1:N":
                        inverse_composition_1n_fields.append(_row["field_name"].strip())

    for rel in inverse_composition_rels:
        f_name = rel["field"]
        tgt_class = rel["target"]
        tgt_lower = tgt_class.lower()
        relation_properties.append(f_name)
        xml_relation_data_containers += f'        <collection id="{tgt_lower}sDc" class="{COMPANY}.{project_name}.entity.{tgt_class}">\n'
        xml_relation_data_containers += '            <fetchPlan extends="_base"/>\n'
        xml_relation_data_containers += (
            f'            <loader id="{tgt_lower}sDl">\n'
        )
        xml_relation_data_containers += "                <query>\n"
        xml_relation_data_containers += (
            f"                   <![CDATA[select e from {tgt_class} e]]>\n"
        )
        xml_relation_data_containers += "                </query>\n"
        xml_relation_data_containers += "            </loader>\n"
        xml_relation_data_containers += "        </collection>\n"
        xml_form_components += f'            <entityComboBox id="{f_name}Field" property="{f_name}" label="msg://{COMPANY}.{project_name}.entity/{name}.{f_name}">\n'
        xml_form_components += "                <actions>\n"
        xml_form_components += '                    <action id="entityLookupAction" type="entity_lookup"/>\n'
        xml_form_components += '                    <action id="entityOpenAction" type="entity_open"/>\n'
        xml_form_components += '                    <action id="entityClearAction" type="entity_clear"/>\n'
        xml_form_components += "                </actions>\n"
        xml_form_components += "            </entityComboBox>\n"

    relation_properties.extend(inverse_composition_1n_fields)

    fetch_plan_props = ""
    if relation_properties:
        fetch_plan_props = "            <fetchPlan extends=\"_base\">\n"
        for prop in relation_properties:
            fetch_plan_props += f"                <property name=\"{prop}\" fetchPlan=\"_base\"/>\n"
        fetch_plan_props += "            </fetchPlan>\n"

    xml_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<view xmlns="http://jmix.io/schema/flowui/view"
      title="msg://{lower_name}DetailView.title"
      focusComponent="form">
    <data>
    	<instance id="{lower_name}Dc"
                    class="{COMPANY}.{project_name}.entity.{name}">
{fetch_plan_props}            <loader id="{lower_name}Dl"/>
        </instance>
{xml_relation_data_containers}    </data>
    <facets>
        <dataLoadCoordinator auto="true"/>
    </facets>
    <actions>
        <action id="saveAction" type="detail_saveClose"/>
        <action id="closeAction" type="detail_close"/>
    </actions>
    <layout classNames="fluid-layout" width="100%">
        <formLayout id="form" dataContainer="{lower_name}Dc">
{xml_form_components}        </formLayout>
        <hbox id="detailActions">
            <button id="saveAndCloseBtn" action="saveAction"/>
            <button id="closeBtn" action="closeAction"/>
        </hbox>
    </layout>
</view>
"""

    java_content = f"""package {COMPANY}.{project_name}.view.{lower_name};

import {COMPANY}.{project_name}.entity.{name};
import {COMPANY}.{project_name}.view.main.MainView;
import com.vaadin.flow.router.Route;
import io.jmix.flowui.view.*;

@Route(value = "{lower_name}s/:id", layout = MainView.class)
@ViewController("{name}.detail")
@ViewDescriptor("{lower_name}-detail-view.xml")
@EditedEntityContainer("{lower_name}Dc")
public class {name}DetailView extends StandardDetailView<{name}> {{
}}
"""

    view_dir = PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name / "view" / lower_name
    java_dir = PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "view" / lower_name
    cleaned_xml = _cleanup_view_xml(xml_content)
    write_file(view_dir / f"{lower_name}-detail-view.xml", cleaned_xml)
    write_file(java_dir / f"{name}DetailView.java", java_content)
