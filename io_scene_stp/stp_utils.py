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

torus_from_outbound = 1
cylindrical_faces_from_outbound = 1
circular_ring = 1

### UTILS ####

def p3_p3_dist (a,b):
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)

def v3_len(a):
    return math.sqrt (a[0]**2 + a[1]**2 + a[2]**2) 

def sub_v3_v3(a,b):
    return [a[0]-b[0], a[1]-b[1], a[2]-b[2]] 

def add_v3_v3(a,b):
    return [a[0]+b[0], a[1]+b[1], a[2]+b[2]] 

def v3_from_p3_p3 (a,b):
    return [b[0]-a[0], b[1]-a[1], b[2]-a[2]]

def is_parallel_v3 (a,b):
    return math.fabs(np.dot(a,b)) == v3_len(a)*v3_len(b)

def normalize_v3 (a):
    return a / v3_len(a)

def eq_v3 (a,b):
    return a[0]==b[0] and a[1]==b[1] and a[2]==b[2]

def convert_v3_to_v4 (v, val = 0):
    ret = [0,0,0,val]
    ret[0], ret[1], ret[2] = v[0], v[1], v[2]
    return ret

def convert_v4_to_v3 (v):
    ret = [0,0,0]
    ret[0], ret[1], ret[2] = v[0], v[1], v[2]
    return ret    

def convert_m4_to_m3 (m):
    ret = []
    ret.append(convert_v4_to_v3(m[0]))
    ret.append(convert_v4_to_v3(m[1]))
    ret.append(convert_v4_to_v3(m[2]))
    return ret
    

# Cosine Theorem
def a_from_b_c_A (b, c, A):
    return math.sqrt(b**2 + c**2 - 2*b*c*math.cos(A))

# l is length of vectors
def angle_v3_v3 (a, b):
    return math.acos(np.dot(normalize_v3(a),normalize_v3(b))) 

def sin_cos_angle_v3_v3 (a,b):
    au = normalize_v3(a)
    bu = normalize_v3(b)
    cos = np.dot(au,bu)
    sin = math.sqrt(1-cos**2)
    
    if sin > 0:
        #correct sign
        #given the sign on of cos of a 90 degrees rotated vector
        a90  = np.dot (rotation_matrix_axis(np.cross (au,bu), math.pi /2), au)
        cos2 = np.dot(a90,bu)
        if cos2 < 0:
            sin = -sin
        
    return sin, cos 

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
                
def load_referenced_instance(instance, number, n_exp, var_name):
    new_instance = load_instance(get_instance(number),instance, var_name)
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
            #load with 0.001 prec
            value  = int(value*1000) / 1000.0
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

def fill_instance_data(instance, st):
    if not st:
        return    
    
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
                c = 0
                for a in instance["params"][idx]:
                    c = c +1
                    if a[0] == '#':
                        instance["data"][n].append(load_referenced_instance(instance,a, n_exp, n + "["+str(c)+"]"))
                    else:
                        instance["data"][n].append(check_instance_value(instance, a, n_exp))
                
            elif param[0] == '#':
                instance["data"][n] = load_referenced_instance(instance, param, n_exp, n)
            else:
                instance["data"][n] = check_instance_value(instance, param, n_exp)

   
def load_instance(instance, parent = None, var_name = None):
    
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
            
            if parent:
                instance["parent"] = {"instance" : parent, "var_name" : var_name}
            else:
                instance["parent"] = None
                
            execute_instance_functions(instance,"init")
            
            fill_instance_data(instance, st)
                                    
            execute_instance_functions(instance,"first_load")
            execute_instance_functions(instance,"load")
        else:
            if (parent):
                                
                #object was loaded from another side
                if not isinstance(instance["parent"],list):
                    instance["parent"] = [instance["parent"]]
                    
                
                is_new = True
                for child in instance["parent"]:
                    if child["instance"] == parent and child["var_name"] == var_name:
                        is_new = False
                        break
                
                if is_new:
                    instance["parent"].append({"instance" : parent, "var_name" : var_name})
                    #Debug and analisis, fill parent data on nexts objects
                    fill_instance_data(instance, st)
                
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
    
    instance["printed"] = False
            
