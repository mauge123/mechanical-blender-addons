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

import pprint
pp = pprint.PrettyPrinter(indent=4)

structure = {}
structure_func = {}

instances = []
data = []   # Instance blender data

object_name = ""
vertexs = [] # Mesh Vertices
edges = [] # Mesh Edges
faces = [] # Mesh Faces

#Stores MANIFOLD_SOLID_BREP processed instance numbers
solids = []  

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
    instances.insert(id,{"name" : name, "params" : params,  "line" : line, "data" : data, "number" : number}) 

def get_instance(number):
    global instances
    instance = instances[get_instance_number(number)]
    if (number != instance["number"]):
        print ("Error: Expected " + number + ", found " + instance["number"])
    
    return instance
    
def check_instance_name (instance, name):
     if (instance["name"] != name):
        print ("ERROR: expected " + name + ", found "+ instance["name"] + instance["number"])
   
def load_instance(instance, parent = None):
    if instance["name"] in structure:
        if not instance["data"]:
            instance["data"] = {}
            if not (len(structure[instance["name"]]) == len(instance["params"])):
                print ("Diferent number of parameters in " + instance["number"]+" " +instance["name"])
            for idx,n  in enumerate(structure[instance["name"]]):
                if n:
                    n_exp = n.split("|")
                    n = n_exp.pop()
                    param = instance["params"][idx]
                    if isinstance(param, list):
                        instance["data"][n] = []
                        for a in instance["params"][idx]:
                            if a[0] == '#':
                                new_instance = load_instance(get_instance(a),instance)
                                if len(n_exp) and not new_instance["name"] in n_exp:
                                    print ("Error: not expected " + new_instance["name"] + " in " +  instance["number"] + " " + instance ["name"])
                                elif not len(n_exp):
                                    print ("loading object " + new_instance["name"] +" with no instance name defined in " + instance["number"] + " " + instance["name"])
                                instance["data"][n].append(new_instance)
                            else:
                                if len(n_exp):
                                    print ("Error: Expected instance")
                                instance["data"][n].append(a)
                    elif param[0] == '#':
                        new_instance = load_instance(get_instance(param), instance)
                        if len(n_exp) and not new_instance["name"] in n_exp:
                            print ("Error: not expected " + new_instance["name"] + "in " + instance["number"] + " " + instance["name"])
                        elif not len(n_exp):
                            print ("loading object " + new_instance["name"] + " with no instance name defined in " + instance["number"] + " " + instance["name"])
                        instance["data"][n] = new_instance
                    else:
                        if len(n_exp):
                            print ("Error: Expected instance")
                        instance["data"][n] = param
            if instance["name"] in structure_func:
                structure_func[instance["name"]](instance)
    else:
        print ("Not defined instance " + instance["number"] + " " +instance["name"])
        print ("loaded fom " + parent["number"] + " " + parent["name"])

    return instance

def get_instance_value(instance,path, index=0):
    if isinstance(path, list): 
        value = instance["data"][path[index]]
        if index+1 < len(path):
            value = get_instance_value(value,path, index+1)
    else:
        value = instance["data"][path]
        
    return value

def print_instance(instance, max_levels=-1, name = "", level =0):
    if max_levels > -1 and level > max_levels:
        return
    
    spaces=""
    for i in range(level):
        spaces=spaces+"|"
    print (spaces + name + instance["number"] + " " + instance["name"])
    spaces=spaces+"|"
    for name in instance["data"]:
        value = instance["data"][name]
        if isinstance(value, str):
            print (spaces + name + ":" + value) 
        elif isinstance(value,list):
            for idx,value2 in enumerate(value):
                if isinstance(value2, str):
                    print (spaces+name+"["+str(idx)+"]:"+value2)
                else:
                    print_instance(value2, max_levels, name + "["+str(idx)+"]:", level+1)
        else:
            print_instance(value, max_levels, name + ":", level+1)

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
            ## Unknown at this moment
            #X = ( GEOMETRIC_REPRESENTATION_CONTEXT(2) PARAMETRIC_REPRESENTATION_CONTEXT() REPRESENTATION_CONTEXT('2D SPACE','') );
            add_instance(line, name= "", params = [], data="", number=parsed[0])
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
        if (str[i] == ","):
            if (v):
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



### INSTANCE STRUCTURES ####

#X= PLANE('',#33);
structure["PLANE"] = ["unknown", "AXIS2_PLACEMENT_3D|axis2_placement_3d"]

#X = ADVANCED_FACE('',(#18),#32,.F.);
structure["ADVANCED_FACE"] = ["unknown","FACE_BOUND|data","PLANE|plane", "unknown2"]
    
#X = FACE_BOUND('',#19,.F.);
structure["FACE_BOUND"] = ["unknown1", "EDGE_LOOP|edge_loop", "unknown2"]
    
#X = EDGE_LOOP('',(#20,#55,#83,#111));
structure["EDGE_LOOP"] = ["unknown1", "ORIENTED_EDGE|oriented_edges"]

