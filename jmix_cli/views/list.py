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

from jmix_cli.core.project import COMPANY, PROIECT_PATH, company_path, project_name
from jmix_cli.core.files import write_file


def gen_list_view_from_csv(
    name: str, fields_list: list[dict[str, Any]], relations_list: list[dict[str, Any]] = []
) -> None:
    lower_name = name.lower()
    xml_columns = ""
    for field in fields_list:
        f_name = field["name"]
        xml_columns += f'                <column property="{f_name}"/>\n'

    xml_fetch_plan_properties = ""
    created_targets: set[str] = set()
    for rel in relations_list:
        if rel["type"] == "N:1" or rel["type"] == "1:1" or rel["type"] == "COMPOSITION_1:1" or rel["type"] == "COMPOSITION_1:N":
            if rel["type"] == "COMPOSITION_1:N":
                has_direct_relation = any(
                    r["type"] in ("N:1", "1:1") and r["target"] == rel["target"]
                    for r in relations_list
                )
                if has_direct_relation:
                    continue
                f_name = rel["target"][0].lower() + rel["target"][1:]
            else:
                f_name = rel["field"]
            if rel["target"] in created_targets:
                continue
            created_targets.add(rel["target"])
            xml_fetch_plan_properties += (
                f'                <property name="{f_name}" fetchPlan="_base"/>\n'
            )
            xml_columns += f'                <column property="{f_name}"/>\n'
        elif rel["type"] == "N:N":
            f_name = rel["field"]
            xml_fetch_plan_properties += (
                f'                <property name="{f_name}" fetchPlan="_base"/>\n'
            )

    xml_fetch_plan_block = ""
    if xml_fetch_plan_properties:
        xml_fetch_plan_block = f"""            <fetchPlan extends="_base">
{xml_fetch_plan_properties}            </fetchPlan>"""
    else:
        xml_fetch_plan_block = '            <fetchPlan extends="_base"/>'

    xml_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<view xmlns="http://jmix.io/schema/flowui/view"
	  xmlns:c="http://jmix.io/schema/flowui/jpql-condition"
        title="msg://{lower_name}ListView.title"
        focusComponent="{lower_name}sDataGrid">
    <data readOnly="true">
        <collection id="{lower_name}sDc"
         			class="{COMPANY}.{project_name}.entity.{name}">
{xml_fetch_plan_block}
            <loader id="{lower_name}sDl" readOnly="true">
                <query>
                	<![CDATA[select e from {name} e]]>
                </query>
            </loader>
        </collection>
    </data>
    <facets>
        <dataLoadCoordinator auto="true"/>
        <urlQueryParameters>
            <genericFilter component="genericFilter"/>
            <pagination component="pagination"/>
        </urlQueryParameters>
    </facets>
    <actions>
        <action id="selectAction" type="lookup_select"/>
        <action id="discardAction" type="lookup_discard"/>
    </actions>
    <layout>
    	<genericFilter id="genericFilter"
                       dataLoader="{lower_name}sDl">
                   <properties include=".*"/>
        </genericFilter>
        <hbox id="buttonsPanel" classNames="buttons-panel">
        	<startSlot>
            	<button id="createBtn" action="{lower_name}sDataGrid.createAction"/>
             	<button id="editBtn" action="{lower_name}sDataGrid.editAction"/>
               	<button id="removeBtn" action="{lower_name}sDataGrid.removeAction"/>
            </startSlot>
            <endSlot>
                <simplePagination id="pagination" dataLoader="{lower_name}sDl"/>
                <gridColumnVisibility dataGrid="{lower_name}sDataGrid" icon="COG" themeNames="icon"/>
            </endSlot>
        </hbox>
        <dataGrid id="{lower_name}sDataGrid"
         		  width="100%" minHeight="20em"
             		  dataContainer="{lower_name}sDc"
                 	  columnReorderingAllowed="true"
                   multiSortOnShiftClickOnly="true">
            <actions>
                <action id="createAction" type="list_create"/>
                <action id="editAction" type="list_edit"/>
                <action id="removeAction" type="list_remove"/>
            </actions>
            <columns resizable="true">
{xml_columns}            </columns>
        </dataGrid>
        <hbox id="lookupActions" visible="false">
            <button id="selectButton" action="selectAction"/>
            <button id="discardButton" action="discardAction"/>
        </hbox>
    </layout>
</view>
"""

    java_content = f"""package {COMPANY}.{project_name}.view.{lower_name};

import {COMPANY}.{project_name}.entity.{name};
import {COMPANY}.{project_name}.view.main.MainView;
import com.vaadin.flow.router.Route;
import io.jmix.flowui.view.*;

@Route(value = "{lower_name}s", layout = MainView.class)
@ViewController("{name}.list")
@ViewDescriptor("{lower_name}-list-view.xml")
@LookupComponent("{lower_name}sDataGrid")
@DialogMode(width = "64em", height = "48em")
public class {name}ListView extends StandardListView<{name}> {{
}}
"""

    view_dir = PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name / "view" / lower_name
    java_dir = PROIECT_PATH / "src" / "main" / "java" / company_path / project_name / "view" / lower_name
    write_file(view_dir / f"{lower_name}-list-view.xml", xml_content)
    write_file(java_dir / f"{name}ListView.java", java_content)
