import ast
from enum import Enum
from copy import copy, deepcopy
import random

global_vardict = {}


class Value():
    def __init__(self):
        self.child = None

    def __str__(self):
        return 'value'


class Potential():
    def __init__(self):
        self.child = None

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

        # previous parents of child are removed, more efficient
        if nc and r1.child and r1 in nc.parents:
            nc.parents.remove(r1)
        if nc and r2.child and r2 in nc.parents:
            nc.parents.remove(r2)

        # create the new Reference by combining two nodes
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


def get_name(name):
    if isinstance(name, ast.Name):
        try:
            return name.id + "." + name.attr
        except BaseException:
            return name.id
    elif isinstance(name, ast.Attribute):
        try:
            return get_name(name.value) + "." + name.attr
        except BaseException:
            return get_name(name.value)
    elif isinstance(name, ast.Subscript):
        try:
            return get_name(name.value) + "." + name.attr
        except BaseException:
            return get_name(name.value)
    return None


def ref_from_stmt(key, stmt, vardict):
    '''Create references from a literal statement, follows levelled structure.
    Joins all variables contained at the same level.'''

    if isinstance(stmt, ast.Name):
        return vardict[get_name(stmt)]

    if not isinstance(stmt, ast.List):
        return None

    refs = set()
    for e in stmt.elts:
        a = ref_from_stmt(str(random.random()), e, vardict)
        if a is not None:
            refs.add(a)
    refs = list(refs)

    if len(refs) == 0:
        r = Reference(set(), set([key]), None)
        vardict[key] = r
        return r

    s = refs[0]
    for i in range(1, len(refs)):
        s = Reference.join(s, refs[i], vardict)
    r = Reference(set(), set([key]), s)
    s.parents.add(r)
    vardict[key] = r
    return r


def ref_from_ref(key, ref, vardict):
    if ref is None:
        return None
    c = ref_from_ref(None, ref.child, vardict)
    if key is None:
        # generate a key that is unique
        key = str(random.random())
    p = Reference(set(), set([key]), c)
    vardict[key] = p

    if c:
        c.parents.add(p)
    return p


def process_slice(expr):
    if isinstance(expr, ast.Constant):
        return 0
    if isinstance(expr, ast.Subscript):
        return 1 + process_slice(expr.slice)
    elif isinstance(expr, ast.Name):
        return 0
    raise Exception("Error in processing isabeau")

def user_defined(vardict):
    user_defined = []
    for k in vardict:
        try:
            float(k)
            # print('float', k)
        except:
            # print('str', k)
            user_defined.append(k)
    return user_defined

def check_reference(locs_seen, lineno, name, vardict, levels=0):
    node = vardict[name]
    for _ in range(levels):
        node = node.child

    # pprint(vardict)
    for k in user_defined(vardict):
        if k == name:
            continue
        n = vardict[k]
        while n is not None:
            if n == node and n not in locs_seen:
                locs_seen.add(n)
                print("Line", lineno, "WARNING:", name, k, "at", levels, "levels down refer to the same memory, one was mutated.")
            n = n.child


def check_all(locs_seen, stmt, vardict):
    if isinstance(stmt, ast.Constant):
        return
    if isinstance(stmt, ast.Name):
        lineno = stmt.lineno
        name = get_name(stmt)
        check_reference(locs_seen, lineno, name, vardict)

    elif isinstance(stmt, ast.Subscript):
        lineno = stmt.lineno
        name = get_name(stmt.value)
        levels = process_slice(stmt)
        check_reference(locs_seen, lineno, name, vardict, levels)

    elif isinstance(stmt, ast.Assign):
        # TODO; avoid double print for error
        for t in stmt.targets:
            check_all(locs_seen, t, vardict)

        # TODO: check reference for targets in subscripts
        check_all(locs_seen, stmt.value, vardict)
    elif isinstance(stmt, ast.AugAssign):
        # TODO: copy assign code
        check_all(locs_seen, stmt.value, vardict)


def assign(stmt, vardict):
    '''Only processes singular assignment.'''
    # print(ast.dump(stmt))
    keys = []

    if len(stmt.targets) != 1:
        return

    key = get_name(stmt.targets[0])
    if key is None:
        return

    if isinstance(stmt.value, ast.List):
        # initialize the reference object for any list
        vardict[key] = ref_from_stmt(key, stmt.value, vardict)
    elif isinstance(stmt.value, ast.Name):
        name = get_name(stmt.value)
        if key in vardict:
            Reference.join(vardict[key], vardict[name], vardict)
        else:
            vardict[key] = vardict[name]
            vardict[name].vars.add(key)
    elif isinstance(stmt.value, ast.Call):
        if get_name(stmt.value.func) == 'copy.copy':
            # shallow copy only creates one new layer
            name = get_name(stmt.value.args[0])
            vardict[key] = Reference(set(), set([key]), vardict[name].child)
            vardict[name].child.parents.add(vardict[key])
        elif get_name(stmt.value.func) == 'copy.deepcopy':
            # deepcopy requires a new reference at every layer
            name = get_name(stmt.value.args[0])
            vardict[key] = ref_from_ref(key, vardict[name], vardict)


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
    elif isinstance(node, ast.AugAssign):
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
                vardict[a.arg] = ref_from_stmt(a.arg, d, vardict)
        else:
            vardict[a.arg] = Potential()

    # Detect copies immediately, shouldn't happen in intraprocedural analysis
    detect(node.args, vardict)

    for stmt in node.body:
        # print(ast.dump(stmt))
        if isinstance(stmt, ast.Assign):
            assign(stmt, vardict)
            detect(stmt, vardict)
            # pprint(vardict)
        elif isinstance(stmt, ast.AugAssign):
            assign(stmt, vardict)
            detect(stmt, vardict)
            # pprint(vardict)

        locs_seen = set()
        check_all(locs_seen, stmt, vardict)

    # print("End:")
    pprint(vardict)


seen = set()


def detect(stmt, vardict):
    user_vars = user_defined(vardict)

    # print(user_vars)
    for i in range(len(user_vars)):
        for j in range(i + 1, len(user_vars)):
            v1 = user_vars[i]
            v2 = user_vars[j]
            if vardict[v1] == vardict[v2] and vardict[v1] not in seen:
                print("Line", stmt.lineno, 'WARNING: the following variables point to the same memory:',
                      v1, v2, '. Is this intended?')
        seen.add(vardict[v1])


with open('example.py', 'r') as file:
    file_contents = file.read()

node = ast.parse(file_contents)
# print(type(node))
# print(ast.dump(node))
recurse(node)
# pprint(global_vardict)

# consider adding astor