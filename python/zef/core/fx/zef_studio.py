# Copyright 2022 Synchronous Technologies Pte Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from .fx_types import Effect, FX
from .._ops import *
from ..zef_functions import func
from ..VT import *
from ..logger import log


#-------------------------------------------------------------
#---------------------Resolvers-------------------------------
#-------------------------------------------------------------
# TODO: Add Better Error Reporting

@func
def graphs(query_args):
    from zef import pyzef
    uids = pyzef.internals.list_graph_manager_uids()
    return (
        uids
        | map[lambda uid: {'labels': [str(uid)], 'id': str(uid)}]
        | collect
    )
    return (
        globals() 
        | items     
        | filter[lambda kv: is_a(kv[1], Graph)]
        | map[lambda kv: {'labels': [kv[0]], 'id': str(uid(kv[1]))}]
        | collect
    )

@func
def entity_types(query_args):
    graph_id = query_args.get('graphID', None)
    if not graph_id: return None
    return list(Graph(graph_id) | now | all[ET] | map[rae_type] | func[set] | collect)


def make_cellet_value(obj):
    if has_out(obj, RT.Name):
        label = value(obj | Out[RT.Name])
    elif has_out(obj, RT.Label):
        label = value(obj | Out[RT.Label])
    else:
        label = None
        
    return {
            "type": "CellET",
            "id": uid(obj),
            "label": label,
            "etType": str(rae_type(obj)),
        }

def make_individual_value(obj):
   if is_a(obj, ET): return make_cellet_value(obj)

   types = {AET.String: "CellString", AET.Float: "CellFloat", AET.Bool: "CellBoolean", AET.Int: "CellInt"}
      
   return {
      "type": types.get(rae_type(obj), "CellZef"),
      "id": str(uid(obj)),
      "value": obj | attempt[value][str(rae_type(obj))] | collect ,
   }

def make_cell(obj, rt):
   trgts = obj | Outs[rt] | collect
   if not trgts: 
      return None
   elif len(trgts) == 1:
      return make_individual_value(trgts[0])
   else:
      return {
         "type": "CellList",
         "id": f"{uid(obj)}_{rt}_{len(trgts)}",
         "value": [make_individual_value(obj) for obj in trgts]
      }

def make_row(obj, connected_rels):
   return {
      "cells": [make_cell(obj, rt) for rt in connected_rels]
   }


@func
def make_column(column):
   return {
      "header": str(column)
   }

def make_columns(g, entity_type):
   # TODO Add sorting of columns
   z = delegate_of(entity_type, g)
   connected_rels = z | out_rels[RT] | map[rae_type] | collect
   return connected_rels, connected_rels | map[make_column] | collect

def make_table_return(g, entity_type, entities):
   connected_rels, columns = make_columns(g, entity_type)
   return {
      # 'id': f"{graph_id}_{entity_type}",
      'columns': columns,
      'rows': [make_row(obj, connected_rels) for obj in entities],
   }

@func
def entity_table(query_args):
   graph_id = query_args.get('graphID', None)
   et_type  = query_args.get('entityType', None)
   if not graph_id or not et_type: return None

   et_type = ET(et_type)
   limit  = query_args.get('limit', 10)
   g = Graph(graph_id)
   return make_table_return(g, et_type, list(g | now |  all[et_type] | take[limit] | collect))

@func
def single_entity(query_args):
   graph_id = query_args.get('graphID', None)
   et_id  = query_args.get('entityID', None)
   if not graph_id or not et_id: return None

   g = Graph(graph_id)
   entity = g[et_id]
   if not is_a(entity, ET): return None
   et_type = rae_type(entity)

   return make_table_return(g, et_type, [entity])

@func
def cell_interface_resolver(obj, *_):
   return obj.get('type', "CellString")


@func
def assign_value_general(query_args, aet_type):
    graphID = query_args['ids']['graphID']
    aetID = query_args['ids']['aetID']

    g = Graph(graphID)
    aet = g[aetID]

    if not is_a(aet, AET): 
      log.error(f"Cannot assign value to {aetID} as it is not an AET")
      return False 

    if not is_a(aet, aet_type): 
      log.error(f"Cannot assign value to {aetID} as it is not an {aet_type}")
      return False

    try:
      aet_value = query_args['value']
      aet | assign[aet_value] | g | run
      
      return True
    except Exception as e:
      log.error(f"Failed to assign value to {aetID}. {e}")
      return False

