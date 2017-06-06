# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

"""
Import and export STP files

Used as a blender script, it load all the stl files in the scene:

blender --python stp_utils.py -- file1.stl file2.stl file3.stl ...
"""

import re
import bpy
import numpy as np
import math

import pprint
pp = pprint.PrettyPrinter(indent=4)

structure = {}
structure_func = {}
structure_params = {}

instances = []
data = []   # Instance blender data

object_name = ""
object_location = [0,0,0]
vertexs = [] # Mesh Vertices
edges = [] # Mesh Edges
faces = [] # Mesh Faces

print_verbose_level = 10

### COMMON FUNCTION ###

def read_stp_single_line(f):
    return f.readline().decode("utf-8").strip()    

def read_stp_line(f):
    line = ""
    while (line == "" or line[-1] != ";"):
        line = line  +read_stp_single_line(f)
    return line[:-1]  #remove ';'

def get_instance_number(str):
    return int(str[1:])  #removes '#'

def add_instance (line, name, params, data, number):
    global instances;
    id = get_instance_number(number);
    while (len(instances) < id): 
        instances.append({"name" : ""})
    new_instance = {"name" : name, "params" : params,  "line" : line, "data" : data, "number" : number}
    instances.insert(id,new_instance) 
    return new_instance

def get_instance(number):
    global instances
    instance = instances[get_instance_number(number)]
    if (number != instance["number"]):
        print ("Error: Expected " + number + ", found " + instance["number"])
    
    return instance
    
def check_instance_name (instance, name):
     if (instance["name"] != name):
        print ("ERROR: expected " + name + ", found "+ instance["name"] + instance["number"])
        
def execute_instance_functions(instance, type):
    if instance["name"] in structure_func:
        if type in structure_func[instance["name"]]:
            func = structure_func[instance["name"]][type]
            if isinstance(func, list):
                for f in func:
                    f(instance)
            else:
                func(instance)
                
def load_referenced_instance(instance, number, n_exp):
    new_instance = load_instance(get_instance(number),instance)
    if len(n_exp) and not new_instance["name"] in n_exp:
        if not "multiple" in new_instance and not "multiple" in n_exp:
            print ("Error: Not expected " + new_instance["name"] + " in " +  instance["number"] + " " + instance ["name"])
    elif not len(n_exp):
        print ("loading object " + new_instance["name"] +" with no instance name defined in " + instance["number"] + " " + instance["name"])
    return new_instance
    
def check_instance_value(instance, value, n_exp):
    if len(n_exp):
        if "func" in n_exp:
            None
        elif "float" in n_exp:
            value = float(value)
        elif "int" in n_exp:
            value = int(value)
        elif "str" in n_exp:
            if value[0] == "'" and value[-1] == "'":
                value = value[1:-1]
            else:
                print ("Expected 'string'")
        elif value == "*":
            None
        else:
            print ("Error: Expected instance: " + value + " on " + instance["name"])
    
    return value
   
def load_instance(instance, parent = None):
    
    if instance["name"] in structure:
        st = structure[instance["name"]] 
        
        if isinstance(st,list):
            for st in structure[instance["name"]]:
                if (len(st) == len(instance["params"])):         
                    break
        
        if st and not isinstance(st,tuple):
            print("ERROR, expecting tuple st " + instance["name"])
            return instance
        
        if not instance["data"]:                    
            instance["data"] = {}
            
            instance["parent"] = parent
            
            execute_instance_functions(instance,"init")
            
            if st:
                
                if not (len(st) == len(instance["params"])):
                    print ("Diferent number of parameters in " + instance["number"]+" " +instance["name"] + ". IGNORED")
                    return instance
                for idx,n  in enumerate(st):
                    if n:
                        n_exp = n.split("|")
                        n = n_exp.pop()  #last postion is the data name
                        param = instance["params"][idx]

                        if isinstance(param, list):
                            instance["data"][n] = []
                            for a in instance["params"][idx]:
                                if a[0] == '#':
                                    instance["data"][n].append(load_referenced_instance(instance,a, n_exp))
                                else:
                                    instance["data"][n].append(check_instance_value(instance, a, n_exp))
                                    
                        elif param[0] == '#':
                            instance["data"][n] = load_referenced_instance(instance, param, n_exp)
                        else:
                            instance["data"][n] = check_instance_value(instance, param, n_exp)
                        
            execute_instance_functions(instance,"first_load")
            execute_instance_functions(instance,"load")
        else: 
            #Already loaded
            execute_instance_functions(instance,"load")
    elif "multiple" in instance:
        for sub_instance in instance["multiple"]:
            load_instance(sub_instance,parent)
    else:
        print ("Not defined instance " + instance["number"] + " " +instance["name"])
        print ("loaded fom " + parent["number"] + " " + parent["name"])

    return instance

