import json
from pathlib import Path

from calmlib.obsidian.note_parser.models import (
    CodeBlock,
    DumpItem,
    EmptyItem,
    Header,
    ListItem,
    PlainText,
    Separator,
    TaskItem,
    TodoItem,
)
from calmlib.obsidian.note_parser.parser import parse_items

resources_dir = Path(__file__).parent / "resources"
source_dir = resources_dir / "source"
expected_dir = resources_dir / "expected"
complex_source_dir = resources_dir / "complex_source"
complex_expected_dir = resources_dir / "complex_expected"


TYPE_MAP = {
    TodoItem: "todo",
    ListItem: "list_item",
    TaskItem: "task",
    DumpItem: "dump",
    Header: "header",
    PlainText: "plain_text",
    Separator: "separator",
    CodeBlock: "code_block",
    EmptyItem: "empty",
}


def item_to_dict(item):
    """Convert Item to dict for JSON comparison"""
    item_type = type(item)
    if item_type not in TYPE_MAP:
        raise ValueError(f"Unknown item type: {item_type}")

    result = {
        "type": TYPE_MAP[item_type],
        "text": item.content,
    }
    if item.checked is not None:
        result["checked"] = item.checked
    if item.children:
        result["children"] = [item_to_dict(child) for child in item.children]
    return result


import pytest

COMPLEX_EXAMPLES = [
    "example_1",
    "example_2",
    "example_3",
    "example_4",
    "example_5",
    "workalong_example",
    "dump_example",
    "daily_example",
    "person_example",
    "project_example",
    "action_example",
]


@pytest.mark.parametrize(
    "filename",
    [
        "todos",
        "tasks",
        "dumps",
        "todos_2",
        "tasks_2",
        "dumps_2",
        "headers",
        "plain_text",
        "separators",
        "code_blocks",
        "empty_lines",
        "list_items",
    ]
    + COMPLEX_EXAMPLES,
)
def test_item_types(filename):
    """Test parsing of different item types"""
    # Determine which directories to use
    if filename in COMPLEX_EXAMPLES:
        src_dir = complex_source_dir
        exp_dir = complex_expected_dir
    else:
        src_dir = source_dir
        exp_dir = expected_dir

    # Read source
    source_file = src_dir / f"{filename}.md"
    with open(source_file) as f:
        text = f.read()

    # Parse
    items = parse_items(text)

    # Convert to dict
    result = {"items": [item_to_dict(item) for item in items]}

    # Read expected
    expected_file = exp_dir / f"{filename}.json"
    if not expected_file.exists():
        expected_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    expected = json.loads(expected_file.read_text())

    # Compare
    assert result == expected, (
        f"Parsed result doesn't match expected.\nGot: {json.dumps(result, indent=2)}\nExpected: {json.dumps(expected, indent=2)}"
    )


def normalize_text(text: str) -> str:
    """Normalize text for comparison, ignoring cosmetic differences"""
    import re

    lines = text.splitlines()

    # Normalize YAML frontmatter quotes and null values
    in_frontmatter = False
    normalized_lines = []
    for line in lines:
        if line.strip() == "---":
            in_frontmatter = not in_frontmatter
            normalized_lines.append(line)
        elif in_frontmatter:
            # Normalize quotes: both single and double quotes to single
            line = re.sub(r'"([^"]*)"', r"'\1'", line)
            # Normalize null values: "key: null" becomes "key:"
            line = re.sub(r"^(\s*\w+):\s*null\s*$", r"\1:", line)
            normalized_lines.append(line)
        else:
            normalized_lines.append(line)

    return "\n".join(normalized_lines)


@pytest.mark.parametrize(
    "filename",
    [
        "todos",
        "tasks",
        "dumps",
        "todos_2",
        "tasks_2",
        "dumps_2",
        "headers",
        "plain_text",
        "separators",
        "code_blocks",
        "empty_lines",
        "list_items",
    ]
    + COMPLEX_EXAMPLES,
)
def test_roundtrip(filename):
    """Test that parsing and rendering returns the same text"""
    # Determine which directory to use
    if filename in COMPLEX_EXAMPLES:
        src_dir = complex_source_dir
    else:
        src_dir = source_dir

    # Read source
    source_file = src_dir / f"{filename}.md"
    with open(source_file) as f:
        original_text = f.read()

    # Parse using Note.from_text to preserve frontmatter
    from calmlib.obsidian.note_parser.models import Note

    note = Note.from_text(original_text)

    # Render back
    rendered_text = note.render()

    # Normalize both for comparison (handles trailing whitespace and empty lines)
    normalized_original = normalize_text(original_text)
    normalized_rendered = normalize_text(rendered_text)

    # Compare
    if normalized_rendered != normalized_original:
        import difflib

        diff = difflib.unified_diff(
            normalized_original.splitlines(keepends=True),
            normalized_rendered.splitlines(keepends=True),
            fromfile="original",
            tofile="rendered",
            lineterm="",
        )
        diff_text = "".join(diff)
        assert False, (
            f"Round-trip failed.\n\nDiff:\n{diff_text}\n\n"
            f"Original:\n{normalized_original}\n\nRendered:\n{normalized_rendered}"
        )
