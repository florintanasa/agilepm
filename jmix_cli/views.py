from pathlib import Path
from typing import Any

from jmix_cli.entity import get_entities_from_csv
from jmix_cli.utils import (
    COMPANY,
    PROIECT_PATH,
    append_unique,
    company_path,
    inject_import_if_missing,
    project_name,
    write_file,
)


def gen_list_view_from_csv(
    name: str, fields_list: list[dict[str, Any]], relations_list: list[dict[str, Any]] = []
) -> None:
    lower_name = name.lower()
    xml_columns = ""
    for field in fields_list:
        f_name = field["name"]
        xml_columns += f'                <column property="{f_name}"/>\n'

    xml_fetch_plan_properties = ""
    for rel in relations_list:
        if rel["type"] == "N:1" or rel["type"] == "1:1":
            f_name = rel["field"]
            xml_fetch_plan_properties += (
                f'                <property name="{f_name}" fetchPlan="_base"/>\n'
            )
            xml_columns += f'                <column property="{f_name}"/>\n'

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
    print(f" 🖥️ Successfully generated List View for: {name}")


def gen_detail_view_from_csv(
    name: str, fields_list: list[dict[str, Any]], relations_list: list[dict[str, Any]] = []
) -> None:
    print(f" 🖥️ Starting FlowUI Detail View architecture for entity: '{name}'")
    lower_name = name.lower()

    xml_form_components = ""
    for field in fields_list:
        f_name = field["name"]
        f_type = field["type"].lower()
        if f_type in ["boolean", "bool"]:
            xml_form_components += (
                f'            <checkBox id="{f_name}Field" property="{f_name}"/>\n'
            )
        elif f_type in ["date", "localdate", "datetime", "localdatetime"]:
            xml_form_components += (
                f'            <datePicker id="{f_name}Field" property="{f_name}"/>\n'
            )
        else:
            xml_form_components += (
                f'            <textField id="{f_name}Field" property="{f_name}"/>\n'
            )

    xml_relation_data_containers = ""
    for rel in relations_list:
        if (
            rel["type"] == "N:1"
            or rel["type"] == "1:1"
            or rel["type"] == "COMPOSITION_1:1"
        ):
            f_name = rel["field"]
            tgt_class = rel["target"]
            tgt_lower = tgt_class.lower()
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
            xml_form_components += f'            <entityComboBox id="{f_name}Field" property="{f_name}" itemsContainer="{tgt_lower}sDc">\n'
            xml_form_components += "                <actions>\n"
            xml_form_components += '                    <action id="entityLookupAction" type="entity_lookup"/>\n'
            xml_form_components += '                    <action id="entityOpenAction" type="entity_open"/>\n'
            xml_form_components += '                    <action id="entityClearAction" type="entity_clear"/>\n'
            xml_form_components += "                </actions>\n"
            xml_form_components += "            </entityComboBox>\n"

    xml_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<view xmlns="http://jmix.io/schema/flowui/view"
      title="msg://{lower_name}DetailView.title"
      focusComponent="form">
    <data>
    	<instance id="{lower_name}Dc"
                   class="{COMPANY}.{project_name}.entity.{name}">
            <fetchPlan extends="_base"/>
            <loader id="{lower_name}Dl"/>
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
    write_file(view_dir / f"{lower_name}-detail-view.xml", xml_content)
    write_file(java_dir / f"{name}DetailView.java", java_content)
    print(f" 🖥️ Detail View successfully generated for: {name}")

    _inject_composition_ui_into_parent(name, fields_list, relations_list)


