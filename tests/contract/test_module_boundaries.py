"""The boundary between the tool families, held by a gate instead of by an underscore.

A leading underscore is a promise: nobody outside this module hangs on this name, so it may be
renamed, resharpened or removed without asking around. ``tools/chatgpt.py`` broke that promise
for ``tools/talk.py`` until TOOL-19, and the damage was not a matter of style. The docstring of
the reached function carries the mitigation of T-09-21 (never ``GET /room/{token}`` with a token
that came out of a model), and a refactoring inside ``talk.py`` would have been free to take it
along, because the name said that nobody was watching. Discipline had already failed once here,
so the boundary gets a gate.

Two things make this gate trustworthy rather than decorative:

*   **It walks the tree, it does not grep the text.** ``tools/context.py`` names four private
    functions of other tool modules in prose, in the docstrings that explain which decisions it
    inherits from them. A text gate would go red on those four sentences, and the cheapest
    repair would be to delete them, which trades documentation for a green check. A docstring
    and a comment are no ``ast.Attribute`` node, so they cost nothing here, and ``context.py``
    is the second counter proof below for exactly that reason.
*   **Every finding names file, line and expression**, so a violation is a one line fix and
    never a hunt through the tree.

Why an ``ast`` gate and not ``ruff --select SLF``, measured instead of assumed (run of
2026-08-25): ``SLF`` reports three hits in ``src/`` and 53 in ``tests/``. Two of the three are an
object reaching into the internals of its own class in ``oauth/provider.py``, and all 53 in
``tests/`` are source gates doing the job they exist for. The lint rule would therefore cost two
``noqa`` lines plus a ``per-file-ignores`` entry, and after paying that it would still check a
different sentence than this file does: not "no private member anywhere" but "no module reaches
into the privates of a tool module that is not itself".
"""

import ast
from pathlib import Path, PurePosixPath

SRC = Path(__file__).resolve().parents[2] / "src" / "mcp_connector"
TOOLS = SRC / "tools"
PACKAGE = "mcp_connector"
TOOLS_PACKAGE = f"{PACKAGE}.tools"


def _source_files() -> list[Path]:
    """Every production source, not only the ones under ``tools/``.

    A reach out of ``server/`` or ``oauth/`` into a tool internal is the same break, and a gate
    that only looked at siblings would call it clean.
    """
    files = sorted(SRC.rglob("*.py"))
    assert files, f"no production sources found under {SRC}"
    return files


def _tool_modules() -> set[str]:
    """The module stems under ``tools/``, read from the directory and never listed by hand."""
    stems = {path.stem for path in TOOLS.glob("*.py") if path.stem != "__init__"}
    assert stems, f"no tool modules found under {TOOLS}"
    return stems


def _dotted(relative: str) -> str:
    """The module name a source file has inside the package, e.g. ``tools/talk.py``."""
    parts = PurePosixPath(relative).with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join((PACKAGE, *parts))


def _package_of(relative: str) -> str:
    """The package a relative import inside this file starts from."""
    dotted = _dotted(relative)
    if PurePosixPath(relative).name == "__init__.py":
        return dotted
    return dotted.rpartition(".")[0]


def _base_of(node: ast.ImportFrom, package: str) -> str:
    """What the ``from`` half of one import names, with the dots resolved.

    Level 0 is the absolute form, level 1 the package of the file itself, and every level
    above that climbs one package further up. All four forms occur in this tree.
    """
    if not node.level:
        return node.module or ""
    anchor = package.split(".")
    kept = anchor[: max(len(anchor) - (node.level - 1), 0)]
    base = ".".join(kept)
    if not node.module:
        return base
    return f"{base}.{node.module}" if base else node.module