def get_instance_path (instance, level=0):
    path = instance["number"] + " " + instance["name"]
    if "parent" in instance and instance["parent"]:
        if isinstance(instance["parent"],list):
            # multiple parents
            level = level +1
            for child in instance["parent"]:
                path = path + "\n" + str(level) + ")" + get_instance_path(child["instance"],level)
        else:
            path = path + ">" + get_instance_path(instance["parent"]["instance"], level)
    return path

def print_instance_tree (instance, level=0, var_name = ""):
    spaces = ""
    i=0
    while i < level:
        spaces = spaces + " "
        i = i + 1
        
    if var_name:
        var_name = "=> " + var_name
    
    print (spaces +instance["number"] + " " + instance["name"] + var_name)
    if "parent" in instance and instance["parent"]:
        if isinstance(instance["parent"],list):
            level = level +1
            for child in instance["parent"]:
                print_instance_tree (child["instance"],level, child["var_name"])
        else:
            print_instance_tree(instance["parent"]["instance"], level, instance["parent"]["var_name"])
    else:
        print ("")

# Recursive func to get a parent instance, by name 
def get_parent_instance(instance, name):
    found = None
    if instance["name"]:
        found = instance
    elif instance["parent"]:
        found = get_instance_parent(instance, name)
    
    return found
         

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
def get_ordered_verts_from_edges(edges):
    
    verts = []
    
                
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


def get_plane_from_axis2_placement_3d(instance):
    return np.array(get_instance_value(instance,["dir1","values"]))
    
def get_matrix_from_axis2_placement_3d(instance):
    dir1 = np.array(get_instance_value(instance,["dir1","values"]))
    dir2 = np.array(get_instance_value(instance,["dir2","values"]))
    co = np.array(get_instance_value(instance,["point","coordinates"]))
    
    dir3 = np.cross(dir1,dir2)
    
    return [np.append(dir3,0), np.append(dir2,0), np.append(dir1,0), np.append(co,1.0)]

def get_matrix3_from_axis2_placement_3d(instance):
    dir1 = np.array(get_instance_value(instance,["dir1","values"]))
    dir2 = np.array(get_instance_value(instance,["dir2","values"]))
    co = np.array(get_instance_value(instance,["point","coordinates"]))
    
    dir3 = np.cross(dir1,dir2)
    
    return [dir3, dir2, dir1]

def rotation_matrix (angle, dim=4):
    return rotation_matrix_sin_cos (math.sin(angle), math.sin(cos), dim)
    