def _inject_composition_ui_into_parent(
    name: str, fields_list: list[dict[str, Any]], relations_list: list[dict[str, Any]]
) -> None:
    for rel in relations_list:
        if rel["type"] != "COMPOSITION_1:N":
            continue
        tgt_class = rel["target"]
        tgt_lower = tgt_class.lower()
        f_name = rel["field"]
        src_class = name
        tgt_xml_path = (
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
        if not tgt_xml_path.exists():
            continue
        xml_tgt_content = tgt_xml_path.read_text(encoding="utf-8")
        if f'id="{f_name}DataGrid"' in xml_tgt_content:
            continue

        print(f" 🖥️ Dynamic injecting @Composition UI in: {tgt_class} Detail View")
        property_container = f'            <collection id="{f_name}Dc" property="{f_name}"/>\n'
        if f'id="{tgt_lower}Dc"' in xml_tgt_content:
            xml_tgt_content = xml_tgt_content.replace(
                "</instance>", f"{property_container}        </instance>"
            )

        child_fields = get_entities_from_csv("entities.csv", src_class)
        xml_composition_columns = ""
        if child_fields:
            for c_field in child_fields:
                xml_composition_columns += f'                <column property="{c_field["name"]}"/>\n'
        else:
            xml_composition_columns = '                <column property="notFound"/>\n'

        composition_grid = (
            f'        <h3 text="msg://{tgt_lower}DetailView.{f_name}"/>\n'
        )
        composition_grid += f'        <hbox id="{f_name}ButtonsPanel" classNames="buttons-panel">\n'
        composition_grid += f'            <button id="{f_name}CreateBtn" action="{f_name}DataGrid.create"/>\n'
        composition_grid += f'            <button id="{f_name}EditBtn" action="{f_name}DataGrid.edit"/>\n'
        composition_grid += f'            <button id="{f_name}RemoveBtn" action="{f_name}DataGrid.remove"/>\n'
        composition_grid += "        </hbox>\n"
        composition_grid += f'        <dataGrid id="{f_name}DataGrid" width="100%" minHeight="15em" dataContainer="{f_name}Dc">\n'
        composition_grid += "            <actions>\n"
        composition_grid += '                <action id="create" type="list_create"/>\n'
        composition_grid += '                <action id="edit" type="list_edit"/>\n'
        composition_grid += '                <action id="remove" type="list_remove"/>\n'
        composition_grid += "            </actions>\n"
        composition_grid += "            <columns>\n"
        composition_grid += f"{xml_composition_columns}"
        composition_grid += "            </columns>\n"
        composition_grid += "        </dataGrid>\n"

        if "</formLayout>" in xml_tgt_content:
            xml_tgt_content = xml_tgt_content.replace(
                "</formLayout>", f"</formLayout>\n{composition_grid}"
            )
        write_file(tgt_xml_path, xml_tgt_content)


def inject_list_ui_into_existing_user(relations_list: list[dict[str, Any]]) -> None:
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
    for rel in relations_list:
        if rel["type"] != "N:1":
            continue
        f_name = rel["field"]
        if (
            f'name="{f_name}"' not in xml_content
            and '<fetchPlan extends="_base">' in xml_content
        ):
            fp_prop = f'                <property name="{f_name}" fetchPlan="_base"/>\n'
            xml_content = xml_content.replace(
                '<fetchPlan extends="_base">',
                f'<fetchPlan extends="_base">\n{fp_prop}',
            )
            modified = True
        if (
            f'property="{f_name}"' not in xml_content
            and "</columns>" in xml_content
        ):
            ui_column = f'    <column property="{f_name}"/>\n'
            xml_content = xml_content.replace(
                "</columns>", f"{ui_column}            </columns>"
            )
            modified = True
    if modified:
        write_file(xml_path, xml_content)
        print("✨ [UI-List] user-list-view.xml successfully updated dynamically!")


def inject_detail_ui_into_existing_user(relations_list: list[dict[str, Any]]) -> None:
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
    accumulated_components = ""
    modified = False
    for rel in relations_list:
        rel_type = rel["type"].strip().upper()
        if rel_type != "N:1":
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
            and f'id="{component_id}"' not in accumulated_components
        ):
            ui_block = f'            <entityComboBox id="{component_id}" property="{f_name}" itemsContainer="{container_id}"/>\n'
            accumulated_components += ui_block
            modified = True
    if modified:
        if accumulated_containers and "</data>" in xml_content:
            xml_content = xml_content.replace(
                "</data>", f"{accumulated_containers}    </data>"
            )
        if accumulated_components and "</formLayout>" in xml_content:
            xml_content = xml_content.replace(
                "</formLayout>", f"{accumulated_components}        </formLayout>"
            )
        write_file(xml_path, xml_content)
        print(
            "✨ [UI-Detail] user-detail-view.xml successfully updated with fields!"
        )
