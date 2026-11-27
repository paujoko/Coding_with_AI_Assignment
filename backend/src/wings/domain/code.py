"""Design versus code, computed by code: what the class diagrams of the design say and what the
Python and JavaScript sources do, in both directions (drift).

Compared: classes, public operations, inheritance and realisation, and attributes where both sides
are unambiguous. Python is read with the standard `ast` module; JavaScript (`.js`, `.mjs`, `.cjs`,
ADR 0020) with a small tokenizer below that skips comments, strings, template literals and regular
expressions. Both fill the same structure, so one design is compared with a project in either
language or both. Private names (leading underscore, and `#name` in JavaScript) and dunder methods
are implementation details on both sides.

Rules that keep the report free of noise (lessons.md, "Noise hides signal"):
- One difference gives one line. A class that is missing is not also listed with its operations; a
  missing inheritance line is not also listed as the operations and attributes that came with it.
- Inheritance is met by an indirect base too (through a class in between, also a private one), and a
  `typing.Protocol` is realised by any class that has all its methods.
- Attributes of the diagram count as missing in the code only when marked public (`+name`, with or
  without a type). They are met by a declared field, an assignment `self.name = ...` (`this.name`)
  anywhere in the class, a property (getter), or the same in a base class. A class with a base Wings
  cannot read (anything outside the files except ABC, Protocol, Generic, object) is not judged.
- Fields of the code count as missing in the diagram only when they are declared in the class body
  (`name: type`, as in a dataclass; JavaScript has no such declaration), the diagram shows attributes
  for that class at all, and neither the type nor the name points at an association of the diagram
  (a class of the diagram as type, or the name of an association end: such a field is the
  association line, not an attribute).
- An operation named like its class (`Store(dbPath)` in `class Store`) is the constructor.
"""

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from wings.domain.uml import ancestors, class_model

_READABLE_BASES = frozenset({"object", "ABC", "Protocol", "Generic"})  # bases that add no attributes
_OPAQUE = frozenset({"__getattr__", "__getattribute__", "__slots__"})  # attributes cannot be read from the source
_WORD = re.compile(r"[A-Za-z_]\w*")


class DriftReport(BaseModel):
    missing_in_code: list[str] = Field(default_factory=list)  # classes in the diagram, not in the code
    missing_in_diagram: list[str] = Field(default_factory=list)  # classes in the code, not in the diagram
    operations_missing_in_code: list[str] = Field(default_factory=list)  # "Class.op"
    operations_missing_in_diagram: list[str] = Field(default_factory=list)
    inheritance_missing_in_code: list[str] = Field(default_factory=list)  # "Child(Parent)"
    inheritance_missing_in_diagram: list[str] = Field(default_factory=list)
    attributes_missing_in_code: list[str] = Field(default_factory=list)  # "Class.attribute"
    attributes_missing_in_diagram: list[str] = Field(default_factory=list)
    unparsable: list[str] = Field(default_factory=list)  # files that are not valid Python

    @property
    def in_sync(self) -> bool:
        return not (
            self.missing_in_code
            or self.missing_in_diagram
            or self.operations_missing_in_code
            or self.operations_missing_in_diagram
            or self.inheritance_missing_in_code
            or self.inheritance_missing_in_diagram
            or self.attributes_missing_in_code
            or self.attributes_missing_in_diagram
        )

    def lines(self) -> list[str]:
        out = [f"{c} is in the class diagram but not in the code." for c in self.missing_in_code]
        out += [f"{c} is in the code but not in the class diagram." for c in self.missing_in_diagram]
        out += [f"{_inherits(i)} in the class diagram but not in the code." for i in self.inheritance_missing_in_code]
        out += [f"{_inherits(i)} in the code but not in the class diagram." for i in self.inheritance_missing_in_diagram]
        out += [f"{o}() is in the class diagram but not in the code." for o in self.operations_missing_in_code]
        out += [f"{o}() is in the code but not in the class diagram." for o in self.operations_missing_in_diagram]
        out += [f"{a} is in the class diagram but not in the code." for a in self.attributes_missing_in_code]
        out += [f"{a} is in the code but not in the class diagram." for a in self.attributes_missing_in_diagram]
        out += [f"{f} is not valid Python." for f in self.unparsable]
        return out


