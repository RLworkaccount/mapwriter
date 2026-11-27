"""Write scene data as YAML that reads like a hand-written scene file.

Small items (a prop, a door, a light) go on one line as ``{ want: chair, at: [3, 4] }``;
bigger things (a room with doors and windows) are written out as blocks.
"""
from __future__ import annotations

import yaml

LINE = 110


def _flow(v) -> str:
    s = yaml.safe_dump(v, default_flow_style=True, sort_keys=False, width=10 ** 6, allow_unicode=True).strip()
    if s.endswith("..."):
        s = s[:-3].strip()
    if isinstance(v, dict) and s.startswith("{") and s.endswith("}"):
        s = "{ " + s[1:-1] + " }"
    return s


def _simple(v) -> bool:
    if isinstance(v, dict):
        return all(_simple(x) for x in v.values())
    if isinstance(v, list):
        return all(not isinstance(x, dict) and _simple(x) for x in v)
    return True


def _emit(v, indent: int, out: list[str]):
    pad = " " * indent
    if isinstance(v, dict):
        for k, x in v.items():
            key = _flow(k)
            if isinstance(x, (dict, list)) and x and not (_simple(x) and len(pad) + len(key) + len(_flow(x)) + 2 <= LINE):
                out.append(f"{pad}{key}:")
                _emit(x, indent + 2, out)
            else:
                out.append(f"{pad}{key}: {_flow(x)}")
    elif isinstance(v, list):
        for x in v:
            if isinstance(x, dict) and _simple(x) and len(pad) + len(_flow(x)) + 2 <= LINE:
                out.append(f"{pad}- {_flow(x)}")
            elif isinstance(x, dict):
                sub: list[str] = []
                _emit(x, indent + 2, sub)
                out.append(f"{pad}- {sub[0].lstrip()}")
                out += sub[1:]
            else:
                out.append(f"{pad}- {_flow(x)}")
    else:
        out.append(f"{pad}{_flow(v)}")


def dump(data: dict, header: str | None = None) -> str:
    out: list[str] = []
    if header:
        out += [f"# {line}".rstrip() for line in header.splitlines()]
    for i, (k, v) in enumerate(data.items()):
        if i and isinstance(v, (list, dict)) and not (_simple(v) and len(_flow(v)) < 60):
            out.append("")
        _emit({k: v}, 0, out)
    text = "\n".join(out) + "\n"
    assert yaml.safe_load(text) == data, "yaml writer lost data"
    return text
