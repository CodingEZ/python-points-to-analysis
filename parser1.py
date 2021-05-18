import ast
from enum import Enum
from copy import copy, deepcopy
import random


global_vardict = {}

class Value():
    def __str__(self):
        return 'value'

class Potential():
    def __str__(self):
        return 'potential'

class Reference():
    def __init__(self, parents, vars, child=None):
        if isinstance(parents, list):
            assert(False)
        if isinstance(vars, list):
            assert(False)

        self.parents = parents
        self.vars = vars
        self.child = child

    def __str__(self):
        return f'{self.vars} -> {self.child.__str__()}'
        # return f'{[p.vars for p in self.parents]} {self.vars} -> {self.child.__str__()}'

    @staticmethod
    def join(r1, r2, vardict):
        # bug, no children for some reason
        if r1 is None and r2 is None:
            return None
        elif r1 is None:
            return r2
        elif r2 is None:
            return r1

        # print("child 1", r1.child)
        # print("child 2", r2.child)
        nc = __class__.join(r1.child, r2.child, vardict)
        # print("child join", nc)
        if nc and r1.child and r1 in nc.parents:
            nc.parents.remove(r1)
        if nc and r2.child and r2 in nc.parents:
            nc.parents.remove(r2)

        np = r1.parents.union(r2.parents)
        nr = r1.vars.union(r2.vars)
        n = Reference(np, nr, nc)
        
        if nc is not None:
            nc.parents.add(n)

        for p in n.parents:
            p.child = n
        for var in n.vars:
            vardict[var] = n
        return n

def pprint(d):
    for k in sorted(d.keys()):
        print(f'{k}: {d[k]}')
    print()

def getName(name):
    if isinstance(name, ast.Name):
        try:
            return name.id + "." + name.attr
        except:
            return name.id
    elif isinstance(name, ast.Attribute):
        try:
            return getName(name.value) + "." + name.attr
        except:
            return getName(name.value)
    raise Exception("Unhandled target")

def getLevels(stmt, vardict):
    # if isinstance(stmt, ast.Name):
    #     return 1 + vardict[getName(stmt)]
    if isinstance(stmt, ast.List):
        return 1 + max([0] + [getLevels(elt, vardict) for elt in stmt.elts])
    return 0

def refFromStmt(key, stmt, vardict):
    '''Create references from a literal statement, follows levelled structure.
    Joins all variables contained at the same level.'''

    if isinstance(stmt, ast.Name):
        return vardict[getName(stmt)]

    if not isinstance(stmt, ast.List):
        return None

    val = 0
    if isinstance(stmt, ast.List):
        val = getLevels(stmt, vardict)
    if val == 0:
        return None

    r = None
    for _ in range(val - 1):
        child = r
        k = str(random.random())
        r = Reference(set(), set([k]), child)
        if child:
            child.parents.append(r)
        vardict[k] = r
    child = r
    r = Reference(set(), set([key]), child)
    if child:
        child.parents.add(r)
    return r

def refFromRef(key, ref, vardict):
    if ref is None:
        return None
    c = refFromRef(None, ref.child, vardict)
    if key is None:
        # generate a key that is unique
        key = str(random.random())
    p = Reference(set(), set([key]), c)
    vardict[key] = p

    if c:
        c.parents.add(p)
    return p

# assume singular assignment
def assign(stmt, vardict):
    # print(ast.dump(stmt))
    keys = []

    assert(len(stmt.targets) == 1)
    try:
        key = getName(stmt.targets[0])
    except:
        return

    if isinstance(stmt.value, ast.List):
        # initialize the reference object for any list
        vardict[key] = refFromStmt(key, stmt.value, vardict)
    elif isinstance(stmt.value, ast.Name):
        name = getName(stmt.value)
        if key in vardict:
            Reference.join(vardict[key], vardict[name], vardict)
        else:
            vardict[key] = vardict[name]
            vardict[name].vars.add(key)
    elif isinstance(stmt.value, ast.Call):
        if getName(stmt.value.func) == 'copy.copy':
            # shallow copy only creates one new layer
            name = getName(stmt.value.args[0])
            vardict[key] = Reference(set(), set([key]), vardict[name].child)
            vardict[name].child.parents.add(vardict[key])
        elif getName(stmt.value.func) == 'copy.deepcopy':
            # deepcopy requires a new reference at every layer
            name = getName(stmt.value.args[0])
            vardict[key] = refFromRef(key, vardict[name], vardict)

    # pprint(vardict)

def recurse(node):
    if isinstance(node, ast.Module):
        for i in range(len(node.body)):
            recurse(node.body[i])
    elif isinstance(node, ast.ImportFrom):
        return
    elif isinstance(node, ast.Import):
        return
    elif isinstance(node, ast.ClassDef):
        for i in range(len(node.body)):
            recurse(node.body[i])
    elif isinstance(node, ast.FunctionDef):
        # print(ast.dump(node))
        traverse(node)
    elif isinstance(node, ast.Assign):
        assign(node, global_vardict)
    elif isinstance(node, ast.Assign):
        assign(node, global_vardict)

def traverse(node):
    # var --> type
    vardict = dict()
    # print(ast.dump(node.args))

    # process input arguments
    for i in range(len(node.args.args)):
        a = node.args.args[::-1][i]
        if i < len(node.args.defaults):
            d = node.args.defaults[::-1][i]
            if isinstance(d, ast.Constant):
                vardict[a.arg] = Value()
            elif isinstance(d, ast.List):
                vardict[a.arg] = refFromStmt(a.arg, d, vardict)
        else:
            vardict[a.arg] = Potential()

    # Detect copies immediately, shouldn't happen in intraprocedural analysis
    detect(vardict)

    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            assign(stmt, vardict)
            detect(vardict)
            # pprint(vardict)
        elif isinstance(stmt, ast.AugAssign):
            assign(stmt, vardict)
            detect(vardict)
            # pprint(vardict)

    print("End:")
    pprint(vardict)

def detect(vardict):
    user_defined = []
    for k in vardict:
        try:
            float(k)
            # print('float', k)
        except:
            # print('str', k)
            user_defined.append(k)

    # print(user_defined)


with open('example.py', 'r') as file:
    file_contents = file.read()

node = ast.parse(file_contents)
# print(type(node))
# print(ast.dump(node))
recurse(node)
# pprint(global_vardict)
