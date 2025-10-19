from collections.abc import Generator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import yaml

from calmlib.utils.pretty_yaml_dumper import PrettyDumper


class LineType(Enum):
    """Line types"""

    # Main item types
    TODO_ITEM = "todo_item"  # - a, - b, - ab (1-2 letters at indent 0)
    TASK_ITEM = "task_item"  # - 01, - 02 (exactly 2 digits)
    DUMP_ITEM = "dump_item"  # - 001, - 002 (exactly 3 digits)

    # Basic
    PLAIN_TEXT = "plain_text"  # plain text (implicit header)
    LIST_ITEM = "list_item"  # - anything else

    # Structural
    HEADER = "header"  # # Header, ## Header, etc.
    SEPARATOR = "separator"  # ---

    # empty
    EMPTY = "empty"  # blank lines

    # Complications
    CODE_BLOCK = "code_block"  # ```python, ```, ~~~python, ~~~


# ============================================================================
# Internal Parsing Structure
# ============================================================================


@dataclass
class ParsedLine:
    """Internal structure for parsed lines (used during parsing only)"""

    content: str  # Content after - and checkbox
    line_type: LineType
    indent_level: int = 0
    checked: bool | None = None  # None = no checkbox, False = [ ], True = [x]
    raw_text: str | None = None


NOT_A_HEADER = 999


@dataclass
class Item:
    """Base class for all items in a note"""

    indent_level: int = 0  # Actual spaces in document
    content: str = ""  # Main content (text after markers)
    children: list["Item"] = field(default_factory=list)
    checked: bool | None = None  # None = no checkbox, False = [ ], True = [x]
    _note: Optional["Note"] = None  # Back reference to parent Note
    parent: Optional["Item"] = None  # Back reference to parent Item

    @property
    def visual_level(self) -> int:
        """Visual level = indentation tier in document (0, 1, 2, ...)"""
        if self._note is None:
            raise ValueError(
                f"Item.visual_level accessed but _note not set. "
                f"Item must be linked to Note to calculate visual_level. "
                f"indent_level={self.indent_level}"
            )
        return self._note.visual_level_for_indent(self.indent_level)

    @property
    def has_checkbox(self) -> bool:
        """Does this item have a checkbox?"""
        return self.checked is not None

    @property
    def child_count(self) -> int:
        """Total number of direct children"""
        return len(self.children)

    @property
    def total_descendants(self) -> int:
        """Total number of all descendants (recursive)"""
        count = len(self.children)
        for child in self.children:
            count += child.total_descendants
        return count

    @property
    def depth(self) -> int:
        """Depth of the subtree (0 = no children, 1 = children but no grandchildren, etc)"""
        if not self.parent:
            return 0
        return 1 + self.parent.depth

    @property
    def max_depth(self) -> int:
        """Maximum depth of the subtree (0 = no children, 1 = children but no grandchildren, etc)"""
        if not self.children:
            return 0
        return 1 + max(child.max_depth for child in self.children)

    def render(self) -> list[str]:
        """Render this item and children back to text"""
        # Reconstruct line from components
        indent = " " * self.indent_level

        # Subclasses override _render_content() to provide their specific format
        content = self._render_content()

        line = indent + content
        lines = [line]

        for child in self.children:
            lines.extend(child.render())
        return lines

    def _render_content(self) -> str:
        """Override in subclasses to render content"""
        raise NotImplementedError("Subclasses must implement _render_content()")

    @property
    def header_level(self) -> int:
        return NOT_A_HEADER

    def add_child(self, child: "Item", index: int | None = None):
        if index is None:
            self.children.append(child)
        else:
            self.children.insert(index, child)
        if self._note:
            self._note._refresh_indent_levels()
            child._note = self._note
            child.parent = self

    def remove_child(self, child: "Item"):
        self.children.remove(child)
        if self._note:
            self._note._refresh_indent_levels()
            child.parent = None


@dataclass
class ListItem(Item):
    """Generic list items: - anything else"""

    def __repr__(self) -> str:
        check = "✓" if self.checked else "☐" if self.checked is False else ""
        preview = self.content[:20] + "..." if len(self.content) > 20 else self.content
        children_info = f", {self.child_count} children" if self.children else ""
        return f"ListItem({check}{preview!r}{children_info})"

    def _render_content(self) -> str:
        """Render: - [checkbox] content"""
        checkbox = ""
        if self.checked is not None:
            checkbox = "[x] " if self.checked else "[ ] "
        return f"- {checkbox}{self.content}"