def get_instance_value(instance,path, index=0):
    if isinstance(path, list): 
        if path[index] in instance["data"]:
            value = instance["data"][path[index]]
            if index+1 < len(path):
                value = get_instance_value(value,path, index+1)
        else:
            value = None
    elif path in instance["data"]:
        value = instance["data"][path]
    else:
        value = None
        
    return value

# Debug function
def print_instance(instance, max_levels=-1, name = "", level =0):
    
    if level==0:
        for ins in instances:
            ins["printed"] = False
    
    global print_verbose_level
    
    if max_levels > -1 and level > max_levels:
        return
    
    spaces=""
    for i in range(level):
        spaces=spaces+"|"
    print (spaces + name + instance["number"] + " " + instance["name"])
    
    if instance["printed"]:
        print (spaces + "recursive_call")
        return
        
    instance["printed"] = True
    
    
    if instance["name"] in structure_params and "print_verbose" in structure_params[instance["name"]]:
        pv = structure_params[instance["name"]]["print_verbose"]
        if pv > print_verbose_level: 
            return
    
    spaces=spaces+"|"
    for name in instance["data"]:
        value = instance["data"][name]
        if isinstance(value, str):
            print (spaces + name + ":" + value) 
        elif isinstance(value, int) or isinstance(value, float):
            print (spaces + name + ":" + str(value)) 
        elif isinstance(value,list):
            for idx,value2 in enumerate(value):
                if isinstance(value2, str):
                    print (spaces+name+"["+str(idx)+"]:"+value2)
                elif isinstance(value2, int) or isinstance(value2, float): 
                    print (spaces+name+"["+str(idx)+"]:"+str(value2))
                else:
                    print_instance(value2, max_levels, name + "["+str(idx)+"]:", level+1)
        else:
            print_instance(value, max_levels, name + ":", level+1)
            
def get_instance_path (instance):
    str = instance["number"] + " " + instance["name"]
    if "parent" in instance and instance["parent"]:
        str = str + ">" + get_instance_path(instance["parent"])
    return str

### HEADER ###

def parse_stp_header_line(line):
    pattern = r'(\w[\w\d_]*)\((.*)\)$'
    match = re.match(pattern, line)
    data = list(match.groups()) if match else []
    if (len(data)):
        print ("header: ignoring " + data[0])
        
def read_stp_header_line(f):
    
    line = read_stp_line(f)
    parse_stp_header_line(line)
    return line

def read_stp_header(f):
    line = ""
    while (line != "ENDSEC"):
        line = read_stp_header_line(f)


### DATA READING ####
def parse_stp_instance_multiple(instance, content, number):
    pattern = r'\s?(\w[\w\d_]*)\((.*)\)$'
    c=0
    i=0
    start =0
    while i < len(content):
        if content[i] == '(':
            c=c+1
        if content[i] == ')':
            c=c-1
            if c == 0:
                i = i +1
                sub_instance = content[start:i]
                match = re.match(pattern, sub_instance)
                parsed = list(match.groups()) if match else []
                if (len(parsed)):
                    #X = NAME(a,b,...);
                    n_params = []
                    parse_params(parsed[1],n_params)
                    instance["multiple"].append({"name" : parsed[0], "params" : n_params, "number": number, "data" : data})
                else:
                    print ("Error on parse")
                
                start = i
        i=i+1 


def parse_stp_data_line(line):
    
    pattern = r'(#[\d]*)\s?=\s?(\w[\w\d_]*)\((.*)\)$'
    match = re.match(pattern, line)
    parsed = list(match.groups()) if match else []
    if (len(parsed)):
        #X = NAME(a,b,...);
        
        n_params = []
        parse_params(parsed[2],n_params)
        add_instance(line, name= parsed[1], params = n_params,data="", number=parsed[0])
    else:
        pattern = r'(#[\d]*)\s?=\s?\((.*)\)$'
        match = re.match(pattern, line)
        parsed = list(match.groups()) if match else []
        if (len(parsed)):
            #X = ( GEOMETRIC_REPRESENTATION_CONTEXT(2) PARAMETRIC_REPRESENTATION_CONTEXT() REPRESENTATION_CONTEXT('2D SPACE','') );
            instance = add_instance(line, name= "", params = [], data="", number=parsed[0])
            instance["multiple"] = []
            parse_stp_instance_multiple(instance,parsed[1], number=parsed[0])
        else:
            print ("Unknown match for: " + line);
        
        

def read_stp_data_line(f):
    line = read_stp_line(f)
    parse_stp_data_line(line)
    return line

def read_stp_data(f):
    global instances
    line = ""
    while (line != "ENDSEC"):
        line = read_stp_data_line(f)    
        
    print ("Readed " + str(len(instances)) + " instances")   