#X = ORIENTED_EDGE('',*,*,#21,.F.);
structure["ORIENTED_EDGE"] = ["unknown1", "unknown2", "unknown3", "EDGE_CURVE|edge_curve", "unknown5"]
    
#X = EDGE_CURVE('',#22,#24,#26,.T.);
def set_edge_index(instance):
    global edges
    v1 = get_instance_value(instance, ["v1","vertex_id"])
    v2 = get_instance_value(instance, ["v2", "vertex_id"])
    edges.append([v1,v2])
    instance["data"]["edge_id"] = len(edges) -1
        
structure["EDGE_CURVE"] = ["unknown1", "VERTEX_POINT|v1", "VERTEX_POINT|v2", "SURFACE_CURVE|surface_curve", "unknown5"]
structure_func["EDGE_CURVE"] = set_edge_index

#X = SURFACE_CURVE('',#27,(#31,#43),.PCURVE_S1.)
structure["SURFACE_CURVE"] = ["unknown", "LINE|line", "PCURVE|data", "unknown2"]

#X = PCURVE('',#32,#37);
structure["PCURVE"] = ["unknown","PLANE|plane","DEFINITIONAL_REPRESENTATION|def_representation"]

#X = DEFINITIONAL_REPRESENTATION('',(#38),#42);
structure["DEFINITIONAL_REPRESENTATION"] = ["unkown", "LINE|data", None]

#X = LINE('',#28,#29);
structure["LINE"] = ["unknown1", "CARTESIAN_POINT|cartesian_point", "VECTOR|vector"]

#X = VECTOR('',#30,1.);
structure["VECTOR"] = ["unknown1", "DIRECTION|direction", "value"]

#X = VERTEX_POINT('',#23);
def set_vertex_index (instance):
    global vertexs
    co = get_instance_value(instance, ["cartesian_point","coordinates"])
    vertexs.append ([float(co[0]), float(co[1]), float(co[2])])
    instance["data"]["vertex_id"] = len(vertexs)-1

structure["VERTEX_POINT"] = ["unknown1","CARTESIAN_POINT|cartesian_point"]
structure_func["VERTEX_POINT"] = set_vertex_index

#X = CLOSED_SHELL('',(#17,#137,#237,#284,#331,#338));
structure["CLOSED_SHELL"] = ["unknown", "ADVANCED_FACE|data"]

#X = MANIFOLD_SOLID_BREP('',#16);
def set_faces (instance):
     for face in get_instance_value(instance, ["closed_shell", "data"]):
        if (face["name"] == "ADVANCED_FACE"):
            for fb in get_instance_value(face,["data"]):
                if (fb["name"] == "FACE_BOUND"):
                    faces.append(get_edge_loop_verts(get_instance_value(fb, ["edge_loop"])))
                else:
                    print ("Unknon instance")
        else:
            print ("Unknown instance")
            
    
            
structure["MANIFOLD_SOLID_BREP"] = ["unknown", "CLOSED_SHELL|closed_shell"]
structure_func["MANIFOLD_SOLID_BREP"] = set_faces

#X = DIRECTION('',(1.,0.,-0.));
structure["DIRECTION"] = ["unknown", "values"]

#X = CARTESIAN_POINT('',(0.,0.,0.));
structure["CARTESIAN_POINT"] = ["unknown", "coordinates"]

#X = AXIS2_PLACEMENT_3D('',#12,#13,#14);
structure["AXIS2_PLACEMENT_3D"] = ["name", "CARTESIAN_POINT|point", "DIRECTION|dir1", "DIRECTION|dir2"]

#X = APPLICATION_CONTEXT('core data for automotive mechanical design processes');
structure["APPLICATION_CONTEXT"] = ["description"]

#X = MECHANICAL_CONTEXT('',#2,'mechanical');
structure["MECHANICAL_CONTEXT"] =  ["unknown", "APPLICATION_CONTEXT|application_context", "name"]

#X = PRODUCT_CONTEXT('',#5,'mechanical');
structure["PRODUCT_CONTEXT"] = ["unknown", "application_context", "name"]

#X = PRODUCT('Cube','Cube','',(#8));
def set_product_name(instance):
    global object_name
    object_name = get_instance_value(instance,"name")

structure["PRODUCT"] = ["name", "description", "unknown1", "PRODUCT_CONTEXT|MECHANICAL_CONTEXT|contexts"]
structure_func["PRODUCT"] = set_product_name

#X = PRODUCT_TYPE('part',$,(#7));
structure["PRODUCT_TYPE"] = ["type", "unknwown1", "PRODUCT|products"]

#X = PRODUCT_DEFINITION_FORMATION('','',#7);
structure["PRODUCT_DEFINITION_FORMATION"] = ["unknown1", "unknown2", "product"]

