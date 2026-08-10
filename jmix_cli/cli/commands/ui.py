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

from jmix_cli.views import (
    gen_list_view_from_csv,
    gen_detail_view_from_csv,
    inject_list_ui_into_existing_user,
    inject_detail_ui_into_existing_user,
    inject_nn_grid_into_inverse_entity,
    inject_nn_datagrid_into_source_entity,
)
from jmix_cli.entity import get_entities_from_csv, get_relations_from_csv, get_sorted_entities_by_dependency
from jmix_cli.entity.generator import _inject_composition_into_parent
from jmix_cli.cli.commands.entity import _get_inverse_composition_relations
from jmix_cli.i18n import update_messages_entity
from jmix_cli.entity.traits import get_traits_from_csv
from jmix_cli.core.project import COMPANY, project_name


def generate_all_list_views() -> None:
    ordered_list = get_sorted_entities_by_dependency()
    for ent in ordered_list:
        fields_list = get_entities_from_csv("entities.csv", ent)
        relations_list = get_relations_from_csv("relations.csv", ent)
        if ent == "User":
            if fields_list or relations_list:
                inject_list_ui_into_existing_user(relations_list, fields_list)
        elif fields_list:
            gen_list_view_from_csv(ent, fields_list, relations_list)


def generate_all_detail_views() -> None:
    ordered_list = get_sorted_entities_by_dependency()
    for ent in ordered_list:
        relations_list = get_relations_from_csv("relations.csv", ent)
        composition_rels = [rel for rel in relations_list if rel["type"] == "COMPOSITION_1:N"]
        if composition_rels:
            _inject_composition_into_parent(ent, composition_rels)
    for ent in ordered_list:
        fields_list = get_entities_from_csv("entities.csv", ent)
        relations_list = get_relations_from_csv("relations.csv", ent)
        inverse_rels = _get_inverse_composition_relations(ent)
        relations_list_for_messages = relations_list + inverse_rels
        for rel in relations_list:
            if rel["type"] == "COMPOSITION_1:N":
                inv_field_name = rel["target"][0].lower() + rel["target"][1:]
                relations_list_for_messages.append({
                    "type": rel["type"],
                    "target": rel["target"],
                    "field": inv_field_name,
                    "mandatory": rel.get("mandatory", False),
                })
        if ent == "User":
            if fields_list or relations_list:
                inject_detail_ui_into_existing_user(relations_list, fields_list)
        elif fields_list:
            gen_detail_view_from_csv(ent, fields_list, relations_list)
        computed_traits_list = [row["field_name"].strip() for row in csv.DictReader(Path("entities.csv").open(encoding="utf-8")) if row["entity_name"].strip() == ent.strip()]
        if not computed_traits_list:
            computed_traits_list = ["name"]
        update_messages_entity(
            project_dir=".",
            base_package=COMPANY + "." + project_name,
            entity_name=ent,
            traits_list=computed_traits_list,
            relations_list=relations_list_for_messages,
        )
    all_relations = []
    for ent in ordered_list:
        rels = get_relations_from_csv("relations.csv", ent)
        for rel in rels:
            rel["source_entity"] = ent
        all_relations.extend(rels)
    inject_nn_datagrid_into_source_entity(all_relations)
    inject_nn_grid_into_inverse_entity(all_relations)


def generate_single_list_view(name: str) -> None:
    if name == "User":
        relations_list = get_relations_from_csv("relations.csv", "User")
        inject_list_ui_into_existing_user(relations_list)
    else:
        fields_list = get_entities_from_csv("entities.csv", name)
        relations_list = get_relations_from_csv("relations.csv", name)
        if not fields_list:
            raise ValueError(f"Fields for entity '{name}' do not exist in entities.csv")
        gen_list_view_from_csv(name, fields_list, relations_list)


def generate_single_detail_view(name: str) -> None:
    if name == "User":
        relations_list = get_relations_from_csv("relations.csv", "User")
        inject_detail_ui_into_existing_user(relations_list)
    else:
        fields_list = get_entities_from_csv("entities.csv", name)
        relations_list = get_relations_from_csv("relations.csv", name)
        if not fields_list:
            raise ValueError(f"Fields for '{name}' do not exist in entities.csv")
        gen_detail_view_from_csv(name, fields_list, relations_list)