def parse_params(str, params):
    v =  ""
    i  = 0
    while (i<len(str) and str[i] != ")"):
        
        if not v and str[i] == "'":
            #string
            while True:
                v = v + str[i]
                i=i+1
                if i >= len(str) or str[i] == "'":
                    break
            
        if str[i] == ",":
            #new param
            if v:
                params.append(v)
                v = ""
        elif str[i] == "(":
            n = [];
            i = i + parse_params(str[(i+1):], n)
            params.append(n);
            v = ""
        else:
            v = v + str[i];
        
        i = i+1
        
    if (v):
        params.append(v)
    
    return i+1;
    
### INSTANCE UTILS ###

# Retuns verts of an edge loop
def get_edge_loop_verts(edge_loop):
    edges = []
    verts = []
    
    for ed in get_instance_value(edge_loop,["oriented_edges"]):
        edges.append([
            get_instance_value(ed, ["edge_curve","v1","vertex_id"]),
            get_instance_value(ed, ["edge_curve","v2","vertex_id"])
        ])
                
    ordered_edges = []
    ordered_edges.append(edges[0])
    edges.remove(edges[0])
    
    ok = True
    while len(edges) and ok:
        ok = False
        for ed in edges:
            if (ed[1] == ordered_edges[-1][1]):
                #swap
                 ed[0], ed[1] = ed[1], ed[0]
                
            if (ed[0] == ordered_edges[-1][1]):
                ordered_edges.append(ed)
                edges.remove(ed)
                ok = True
                break

    if not ok:
        print ("ERROR: incorrect loop")        
                     
    if (ordered_edges[0][0] != ordered_edges[-1][1]):
        print ("ERROR: incorrect loop, not closed")     

    for ed in ordered_edges:
        if (not ed[0] in verts):
            verts.append(ed[0])

        if (not ed[1] in verts):
            verts.append(ed[1])

    return verts


def get_matrix_from_axis2_placement_3d(instance):
    dir1 = np.array(get_instance_value(instance,["dir1","values"]))
    dir2 = np.array(get_instance_value(instance,["dir2","values"]))
    co = np.array(get_instance_value(instance,["point","coordinates"]))
    
    dir3 = np.cross(dir1,dir2)
    
    return [np.append(dir3,0), np.append(dir2,0), np.append(dir1,0), np.append(co,1.0)]