#X = PRODUCT_DEFINITION_CONTEXT('part definition',#2,'design')
structure["PRODUCT_DEFINITION_CONTEXT"] = ["name", "application_context", "type"]

#X = PRODUCT_DEFINITION('design','',#6,#9);
structure["PRODUCT_DEFINITION"] = ["type", "unknown1", "product_definition_formation", "product_definition_context"]

#X = PRODUCT_DEFINITION_SHAPE('','',#5);
structure["PRODUCT_DEFINITION_SHAPE"] = ["unknown1", "unknown2", "product_definition"]

#X = ADVANCED_BREP_SHAPE_REPRESENTATION('',(#11,#15),#345);
structure["ADVANCED_BREP_SHAPE_REPRESENTATION"] = ["unknown1"," AXIS2_PLACEMENT_3D|MANIFOLD_SOLID_BREP|data", None]

#X = SHAPE_REPRESENTATION('',(#37,#977,#1751,#3984),#36);
structure["SHAPE_REPRESENTATION"] = ["unknown1", "data", None]

#X = SHAPE_DEFINITION_REPRESENTATION(#4,#10);
structure["SHAPE_DEFINITION_REPRESENTATION"] = ["product_definition_shape", "SHAPE_REPRESENTATION|ADVANCED_BREP_SHAPE_REPRESENTATION|shape_representation"]

#X = MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',(#78,#887,#1748,#2092,#2394,#2684,#2685,#3225,#3226,#3227,#3228,#3969),#67);
structure["MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION"] = ["unknown1", "STYLED_ITEM|data", None]

#X = PRESENTATION_STYLE_ASSIGNMENT((#76));
structure["PRESENTATION_STYLE_ASSIGNMENT"] = ["SURFACE_STYLE_USAGE|CURVE_STYLE|styles"]

#X= SURFACE_STYLE_USAGE(.BOTH.,#355);
structure["SURFACE_STYLE_USAGE"] = ["unknown", "SURFACE_SIDE_STYLE|side_style"]

#X = SURFACE_SIDE_STYLE('',(#356));
structure["SURFACE_SIDE_STYLE"] = ["unknown", "SURFACE_STYLE_FILL_AREA|styles"]

#X = SURFACE_STYLE_FILL_AREA(#357);
structure["SURFACE_STYLE_FILL_AREA"] = ["FILL_AREA_STYLE|area_style"]

#X = FILL_AREA_STYLE('',(#358));
structure["FILL_AREA_STYLE"] = ["unknown", "FILL_AREA_STYLE_COLOUR|data"]

#X = FILL_AREA_STYLE_COLOUR('',#359);
structure["FILL_AREA_STYLE_COLOUR"] = ["unknown", "COLOUR_RGB|color"]

#X = COLOUR_RGB('',0.800000011921,0.800000011921,0.800000011921);
structure["COLOUR_RGB"] = ["unknown", "red", "green", "blue"]

#X = CURVE_STYLE('',#361,POSITIVE_LENGTH_MEASURE(0.1),#359);
structure["CURVE_STYLE"] = ["unknown","DRAUGHTING_PRE_DEFINED_CURVE_FONT|curve_font", "unknown_func", "COLOUR_RGB|color"]

#X = STYLED_ITEM('',(#77),#73);
structure["STYLED_ITEM"] = ["unknown1", "PRESENTATION_STYLE_ASSIGNMENT|data", "TRIMMED_CURVE|MANIFOLD_SOLID_BREP|object"]

#X = DRAUGHTING_PRE_DEFINED_CURVE_FONT('continuous');
structure["DRAUGHTING_PRE_DEFINED_CURVE_FONT"] = ["unkown"]
  
### DATA PROCESSING ###
          
def process_stp_data():
    
    global vertexs, edeges, faces, object_name
    
    for instance in instances:
        if instance["name"] == "PRODUCT_TYPE":
            # loads part name
            load_instance(instance)
            if get_instance_value(instance, ["type"]) == "'part'":
                None
            else:
                print ("Unknown product type: "  + get_instance_value(instance, ["type"]))
                
    for instance in instances:

        if instance["name"] == "MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION":
            vertexs = []
            edges = [] 
            faces = []    
            
            #fills object data
            load_instance(instance)
            
            if not object_name:
                object_name = "Unknown Object"
                
            print ("Importing " + object_name)
            
            continue
        
            me = bpy.data.meshes.new(object_name)    
            ob = bpy.data.objects.new(object_name, me)
            scn = bpy.context.scene
            scn.objects.link(ob)
            scn.objects.active = ob
            ob.select = True 
    
            me.from_pydata(vertexs, edges, faces)

            me.validate()    
            me.update()
            

        
        if (False and instance["name"] == "SHAPE_DEFINITION_REPRESENTATION"):
            #object is loaded previosly
            load_instance(instance)
                
               
            
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
        
    read_stp(test_folder + "cube.stp")
    #read_stp(test_folder + "SIEM-CONJ-L00025.stp")
    
    