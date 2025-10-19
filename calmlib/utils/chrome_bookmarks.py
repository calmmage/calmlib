#!/usr/bin/env python3
"""
Chrome Bookmarks CLI (local, offline)

Features:
- Auto-detects Chrome Bookmarks file (macOS/Linux/Windows)
- Lists and searches bookmarks
- Adds URLs and creates folders
- Removes items by id or by query
- Makes timestamped backups before writing

Notes:
- Close Chrome before modifying bookmarks to avoid sync overwrite.
- Works with the JSON Bookmarks file directly; Chrome recomputes checksum.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import platform
import shutil
import sys
from collections.abc import Iterable
from pathlib import Path

# ---------- Paths & IO ----------


def default_chrome_user_data_dir(browser: str = "chrome") -> Path:
    home = Path.home()
    system = platform.system()
    browser = browser.lower()

    # Map browser to base directory names
    if system == "Darwin":  # macOS
        if browser == "chrome":
            return home / "Library/Application Support/Google/Chrome"
        elif browser == "chromium":
            return home / "Library/Application Support/Chromium"
        elif browser == "brave":
            return home / "Library/Application Support/BraveSoftware/Brave-Browser"
    elif system == "Windows":
        local = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if not local:
            raise RuntimeError("Cannot determine LOCALAPPDATA/APPDATA on Windows.")
        if browser == "chrome":
            return Path(local) / "Google/Chrome/User Data"
        elif browser == "chromium":
            return Path(local) / "Chromium/User Data"
        elif browser == "brave":
            return Path(local) / "BraveSoftware/Brave-Browser/User Data"
    else:  # Linux / other unix
        if browser == "chrome":
            return home / ".config/google-chrome"
        elif browser == "chromium":
            return home / ".config/chromium"
        elif browser == "brave":
            return home / ".config/BraveSoftware/Brave-Browser"

    raise RuntimeError(f"Unsupported browser '{browser}' for {system}.")


def bookmarks_file_path(
    browser: str = "chrome", profile: str = "Default", explicit: Path | None = None
) -> Path:
    if explicit:
        return explicit
    return default_chrome_user_data_dir(browser) / profile / "Bookmarks"


def load_bookmarks(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def backup(path: Path) -> Path:
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = path.with_name(f"{path.name}.bak.{ts}")
    shutil.copy2(path, dst)
    return dst


def save_bookmarks(path: Path, data: dict, make_backup: bool = True) -> None:
    if make_backup and path.exists():
        backup(path)
    # Remove checksum to let Chrome recompute
    data.pop("checksum", None)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


# ---------- Tree utilities ----------

Node = dict


def _roots(data: dict) -> dict[str, Node]:
    return data.get("roots", {})


def _iter_nodes(
    roots: dict[str, Node], include_folders: bool = True
) -> Iterable[tuple[Node, list[str], Node | None, int | None]]:
    stack: list[tuple[Node, list[str], Node | None]] = []
    for key in ["bookmark_bar", "other", "synced"]:
        if key in roots:
            stack.append((roots[key], [key], None))
    while stack:
        node, path_parts, parent = stack.pop()
        # Yield folders by default, URLs always
        if node.get("type") == "url" or include_folders:
            # index within parent will be resolved by parent when needed
            yield node, path_parts, parent, None
        if node.get("type") == "folder":
            for child in reversed(node.get("children", [])):
                stack.append((child, path_parts + [child.get("name", "")], node))


def _find_folder_by_path(roots: dict[str, Node], folder_path: str) -> Node | None:
    parts = [p for p in folder_path.split("/") if p]
    if not parts:
        return None
    # Root must be one of the named roots
    root_key = parts[0]
    node = roots.get(root_key)
    if not node or node.get("type") != "folder":
        return None
    for segment in parts[1:]:
        found = None
        for ch in node.get("children", []):
            if ch.get("type") == "folder" and ch.get("name") == segment:
                found = ch
                break
        if not found:
            return None
        node = found
    return node


def _ensure_folder_path(
    roots: dict[str, Node], folder_path: str, next_id: callable
) -> Node:
    parts = [p for p in folder_path.split("/") if p]
    if not parts:
        raise ValueError("Folder path cannot be empty")
    root_key = parts[0]
    node = roots.get(root_key)
    if not node or node.get("type") != "folder":
        raise ValueError(
            f"Root '{root_key}' not found. Use one of: bookmark_bar, other, synced"
        )
    for segment in parts[1:]:
        found = None
        for ch in node.get("children", []):
            if ch.get("type") == "folder" and ch.get("name") == segment:
                found = ch
                break
        if not found:
            new_folder = {
                "type": "folder",
                "name": segment,
                "id": str(next_id()),
                "date_added": "0",
                "children": [],
            }
            node.setdefault("children", []).append(new_folder)
            node = new_folder
        else:
            node = found
    return node


def _collect_max_id(roots: dict[str, Node]) -> int:
    max_id = 0
    for node, _, _, _ in _iter_nodes(roots, include_folders=True):
        try:
            max_id = max(max_id, int(node.get("id", 0)))
        except ValueError:
            continue
    return max_id


def _generate_id_func(roots: dict[str, Node]):
    start = _collect_max_id(roots)
    counter = start

    def next_id() -> int:
        nonlocal counter
        counter += 1
        return counter

    return next_id


def format_tree(
    roots: dict[str, Node], flat: bool = False, urls_only: bool = False
) -> str:
    """Format bookmarks tree as a string instead of printing."""
    lines = []

    def emit(prefix: str, node: Node, path: list[str]):
        t = node.get("type")
        nid = node.get("id", "")
        if t == "folder":
            if not urls_only:
                lines.append(f"{prefix}[{nid}] 📁 {'/'.join(path)}")
        else:
            url = node.get("url", "")
            name = node.get("name", "")
            if flat:
                lines.append(f"[{nid}] 🔗 {name}  <{url}>  — {'/'.join(path[:-1])}")
            else:
                lines.append(f"{prefix}[{nid}] 🔗 {name}  <{url}>")

    def walk(node: Node, depth: int, path: list[str]):
        prefix = ("  " * depth) if not flat else ""
        if node.get("type") == "folder":
            if not urls_only:
                emit(prefix, node, path)
            for ch in node.get("children", []):
                ch_path = (
                    path + [ch.get("name", "")]
                    if ch.get("type") == "folder"
                    else path + [ch.get("name", "")]
                )
                walk(ch, depth + (0 if flat else 1), ch_path)
        else:
            emit(prefix, node, path)

    for key in ["bookmark_bar", "other", "synced"]:
        if key in roots:
            walk(roots[key], 0, [key])

    return "\n".join(lines)


def print_tree(
    roots: dict[str, Node], flat: bool = False, urls_only: bool = False
) -> None:
    """Print bookmarks tree to stdout."""
    print(format_tree(roots, flat=flat, urls_only=urls_only))


def search(
    roots: dict[str, Node], query: str, field: str = "both"
) -> list[tuple[Node, list[str]]]:
    q = query.lower()
    out: list[tuple[Node, list[str]]] = []
    for node, path, _, _ in _iter_nodes(roots, include_folders=False):
        if node.get("type") != "url":
            continue
        name = node.get("name", "").lower()
        url = node.get("url", "").lower()
        if field == "name" and q in name:
            out.append((node, path))
        elif field == "url" and q in url:
            out.append((node, path))
        elif field == "both" and (q in name or q in url):
            out.append((node, path))
    return out


def remove_by_id(roots: dict[str, Node], node_id: str) -> bool:
    # DFS with parent references
    stack: list[tuple[Node, Node | None]] = []
    for key in ["bookmark_bar", "other", "synced"]:
        if key in roots:
            stack.append((roots[key], None))
    while stack:
        node, parent = stack.pop()
        if node.get("id") == node_id:
            if parent is None:
                # do not remove a root
                return False
            children = parent.get("children", [])
            for i, ch in enumerate(children):
                if ch is node:
                    del children[i]
                    return True
        if node.get("type") == "folder":
            for ch in node.get("children", []):
                stack.append((ch, node))
    return False


def remove_duplicate_urls(roots: dict[str, Node]) -> int:
    """
    Remove duplicate bookmarks by URL, keeping the one with the shortest folder path.
    Returns the number of duplicates removed.
    """
    from collections import defaultdict

    # Track duplicates by URL
    url_to_nodes = defaultdict(list)

    # Collect all bookmark nodes with their paths
    for node, path, parent, _ in _iter_nodes(roots, include_folders=True):
        if node.get("type") == "url":
            url = node.get("url", "")
            url_to_nodes[url].append(
                {"node": node, "path": path, "parent": parent, "path_length": len(path)}
            )

    # Find duplicates
    duplicates = {url: nodes for url, nodes in url_to_nodes.items() if len(nodes) > 1}

    if not duplicates:
        return 0

    # For each duplicate URL, keep the one with shortest path
    nodes_to_remove = []
    for url, nodes in duplicates.items():
        # Sort by path length (ascending)
        nodes_sorted = sorted(nodes, key=lambda x: x["path_length"])
        to_remove = nodes_sorted[1:]  # Remove all except the first (shortest path)
        nodes_to_remove.extend(to_remove)

    # Remove duplicates from their parent folders
    removed_count = 0
    for item in nodes_to_remove:
        parent = item["parent"]
        node = item["node"]
        if parent and "children" in parent:
            try:
                parent["children"].remove(node)
                removed_count += 1
            except ValueError:
                pass  # Already removed

    return removed_count


# ---------- CLI commands ----------


def cmd_list(args: argparse.Namespace) -> int:
    path = bookmarks_file_path(
        browser=args.browser,
        profile=args.profile,
        explicit=Path(args.file) if args.file else None,
    )
    data = load_bookmarks(path)
    roots = _roots(data)
    if args.folder:
        folder = _find_folder_by_path(roots, args.folder)
        if not folder:
            print(f"Folder not found: {args.folder}", file=sys.stderr)
            return 2
        # Print just this subtree; wrap as pseudo-roots
        pseudo = {"root": folder}
        print_tree({"root": folder}, flat=args.flat, urls_only=args.urls_only)
        return 0
    print_tree(roots, flat=args.flat, urls_only=args.urls_only)
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    path = bookmarks_file_path(
        browser=args.browser,
        profile=args.profile,
        explicit=Path(args.file) if args.file else None,
    )
    data = load_bookmarks(path)
    results = search(_roots(data), args.query, field=args.field)
    for node, p in results:
        nid = node.get("id", "")
        name = node.get("name", "")
        url = node.get("url", "")
        print(f"[{nid}] 🔗 {name}  <{url}>  — {'/'.join(p[:-1])}")
    return 0


def cmd_mkdir(args: argparse.Namespace) -> int:
    path = bookmarks_file_path(
        browser=args.browser,
        profile=args.profile,
        explicit=Path(args.file) if args.file else None,
    )
    data = load_bookmarks(path)
    roots = _roots(data)
    next_id = _generate_id_func(roots)
    folder = _ensure_folder_path(roots, args.folder, next_id)
    save_bookmarks(path, data, make_backup=not args.no_backup)
    print(f"Ensured folder: {'/'.join([args.folder])}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    if not args.name:
        args.name = args.url
    path = bookmarks_file_path(
        browser=args.browser,
        profile=args.profile,
        explicit=Path(args.file) if args.file else None,
    )
    data = load_bookmarks(path)
    roots = _roots(data)
    next_id = _generate_id_func(roots)
    folder = _ensure_folder_path(roots, args.folder, next_id)

    new_node = {
        "type": "url",
        "name": args.name,
        "url": args.url,
        "id": str(next_id()),
        "date_added": "0",
    }
    children = folder.setdefault("children", [])
    pos = max(
        0,
        min(
            args.position if args.position is not None else len(children), len(children)
        ),
    )
    children.insert(pos, new_node)
    save_bookmarks(path, data, make_backup=not args.no_backup)
    print(
        f"Added: [{new_node['id']}] {args.name} -> {args.url}  to {args.folder} at {pos}"
    )
    return 0


def cmd_rm(args: argparse.Namespace) -> int:
    path = bookmarks_file_path(
        browser=args.browser,
        profile=args.profile,
        explicit=Path(args.file) if args.file else None,
    )
    data = load_bookmarks(path)
    roots = _roots(data)

    if args.id:
        ok = remove_by_id(roots, args.id)
        if not ok:
            print(f"No node with id {args.id}", file=sys.stderr)
            return 2
        save_bookmarks(path, data, make_backup=not args.no_backup)
        print(f"Removed id {args.id}")
        return 0

    if args.match:
        matches = search(roots, args.match, field=args.field)
        if not matches:
            print("No matches.")
            return 0
        if not args.yes and sys.stdin.isatty():
            for node, p in matches:
                print(
                    f"[{node.get('id')}] {node.get('name')} <{node.get('url')}> — {'/'.join(p[:-1])}"
                )
            ans = input(f"Remove {len(matches)} item(s)? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                print("Aborted.")
                return 1
        removed = 0
        for node, _ in matches:
            if remove_by_id(roots, node.get("id", "")):
                removed += 1
        if removed:
            save_bookmarks(path, data, make_backup=not args.no_backup)
        print(f"Removed {removed} item(s)")
        return 0

    print("Specify --id or --match", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Work with local Chrome/Chromium/Brave bookmarks.",
    )
    p.add_argument(
        "--browser",
        default="chrome",
        choices=["chrome", "chromium", "brave"],
        help="Target browser profile root",
    )
    p.add_argument(
        "--profile",
        default="Default",
        help="Profile directory name, e.g. 'Default', 'Profile 2'",
    )
    p.add_argument(
        "--file", help="Explicit Bookmarks file path (overrides browser/profile)"
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="List bookmarks")
    sp.add_argument("--folder", help="Limit to a folder path like 'bookmark_bar/Dev'")
    sp.add_argument("--flat", action="store_true", help="Flat listing with paths")
    sp.add_argument(
        "--urls-only", action="store_true", help="Only list URLs, skip folders"
    )
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("search", help="Search bookmarks")
    sp.add_argument("query")
    sp.add_argument("--field", choices=["name", "url", "both"], default="both")
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("mkdir", help="Ensure a folder path exists")
    sp.add_argument("folder", help="Folder path like 'bookmark_bar/Dev/Work'")
    sp.add_argument(
        "--no-backup", action="store_true", help="Do not create a backup before saving"
    )
    sp.set_defaults(func=cmd_mkdir)

    sp = sub.add_parser("add", help="Add a URL to a folder")
    sp.add_argument("folder", help="Folder path like 'bookmark_bar/Dev'")
    sp.add_argument("url", help="URL to add")
    sp.add_argument("--name", help="Display name (defaults to URL)")
    sp.add_argument("--position", type=int, help="Insert position (0-based)")
    sp.add_argument(
        "--no-backup", action="store_true", help="Do not create a backup before saving"
    )
    sp.set_defaults(func=cmd_add)

    sp = sub.add_parser("rm", help="Remove bookmarks by id or match")
    sp.add_argument("--id", help="Bookmark id to remove")
    sp.add_argument("--match", help="Substring match to remove multiple items")
    sp.add_argument("--field", choices=["name", "url", "both"], default="both")
    sp.add_argument(
        "--yes", "-y", action="store_true", help="Assume yes for destructive ops"
    )
    sp.add_argument(
        "--no-backup", action="store_true", help="Do not create a backup before saving"
    )
    sp.set_defaults(func=cmd_rm)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(f"File not found: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
