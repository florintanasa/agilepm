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
from jmix_cli.core.files import write_file, replace_entity_messages, append_unique
from jmix_cli.core.constants import ISO_LANG_NAMES
from jmix_cli.i18n.translator import ask_ollama_translation
from jmix_cli.entity import get_entities_from_csv


def inject_composition_ui_into_parent(
    name: str, fields_list: list[dict[str, str]], relations_list: list[dict[str, str]]
) -> None:
    for rel in relations_list:
        if rel["type"] != "COMPOSITION_1:N":
            continue
        tgt_class = rel["target"]
        tgt_lower = tgt_class.lower()
        f_name = rel["field"]
        src_class = name
        mapped_by_prop = tgt_class[0].lower() + tgt_class[1:]

        from jmix_cli.i18n.translator import ask_ollama_translation
        base_package = f"{COMPANY}.{project_name}"
        msg_key = f"{base_package}.view.{tgt_lower}/{tgt_lower}DetailView.{f_name}"
        readable_en = f_name.capitalize()
        properties_base = PROIECT_PATH / "src" / "main" / "resources" / company_path / project_name

        locales = ["en"]
        app_props = PROIECT_PATH / "src" / "main" / "resources" / "application.properties"
        if app_props.exists():
            for _line in app_props.read_text(encoding="utf-8").splitlines():
                if "jmix.core.available-locales" in _line:
                    _match = re.search(r"jmix\.core\.available-locales\s*=\s*(.*)", _line)
                    if _match:
                        locales = [loc.strip() for loc in _match.group(1).split(",") if loc.strip()]

        for locale in locales:
            if locale == "en":
                msg_value = readable_en
            else:
                _primary_iso = locale.split("_")[0].lower()
                _lang_name = ISO_LANG_NAMES.get(_primary_iso, locale)
                try:
                    _translated = ask_ollama_translation(readable_en, _lang_name)
                    msg_value = _translated if _translated else readable_en
                except Exception:
                    msg_value = readable_en

            msg_line = f"{msg_key}={msg_value}"
            _files = []
            if locale == "en":
                _files = [
                    str(properties_base / "messages_en.properties"),
                    str(properties_base / "messages.properties"),
                ]
            else:
                _files = [str(properties_base / f"messages_{locale}.properties")]

            for _pf in _files:
                replace_entity_messages(_pf, base_package, tgt_lower, [msg_line])

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
        composition_grid += f'            <button id="{f_name}AddBtn" action="{f_name}DataGrid.add"/>\n'
        composition_grid += f'            <button id="{f_name}ExcludeBtn" action="{f_name}DataGrid.exclude"/>\n'
        composition_grid += "        </hbox>\n"
        composition_grid += f'        <dataGrid id="{f_name}DataGrid" width="100%" minHeight="15em" dataContainer="{f_name}Dc">\n'
        composition_grid += "            <actions>\n"
        composition_grid += '                <action id="add" type="list_add"/>\n'
        composition_grid += '                <action id="exclude" type="list_exclude"/>\n'
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

        child_xml_path = (
            PROIECT_PATH
            / "src"
            / "main"
            / "resources"
            / company_path
            / project_name
            / "view"
            / src_class.lower()
            / f"{src_class.lower()}-detail-view.xml"
        )
        if child_xml_path.exists():
            child_xml_content = child_xml_path.read_text(encoding="utf-8")
            tgt_lower_for_combo = tgt_class.lower()
            child_collection = (
                f'        <collection id="{tgt_lower_for_combo}sDc" class="{COMPANY}.{project_name}.entity.{tgt_class}">\n'
            )
            child_collection += '            <fetchPlan extends="_base"/>\n'
            child_collection += f'            <loader id="{tgt_lower_for_combo}sDl">\n'
            child_collection += "                <query>\n"
            child_collection += f'                   <![CDATA[select e from {tgt_class} e]]>\n'
            child_collection += "                </query>\n"
            child_collection += "            </loader>\n"
            child_collection += "        </collection>\n"

            child_combo = (
                f'            <entityComboBox id="{mapped_by_prop}Field" '
                f'property="{mapped_by_prop}" itemsContainer="{tgt_lower_for_combo}sDc">\n'
            )
            child_combo += "                <actions>\n"
            child_combo += '                    <action id="entityLookupAction" type="entity_lookup"/>\n'
            child_combo += '                    <action id="entityOpenAction" type="entity_open"/>\n'
            child_combo += '                    <action id="entityClearAction" type="entity_clear"/>\n'
            child_combo += "                </actions>\n"

            if f'id="{tgt_lower_for_combo}sDc"' not in child_xml_content:
                if "</instance>" in child_xml_content:
                    child_xml_content = child_xml_content.replace(
                        "</instance>", f"</instance>\n{child_collection}"
                    )

            if f'id="{mapped_by_prop}Field"' not in child_xml_content:
                _form_match = re.search(r'(\s*)</formLayout>', child_xml_content)
                if _form_match:
                    _form_indent = _form_match.group(1)
                    child_xml_content = child_xml_content.replace(
                        _form_indent + "</formLayout>",
                        f"\n{child_combo}{_form_indent}</formLayout>"
                    )

            write_file(child_xml_path, child_xml_content)