def rotation_matrix (angle):
    return [[math.cos(angle), -math.sin(angle), 0, 0], [math.sin(angle), math.cos(angle), 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    
def generate_torus_faces (instance, face):
    if instance["name"] != "TOROIDAL_SURFACE":
        return
    
    iv = len(vertexs)
    r1 = get_instance_value(instance,"r1")
    r2 = get_instance_value(instance,"r2")
    pm = get_matrix_from_axis2_placement_3d(get_instance_value(instance,"axis2_placement3d"))
    prec = 32
    for i in range(0,prec):
        a1 = ((math.pi*2)/prec)*i
        tm = [[1.0, 0.0, 0.0, 0.0],[0.0, 1.0, 0.0, 0.0],[0.0, 0.0, 1.0, 0.0],[r1, 0.0, 0.0, 1.0]]
        rm = rotation_matrix(a1)
        rm = np.matmul(rm, pm)
        tm = np.matmul(tm, rm)
        for j in range (0,prec):
            a2 = ((math.pi*2)/prec)*j
            v4 = [math.cos(a2)*r2,0.0, math.sin(a2)*r2, 1.0]
            v4 = np.matmul(v4,tm)
            v3 = [0,0,0]
            for k in range(0,3):
                v3[k] = v4[k]
                 
            vertexs.append(v3)

            if j==31:
                edges.append([iv+i*32+j,iv+i*32+1])
                if i==31:
                    faces.append([iv+i*32+j,iv+j,iv,iv+i*32])
                else:
                    faces.append([iv+i*32+j,iv+(i+1)*32+j,iv+(i+1)*32,iv+i*32])
            else:
                edges.append([iv+i*32+j,iv+i*32+j+1])
                if i==31:
                    edges.append([iv+i*32+j,iv+j])
                    faces.append([iv+i*32+j,iv+j,iv+j+1,iv+i*32+j+1])
                else:
                    edges.append([iv+i*32+j,iv+(i+1)*32+j])
                    faces.append([iv+i*32+j,iv+(i+1)*32+j,iv+(i+1)*32+j+1,iv+i*32+j+1])
          
def generate_cilinder_faces(instance, face):          
    None

### INSTANCE STRUCTURES ####

#X= PLANE('',#33);
structure["PLANE"] = "unknown", "AXIS2_PLACEMENT_3D|axis2_placement_3d"

#X = ADVANCED_FACE('',(#18),#32,.F.);
structure["ADVANCED_FACE"] = "unknown","FACE_BOUND|FACE_OUTER_BOUND|data","PLANE|CYLINDRICAL_SURFACE|TOROIDAL_SURFACE|CONICAL_SURFACE|SPHERICAL_SURFACE|SURFACE_OF_REVOLUTION|def", "unknown2"
    
#X = FACE_BOUND('',#19,.F.);
structure["FACE_BOUND"] = "unknown1", "EDGE_LOOP|VERTEX_LOOP|loop", "unknown2"

#X = FACE_OUTER_BOUND('',#1091,.T.);
structure["FACE_OUTER_BOUND"] = "unknown1", "EDGE_LOOP|edge_loop", "unknown2"
    
#X = EDGE_LOOP('',(#20,#55,#83,#111));
structure["EDGE_LOOP"] = "unknown1", "ORIENTED_EDGE|oriented_edges"

#X = VERTEX_LOOP('',#20);
structure["VERTEX_LOOP"] = "unknown1", "VERTEX_POINT|vertex"

#X = ORIENTED_EDGE('',*,*,#21,.F.);
structure["ORIENTED_EDGE"] = "unknown1", "unknown2", "unknown3", "EDGE_CURVE|edge_curve", "unknown5"

#X = CONICAL_SURFACE('',#512,6.052999999999996,45.000000000000142);
structure["CONICAL_SURFACE"] = "unknown1", "AXIS2_PLACEMENT_3D|axis2_placement3d", "unknown2", "uknown3"

#X = EDGE_CURVE('',#22,#24,#26,.T.);
def set_edge(instance):
    global edges
    
    #v1 = get_instance_value(instance, ["v1","vertex_id"])
    #v2 = get_instance_value(instance, ["v2", "vertex_id"])
    #edges.append([v1,v2])
    
    object = get_instance_value(instance,"object")
    if object["name"] == "SURFACE_CURVE": 
        None
    elif object["name"] == "CIRCLE":
        None
    elif object["name"] == "LINE":
        None
    elif object["name"] == "B_SPLINE_CURVE_WITH_KNOTS":
        None
    elif object["name"] == "ELLIPSE": 
        None
    elif object["name"] == "SEAM_CURVE": 
        None
    else:
        print ("Unkown object")
        
structure["EDGE_CURVE"] = "unknown1", "VERTEX_POINT|v1", "VERTEX_POINT|v2", "SURFACE_CURVE|CIRCLE|LINE|B_SPLINE_CURVE_WITH_KNOTS|ELLIPSE|SEAM_CURVE|object", "unknown5"
structure_func["EDGE_CURVE"] = {"first_load" : set_edge }

#X = CIRCLE('',#3900,13.230000000000002);
structure["CIRCLE"] = "unknown1", "AXIS2_PLACEMENT_3D|AXIS2_PLACEMENT_2D|placement", "unknown2"

#X= ELLIPSE('',#539,7.296415549894075,5.053)
structure["ELLIPSE"] = "unknown1", "AXIS2_PLACEMENT_3D|axis2_placement3d", "r1", "r2"

#X = SURFACE_CURVE('',#27,(#31,#43),.PCURVE_S1.)
def surface_curve_load(instance):
    None
    #print (get_instance_path(instance))

structure["SURFACE_CURVE"] = "unknown", "LINE|CIRCLE|object", "PCURVE|data", "unknown2"
structure_func["SURFACE_CURVE"] = { "load" : surface_curve_load }

#X = SPHERICAL_SURFACE('',#387,4.25);
structure["SPHERICAL_SURFACE"] = "unknown", "AXIS2_PLACEMENT_3D|axis2_placement3d", "float|radi"

#X = TOROIDAL_SURFACE('',#3175,1.399999999999998,0.300000000000002);
structure["TOROIDAL_SURFACE"] = "unknown", "AXIS2_PLACEMENT_3D|axis2_placement3d", "float|r1", "float|r2"

#X = SURFACE_OF_REVOLUTION('',#34,#39);
structure["SURFACE_OF_REVOLUTION"] = "unknown", "circle|circle", "AXIS1_PLACEMENT_3D|axis"


#X = B_SPLINE_CURVE_WITH_KNOTS('',3,(#),.UNSPECIFIED.,.T.,.U.,(4),(0.0),.UNSPECIFIED.);
# ( B_SPLINE_CURVE_WITH_KNOTS((1),(0.0),.UNSPECIFIED.))
structure ["B_SPLINE_CURVE_WITH_KNOTS"] = []
t = "int_data_unknown", "float_data_unknown", "unknown6"
structure ["B_SPLINE_CURVE_WITH_KNOTS"].append(t)
t= "unknown", "unknown2", "CARTESIAN_POINT|data", "unknown3", "unknown4", "unkown5", "int_data_unknown", "float_data_unknown", "unknown6"
structure ["B_SPLINE_CURVE_WITH_KNOTS"].append(t)

#X = PCURVE('',#32,#37);
structure["PCURVE"] = "unknown","PLANE|SURFACE_OF_REVOLUTION|CYLINDRICAL_SURFACE|object","DEFINITIONAL_REPRESENTATION|def_representation"

#X = SEAM_CURVE('',#27,(#32,#48),.PCURVE_S1.);
def seam_curve_load(instance):
    #Assing to object to retrieve information 
    #print_instance(instance)
    pcurves = get_instance_value(instance, "pcurve")
    for pcurve in pcurves:
        obj = get_instance_value(pcurve,"object")
        obj["data"]["seam_curve"] = instance
     
structure["SEAM_CURVE"] = "unknown", "CIRCLE|LINE|circle", "PCURVE|pcurve", "unknown2"
structure_func["SEAM_CURVE"] = {"first_load" : seam_curve_load }

#X = SURFACE_OF_REVOLUTION('',#34,#39);
structure["SURFACE_OF_REVOLUTION"] = "unknown", "CIRCLE|circle", "AXIS1_PLACEMENT|axis"

#X = DEFINITIONAL_REPRESENTATION('',(#38),#42);
structure["DEFINITIONAL_REPRESENTATION"] = "unkown", "LINE|multiple|data", None

#X = LINE('',#28,#29);
structure["LINE"] = "unknown1", "CARTESIAN_POINT|cartesian_point", "VECTOR|vector"

#X = VECTOR('',#30,1.);
structure["VECTOR"] = "unknown1", "DIRECTION|direction", "value"

#X = VERTEX_POINT('',#23);
def set_vertex_index (instance):
    global vertexs
    co = get_instance_value(instance, ["cartesian_point","coordinates"])
    vertexs.append ([co[0], co[1], co[2]])
    instance["data"]["vertex_id"] = len(vertexs)-1

structure["VERTEX_POINT"] = "unknown1","CARTESIAN_POINT|cartesian_point"
structure_func["VERTEX_POINT"] = {"first_load" : set_vertex_index}
structure_params["VERTEX_POINT"] = {"print_verbose" : 1}

#X = CLOSED_SHELL('',(#17,#137,#237,#284,#331,#338));
structure["CLOSED_SHELL"] = "unknown", "ADVANCED_FACE|data"

#X = MANIFOLD_SOLID_BREP('',#16);
def set_faces (instance):
    print ("Solid data")
    for face in get_instance_value(instance, ["closed_shell", "data"]):
        if (face["name"] == "ADVANCED_FACE"):
            obj = get_instance_value(face,"def")
            if obj["name"] == "PLANE":
                for fb in get_instance_value(face,["data"]):
                    if (fb["name"] == "FACE_BOUND"):
                        oedges = get_instance_value(fb, ["loop","oriented_edges"])
                        if oedges:
                            loop = False
                            for oe in oedges:
                                edge_curve = get_instance_value(oe, "edge_curve")
                                surf = get_instance_value(edge_curve,"object")
                                object = get_instance_value(surf,"object")
                                if object and object["name"] == "CIRCLE": 
                                    print ("A Circle")
                                elif object and object["name"] == "LINE":
                                    loop = True
                                elif object:
                                    print("unknown " + object["name"])
                            if loop:
                                faces.append(get_edge_loop_verts(get_instance_value(fb, ["loop"])))
                    elif (fb["name"] == "FACE_OUTER_BOUND"):
                        None
                        #faces.append(get_edge_loop_verts(get_instance_value(fb, ["edge_loop"])))
                    else:
                        print ("Unknown instance "  + fb["name"])
            elif obj["name"] == "TOROIDAL_SURFACE":
                generate_torus_faces(obj, face)
            elif obj["name"] == "CYLINDRICAL_SURFACE":
                generate_cilinder_faces(obj, face)
            else:
                print ("Unknow definition " + obj["name"])
        else:
            print ("Unknown instance")
        
structure["MANIFOLD_SOLID_BREP"] = "unknown", "CLOSED_SHELL|closed_shell"
structure_func["MANIFOLD_SOLID_BREP"] = {"first_load" : set_faces}

#X = DIRECTION('',(1.,0.,-0.));
structure["DIRECTION"] = "unknown", "float|values"
structure_params["DIRECTION"] = {"print_verbose" : 2}

#X = CARTESIAN_POINT('',(0.,0.,0.));
#X = CARTESIAN_POINT('',(0.,0.));
def cartesian_point_load(instance):
    None
    
structure["CARTESIAN_POINT"] = "unknown", "float|coordinates"
structure_params["CARTESIAN_POINT"] = {"print_verbose" : 2}
structure_func["CARTESIAN_POINT"] = {"load" : cartesian_point_load}

#X = AXIS1_PLACEMENT('',#40,#41);
structure["AXIS1_PLACEMENT"] = "name", "CARTESIAN_POINT|point", "DIRECTION|dir"
structure_params["AXIS2_PLACEMENT_3D"] = {"print_verbose" : 1}

#X = AXIS2_PLACEMENT_3D('',#12,#13,#14);
structure["AXIS2_PLACEMENT_3D"] = "name", "CARTESIAN_POINT|point", "DIRECTION|dir1", "DIRECTION|dir2"
structure_params["AXIS2_PLACEMENT_3D"] = {"print_verbose" : 1}

#X = AXIS2_PLACEMENT_2D('',#51,#52);
structure["AXIS2_PLACEMENT_2D"] = "str|unknown", "CARTESIAN_POINT|point", "DIRECTION|dir"
structure_params["AXIS2_PLACEMENT_3D"] = {"print_verbose" : 1}

#X = APPLICATION_CONTEXT('core data for automotive mechanical design processes');
structure["APPLICATION_CONTEXT"] = "description",

#X = MECHANICAL_CONTEXT('',#2,'mechanical');
structure["MECHANICAL_CONTEXT"] =  "unknown", "APPLICATION_CONTEXT|application_context", "name"

#X = PRODUCT_CONTEXT('',#5,'mechanical');
structure["PRODUCT_CONTEXT"] = "unknown", "APPLICATION_CONTEXT|application_context", "name"

#X = PRODUCT('Cube','Cube','',(#8));
def set_product_name(instance):
    global object_name
    object_name = get_instance_value(instance,"name")

structure["PRODUCT"] = "str|name", "description", "unknown1", "PRODUCT_CONTEXT|MECHANICAL_CONTEXT|contexts"
structure_func["PRODUCT"] = {"first_load": set_product_name}

#X = PRODUCT_TYPE('part',$,(#7));
structure["PRODUCT_TYPE"] = "type", "unknwown1", "PRODUCT|products"

#X = PRODUCT_DEFINITION_FORMATION('','',#7);
structure["PRODUCT_DEFINITION_FORMATION"] = "unknown1", "unknown2", "PRODUCT|product"

#X = PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE(' ','NONE',#161,.NOT_KNOWN.);
structure["PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE"] = "unknown1", "unknown2", "PRODUCT|product", "unknown4"

#X = PRODUCT_DEFINITION_CONTEXT('part definition',#2,'design')
structure["PRODUCT_DEFINITION_CONTEXT"] = "name", "APPLICATION_CONTEXT|application_context", "type"

#X = PRODUCT_DEFINITION('design','',#6,#9);
structure["PRODUCT_DEFINITION"] = "type", "unknown1", "PRODUCT_DEFINITION_FORMATION|PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE|formation", "PRODUCT_DEFINITION_CONTEXT|context"

#X = PRODUCT_DEFINITION_SHAPE('','',#5);
structure["PRODUCT_DEFINITION_SHAPE"] = "name", "desc", "PRODUCT_DEFINITION|NEXT_ASSEMBLY_USAGE_OCCURRENCE|product_definition"

#X = NEXT_ASSEMBLY_USAGE_OCCURRENCE('SIEM-PM-L00135:1','SIEM-PM-L00135:1','SIEM-PM-L00135:1',#12,#126,'SIEM-PM-L00135:1');
structure["NEXT_ASSEMBLY_USAGE_OCCURRENCE"] = ["name","desc","unknown_str1","PRODUCT_DEFINITION|product_definition_1", "PRODUCT_DEFINITION|product_definition_2", "unknown_str2"]

#X = ADVANCED_BREP_SHAPE_REPRESENTATION('',(#11,#15),#345);
def init_object(instance):
    global object_name
    print ("Loading Object " + object_name)
    global vertexs, edges, faces
    vertexs = []
    edges = []
    faces = []
    
    for i in range(0,3):
        object_location[i] = 0
    
def import_shape(instance):
    global object_name
    print ("Importing: " + object_name)
    if object_name == "inafag_6010_brbohxyclh6y8oik8swwpry0n_1":
        None
        #print_instance (instance,4)
    
    import_data_to_blender()

structure["ADVANCED_BREP_SHAPE_REPRESENTATION"] = "unknown1", "AXIS2_PLACEMENT_3D|MANIFOLD_SOLID_BREP|data", "multiple|unknown2"
structure_func["ADVANCED_BREP_SHAPE_REPRESENTATION"] = {"init" : init_object, "first_load" : import_shape }

#X = SHAPE_REPRESENTATION('',(#37,#977,#1751,#3984),#36);
def set_shape_name(instance):
    definition = get_instance_value(instance, "shape_definition_representation")
    if definition:
        set_product_name(get_instance_value(definition,["product_definition_shape", "product_definition", "formation", "product"]))
                    

structure["SHAPE_REPRESENTATION"] = "unknown1", "AXIS2_PLACEMENT_3D|data", "multiple|unknown2"
structure_func["SHAPE_REPRESENTATION"] = {"load" : set_shape_name }

#X = SHAPE_DEFINITION_REPRESENTATION(#4,#10);
def set_shape_representation_parent(instance):
    ## Allow get the shape definition representation, when accessing from SHAPE_REPRESENTATION_RELATIONSHIP
    shape = get_instance_value(instance,"representation");
    if shape["name"] == "SHAPE_REPRESENTATION":
        shape["data"]["shape_definition_representation"] = instance

structure["SHAPE_DEFINITION_REPRESENTATION"] = "PRODUCT_DEFINITION_SHAPE|product_definition_shape", "SHAPE_REPRESENTATION|ADVANCED_BREP_SHAPE_REPRESENTATION|representation"
structure_func["SHAPE_DEFINITION_REPRESENTATION"] = {"first_load" : set_shape_representation_parent}

#X = MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',(#78,#887,#1748,#2092,#2394,#2684,#2685,#3225,#3226,#3227,#3228,#3969),#67);
structure["MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION"] = "unknown1", "STYLED_ITEM|data", "multiple|unknown2"

#X = PRESENTATION_STYLE_ASSIGNMENT((#76));
structure["PRESENTATION_STYLE_ASSIGNMENT"] = "SURFACE_STYLE_USAGE|CURVE_STYLE|styles"

#X= SURFACE_STYLE_USAGE(.BOTH.,#355);
structure["SURFACE_STYLE_USAGE"] = "unknown", "SURFACE_SIDE_STYLE|side_style"

#X = SURFACE_SIDE_STYLE('',(#356));
#X = SURFACE_SIDE_STYLE('192,192,192',(#3221));
structure["SURFACE_SIDE_STYLE"] = "unknown", "SURFACE_STYLE_FILL_AREA|styles"

#X = SURFACE_STYLE_FILL_AREA(#357);
structure["SURFACE_STYLE_FILL_AREA"] = "FILL_AREA_STYLE|area_style"

#X = FILL_AREA_STYLE('',(#358));
structure["FILL_AREA_STYLE"] = "unknown", "FILL_AREA_STYLE_COLOUR|data"

#X = FILL_AREA_STYLE_COLOUR('',#359);
structure["FILL_AREA_STYLE_COLOUR"] = "unknown", "COLOUR_RGB|color"

#X = COLOUR_RGB('',0.800000011921,0.800000011921,0.800000011921);
structure["COLOUR_RGB"] = "unknown", "red", "green", "blue"

#X = CURVE_STYLE('',#361,POSITIVE_LENGTH_MEASURE(0.1),#359);
structure["CURVE_STYLE"] = "unknown","DRAUGHTING_PRE_DEFINED_CURVE_FONT|curve_font", "unknown_func", "COLOUR_RGB|color"

#X = STYLED_ITEM('',(#77),#73);
structure["STYLED_ITEM"] = "unknown1", "PRESENTATION_STYLE_ASSIGNMENT|data", "TRIMMED_CURVE|MANIFOLD_SOLID_BREP|ADVANCED_FACE|object"

#X = DRAUGHTING_PRE_DEFINED_CURVE_FONT('continuous');
structure["DRAUGHTING_PRE_DEFINED_CURVE_FONT"] = "unkown",

#X = TRIMMED_CURVE('',#970,(PARAMETER_VALUE(0.0),#967),(PARAMETER_VALUE(1.0),#971),.T.,.PARAMETER.);
structure["TRIMMED_CURVE"] = "unknown1", "LINE|line", "func|CARTESIAN_POINT|p1_data", "func|CARTESIAN_POINT|p2_data", "unknown1", "unknown2"
  
#X = CYLINDRICAL_SURFACE('',#3893,13.230000000000002);
structure["CYLINDRICAL_SURFACE"] = "unknown1", "AXIS2_PLACEMENT_3D|axis2_placement_3d", "float|radi"
  
#X = SHAPE_REPRESENTATION_RELATIONSHIP('SRR','None',#2093,#1838);
structure["SHAPE_REPRESENTATION_RELATIONSHIP"] = "unknown1", "unknown2", "ADVANCED_BREP_SHAPE_REPRESENTATION|GEOMETRICALLY_BOUNDED_SURFACE_SHAPE_REPRESENTATION|shape","SHAPE_REPRESENTATION|shape_representation"

#X = GEOMETRICALLY_BOUNDED_SURFACE_SHAPE_REPRESENTATION('GBSSR',(#80),#36);
structure["GEOMETRICALLY_BOUNDED_SURFACE_SHAPE_REPRESENTATION"] = "unknown", "GEOMETRIC_SET|geomteric_set", "multiple|unknown2"

#X = GEOMETRIC_SET('GEOSET',(#73,#112));
structure["GEOMETRIC_SET"]= "unknown","TRIMMED_CURVE|data"

#( GEOMETRIC_REPRESENTATION_CONTEXT (3))
structure["GEOMETRIC_REPRESENTATION_CONTEXT"]= "int|unknown",

#( GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#31)) )
structure["GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT"] = "UNCERTAINTY_MEASURE_WITH_UNIT|mesure",

# ( GLOBAL_UNIT_ASSIGNED_CONTEXT((#28,#29,#30)) )
structure["GLOBAL_UNIT_ASSIGNED_CONTEXT"] = "multiple|unit_data",

#X = UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),#28,'distance_accuracy_value','confusion accuracy');
structure["UNCERTAINTY_MEASURE_WITH_UNIT"] = "func|leng_measure", "multiple|units", "str|unknown1", "str|unknown2"

#( LENGTH_UNIT())
structure["LENGTH_UNIT"] =  None

# (PLANE_ANGLE_UNIT() )
structure["PLANE_ANGLE_UNIT"] = None

# (SOLID_ANGLE_UNIT() )
structure["SOLID_ANGLE_UNIT"] = None

#( CONVERSION_BASED_UNIT('MILLIMETRE',#178) )
structure["CONVERSION_BASED_UNIT"] = "str|unit", "LENGTH_MEASURE_WITH_UNIT|lengh_mesure"

#181 = DIMENSIONAL_EXPONENTS(1.0,0.0,0.0,0.0,0.0,0.0,0.0);
structure["DIMENSIONAL_EXPONENTS"] = "float|a1", "float|a2", "float|a3", "float|a4", "float|a5", "float|a6", "float|a7"

#178=LENGTH_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.0),#334);
structure["LENGTH_MEASURE_WITH_UNIT"] = "func|length", "multiple|units"

#( NAMED_UNIT(*) )
#( NAMED_UNIT(#181) )
structure["NAMED_UNIT"] = "DIMENSIONAL_EXPONENTS|unknown",

#(SI_UNIT(.MILLI.,.METRE.))
structure["SI_UNIT"] = "scale", "unit"

#( BOUNDED_CURVE())
structure["BOUNDED_CURVE"] = None

#(B_SPLINE_CURVE(2,(#78,#79,#80,#81,#82,#83,#84),.UNSPECIFIED.,.F.,.F.))
structure["B_SPLINE_CURVE"] = "unknown", "CARTESIAN_POINT|data", "unknown2", "unknow3", "unknown4"

#(CURVE())
structure["CURVE"] = None

#(GEOMETRIC_REPRESENTATION_ITEM() )
structure["GEOMETRIC_REPRESENTATION_ITEM"] = None

#RATIONAL_B_SPLINE_CURVE((1.,0.5,1.,0.5,1.,0.5,1.))
structure["RATIONAL_B_SPLINE_CURVE"] = "float|data",

#(REPRESENTATION_ITEM(''))
structure["REPRESENTATION_ITEM"] = "str|unknown",

#( REPRESENTATION_CONTEXT('Context #1','3D Context with UNIT and UNCERTAINTY') )
structure["REPRESENTATION_CONTEXT"] = "str|name", "str|desc"

### DATA PROCESSING ###

def import_data_to_blender():
    
    global object_name, object_location
    global vertexs, edges, faces    
                
    if not object_name:
        object_name = "Unknown Object"
            

    print ("Importing " + object_name)
    #print (object_location)
            
    me = bpy.data.meshes.new(object_name)    
    ob = bpy.data.objects.new(object_name, me)
    scn = bpy.context.scene
    scn.objects.link(ob)
    scn.objects.active = ob
    ob.select = True 

    #print (vertexs)
    #print (edges)
    #print (faces)
    me.from_pydata(vertexs, edges, faces)

    me.validate()    
    me.update()

          
def process_stp_data():
    
    for instance in instances:            
        if instance["name"] == "SHAPE_DEFINITION_REPRESENTATION":
            load_instance(instance)
            
    for instance in instances:
        if instance["name"] == "SHAPE_REPRESENTATION_RELATIONSHIP":
            load_instance(instance)
            
    return
               
            
    #printed = []
    #for instance in instances:
    #    if instance["name"] and not instance["data"] and not instance["name"] in printed:
    #        printed.append(instance["name"])
    #        print ("Not loaded instance " + instance["number"] + instance["name"])
            

### MAIN FUNC ####

def read_stp(filepath): 
    
    instances=[]
   
    f = open(filepath, 'rb')
    line = read_stp_line(f)
    if (line == "ISO-10303-21"):
        print ("Reading ISO-10303-21 file")
    else:
        print ("Not recognized " + line + "- abort")
        return

    line = read_stp_line(f)
    if (line == "HEADER"):
        read_stp_header(f)
    else:
        print ("Error: Expected header")

    line = read_stp_line(f)
    if (line == "DATA"):
        read_stp_data(f)
    else:
        print ("Error Expected data")
    
    process_stp_data()
    
    print ("Done!")

if __name__ == '__main__':
    import sys
    import bpy

    #filepaths = sys.argv[sys.argv.index('--') + 1:]
    
    #for filepath in filepaths:
    #    read_stp(filepath)
    
    test_folder = "/home/jaume/src/mechanical-blender-addons/io_scene_stp/test_files/"
        
    #read_stp(test_folder + "cube.stp")
    #read_stp(test_folder + "torus.stp")
    #read_stp(test_folder + "revolve.stp")
    read_stp(test_folder + "cylinder.stp")
    #read_stp(test_folder + "SIEM-CONJ-L00025.stp")
    #read_stp(test_folder + "inafag_6010_brbohxyclh6y8oik8swwpry0n.stp")
    