def rotation_matrix_sin_cos (sin, cos, dim=4):
    if dim == 4:
        return [[cos, -sin, 0, 0], [sin, cos, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    if dim == 3:
        return [[cos, -sin, 0], [sin, cos, 0], [0, 0, 1]]
    
    
def rotation_matrix_axis(axis, theta):
    """
    Return the rotation matrix associated with counterclockwise rotation about
    the given axis by theta radians.
    """
    axis = np.asarray(axis)
    axis = axis/math.sqrt(np.dot(axis, axis))
    a = math.cos(theta/2.0)
    b, c, d = -axis*math.sin(theta/2.0)
    aa, bb, cc, dd = a*a, b*b, c*c, d*d
    bc, ad, ac, ab, bd, cd = b*c, a*d, a*c, a*b, b*d, c*d
    return np.array([[aa+bb-cc-dd, 2*(bc+ad), 2*(bd-ac)],
                     [2*(bc-ad), aa+cc-bb-dd, 2*(cd+ab)],
                     [2*(bd+ac), 2*(cd-ab), aa+dd-bb-cc]])
                     

def translate_matrix (m, v3):
    ret = []
    for i in range (0,4):
        ret.append([m[i][0],m[i][1],m[i][2],m[i][3]])
        
    for i in range(0,3):
        ret[3][i] = ret[3][i]+v3[i]
        
    return ret 
                     
        
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
                 
            vertexs.append(convert_v4_to_v3(v4))

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
   
def get_circle_verts(pm, r):
    
    verts = []
    prec = 32
    #iv = len(vertexs)
    for i in range(0,prec):
        a = ((math.pi*2)/prec)*i
        v4 = [math.cos(a)*r,math.sin(a)*r, 0.0, 1.0]
        v4 = np.matmul(v4,pm)
                 
        verts.append(convert_v4_to_v3(v4))
        #vertexs.append(v3)
        #if i== 31:
        #    edges.append([iv+i,iv])
        #else:
        #    edges.append([iv+i,iv+i+1])
        
    #faces.append(range(iv,iv+32))
    return verts
    
 
    
def generate_circle_face (instance):
    if instance["name"] != "CIRCLE":
        return 
    
    
    verts = get_circle_verts(
        get_matrix_from_axis2_placement_3d(get_instance_value(instance,"placement")),
        get_instance_value(instance,"radi")
    )
    
    iv = len(vertexs)
    for v in verts:
        vertexs.append(v3)
    
    faces.append(range(iv,iv+32))
    
    
def get_arc_verts (instance, p1, p2):    
    verts = []
    
    if instance["name"] != "CIRCLE":
        return
    
    r = get_instance_value(instance,"radi")
    center = get_instance_value(instance, ["placement", "point", "coordinates"])

    if p3_p3_dist (center,p1) - r > 0.01:
        print ("Invalid p1:")
        
    if p3_p3_dist (center,p2) - r > 0.01:
        print ("Invalid p1")
        
    # Plane check?
    
    pm = get_matrix_from_axis2_placement_3d(get_instance_value(instance,"placement"))
    
    prec = 32

    l = a_from_b_c_A (r,r,(math.pi*2)/prec)

    sign = -1
    
    #find first point
    s = 0
    for i in range(0,prec):
        a = ((math.pi*2)/prec)*i * sign
        v4 = [math.cos(a)*r,math.sin(a)*r, 0.0, 1.0]
        v4 = np.matmul(v4,pm)
            
        if p3_p3_dist (v4,p1) <= l:
            s = i+1
            break
        
    verts.append(p1)
    
    match = None

    for i in range(0,prec):

        a = ((math.pi*2)/prec)*(i+s) *sign

        v4 = [math.cos(a)*r,math.sin(a)*r, 0.0, 1.0]
        v4 = np.matmul(v4,pm)
        
        if match is not None:
            if p3_p3_dist (v4,p2) < l:
                verts.append(convert_v4_to_v3(match))
                    
            verts.append(p2)
            break;    
                
        if p3_p3_dist (v4,p2) < l:    
            # Precision problems, do not break, test next
            match = v4 
            #verts.append(p2)
            #break
        else:
            # Last Point
            verts.append(convert_v4_to_v3(v4))
            
    return verts
            
def generate_edges (verts):
    iv = len(vertexs)
    i=0
    l = len(verts)-1
    for v in verts:
        vertexs.append(v)
        if i<l:
            edges.append([iv+i,iv+i+1])
            
        i=i+1     

def generate_arc (instance, p1, p2):
    verts = get_arc_verts(instance, p1, p2)
    generate_edges(verts)
    
def generate_circular_ring (center, plane, r1, r2):
    if not circular_ring:
        return 
    
    global vertexs
    x = [0,0,1]
    if (np.dot(x,plane) in [1,-1]):
        x = [0,1,0]
    tm = []
    
    tm.append (convert_v3_to_v4(x))
    tm.append (convert_v3_to_v4(np.cross(x, plane)))
    tm.append (convert_v3_to_v4(plane))
    tm.append (convert_v3_to_v4(center,1))
    
    
    iv = len(vertexs)
    v1 = get_circle_verts(tm,r1)
    v2 = get_circle_verts(tm,r2)
    
    for i in range (0,32):
        vertexs.append(v1[i])
        vertexs.append(v2[i])
        
        if (i==31):
            faces.append([iv+i*2, iv, iv+1, iv+i*2+1])
        else:
            faces.append([iv+i*2, iv+i*2+2, iv+i*2+3, iv+i*2+1])
        

def order_segments (segments):
    new_segments = []
    new_segments.append(segments[0])
    segments.remove(segments[0])
    ok = True
    while len(segments) and ok:
        ok = False
        i=0
        for seg in segments:
            if (seg["verts"][0] == new_segments[-1]["verts"][-1]):
                new_segments.append(seg)
                #segments.remove(seg)
                del segments[i]
                ok = True
                break
            if (seg["verts"][-1] == new_segments[-1]["verts"][-1]):
                seg["verts"] = list(reversed(seg["verts"]))
                seg["sign"] = seg["sign"] * -1
                new_segments.append(seg)
                #segments.remove(seg)
                del segments[i]
                ok = True
                break
            i=i+1
            
    if (not ok):
        print ("Incorrect loop")
    elif (new_segments[0]["verts"][0] != new_segments[-1]["verts"][-1]):
        print ("Not closed loop")
    
    return new_segments

def get_segments(data, gen_edges = False):
    segments = []
    
    #first node
    append_to_segment (segments, data[0]["surf"],  data[0]["edge_curve"] )
    
    i=1
    while i<len(data): 
        if not continue_segment(segments, data[i]["surf"], data[i]["edge_curve"]):
            append_to_segment (segments, data[i]["surf"],  data[i]["edge_curve"])
                
        i=i+1
    
    if gen_edges:
        print ("Debug: Drawing generated edges")
        for i in range(0, len(segments)):
           generate_edges(segments[i]["verts"])
            
    return order_segments(segments)


def generate_planar_faces_from_outbound (instance, data, segment):
    segments = get_segments (data)
    if segment["name"] == "CIRCLE":
        if len(segments) == 1 and segments[0]["name"] == "CIRCLE":
            ca, cb = segment, segments[0]
            r1, r2 = ca["radi"], cb["radi"]
            if eq_v3(ca["center"], cb["center"]) and np.dot(ca["plane"], cb["plane"]) in [1,-1]:
                generate_circular_ring (ca["center"], ca["plane"], r1, r2)
            else: 
                print ("Not in concentric or in same plane")
        else:
            print ("Not perfomed")
    else:
        print ("Unknown planar surface to apply face bound")
    
def generate_cylindrical_faces_from_outbound (instance, data):
    if not cylindrical_faces_from_outbound:
        return
    
    global faces, edges, vertexs
    
    segments = get_segments(data)
    
    
    if len(segments) != 4:
        print ("Expected 4 segments")
        return
    
    if segments[0]["name"] != "ARC":
        #start on a circle
        seg = segments[0]
        segments.remove(seg)
        segments.append(seg)
        
    if segments[0]["name"] == "ARC" and segments[1]["name"] == "LINE":
        # Get rotation matrix and calc vertices!
        i=0
        iv = len(vertexs)
        h = sub_v3_v3 (segments[1]["verts"][1],segments[1]["verts"][0])
        im=len(segments[0]["verts"])
        for i in range(0,im):
            a = segments[0]["verts"][i]
            b = add_v3_v3 (a, h)
            
            vertexs.append(a)
            vertexs.append(b)
        
            if i==im-1:
                None
            else:
                faces.append ([iv+i*2, iv+i*2+1, iv+i*2+3,iv+i*2+2]) 
        
    else:
        print ("expected circle and line")
    
    
    
    
def append_to_segment(segments, surf, edge_curve):
    if surf["name"] == "CIRCLE":
        segments.append ({
                            "radi": get_instance_value(surf, "radi"), 
                            "center" : get_instance_value(surf, ["placement", "point","coordinates"]),
                            "plane" : list(get_plane_from_axis2_placement_3d(get_instance_value(surf,"placement"))),
                            "pm" : get_matrix3_from_axis2_placement_3d(get_instance_value(surf,"placement")),
                            "tm" : get_matrix_from_axis2_placement_3d(get_instance_value(surf,"placement")),
                            "sign" : 1
                        })
        
        if edge_curve:
            segments[-1]["verts"] =  get_arc_verts(
                                surf,
                                get_instance_value(edge_curve, ["v1","cartesian_point","coordinates"]),
                                get_instance_value(edge_curve, ["v2","cartesian_point","coordinates"])
                            )
            segments[-1]["name"] = "ARC"
        else:
            segments[-1]["verts"] = get_circle_verts (
                get_matrix_from_axis2_placement_3d(get_instance_value(surf,"placement")),
                get_instance_value(surf,"radi")
            )
            segments[-1]["name"] = "CIRCLE"

    elif surf["name"] == "LINE":
        segments.append ({
                            "name" : surf["name"],
                            "verts" : [
                                get_instance_value(edge_curve, ["v1","cartesian_point","coordinates"]),
                                get_instance_value(edge_curve, ["v2","cartesian_point","coordinates"])
                            ],
                            "sign" : 1
                        })
    else:
        print ("unexpected for segment", surf["name"])
                    

def continue_segment (segments, surf, edge_curve):
    prv = segments[-1]
    if surf["name"] == "CIRCLE" and prv["name"] == "ARC":
        if prv["radi"] == get_instance_value(surf, "radi") and prv["center"] == get_instance_value(surf, ["placement", "point","coordinates"]):
            #continue
            v = get_arc_verts(
                surf,
                get_instance_value(edge_curve, ["v1","cartesian_point","coordinates"]),
                get_instance_value(edge_curve, ["v2","cartesian_point","coordinates"])
            )
            
            #print (prv["verts"][0],prv["verts"][-1], v[0], v[-1])
            if eq_v3 (prv["verts"][-1], v[0]):
                prv["verts"] = prv["verts"] + v[1:]
            elif eq_v3 (prv["verts"][0], v[-1]):
                prv["verts"] =  list(reversed(prv["verts"])) + list(reversed(v))[1:] 
                prv["sign"] = prv["sign"] * -1
            elif eq_v3 (prv["verts"][0], v[0]):
                prv["verts"] =  list(reversed(prv["verts"])) + v[1:]
                prv["sign"] = prv["sign"] * -1
            else:
                print ("Error") 
                
            if eq_v3(prv["verts"][0], prv["verts"][-1]):
                prv["name"] = "CIRCLE"
                
            return True
        else:
            return False
    else:
        return False

def segments_compare (seg1, seg2):
    ret = True
    ret = ret and seg1["name"] == seg2["name"]
    if ret and seg1["name"] == "CIRCLE":
        ret = ret and seg1["radi"] == seg2["radi"]
        ret = ret and len(seg1["verts"]) == len(seg2["verts"])
        ret = ret and eq_v3(seg1["center"], seg2["center"])
        ret = ret and np.dot(seg1["plane"], seg2["plane"]) in [1,-1]
    elif ret:
        print ("not compared")
                
    return ret
        

def remove_duplicate_segments (segments):
    i = 0
    while i < len(segments):
        j=i+1
        while j < len (segments):
            if segments_compare(segments[i],segments[j]):
                del segments[j]
            else:
                j = j+1
        i = i +1
    
#asumes 4 closed edges            
def generate_torus_from_outbound (instance, data):
    if not torus_from_outbound:
        return
    
    global faces, edges, vertexs
    
    r1 = get_instance_value(instance,"r1")
    r2 = get_instance_value(instance,"r2")
    verts = []
    segments = get_segments(data)
    
    if len(segments) != 4:
        print ("Torus outbound: Expected 4 segments")
        return
    
    for s in segments:
        if (s["name"] != "ARC"):
            print ("Unexpected!")
            return
                
    if segments[0]["radi"] != r2:
        #start on a r2 segment
        seg = segments[0]
        segments.remove(seg)
        segments.append(seg)
            
    if segments[0]["radi"] == r2:
        # Get rotation matrix and calc vertices!
        i=0
        im=len(segments[1]["verts"])
        j=0
        jm=len(segments[0]["verts"])
        #generate_edges(segments[1]["verts"])
        
        
        a = sub_v3_v3(segments[1]["verts"][0],segments[1]["center"])
        b = sub_v3_v3(segments[1]["verts"][1],segments[1]["center"]) 
        
        
        sign = segments[1]["sign"]
        
        iv = len(vertexs)
        for i in range (0,im):
            # continue  
            a = sub_v3_v3(segments[1]["verts"][0],segments[1]["center"])
            b = sub_v3_v3(segments[1]["verts"][i],segments[1]["center"])      
            an = angle_v3_v3(np.array(a),np.array(b))*sign
            rm = rotation_matrix_axis (segments[1]["plane"],an)
            vv = []
            for j in range(0,jm):
                vertexs.append (np.dot(rm,segments[0]["verts"][j]))  
                if (j==jm-1):
                    None
                    if (i==im-1):
                        None
                    else:
                        edges.append([iv+i*jm+j,iv+i*jm+j+jm])
                else:
                    edges.append([iv+i*jm+j,iv+i*jm+j+1])
                    if (i==im-1):
                        None
                    else:
                        edges.append([iv+i*jm+j,iv+i*jm+j+jm])
                        faces.append([iv+i*jm+j,iv+i*jm+j+1,iv+i*jm+j+jm+1,iv+i*jm+j+jm])
    else:
        print ("expected r2 segment") 
         
    #the other 2 segments are ignored   
    
def generate_spherical_surface (pm, r):
    global vertexs,faces
    prec = 32
    h = [0,0,0]
    pm3 = convert_m4_to_m3(pm)
    iv = len(vertexs)
    for i in range(0,17):
        a = ((math.pi*2)/prec)*i
        x,y = math.sin(a)*r, math.cos(a)*r    
        h[0], h[1], h[2] = 0, 0, y  
        h = np.dot(h,pm3)
        tm = translate_matrix(pm,h)
        verts = get_circle_verts(tm,x)    
        for j in range (0,prec):
            vertexs.append(verts[j])
            if i == 16:
                None
            else:
                if j==prec-1:
                    faces.append ([iv+i*prec+j,iv+i*prec,iv+(i+1)*prec,iv+(i+1)*prec+j])
                else:
                    faces.append ([iv+i*prec+j,iv+i*prec+j+1,iv+(i+1)*prec+j+1,iv+(i+1)*prec+j]) 
    
def generate_spherical_surface_from_outbound (instance, data):
    segments = get_segments(data)
    
    if len(segments) == 1:
        #Do not know what to do with
        generate_spherical_surface (
            get_matrix_from_axis2_placement_3d(get_instance_value(instance,"placement")),
            get_instance_value(instance,"radi")
        )
    else:
        print ("Outbound not applied")
    
        
### INSTANCE STRUCTURES ####

#X= PLANE('',#33);
structure["PLANE"] = "unknown", "AXIS2_PLACEMENT_3D|axis2_placement_3d"

#X = ADVANCED_FACE('',(#18),#32,.F.);
structure["ADVANCED_FACE"] = "unknown","FACE_BOUND|FACE_OUTER_BOUND|data","PLANE|CYLINDRICAL_SURFACE|TOROIDAL_SURFACE|CONICAL_SURFACE|SPHERICAL_SURFACE|SURFACE_OF_REVOLUTION|def", "unknown2"
    
#X = FACE_BOUND('',#19,.F.);
structure["FACE_BOUND"] = "unknown1", "EDGE_LOOP|VERTEX_LOOP|loop", "unknown2"

#X = FACE_OUTER_BOUND('',#1091,.T.);
structure["FACE_OUTER_BOUND"] = "unknown1", "EDGE_LOOP|loop", "unknown2"
    
#X = EDGE_LOOP('',(#20,#55,#83,#111));
structure["EDGE_LOOP"] = "unknown1", "ORIENTED_EDGE|oriented_edges"

#X = VERTEX_LOOP('',#20);
structure["VERTEX_LOOP"] = "unknown1", "VERTEX_POINT|vertex"

#X = ORIENTED_EDGE('',*,*,#21,.F.);
structure["ORIENTED_EDGE"] = "unknown1", "unknown2", "unknown3", "EDGE_CURVE|edge_curve", "unknown5"

#X = CONICAL_SURFACE('',#512,6.052999999999996,45.000000000000142);
structure["CONICAL_SURFACE"] = "unknown1", "AXIS2_PLACEMENT_3D|axis2_placement3d", "unknown2", "uknown3"

#X = EDGE_CURVE('',#22,#24,#26,.T.);
structure["EDGE_CURVE"] = "unknown1", "VERTEX_POINT|v1", "VERTEX_POINT|v2", "SURFACE_CURVE|CIRCLE|LINE|B_SPLINE_CURVE_WITH_KNOTS|ELLIPSE|SEAM_CURVE|object", "unknown5"

#X = CIRCLE('',#3900,13.230000000000002);
structure["CIRCLE"] = "unknown1", "AXIS2_PLACEMENT_3D|AXIS2_PLACEMENT_2D|placement", "float|radi"

#X= ELLIPSE('',#539,7.296415549894075,5.053)
structure["ELLIPSE"] = "unknown1", "AXIS2_PLACEMENT_3D|axis2_placement3d", "r1", "r2"

#X = SURFACE_CURVE('',#27,(#31,#43),.PCURVE_S1.)
def surface_curve_load(instance):
    None
    #print (get_instance_path(instance))

structure["SURFACE_CURVE"] = "unknown", "LINE|CIRCLE|object", "PCURVE|data", "unknown2"
structure_func["SURFACE_CURVE"] = { "load" : surface_curve_load }

#X = SPHERICAL_SURFACE('',#387,4.25);
structure["SPHERICAL_SURFACE"] = "unknown", "AXIS2_PLACEMENT_3D|placement", "float|radi"

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
    None
    #print (get_instance_path(instance))
    #print_instance (instance)
    #print_instance_tree(instance)
     
structure["SEAM_CURVE"] = "unknown", "CIRCLE|LINE|geom", "PCURVE|pcurves", "unknown2"
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
a = 0
b = 0
def process_face_bound(fb, face, obj):
    ret = None
    loop = get_instance_value(fb,"loop")
    new_edges = []
    segments = []
    if loop["name"] == "EDGE_LOOP":
        for oe in get_instance_value(fb,["loop","oriented_edges"]):  
            edge_curve = get_instance_value(oe, "edge_curve")
            surf = get_instance_value(edge_curve,"object")
            if (surf["name"] == "SURFACE_CURVE"):
                object = get_instance_value(surf,"object")
                if object and object["name" ] == "CIRCLE": 
                    generate_circle_face(object)
                elif object and object["name"] == "LINE":
                    new_edges.append([
                        get_instance_value(edge_curve, ["v1","vertex_id"]),
                        get_instance_value(edge_curve, ["v2","vertex_id"])
                    ])
                elif object:
                    print ("Unknown object " + object["name"])
                else:
                    print ("No object")
                    
            elif (surf["name"] == "SEAM_CURVE"):
                if (obj["name"] == "CYLINDRICAL_SURFACE"):
                    v1 = get_instance_value(edge_curve, "v1")
                    v2 = get_instance_value(edge_curve, "v2")
                    iv = len(vertexs)
                    prec= 32
                    for i in range (0,prec):
                        a1 = ((math.pi*2)/prec)*i
                        rm = rotation_matrix(a1,3)
                        co_v1 = np.matmul (get_instance_value(v1, ["cartesian_point","coordinates"]),rm)
                        co_v2 = np.matmul (get_instance_value(v2, ["cartesian_point","coordinates"]),rm)
                        vertexs.append(co_v1)   
                        vertexs.append(co_v2)
                        edges.append([iv+i*2,iv+i*2+1])
                        if (i==31):
                            faces.append([iv+i*2,iv+i*2+1,iv+1,iv])
                        else:
                            faces.append([iv+i*2,iv+i*2+1,iv+(i+1)*2+1,iv+(i+1)*2])
                elif obj["name"] == "SURFACE_OF_REVOLUTION":
                    print ("TODO: generate surface of revolution")
                else:
                    print ("Unexpected object on seam curve: " + obj["name"])
            elif (surf["name"] == "CIRCLE"):
                append_to_segment (segments, surf, None)
            else:
                print ("Unknown for face bound edge loop " + surf["name"])
        
        if len(new_edges) > 0:
            faces.append(get_ordered_verts_from_edges(new_edges))
        
        if len(segments) > 0:
            remove_duplicate_segments(segments)
            if len(segments) > 1:
                print ("Found multiple segments", len(segments))
            ret = segments[0]
                
    if loop["name"] == "VERTEX_LOOP":
        if obj["name"] == "TOROIDAL_SURFACE":
            generate_torus_faces(obj, face)
        else:
            print ("Unexpected object on vertex_loop " + obj["name"])
            
    #returns a surface instance, to be used on outer bound edge
    return ret
   
def process_face_outer_bound(fb, face, obj, bound):    
    #surf is a definet face_bound
    loop = get_instance_value(fb,"loop")
    data = []
    global b
    if loop["name"] == "EDGE_LOOP":
        for oe in get_instance_value(fb,["loop","oriented_edges"]):
            
            edge_curve = get_instance_value(oe, "edge_curve")
            surf = get_instance_value(edge_curve,"object")
                   
            data.append({"surf" : surf, "edge_curve" : edge_curve})
        
    if obj["name"] == "TOROIDAL_SURFACE":        
        generate_torus_from_outbound(obj, data)
    elif obj["name"] == "PLANE":
        generate_planar_faces_from_outbound(obj,data, bound)
    elif obj["name"] == "CYLINDRICAL_SURFACE":
        generate_cylindrical_faces_from_outbound(obj,data)
    elif obj["name"] == "SPHERICAL_SURFACE":
        generate_spherical_surface_from_outbound(obj, data)
    else:
        print ("Unknown object to apply outer bound ",obj["name"])

def set_faces (instance):
    global a, b
    print ("Solid data")
    segment = None
    for face in get_instance_value(instance, ["closed_shell", "data"]):
        if (face["name"] == "ADVANCED_FACE"):
            surf = None
            obj = get_instance_value(face,"def")
            if not obj["name"] in  ["PLANE",
                                    "TOROIDAL_SURFACE", 
                                    "CYLINDRICAL_SURFACE", 
                                    "SURFACE_OF_REVOLUTION",
                                    "SPHERICAL_SURFACE"]:
                                        
                print ("Unknown definition for advanced face " + obj["name"])
                
            for fb in get_instance_value(face,["data"]):
                if fb["name"] == "FACE_BOUND":
                    if surf != None:
                        print ("More than one face bound?")
                    segment = process_face_bound (fb, face, obj)
                elif fb["name"] == "FACE_OUTER_BOUND":
                    #Process alwas face bound first, outer in next loop
                    None
                else:
                    print ("Unknown instance "  + fb["name"])
                    
            for fb in get_instance_value(face,["data"]):
                if fb["name"] == "FACE_OUTER_BOUND":
                    process_face_outer_bound(fb, face, obj, segment)
               
            
            if obj["name"] == "PLANE":
                None
            elif obj["name"] == "TOROIDAL_SURFACE":
                a = a +1
            elif obj["name"] == "CYLINDRICAL_SURFACE":
                b = b +1
            elif obj["name"] == "SURFACE_OF_REVOLUTION":
                None

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
    co = get_instance_value(instance,"coordinates")
    if False and len(co) == 3 and co[2] == 10:
        print(get_instance_path(instance))
        print("")
    
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
    
    print ()
    print ()
    print ()
    print ()
    
    bpy.ops.object.select_all()
    # remove all selected.
    bpy.ops.object.delete()
    # remove the meshes, they have no users anymore.
    for item in bpy.data.meshes:
        bpy.data.meshes.remove(item)

    #filepaths = sys.argv[sys.argv.index('--') + 1:]
    
    #for filepath in filepaths:
    #    read_stp(filepath)
    
    test_folder = "/home/jaume/src/mechanical-blender-addons/io_scene_stp/test_files/"
        
    #read_stp(test_folder + "cube.stp") #OK
    #read_stp(test_folder + "torus.stp") #OK
    #read_stp(test_folder + "revolve.stp") #UNFINISHED
    #read_stp(test_folder + "cylinder.stp")  #OK
    #read_stp(test_folder + "SIEM-CONJ-L00025.stp")  "NOK"
    read_stp(test_folder + "inafag_6010_brbohxyclh6y8oik8swwpry0n.stp")
    