@dataclass
class TodoItem(ListItem):
    """Items with 1-2 letter pattern at indent 0: - a, - b, - ab"""

    @property
    def letter(self) -> str:
        """Extract letter(s) from content (case insensitive)"""
        return self.content

    @property
    def text(self) -> str:
        """Get all text content (children rendered without indent/letter)"""
        lines = []
        for child in self.children:
            # Render child tree and strip leading indent
            child_lines = child.render()
            for line in child_lines:
                lines.append(line.strip())
        return "\n".join(lines)

    @property
    def is_complex(self) -> bool:
        """
        Heuristic: is this todo complex enough to warrant a separate page?

        Criteria:
        - max_depth > 2 (more than 2 visual indents deep)
        - child_count >= 10 (10+ direct children)
        """
        return self.max_depth > 2 or self.child_count >= 10

    def add_child(
        self, content: str, indent: int = 4, checked: bool | None = None
    ) -> "ListItem":
        """
        Add a child list item to this todo

        Args:
            content: Text content of the list item
            indent: Indent level (default 4 for first level)
            checked: Checkbox state (None = no checkbox)

        Returns:
            The created ListItem
        """
        child = ListItem(
            indent_level=indent,
            content=content,
            checked=checked,
        )
        self.children.append(child)
        if self._note:
            self._note._refresh_indent_levels()
            child._note = self._note
        return child

    def __repr__(self) -> str:
        check = "✓" if self.checked else "☐" if self.checked is False else ""
        children_info = f", {self.child_count} children" if self.children else ""
        return f"TodoItem({check}{self.letter!r}{children_info})"

    def _render_content(self) -> str:
        """Render: - [checkbox] letter"""
        checkbox = ""
        if self.checked is not None:
            checkbox = "[x] " if self.checked else "[ ] "
        return f"- {checkbox}{self.content}"


@dataclass
class EmptyItem(Item):
    """Empty lines - important for preserving spacing"""

    def __repr__(self) -> str:
        return f"EmptyItem(indent={self.indent_level})"

    def _render_content(self) -> str:
        """Render: empty string"""
        return ""

    # @property
    # def header_level(self) -> int:
    #     return 9


@dataclass
class TaskItem(ListItem):
    """Items with 2-digit pattern: - 01, - 02, - 99"""

    @property
    def number(self) -> str:
        """Extract 2-digit number from content"""
        return self.content

    def __repr__(self) -> str:
        check = "✓" if self.checked else "☐" if self.checked is False else ""
        children_info = f", {self.child_count} children" if self.children else ""
        return f"TaskItem({check}{self.number!r}{children_info})"

    def _render_content(self) -> str:
        """Render: - [checkbox] number"""
        checkbox = ""
        if self.checked is not None:
            checkbox = "[x] " if self.checked else "[ ] "
        return f"- {checkbox}{self.content}"


@dataclass
class DumpItem(ListItem):
    """Items with 3-digit pattern: - 001, - 002, - 999"""

    @property
    def number(self) -> str:
        """Extract 3-digit number from content"""
        return self.content

    def __repr__(self) -> str:
        check = "✓" if self.checked else "☐" if self.checked is False else ""
        children_info = f", {self.child_count} children" if self.children else ""
        return f"DumpItem({check}{self.number!r}{children_info})"

    def _render_content(self) -> str:
        """Render: - [checkbox] number"""
        checkbox = ""
        if self.checked is not None:
            checkbox = "[x] " if self.checked else "[ ] "
        return f"- {checkbox}{self.content}"


@dataclass
class CodeBlock(Item):
    """Code block"""

    def __repr__(self) -> str:
        return f"CodeBlock({self.content!r})"

    def _render_content(self) -> str:
        return self.content


@dataclass
class Separator(Item):
    """Separator"""

    def __repr__(self) -> str:
        return f"Separator({self.content!r})"

    def _render_content(self) -> str:
        return self.content


@dataclass
class Header(Item):
    """Header"""

    def __repr__(self) -> str:
        return f"Header({self.content!r})"

    def _render_content(self) -> str:
        # todo: rework to store '#' part as level * '#', not in content
        return self.content

    @property
    def header_level(self) -> int:
        return len(self.content) - len(self.content.lstrip("#"))


@dataclass
class PlainText(Item):
    """Plain text"""

    def __repr__(self) -> str:
        return f"PlainText({self.content!r})"

    def _render_content(self) -> str:
        return self.content

    @property
    def header_level(self) -> int:
        return 9


ITEM_TYPES = {
    LineType.TODO_ITEM: TodoItem,
    LineType.TASK_ITEM: TaskItem,
    LineType.DUMP_ITEM: DumpItem,
    LineType.LIST_ITEM: ListItem,
    LineType.EMPTY: EmptyItem,
    LineType.CODE_BLOCK: CodeBlock,
    LineType.SEPARATOR: Separator,
    LineType.HEADER: Header,
    LineType.PLAIN_TEXT: PlainText,
    "todo": TodoItem,
    "task": TaskItem,
    "dump": DumpItem,
    "list": ListItem,
    "empty": EmptyItem,
    "code_block": CodeBlock,
    "separator": Separator,
    "header": Header,
    "plain_text": PlainText,
}


