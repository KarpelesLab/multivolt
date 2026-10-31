"""Minimal S-expression reader/writer for KiCad files (Python 3.9 compatible)."""
import re

_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)


class Sym(str):
    """An unquoted atom (keyword / number)."""


def parse(text):
    stack = [[]]
    pos = 0
    n = len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError("parse error at %d: %r" % (pos, text[pos:pos + 40]))
        pos = m.end()
        if m.group(1):
            stack.append([])
        elif m.group(2):
            lst = stack.pop()
            stack[-1].append(lst)
        elif m.group(3) is not None:
            stack[-1].append(m.group(3).encode().decode("unicode_escape") if "\\" in m.group(3) else m.group(3))
        else:
            stack[-1].append(Sym(m.group(4)))
    return stack[0][0] if len(stack[0]) == 1 else stack[0]


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def dump(node, indent=0):
    if isinstance(node, list):
        if not node:
            return "()"
        simple = all(not isinstance(x, list) for x in node)
        if simple:
            return "(" + " ".join(dump(x) for x in node) + ")"
        out = "(" + dump(node[0])
        for x in node[1:]:
            if isinstance(x, list):
                out += "\n" + "  " * (indent + 1) + dump(x, indent + 1)
            else:
                out += " " + dump(x)
        return out + ")"
    if isinstance(node, Sym):
        return str(node)
    if isinstance(node, bool):
        return "yes" if node else "no"
    if isinstance(node, (int, float)):
        return fmt(node)
    return q(node)


def fmt(v):
    if isinstance(v, int):
        return str(v)
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def find(node, key):
    for x in node:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def find_all(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]