def _aliases(tree: ast.Module, relative: str) -> dict[str, str]:
    """Local name to module name, for every import that names a *foreign* tool module.

    A name is only taken up when its module resolves to a ``.py`` file under ``tools/`` and is
    not the file being checked: a module reaching into its own privates is the normal case and
    the reason the underscore exists.
    """
    package = _package_of(relative)
    own = _dotted(relative)
    tools = _tool_modules()
    found: dict[str, str] = {}

    def keep(local: str, dotted: str) -> None:
        prefix, _, stem = dotted.rpartition(".")
        if dotted == own or prefix != TOOLS_PACKAGE or stem not in tools:
            return
        found[local] = dotted

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = _base_of(node, package)
            for alias in node.names:
                keep(alias.asname or alias.name, f"{base}.{alias.name}" if base else alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                # ``import a.b.c`` without ``as`` binds ``a``, and a reach through it would be
                # an attribute on an attribute, never a plain name. Only the aliased form and
                # the single segment form bind a name that can carry one.
                if alias.asname:
                    keep(alias.asname, alias.name)
                elif "." not in alias.name:
                    keep(alias.name, alias.name)
    return found


def _is_private(name: str) -> bool:
    """A single leading underscore is the promise; a dunder is the language."""
    if name.startswith("__") and name.endswith("__"):
        return False
    return name.startswith("_")


def _reaches(source: str, relative: str) -> list[str]:
    """Every reach into a foreign tool module's privates, in the form the failure prints.

    Takes the text and the name of a file rather than a path, so the gate and both counter
    proofs can use this one function. A counter proof that reimplements the check proves
    something about the counter proof.

    ``self._state`` and a module internal ``_helper()`` are no finding by construction and not
    by exception: neither is an attribute on the name of an imported module.

    Two spellings of the reach, two walks over the same tree: the attribute on a module alias
    (``talk_tools._room``) and the direct symbol import (``from .talk import _conversation``),
    which binds the private name locally and never produces an ``ast.Attribute`` at all. The
    import itself is the finding there, aliased or not: the moment the name crosses the module
    boundary, the promise of the underscore is broken, whatever it is called afterwards.
    """
    tree = ast.parse(source, filename=relative)
    aliases = _aliases(tree, relative)
    package = _package_of(relative)
    own = _dotted(relative)
    tools = _tool_modules()

    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = _base_of(node, package)
            prefix, _, stem = base.rpartition(".")
            if base == own or prefix != TOOLS_PACKAGE or stem not in tools:
                continue
            for alias in node.names:
                if _is_private(alias.name):
                    hits.append((node.lineno, f"from {base} import {alias.name}"))
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
            and _is_private(node.attr)
        ):
            hits.append((node.lineno, f"{node.value.id}.{node.attr}"))
    return [f"{relative}:{line}: {reach}" for line, reach in sorted(hits)]


def test_no_module_reaches_into_the_privates_of_a_tool_module() -> None:
    """TOOL-19: the underscore between the tool families is a gate, not an agreement."""
    findings: list[str] = []
    for path in _source_files():
        relative = path.relative_to(SRC).as_posix()
        findings.extend(_reaches(path.read_text(encoding="utf-8"), relative))

    assert findings == [], (
        "a module reaches into the privates of a foreign tool module:\n"
        + "\n".join(findings)
        + "\nMake the function public where it lives, with its caller and its reason in the "
        "docstring, the way talk.one_room and talk.one_message do it."
    )


#: One constructed module that carries the reach three times over: once as a real call, once in
#: a docstring and once in a comment. Only the call is a finding, and the two lines of prose are
#: the ones a text gate would have charged for.
_A_MODULE_THAT_REACHES = '''"""A module that borrows talk_tools._room, in prose and for real."""

from . import talk as talk_tools


class Borrower:
    def remember(self, address: str) -> None:
        # And once more in a comment, where talk_tools._room costs nothing.
        self._address = _label(address)


async def borrow(clients: object, token: str) -> object:
    return await talk_tools._room(clients, token, include_last_message=False)


def _label(value: str) -> str:
    return value.strip()
'''


