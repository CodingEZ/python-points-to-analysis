import copy

def f(f = [], g = 0):
    a = [[0]]
    b = a
    c = copy.copy(a)
    # d = copy.deepcopy(a)

    # e = [[]]
    # b = e

    # h = [a, f]
    # i = [[]]

    a[0] = c[0]
