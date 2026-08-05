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
        if ent == "User":
            if fields_list or relations_list:
                inject_detail_ui_into_existing_user(relations_list, fields_list)
        elif fields_list:
            gen_detail_view_from_csv(ent, fields_list, relations_list)
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