def test_the_gate_finds_the_call_and_leaves_the_prose_alone() -> None:
    """Counter proof: one call, two sentences about it, exactly one finding.

    Both halves hang on that single number. A gate that missed the call would report none, and
    a gate that read text instead of nodes would report three. The two lines that are not
    findings are the ones a grep would have made expensive: a docstring and a comment.
    ``self._address`` and ``_label`` are in there for the same reason, one step smaller.
    """
    relative = "tools/borrower.py"
    findings = _reaches(_A_MODULE_THAT_REACHES, relative)

    wanted = next(
        number
        for number, line in enumerate(_A_MODULE_THAT_REACHES.splitlines(), start=1)
        if "return await" in line
    )
    assert findings == [f"{relative}:{wanted}: talk_tools._room"], findings


def test_the_gate_stays_green_on_the_module_that_explains_its_neighbours() -> None:
    """Counter proof: ``tools/context.py`` is the honest fixture for the filter.

    That file names four private functions of other tool modules in its docstrings, because it
    inherits their decisions and says so. It must pass, and it must pass without anybody
    shortening a sentence for it.
    """
    context = TOOLS / "context.py"
    relative = context.relative_to(SRC).as_posix()
    text = context.read_text(encoding="utf-8")

    assert "mail_tools._mailboxes" in text, (
        "context.py is the fixture because it names foreign privates in prose; if it stopped "
        "doing that, this counter proof stopped proving anything"
    )
    assert _reaches(text, relative) == []


def test_every_import_form_in_the_tree_is_resolved() -> None:
    """The alias resolution covers each spelling the tree actually uses, plus the aliased dot.

    Without this the gate could be green because it recognises one import style and walks past
    the other four; the inventory of forms is in the plan of 12-04.
    """
    forms = {
        "tools/one.py": "from . import talk as talk_tools",
        "tools/two.py": "from . import talk",
        "server/three.py": "from ..tools import talk as talk_tools",
        "oauth/four.py": "from mcp_connector.tools import talk as talk_tools",
        "exapp/five.py": "import mcp_connector.tools.talk as talk_tools",
    }
    for relative, line in forms.items():
        alias = "talk" if line == "from . import talk" else "talk_tools"
        source = f"{line}\n\nvalue = {alias}._conversation\n"
        assert _reaches(source, relative) == [f"{relative}:3: {alias}._conversation"], relative

    # The same call inside the module it belongs to is nobody's business but its own.
    own = "from . import talk\n\nvalue = talk._conversation\n"
    assert _reaches(own, "tools/talk.py") == []


def test_the_gate_finds_the_direct_import_of_a_private_name() -> None:
    """Counter proof: ``from .talk import _conversation`` is the cheapest spelling of the break.

    It binds the private name locally, so the later call is an ``ast.Name`` without any
    attribute, and the attribute walk alone would never see it. Each of the three ``from``
    depths the tree uses is checked, plus the aliased form: renaming the symbol on the way
    in hides nothing, because the import itself is the reach.
    """
    forms = {
        "tools/six.py": "from .talk import _conversation",
        "server/seven.py": "from ..tools.talk import _conversation",
        "oauth/eight.py": "from mcp_connector.tools.talk import _conversation",
    }
    for relative, line in forms.items():
        wanted = f"{relative}:1: from mcp_connector.tools.talk import _conversation"
        assert _reaches(f"{line}\n", relative) == [wanted], relative

    aliased = "from .talk import _conversation as conversation\n"
    assert _reaches(aliased, "tools/nine.py") == [
        "tools/nine.py:1: from mcp_connector.tools.talk import _conversation"
    ]

    # The same import inside the module it belongs to is nobody's business but its own,
    # and a public name over the same edge is what talk.one_room exists for, not a finding.
    assert _reaches("from .talk import _conversation\n", "tools/talk.py") == []
    assert _reaches("from .talk import one_room\n", "tools/ten.py") == []


def test_the_gate_looks_at_the_files_it_claims_to_look_at() -> None:
    """A typo in the root would leave a gate that checks nothing and says nothing."""
    checked = {path.relative_to(SRC).as_posix() for path in _source_files()}

    assert "tools/chatgpt.py" in checked, checked
    assert "tools/context.py" in checked, checked
    assert "tools/talk.py" in checked, checked
    assert len(checked) > 20, checked