@func
def assign_value_string(query_args):
    return assign_value_general(query_args, AET.String)

@func
def assign_value_float(query_args):
    return assign_value_general(query_args, AET.Float)

@func
def assign_value_int(query_args):
    return assign_value_general(query_args, AET.Int)

@func
def assign_value_bool(query_args):
    return assign_value_general(query_args, AET.Bool)


#-------------------------------------------------------------
#-------------------Schema String-------------------------------
#-------------------------------------------------------------
simple_schema = """
type Query {
    graphs: [Graph]
    entityTypes(graphID: ID!): [String]
    entityTable(graphID: ID!, entityType: String!, limit: Int): Table
    entity(graphID: ID!, entityID: ID!): Table
}

type Mutation {
    assignValueString(ids: AssignValueIDs!, value: String!): Boolean
    assignValueFloat( ids: AssignValueIDs!, value: Float!): Boolean
    assignValueInt(   ids: AssignValueIDs!, value: Int!): Boolean
    assignValueBool(  ids: AssignValueIDs!, value: Boolean!): Boolean
}

input AssignValueIDs {
    graphID: ID!
    aetID: ID!
}

type Graph {
    id: ID!
    labels: [String]
}

type Table {
columns: [Column]
rows: [Row]
}

type Column {
header: String
}

type Row {
cells: [Cell]
}

interface Cell {
id: ID!
}

type CellInt implements Cell{
id: ID!
value: Int
}

type CellString implements Cell{
id: ID!
value: String
}

type CellFloat implements Cell{
id: ID!
value: Float
}

type CellBoolean implements Cell{
id: ID!
value: Boolean
}

type CellET implements Cell{
id: ID!
label: String
etType: String
}

type CellZef implements Cell{
id: ID!
value: String
}

type CellList implements Cell{
id: ID!
value: [Cell]
}
"""

def create_schema_dict(simple_schema):
   from ...graphql import generate_schema_dict, fill_types_default_resolvers

   schema_dict = generate_schema_dict(simple_schema)
   schema_dict = fill_types_default_resolvers(schema_dict, lambda field_name: get[field_name])
   schema_dict = (
      schema_dict 
      | insert_in[('_Types', 'Query', 'graphs', 'resolver')][graphs] 
      | insert_in[('_Types', 'Query', 'entityTypes', 'resolver')][entity_types] 
      | insert_in[('_Types', 'Query', 'entityTable', 'resolver')][entity_table] 
      | insert_in[('_Types', 'Query', 'entity', 'resolver')][single_entity] 
      | insert_in[('_Types', 'Mutation', 'assignValueString', 'resolver')][assign_value_string]
      | insert_in[('_Types', 'Mutation', 'assignValueFloat', 'resolver')][assign_value_float]
      | insert_in[('_Types', 'Mutation', 'assignValueInt', 'resolver')][assign_value_int]
      | insert_in[('_Types', 'Mutation', 'assignValueBool', 'resolver')][assign_value_bool]
      | insert_in[('_Interfaces', 'Cell', '_interface_resolver')][cell_interface_resolver] 
      | collect
   )
   return schema_dict

def studio_start_server_handler(eff: Dict):
   """Example
   {
      "type": FX.Studio.StartServer,
   } | run
   """
   def open_browser(port):
      studio_url = f"https://studio.zefhub.io/?endpoint=http://localhost:{port}/graphql"
      log.info(f"Started Zef Studio at {studio_url}")
      import webbrowser
      webbrowser.open(studio_url)

   import random
   from .. import internals
   g_process = internals.get_local_process_graph()

   schema_dict = create_schema_dict(simple_schema)

   trials = 5
   while trials:
      random_port = random.randint(10000, 30000)
      try:
         http_r = {
            "type": FX.GraphQL.StartServer,
            "schema_dict" : schema_dict,
            "g" :  Graph(),
            "port" :  random_port, 
            "path" :  "/graphql", 
         } | run

         server_zr = now(g_process[http_r['server_uuid']])
         
         ET.ZefFXService(**{
            "type": Val(eff['type']),
            'owns': server_zr,
         }) | g_process | run # TODO Perform that in a flat way by directly calling into the FX handler

         open_browser(random_port)
         return http_r
      except Exception as e:
         trials -= 1
         if trials: continue
         raise e


def studio_stop_server_handler(eff: Dict):
    return run({**eff, 'type': FX.HTTP.StopServer})

