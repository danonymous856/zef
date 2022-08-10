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

from ..core import *
from ..ops import *
from ariadne import ObjectType, MutationType, SubscriptionType, EnumType, ScalarType, InterfaceType


#--------------------------Resolvers Generator-------------------------
def fill_types_default_resolvers(schema_d):
    if "_Types" not in schema_d: return schema_d

    new_schema_d = {**schema_d}
    new_schema_d["_Types"] = {**schema_d["_Types"]}

    for type_name, fields_dict in new_schema_d["_Types"].items():
        fields_dict = {**fields_dict}
        new_schema_d["_Types"][type_name] = fields_dict

        for field_name, field_dict in fields_dict.items():
            field_dict = {**field_dict}
            new_schema_d["_Types"][type_name][field_name] = field_dict

            if field_name.startswith("_"): continue

            resolver = field_dict.get("resolver", None)
            if not resolver: field_dict["resolver"] = get[field_name]
    
    return new_schema_d

def initialize_object_type(object_type):
    if "Mutation" == object_type:
        return MutationType()
    elif "Subscription" == object_type:
        return SubscriptionType()
    else:
        return ObjectType(object_type)

def resolve_enum_type(object_type, options):
    return EnumType(object_type, options)

def resolve_scalar_type(object_type, options):
    # TODO: Should we check the passed ZefOp/Zef Functions?
    value_parser = options.get("parser", None)
    serializer = options.get("serializer", None)
    return ScalarType(object_type, serializer=serializer, value_parser=value_parser)

def resolve_interface_type(interface_name, interface_d, g):
    interface_resolver = interface_d.get("_interface_resolver", None)
    if interface_resolver is None: raise ValueError(f"{interface_name} Interface's type resolver must be definied")

    interface_type = InterfaceType(interface_name, interface_resolver)
    for field_name, field_dict in interface_d.items():
        if field_name.startswith("_"): continue
        assign_field_resolver(interface_type, field_name, field_dict, g, True)
    
    return interface_type

def resolve_args(args):
    def handle_arg_dict(d):
        arg, arg_d = list(d.items())[0]
        d = {}
        d[arg]  = arg_d.get('default', None)
        return d

    return (
        args
        | map[handle_arg_dict]
        | merge
        | collect
    )

def get_zef_function_args(z_fct, g):
    from ..core.zef_functions import zef_function_args
    zefref_or_func = peel(z_fct)[0][1][0][1]
    if type(zefref_or_func) == Entity:
        full_arg_spec = zef_function_args(g[zefref_or_func] | now  | collect)
        args, defaults =  full_arg_spec.args, full_arg_spec.defaults
        return args[:len(args) - len(defaults)]
    else:
        import types
        assert type(zefref_or_func) == types.FunctionType
        import inspect
        args = inspect.getargs(zefref_or_func.__code__).args
        # Remove the already curried args
        curried = peel(z_fct)[0][1][1:]
        # args = args[:-len(curried)]
        args = args[0:1] + args[1+len(curried):]
        return args

def generate_fct(field_dict, g, allow_none):
    resolver = field_dict["resolver"]
    if resolver is None and not allow_none:
        raise ValueError("A type's field resolver shouldn't be set to None! \
            To use default values for your resolver, explicitly call fill_types_default_resolvers on your schema dictionary!")

    def resolve_field(obj, info, **kwargs):
        context = {
            "obj": obj,
            "query_args": kwargs,
            "graphql_info": info,
            # To be extended
        }
        if is_a(resolver, ZefOp):
            if peel(resolver)[0][0] == RT.Function:
                args = get_zef_function_args(resolver, g)
                arg_values = select_keys(context, *args).values()
                # Check if some args that are present in the Zef Function aren't present in context dict
                if len(arg_values) < len(args): raise ValueError("Some args present in the Zef Function aren't present in context dict")
                arg_values = [context[x] for x in args]
                return resolver(*arg_values)
            else:
                return resolver(obj)
        elif isinstance(resolver, LazyValue):
            return resolver()
        else:
            raise NotImplementedError(f"Cannot generate resolver using the passed object {resolver} of type {type(resolver)}")
    return resolve_field

def assign_field_resolver(object_type, field_name, field_dict, g, allow_none=False):
    fct = generate_fct(field_dict, g, allow_none)
    if fct is not None:
        object_type.field(field_name)(fct)

def generate_resolvers(schema_dict, g):
    """
    Given a schema dict with definied resolvers fields, generates the ariadane resolvers.
    Returns back ariadne object types list.
    """
    fallback_resolver = schema_dict.get("fallback_resolvers", [])
    object_types = []

    types = schema_dict.get("_Types", {})
    for object_type, fields_dict in types.items():
    
        object_type = initialize_object_type(object_type)
        object_types.append(object_type)

        for field_name, field_dict in fields_dict.items():
            if field_name.startswith("_"): continue
            assign_field_resolver(object_type, field_name, field_dict, g)

    enums = schema_dict.get("_Enums", {})
    for object_type, options in enums.items():
        object_types.append(resolve_enum_type(object_type, options))

    scalars = schema_dict.get("_Scalars", {})
    for object_type, options in scalars.items():
        object_types.append(resolve_scalar_type(object_type, options))

    
    interfaces = schema_dict.get("_Interfaces", {})
    for interface_name, interface_d in interfaces.items():
        object_types.append(resolve_interface_type(interface_name, interface_d, g))

    return object_types