def _squash(name: str) -> str:
    """`assignee_id`, `assigneeId` and `Assignee Id` all become `assigneeid`."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


_REFERENCE = re.compile(r"^[a-z]\w*?(?:Ids?|_ids?)$")  # payerId, participant_ids: an id that points at another object


def _implements_association(field_name: str, ends: set[str]) -> bool:
    """A field named after an association end of its class is that association, not an extra attribute:
    the role or the other class (`assignee`, `member`), plus `Id`, `_id`, `Ids`, `_ids` or a plural `s`.
    An `...Id` field of a class with any association counts too, since a role is often prose (`paid by`)."""
    if not ends:
        return False
    if _REFERENCE.match(field_name):
        return True
    squashed = _squash(field_name)
    return any(squashed in (base, base + "id", base + "ids", base + "s") for base in map(_squash, ends))


def _inherits(pair: str) -> str:
    child, _, parent = pair.rstrip(")").partition("(")
    return f"{child} inherits from {parent}"


@dataclass
class _CodeClass:
    """What the source says about one class, its own body only."""

    methods: set[str] = field(default_factory=set)  # public methods, properties included
    properties: set[str] = field(default_factory=set)
    fields: dict[str, set[str]] = field(default_factory=dict)  # declared in the class body: name -> names in its type
    known: set[str] = field(default_factory=set)  # every public attribute name the class is seen to have
    bases: list[str] = field(default_factory=list)
    opaque: bool = False


def _is_property(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in func.decorator_list:
        name = decorator.id if isinstance(decorator, ast.Name) else decorator.attr if isinstance(decorator, ast.Attribute) else ""
        if name in ("property", "cached_property"):
            return True
    return False


def _type_names(annotation: ast.expr) -> set[str]:
    """Every name a type annotation mentions, also inside a quoted annotation."""
    names: set[str] = set()
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.update(_WORD.findall(node.value))
    return names


def _read_class(node: ast.ClassDef, into: _CodeClass) -> None:
    into.bases += [b.id for b in node.bases if isinstance(b, ast.Name)] + [b.attr for b in node.bases if isinstance(b, ast.Attribute)]
    for item in node.body:
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
            if item.name in _OPAQUE:
                into.opaque = True
            if not item.name.startswith("_"):
                into.methods.add(item.name)
                if _is_property(item):
                    into.properties.add(item.name)
            receiver = item.args.args[0].arg if item.args.args else None
            for sub in ast.walk(item):  # self.name = ... anywhere in the method
                if (
                    isinstance(sub, ast.Attribute)
                    and isinstance(sub.ctx, ast.Store)
                    and isinstance(sub.value, ast.Name)
                    and sub.value.id == receiver
                    and not sub.attr.startswith("_")
                ):
                    into.known.add(sub.attr)
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            if not item.target.id.startswith("_"):
                into.known.add(item.target.id)
                into.fields[item.target.id] = _type_names(item.annotation)
        elif isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    if target.id in _OPAQUE:
                        into.opaque = True
                    if not target.id.startswith("_"):
                        into.known.add(target.id)


# JavaScript. A tokenizer, not a parser: it finds `class Name [extends Base] { ... }` by brace matching
# and reads the members at the top level of the body. When it is unsure it reads less, never more: a
# missed method is one missing line, a made-up one is a false alarm.

_JS_SUFFIXES = (".js", ".mjs", ".cjs")
_JS_NAME = re.compile(r"#?(?:[^\W\d]|\$)[\w$]*")
_JS_NUMBER = re.compile(r"\.?\d[\w.]*")
_JS_PUNCT = ("===", "!==", "**=", "...", "<<=", ">>=", ">>>", "&&=", "||=", "??=", "==", "!=", "<=", ">=", "=>", "&&", "||", "??", "?.", "++", "--", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "**", "<<", ">>")
_JS_BEFORE_REGEX = frozenset({"return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw", "case", "do", "else", "yield", "await"})
_JS_MODIFIERS = frozenset({"static", "async", "get", "set", "accessor"})


@dataclass
class _Tok:
    kind: str  # "name", "punct", "num", "str" (a string, a piece of a template literal or a regular expression)
    text: str
    newline: bool = False  # a line break comes before this token


def _js_string_end(text: str, i: int, quote: str) -> int:
    """Index after the string that starts at i; an unterminated string ends at the line break."""
    j = i + 1
    while j < len(text):
        ch = text[j]
        if ch == "\\":
            j += 2
            continue
        if ch == quote:
            return j + 1
        if ch == "\n":
            return j
        j += 1
    return len(text)


def _js_template_end(text: str, i: int) -> tuple[int, bool]:
    """Scan template text from i: (index after it, True when it stopped at `${`)."""
    j = i
    while j < len(text):
        ch = text[j]
        if ch == "\\":
            j += 2
        elif ch == "`":
            return j + 1, False
        elif text.startswith("${", j):
            return j + 2, True
        else:
            j += 1
    return len(text), False


def _js_regex_end(text: str, i: int) -> int | None:
    """Index after the regular expression literal at i, or None when none closes on this line."""
    j, in_class = i + 1, False
    while j < len(text):
        ch = text[j]
        if ch == "\n":
            return None
        if ch == "\\":
            j += 2
            continue
        if in_class:
            in_class = ch != "]"
        elif ch == "[":
            in_class = True
        elif ch == "/":
            j += 1
            while j < len(text) and (text[j].isalnum() or text[j] in "_$"):
                j += 1
            return j
        j += 1
    return None


def _js_regex_allowed(prev: "_Tok | None") -> bool:
    """A `/` starts a regular expression unless it follows a value (then it divides)."""
    if prev is None:
        return True
    if prev.kind == "name":
        return prev.text in _JS_BEFORE_REGEX
    return prev.kind == "punct" and prev.text not in (")", "]", "}", "++", "--")


def _js_tokens(text: str) -> list[_Tok]:
    toks: list[_Tok] = []
    braces: list[str] = []  # "{" for a block, "${" for an expression inside a template literal
    newline = False
    i, n = 0, len(text)
    if text.startswith("#!"):
        i = text.find("\n") if "\n" in text else n

    def emit(kind: str, value: str) -> None:
        nonlocal newline
        toks.append(_Tok(kind, value, newline))
        newline = False

    def template(start: int) -> int:
        end, open_expression = _js_template_end(text, start)
        emit("str", "`")
        if open_expression:
            braces.append("${")
        return end

    while i < n:
        ch = text[i]
        if ch == "\n":
            newline, i = True, i + 1
        elif ch.isspace():
            i += 1
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            newline = newline or "\n" in text[i:end]
            i = end
        elif ch in "'\"":
            end = _js_string_end(text, i, ch)
            emit("str", text[i:end])
            i = end
        elif ch == "`":
            i = template(i + 1)
        elif ch == "}" and braces and braces[-1] == "${":
            braces.pop()
            i = template(i + 1)
        elif ch.isdigit() or (ch == "." and text[i + 1 : i + 2].isdigit()):
            match = _JS_NUMBER.match(text, i)
            end = match.end() if match else i + 1
            emit("num", text[i:end])
            i = end
        elif (match := _JS_NAME.match(text, i)) is not None:
            emit("name", match.group())
            i = match.end()
        elif ch == "/" and _js_regex_allowed(toks[-1] if toks else None) and (end := _js_regex_end(text, i)) is not None:
            emit("str", text[i:end])
            i = end
        else:
            op = next((p for p in _JS_PUNCT if text.startswith(p, i)), ch)
            if op == "{":
                braces.append("{")
            elif op == "}" and braces:
                braces.pop()
            emit("punct", op)
            i += len(op)
    return toks


_JS_PAIRS = {"(": ")", "[": "]", "{": "}"}


def _js_match(toks: list[_Tok], k: int) -> int | None:
    """Index of the bracket that closes the one at k, or None."""
    depth = 0
    for j in range(k, len(toks)):
        if toks[j].kind != "punct":
            continue
        if toks[j].text in _JS_PAIRS:
            depth += 1
        elif toks[j].text in _JS_PAIRS.values():
            depth -= 1
            if depth == 0:
                return j
    return None


def _js_depth(tok: _Tok) -> int:
    if tok.kind != "punct":
        return 0
    return 1 if tok.text in _JS_PAIRS else -1 if tok.text in _JS_PAIRS.values() else 0


def _js_is_class(toks: list[_Tok], k: int) -> bool:
    """The keyword `class` here, not a property called class (`obj.class`, `{ class: 1 }`)."""
    if toks[k].kind != "name" or toks[k].text != "class" or k + 1 >= len(toks):
        return False
    if k > 0 and toks[k - 1].text in (".", "?."):
        return False
    return toks[k + 1].kind == "name" or toks[k + 1].text == "{"


def _js_class_body(toks: list[_Tok], k: int) -> tuple[str | None, list[str], int, int] | None:
    """For `class` at k: (name, bases, index of `{`, index of `}`), or None when the body does not close."""
    j = k + 1
    name = None
    if toks[j].kind == "name" and toks[j].text != "extends":
        name, j = toks[j].text, j + 1
    bases: list[str] = []
    if j < len(toks) and toks[j].text == "extends":
        start, depth = j + 1, 0
        j = start
        while j < len(toks) and not (depth == 0 and toks[j].text == "{"):
            depth += _js_depth(toks[j])
            j += 1
        words = toks[start:j]
        dotted = len(words) % 2 == 1 and all(t.kind == "name" if x % 2 == 0 else t.text == "." for x, t in enumerate(words))
        if words:  # `extends React.Component` is Component; `extends mixin(Base)` stays unreadable on purpose
            bases.append(words[-1].text if dotted else "".join(t.text for t in words))
    if j >= len(toks) or toks[j].text != "{":
        return None
    end = _js_match(toks, j)
    return None if end is None else (name, bases, j, end)


def _js_field_end(toks: list[_Tok], k: int, end: int) -> int:
    """Index after the value of a class field whose `=` is at k (a `;` or a line break ends it)."""
    depth = 0
    for j in range(k + 1, end):
        tok, prev = toks[j], toks[j - 1]
        if depth == 0:
            if tok.text == ";":
                return j + 1
            continues = (prev.kind == "punct" and prev.text not in (")", "]", "}")) or (tok.kind == "punct" and tok.text not in ("*", "["))
            if tok.newline and j > k + 1 and not continues:
                return j
        depth += _js_depth(tok)
    return end


def _js_public(name: str) -> bool:
    return not name.startswith(("_", "#"))


def _read_js_members(toks: list[_Tok], start: int, end: int, into: _CodeClass) -> None:
    """Methods and fields at the top level of a class body (between the braces at start and end)."""
    k = start + 1
    while k < end:
        if toks[k].text == ";":
            k += 1
            continue
        if toks[k].text == "static" and toks[k + 1].text == "{":  # static initialization block
            k = (_js_match(toks, k + 1) or end) + 1
            continue
        accessor = False
        while toks[k].kind == "name" and toks[k].text in _JS_MODIFIERS and toks[k + 1].text not in ("(", "=", ";", "}") and not toks[k + 1].newline:
            accessor = accessor or toks[k].text in ("get", "set")
            k += 1
        if toks[k].text == "*":
            k += 1
        name: str | None = None
        if toks[k].kind == "name":
            name = toks[k].text
        elif toks[k].text == "[":  # a computed name is skipped
            k = _js_match(toks, k) or end
        elif toks[k].kind not in ("str", "num"):  # a quoted name is skipped too; anything else: move on
            k += 1
            continue
        k += 1
        if k < end and toks[k].text == "(":  # a method
            close = _js_match(toks, k)
            if close is None or close + 1 >= end or toks[close + 1].text != "{":
                return  # not a shape we know: read no further
            k = (_js_match(toks, close + 1) or end) + 1
            if name and name != "constructor" and _js_public(name):
                into.methods.add(name)
                if accessor:
                    into.properties.add(name)
        elif k < end and toks[k].text == "=":  # a field with a value
            k = _js_field_end(toks, k, end)
            if name and _js_public(name):
                into.known.add(name)
        elif k >= end or toks[k].text == ";" or toks[k].newline:  # a field without a value
            if name and _js_public(name):
                into.known.add(name)


def _read_js_this(toks: list[_Tok], start: int, end: int, into: _CodeClass) -> None:
    """`this.name = ...` anywhere in the class body (nested classes left out), like `self.name` in Python."""
    k = start + 1
    while k < end:
        if _js_is_class(toks, k):
            body = _js_class_body(toks, k)
            k = body[3] + 1 if body else k + 1
            continue
        tok = toks[k]
        if tok.kind == "name" and tok.text == "this":
            after = toks[k + 1 : k + 4]
            if len(after) == 3 and after[0].text == "." and after[1].kind == "name" and after[2].text == "=" and _js_public(after[1].text):
                into.known.add(after[1].text)
            if after and after[0].text == "[":
                into.opaque = True  # this[name] = ...: the attributes cannot be read from the source
        if tok.text == "assign" and k >= 2 and toks[k - 2].text == "Object" and [t.text for t in toks[k + 1 : k + 3]] == ["(", "this"]:
            into.opaque = True  # Object.assign(this, ...)
        k += 1


def _read_js(text: str, classes: dict[str, _CodeClass]) -> None:
    toks = _js_tokens(text)
    toks.append(_Tok("punct", ""))  # a sentinel, so that looking one token ahead never runs off the end
    for k in range(len(toks) - 1):
        if not _js_is_class(toks, k):
            continue
        body = _js_class_body(toks, k)
        if body is None or body[0] is None:
            continue  # an anonymous class, or a body that does not close: nothing is read
        name, bases, start, end = body
        into = classes.setdefault(name, _CodeClass())
        into.bases += bases
        _read_js_members(toks, start, end, into)
        _read_js_this(toks, start, end, into)


def _scan(files: dict[str, str], unparsable: list[str] | None = None) -> dict[str, _CodeClass]:
    classes: dict[str, _CodeClass] = {}
    for path, text in files.items():
        if path.endswith(_JS_SUFFIXES):
            _read_js(text, classes)
            continue
        if not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            if unparsable is not None:
                unparsable.append(path)
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                _read_class(node, classes.setdefault(node.name, _CodeClass()))
    return classes


def python_classes(files: dict[str, str], unparsable: list[str] | None = None) -> dict[str, set[str]]:
    """Class name -> public methods, inherited methods included (bases found in the same files).
    Despite the name, JavaScript classes are included too."""
    scanned = _scan(files, unparsable)
    bases = {name: c.bases for name, c in scanned.items()}
    return {name: c.methods.union(*(scanned[a].methods for a in ancestors(name, bases) if a in scanned)) for name, c in scanned.items()}


def compare_design_and_code(class_diagrams: str | Iterable[str], files: dict[str, str]) -> DriftReport:
    """Compare the code with all class diagrams of the design, read together (one text or several).

    Private names (leading underscore) are implementation details on both sides: private classes in
    the code and private operations in the diagram are not drift (real run s03: 10 of 11 lines were such)."""
    model = class_model([class_diagrams] if isinstance(class_diagrams, str) else class_diagrams)
    unparsable: list[str] = []
    scanned = _scan(files, unparsable)
    code_bases = {name: c.bases for name, c in scanned.items()}
    designed = set(model.operations)
    coded = {name for name in scanned if not name.startswith("_")}
    both = sorted(designed & coded)

    def code_ancestors(name: str) -> set[str]:
        return {a for a in ancestors(name, code_bases) if a in scanned}

    def all_methods(name: str) -> set[str]:
        return scanned[name].methods.union(*(scanned[a].methods for a in code_ancestors(name)))

    report = DriftReport(unparsable=unparsable)
    report.missing_in_code = sorted(designed - coded)
    report.missing_in_diagram = sorted(coded - designed)

    # Inheritance and realisation, for classes both sides have.
    for child in both:
        for parent in sorted(model.parents.get(child, set()) & coded):
            if parent in code_ancestors(child):
                continue
            if "Protocol" in scanned[parent].bases and all_methods(parent) <= all_methods(child):
                continue  # structural typing: the class has every method of the protocol
            report.inheritance_missing_in_code.append(f"{child}({parent})")
        for parent in sorted(set(scanned[child].bases) & designed & coded):
            if parent not in model.ancestors(child):
                report.inheritance_missing_in_diagram.append(f"{child}({parent})")

    for name in both:
        # What a class inherits from a class both sides have is that class's line, or the inheritance line.
        design_parents = [p for p in model.ancestors(name) if p not in coded]
        code_parents = [p for p in code_ancestors(name) if p not in designed]
        wanted = model.operations[name].union(*(model.operations.get(p, set()) for p in design_parents))
        hidden = set().union(*(model.hidden_operations.get(c, set()) for c in [name, *design_parents]))
        constructors = {name, *model.ancestors(name)}  # `Store(dbPath)` in class Store is `__init__` or `constructor`
        wanted = {op for op in wanted if not op.startswith("_") and op not in hidden and op not in constructors}  # `-op()` is `_op` in Python
        own = scanned[name].methods.union(*(scanned[p].methods for p in code_parents))
        shown = model.all_operations(name) | model.all_attributes(name)  # a property may be drawn as an attribute
        report.operations_missing_in_code += [f"{name}.{op}" for op in sorted(wanted - all_methods(name))]
        report.operations_missing_in_diagram += [f"{name}.{op}" for op in sorted(own - shown)]

        family = [scanned[name], *(scanned[a] for a in code_ancestors(name))]
        readable = all(not c.opaque and all(b in scanned or b in _READABLE_BASES for b in c.bases) for c in family)
        if readable:
            declared = model.public_attributes[name].union(*(model.public_attributes.get(p, set()) for p in design_parents))
            has = set().union(*(c.known | c.properties for c in family))
            report.attributes_missing_in_code += [f"{name}.{a}" for a in sorted(declared - has) if not a.startswith("_")]
        if model.all_attributes(name):
            ends = model.association_ends.get(name, set())
            extra = [
                a
                for a, types in scanned[name].fields.items()
                if "ClassVar" not in types and not (types & designed) and not _implements_association(a, ends)
            ]
            report.attributes_missing_in_diagram += [f"{name}.{a}" for a in sorted(set(extra) - model.all_attributes(name))]
    return report
