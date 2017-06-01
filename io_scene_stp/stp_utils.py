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

instances = []
data = []   # Instance blender data

vertexs = [] # Mesh Vertices
edges = [] # Mesh Edges
faces = [] # Mesh Faces

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

### INSTANCE STRUCTURES ####

#X = ADVANCED_FACE('',(#18),#32,.F.);
def get_advanced_face(instance):
    if (instance["name"] != "ADVANCED_FACE"):
        print ("ERROR: expected ADVANCED_FACE, found "+ instance["name"] + instance["number"])
    
    if(not instance["data"]):
        
        face_bounds = []
        face_outer_bound = None
        for number in instance["params"][1]:
            child_instance = get_instance(number)
            if child_instance["name"] == "FACE_BOUND":
                
                if (not face_outer_bound):
                    face_outer_bound = get_face_bound (child_instance, "FACE_BOUND")
                    
                face_bounds.append (get_face_bound(child_instance))
            elif child_instance["name"] == "FACE_OUTER_BOUND":
                face_outer_bound = get_face_bound (child_instance, "FACE_OUTER_BOUND")
            else:
                print ("Ignored: " + child_instance["name"])
            
        instance["data"] = {
            "unknown1" : instance["params"][0],
            "face_bounds" : face_bounds,
            "face_outer_bound": face_outer_bound ,
            "plane" : get_instance(instance["params"][2]),
            "unknown3" : instance["params"][3]
        }
        
    return instance["data"]


# Retuns verts of an edge loop
def get_edge_loop_verts(edge_loop):
    edges = []
    verts = []

    for ed in edge_loop["oriented_edges"]:
        edges.append([
            ed["edge_curve"]["vertex_point_1"]["vertex_id"],
            ed["edge_curve"]["vertex_point_2"]["vertex_id"]
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

    
#X = FACE_BOUND('',#19,.F.);
def get_face_bound(instance, name = "FACE_BOUND"):
    if (instance["name"] != name):
        print ("ERROR: expected " + name + ", found "+ instance["name"] + instance["number"])
        
    if(not instance["data"]):
        
        el = get_edge_loop(get_instance(instance["params"][1]))
        faces.append(get_edge_loop_verts(el))
        
        instance["data"] = {
            "unknown1" : instance["params"][0],
            "edge_loop" : el,
            "unknown2" : instance["params"][2]
        }
        
    return instance["data"]
    
#X = EDGE_LOOP('',(#20,#55,#83,#111));
def get_edge_loop(instance):
    if (instance["name"] != "EDGE_LOOP"):
        print ("ERROR: expected EDGE_LOOP, found " + instance["name"])
        
    oriented_edges = []
    for v in instance["params"][1]:
        oriented_edges.append(get_oriented_edge(get_instance(v)))
        
    if(not instance["data"]):
        instance["data"] = {
            "unknown1" : instance["params"][0],
            "oriented_edges" : oriented_edges
        }
    
    return instance["data"]

#X = ORIENTED_EDGE('',*,*,#21,.F.);
def get_oriented_edge(instance):
    if (instance["name"] != "ORIENTED_EDGE"):
        print ("ERROR: expected ORIENTED_EDGE, found " + instance["name"])
    
    if(not instance["data"]):
        instance["data"] = {
            "unknown1" : instance["params"][0],
            "unknown2" : instance["params"][1],
            "unknown3" : instance["params"][2],
            "edge_curve" : get_edge_curve(get_instance(instance["params"][3])),
            "unknown5" : instance["params"][4]
        }
        
    return instance["data"]
    
#X = EDGE_CURVE('',#22,#24,#26,.T.);
def get_edge_curve(instance):
    global edges
    if (instance["name"] != "EDGE_CURVE"):
        print ("ERROR: expected EDGE_CURVE, found " + instance["name"])
        
    if(not instance["data"]):
        v1 = get_vertex_point(get_instance(instance["params"][1]))
        v2 = get_vertex_point(get_instance(instance["params"][2]))
        
        edges.append([v1["vertex_id"], v2["vertex_id"]])
        
        instance["data"] = {
            "unknown1" : instance["params"][0],
            "vertex_point_1" : v1,
            "vertex_point_2" : v2,
            "surface_curve" : get_instance(instance["params"][3]),
            "unknown5" : instance["params"][4],
            "edge_id" : len(edges)-1
        }
        
    return instance["data"]

#X = VERTEX_POINT('',#23);
def get_vertex_point(instance):
    global vertexs
    
    if (instance["name"] != "VERTEX_POINT"):
        print ("ERROR: expecte VERTEX_POINT, found " + instance["name"])
                    
    if(not instance["data"]):
        cartesian_point = get_cartesian_point(get_instance(instance["params"][1]))

        vertexs.append ([cartesian_point["x"], cartesian_point["y"], cartesian_point["z"]])
        
        instance["data"] = {
            "unknown1" : instance["params"][0],
            "cartesian_point" : cartesian_point,
            "vertex_id" : len(vertexs)-1
        }
    
    return instance["data"];

#X = CARTESIAN_POINT('',(0.,0.,0.));
def get_cartesian_point(instance):
    if (instance["name"] != "CARTESIAN_POINT"):
        print ("ERROR: expected CARTESIAN_POINT, found " + instance["name"])
        
    if(not instance["data"]):
        instance["data"] = {
            "unknown1" : instance["params"][0],
            "x" : float(instance["params"][1][0]),
            "y" : float(instance["params"][1][1]),
            "z" : float(instance["params"][1][2])
        }
      
    return instance["data"]
  
### DATA PROCESSING ###
   
def process_stp_data_advanced_face (instance):
    print ("Importing ADVANCED_FACE" + instance["number"])
    face = get_advanced_face(instance)
          
def process_stp_data():
    for instance in instances:
        if (instance["name"] == "ADVANCED_FACE"):
            process_stp_data_advanced_face(instance)
            
    


### IMPORT TO BLENDER FUNC

def import_stp_data ():
    global vertexs, edges, faces
    
    #print (vertexs)
    #print (edges)
    #print (faces)

    
    me = bpy.data.meshes.new("TEST")    
    ob = bpy.data.objects.new("TEST", me)
    scn = bpy.context.scene
    scn.objects.link(ob)
    scn.objects.active = ob
    ob.select = True 
    
    
    me.from_pydata(vertexs, edges, faces)
    
    me.validate()    
    me.update()

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
    import_stp_data()
    
    print ("Done!")

if __name__ == '__main__':
    import sys
    import bpy

    #filepaths = sys.argv[sys.argv.index('--') + 1:]
    
    #for filepath in filepaths:
    #    read_stp(filepath)
        
    #read_stp("/home/jaume/tmp/cube.stp")
    read_stp("/home/jaume/Downloads/SIEM-CONJ-L00025.stp")