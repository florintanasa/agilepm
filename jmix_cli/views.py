from pathlib import Path
from typing import Any
import csv

from jmix_cli.entity import get_entities_from_csv
from jmix_cli.utils import (
    COMPANY,
    PROIECT_PATH,
    append_unique,
    company_path,
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
        elif rel["type"] == "N:N":
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
            xml_form_components += f'            <multiSelectComboBoxPicker id="{f_name}Field" property="{f_name}" itemsContainer="{tgt_lower}sDc">\n'
            xml_form_components += "                <actions>\n"
            xml_form_components += '                    <action id="entityLookupAction" type="entity_lookup"/>\n'
            xml_form_components += '                    <action id="entityOpenAction" type="entity_open"/>\n'
            xml_form_components += '                    <action id="entityClearAction" type="entity_clear"/>\n'
            xml_form_components += "                </actions>\n"
            xml_form_components += "            </multiSelectComboBoxPicker>\n"

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
        rel_type = rel["type"].strip().upper()
        if rel_type not in {"N:1", "1:1", "N:N"}:
            continue
        f_name = rel["field"]
        if (
            f'name="{f_name}"' not in xml_content
            and ('<fetchPlan extends="_base">' in xml_content or '<fetchPlan extends="_base"/>' in xml_content)
        ):
            fp_prop = f'                <property name="{f_name}" fetchPlan="_base"/>\n'
            if '<fetchPlan extends="_base"/>' in xml_content:
                xml_content = xml_content.replace(
                    '<fetchPlan extends="_base"/>',
                    f'<fetchPlan extends="_base">\n{fp_prop}            </fetchPlan>',
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
    accumulated_form_components = ""
    modified = False
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
        print(
            "✨ [UI-Detail] user-detail-view.xml successfully updated dynamically!"
        )


def inject_nn_grid_into_inverse_entity(relations_list: list[dict[str, Any]]) -> None:
    for rel in relations_list:
        if rel["type"].strip().upper() != "N:N":
            continue
        source_name = rel.get("source_entity") or ""

def inject_nn_grid_into_inverse_entity(relations_list: list[dict[str, Any]]) -> None:
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
        
        # For inverse ownership, source is inverse side, target is owning - skip (no UI needed for owning side here)
        if ownership == "inverse":
            continue
            
        # Determine inverse field name in target entity
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
        print(f" 🖥️ Dynamic injecting N:N dataGrid in: {tgt_class} Detail View")

        column_props = _get_property_columns(source_name)

        container_id = f"{inv_field_name}Dc"
        container_block = f'            <collection id="{container_id}" property="{inv_field_name}"/>\n'
        
        if ownership == "both-owning":
            buttons_block = f'        <hbox id="buttonsPanel" classNames="buttons-panel">\n'
            buttons_block += f'            <button action="{grid_id}.add"/>\n'
            buttons_block += f'            <button action="{grid_id}.exclude"/>\n'
            buttons_block += "        </hbox>\n"
            grid_block = f'        <dataGrid id="{grid_id}" dataContainer="{container_id}"\n                      width="100%" maxHeight="15rem">\n'
            grid_block += "            <actions>\n"
            grid_block += '                <action id="add" type="list_add"/>\n'
            grid_block += '                <action id="exclude" type="list_exclude"/>\n'
            grid_block += "            </actions>\n"
            grid_block += "            <columns>\n"
            for col in column_props:
                grid_block += f'                <column property="{col}"/>\n'
            grid_block += "            </columns>\n"
            grid_block += "        </dataGrid>\n"
        else:
            buttons_block = ""
            grid_block = f'        <dataGrid id="{grid_id}" dataContainer="{container_id}" selectionMode="MULTI" readOnly="true">\n'
            grid_block += "            <columns>\n"
            for col in column_props:
                grid_block += f'                <column property="{col}"/>\n'
            grid_block += "            </columns>\n"
            grid_block += "        </dataGrid>\n"

        if f'id="{tgt_lower}Dc"' in xml_content and "</instance>" in xml_content:
            xml_content = xml_content.replace(
                f'<loader id="{tgt_lower}Dl"/>',
                f'<loader id="{tgt_lower}Dl"/>\n{container_block}'
            )
            xml_content = xml_content.replace('</instance>\n        </data>', f'        </instance>\n    </data>')
        if "</formLayout>" in xml_content:
            replacement = f"</formLayout>\n{buttons_block}{grid_block}"
            xml_content = xml_content.replace("</formLayout>", replacement)
        write_file(xml_path, xml_content)


def _infer_inverse_n_n_field(target_class: str, source_class: str) -> str | None:
    """Infer the inverse field name for N:N relationship.
    Reads the generated Java entity to find the field with mappedBy pointing to source.
    """
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
    
    # Find the @ManyToMany(mappedBy = "source_field") and extract the field name
    # Pattern: private List<Source> fieldName; followed by @ManyToMany(mappedBy = "source_field")
    import re
    pattern = rf'private\s+List<{source_class}>\s+(\w+)\s*;\s*\n\s*@ManyToMany\(mappedBy\s*=\s*"[^"]+"\s*\)'
    match = re.search(pattern, entity_content)
    if match:
        return match.group(1)
    
    # Alternative: find field with mappedBy containing source name
    pattern2 = rf'private\s+List<{source_class}>\s+(\w+)\s*.\s*@ManyToMany.*mappedBy.*"{source_class.lower()}s?"'
    match2 = re.search(pattern2, entity_content, re.DOTALL)
    if match2:
        return match2.group(1)
    
    # Fallback: common naming convention
    if source_class.lower() == "team":
        return "teams"
    if source_class.lower() == "user":
        return "users"
    
    return None


def _get_property_columns(entity_name: str) -> list[str]:
    """Get column properties for a property-based collection from entities.csv.
    For User entity (built-in), use 'username' as the display property.
    For other entities, read fields from entities.csv and use the first String field (typically @InstanceName).
    """
    # Handle built-in User entity specially
    if entity_name.lower() == "user":
        return ["username"]

    # Read fields from entities.csv for the source entity
    entities_path = Path("entities.csv")
    if not entities_path.exists():
        return ["id"]

    columns = []
    fields_list = get_entities_from_csv("entities.csv", entity_name)
    for field in fields_list:
        f_type = field.get("type", "").lower()
        # Prefer String fields (typically @InstanceName)
        if f_type in ["string", "text"]:
            columns.append(field.get("name", ""))
    # If no string fields found, use id
    return columns if columns else ["id"]





def inject_nn_datagrid_into_source_entity(relations_list: list[dict[str, Any]]) -> None:
    """For both-owning: inject dataGrid with actions in source entity detail view."""
    import re
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
            
        # Remove multiSelectComboBoxPicker for both-owning since we use dataGrid only
        picker_id = f"{f_name}Field"
        if f'id="{picker_id}"' in xml_content:
            picker_pattern = f'<multiSelectComboBoxPicker id="{picker_id}"[^>]*>.*?</multiSelectComboBoxPicker>'
            xml_content = re.sub(picker_pattern, '', xml_content, flags=re.DOTALL)
            print(f"   -> Removed multiSelectComboBoxPicker for {f_name} in {source_name}")
        
        # For both-owning: replace class-based collection with property-based inside instance
        old_inside = f'<loader id="{source_lower}Dl"/>\n        </instance>'
        new_inside = f'<loader id="{source_lower}Dl"/>\n            <collection id="{f_name}Dc" property="{f_name}"/>\n        </instance>'
        if old_inside in xml_content and f'class="{COMPANY}.{project_name}.entity.{tgt_class}"' in xml_content:
            xml_content = xml_content.replace(old_inside, new_inside)
            # Remove the class-based collection outside instance
            old_outside = f'\n        <collection id="{f_name}Dc" class="{COMPANY}.{project_name}.entity.{tgt_class}">.*?</collection>'
            xml_content = re.sub(old_outside, '', xml_content, flags=re.DOTALL)
            print(f" -> Moved collection inside instance for {f_name} in {source_name}")
        
        print(f" 🖥️ Dynamic injecting N:N dataGrid in source: {source_name} Detail View")
        
        column_props = _get_property_columns(tgt_class)
        
        buttons_block = f'        <hbox id="buttonsPanel" classNames="buttons-panel">\n'
        buttons_block += f'            <button action="{grid_id}.add"/>\n'
        buttons_block += f'            <button action="{grid_id}.exclude"/>\n'
        buttons_block += "        </hbox>\n"
        grid_block = f'        <dataGrid id="{grid_id}" dataContainer="{f_name}Dc"\n                      width="100%" maxHeight="15rem">\n'
        grid_block += "            <actions>\n"
        grid_block += '                <action id="add" type="list_add"/>\n'
        grid_block += '                <action id="exclude" type="list_exclude"/>\n'
        grid_block += "            </actions>\n"
        grid_block += "            <columns>\n"
        for col in column_props:
            grid_block += f'                <column property="{col}"/>\n'
        grid_block += "            </columns>\n"
        grid_block += "        </dataGrid>\n"
        
        if "</formLayout>" in xml_content:
            replacement = f"</formLayout>\n{buttons_block}{grid_block}"
            xml_content = xml_content.replace("</formLayout>", replacement)
        write_file(xml_path, xml_content)