def walk(item: Item):
    yield item
    for child in item.children:
        yield from walk(child)


@dataclass
class Note:
    items: list[Item] = field(default_factory=list)
    frontmatter: dict[str, Any] = field(default_factory=dict)  # YAML frontmatter
    _indent_levels: list[int] = field(
        default_factory=list
    )  # Sorted unique indent levels

    @classmethod
    def from_text(cls, text: str) -> "Note":
        from calmlib.obsidian.note_parser.parser import Parser

        parser = Parser()
        return parser.parse_note(text, cls)

    def render(self) -> str:
        lines = []

        # Render frontmatter if present
        if self.frontmatter:
            lines.append("---")
            frontmatter_yaml = yaml.dump(
                self.frontmatter,
                allow_unicode=True,
                sort_keys=False,
                Dumper=PrettyDumper,
            ).strip()
            lines.extend(frontmatter_yaml.splitlines())
            lines.append("---")

        # Render items
        for item in self.items:
            lines.extend(item.render())

        return "\n".join(lines) + "\n"

    def headers(self, level: int | None = None) -> list[Item]:
        """Get header items in the note
        level = None -> All headers
        level = 0 -> Level 0 headers meaning highest level headers in a doc (if # is missing -> ## etc.)
        if any '#' is missing -> plain text indent=0 are considered level 0 headers
        """
        header_levels = set()
        for item in self.items:
            header_levels.add(item.header_level)
        if level is not None:
            assert len(header_levels) > level, f"Header level {level} not found in note"
            header_level = sorted(header_levels)[level]
            return [item for item in self.items if item.header_level == header_level]

        return [item for item in self.items if item.header_level != NOT_A_HEADER]

    @property
    def all_items(self) -> Generator[Item, None, None]:
        for item in self.items:
            yield from walk(item)

    def _refresh_indent_levels(self):
        """Recalculate indent levels after adding items"""
        indent_levels = set()
        for item in self.items:
            for child in self.all_items:
                indent_levels.add(child.indent_level)
        self._indent_levels = sorted(indent_levels)

    def visual_level_for_indent(self, indent: int) -> int:
        """
        Map indent_level (spaces) to visual_level (tier)

        Example: if _indent_levels = [0, 4, 8]
        - indent 0 -> visual_level 0
        - indent 4 -> visual_level 1
        - indent 8 -> visual_level 2
        """
        if indent not in self._indent_levels:
            raise ValueError(
                f"Indent {indent} not found in document indent levels: {self._indent_levels}"
            )
        return self._indent_levels.index(indent)

    def indent_for_visual_level(self, level: int) -> int:
        """
        Map visual_level (tier) to indent_level (spaces)

        Example: if _indent_levels = [0, 4, 8]
        - visual_level 0 -> indent 0
        - visual_level 1 -> indent 4
        - visual_level 2 -> indent 8
        """
        assert level < len(self._indent_levels), (
            f"Visual level {level} not found in document indent levels: {self._indent_levels}"
        )
        return self._indent_levels[level]

    def bump_indent_levels(self, items: list[Item]):
        for item in items:
            index = self._indent_levels.index(item.indent_level)
            if index == len(self._indent_levels) - 1:
                self._indent_levels.append(item.indent_level + 4)
            item.indent_level = self._indent_levels[index + 1]
            self.bump_indent_levels(item.children)

    def find_available_letter(self) -> str:
        """Auto-pick next available letter for todo"""
        existing_todos = self.get_items(item_type=TodoItem)
        used_letters = set()
        for item in existing_todos:
            assert isinstance(item, TodoItem), "Item is not a TodoItem"
            used_letters.add(item.letter.lower())

        # Try single letters first (a-z)
        for letter in "abcdefghijklmnopqrstuvwxyz":
            if letter not in used_letters:
                return letter

        # Try double letters (aa, ab, ac, ...)
        for first in "abcdefghijklmnopqrstuvwxyz":
            for second in "abcdefghijklmnopqrstuvwxyz":
                combo = first + second
                if combo not in used_letters:
                    return combo

        raise ValueError("Ran out of available letter combinations!")

    def get_items(
        self,
        item_type: str | LineType | type | None = None,
        visual_level: int | None = None,
        checked: bool | None = None,
    ) -> list[Item]:
        """Get items matching criteria across all sections"""
        if not isinstance(item_type, type):
            item_type = ITEM_TYPES[item_type]
        assert isinstance(item_type, type), f"Item type {item_type} is not a type"
        results = []
        for item in self.all_items:
            if item_type is not None and not isinstance(item, item_type):
                continue
            if visual_level is not None and item.visual_level != visual_level:
                continue
            if checked is not None and item.checked != checked:
                continue
            results.append(item)
        return results
