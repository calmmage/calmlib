from typing import Any

import yaml
from loguru import logger

from calmlib.obsidian.note_parser.models import (
    ITEM_TYPES,
    EmptyItem,
    Item,
    LineType,
    Note,
    ParsedLine,
)


class Parser:
    def parse_note(self, text: str, cls: type["Note"]) -> "Note":
        # Extract frontmatter first
        frontmatter, content = self._extract_frontmatter(text)

        # Parse the content
        items = self.parse_items(content)

        return cls(items=items, frontmatter=frontmatter)

    def _extract_frontmatter(self, text: str) -> tuple[dict[str, Any], str]:
        """
        Extract YAML frontmatter from text if present.

        Returns: (frontmatter_dict, content_without_frontmatter)
        """
        lines = text.splitlines()

        # Check if text starts with frontmatter delimiter
        if not lines or lines[0].strip() != "---":
            return {}, text

        # Find closing delimiter
        frontmatter_lines = []
        content_start_idx = 0

        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                # Found closing delimiter
                content_start_idx = i + 1
                break
            frontmatter_lines.append(line)
        else:
            # No closing delimiter found, treat as regular content
            return {}, text

        # Parse YAML
        frontmatter_text = "\n".join(frontmatter_lines)
        try:
            frontmatter = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse frontmatter: {e}")
            frontmatter = {}

        # Return content without frontmatter
        content = "\n".join(lines[content_start_idx:])
        return frontmatter, content

    def parse_items(self, text: str) -> list[Item]:
        lines = self._parse_lines(text)
        items = self._build_tree(lines)

        return items

    def _parse_lines(self, text: str) -> list[ParsedLine]:
        lines = []
        in_code_block = False
        code_block_text = ""
        for line in text.splitlines():
            # if in code block -> special handling
            if line.startswith("```"):
                if in_code_block:
                    code_block_text += line
                    lines.append(
                        ParsedLine(
                            line_type=LineType.CODE_BLOCK, content=code_block_text
                        )
                    )
                    code_block_text = ""
                in_code_block = not in_code_block
                if not in_code_block:
                    continue
            if in_code_block:
                code_block_text += line + "\n"
                continue

            # 1. Calculate indent
            indent_level = self._calculate_indent(line)

            # 2. Extract checkbox and content
            checked, content_after_checkbox = self._extract_checkbox(line.strip())

            # 3. Determine line type
            line_type = self._determine_line_type(
                line, indent_level, content_after_checkbox
            )

            # 4. Create ParsedLine
            parsed_line = ParsedLine(
                raw_text=line,
                line_type=line_type,
                indent_level=indent_level,
                content=content_after_checkbox,
                checked=checked,
            )
            lines.append(parsed_line)
        return lines

    def _calculate_indent(self, line: str) -> int:
        """Calculate indentation level (spaces before content)"""
        # warn if there are tabs
        if "\t" in line:
            logger.warning(f"Tab found in line: {line} - indent calculation ambiguous")
        line = line.replace("\t", "    ")
        return len(line) - len(line.lstrip())

    separator_lines = ("---", "- ---")

    def _extract_checkbox(self, line: str) -> tuple[bool | None, str]:
        """
        Extract checkbox state and content without checkbox or list marker

        Returns: (checked_state, pure_content)
        - (None, content) if no checkbox
        - (False, content) if [ ]
        - (True, content) if [x]

        Content has "- " and checkbox removed
        """
        stripped = line.strip()
        if stripped in self.separator_lines:
            return (None, stripped)

        # Remove list marker if present
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()

        # Check for checkbox patterns
        if stripped.startswith("[ ]"):
            # Unchecked: - [ ] task
            content = stripped[3:].strip()  # Remove "[ ] "
            return (False, content)
        elif stripped.startswith("[x]"):
            # Checked: - [x] task (lowercase x only per Obsidian)
            content = stripped[3:].strip()  # Remove "[x] "
            return (True, content)
        else:
            # No checkbox
            return (None, stripped)

    def _determine_line_type(self, line: str, indent: int, content: str) -> LineType:
        """
        Determine line type based on content and position

        Rules:
        - Empty line? -> EMPTY
        - Starts with -?
          - Indent 0 + exactly 2 digits? -> TASK_ITEM
          - Indent 0 + exactly 3 digits? -> DUMP_ITEM
          - Indent 0 + 1-2 letters? -> TODO_ITEM
          - Otherwise? -> LIST_ITEM
        - Otherwise? -> TEXT_HEADER

        Note: Section boundaries are detected at text level, not here
        """
        stripped = line.strip()

        # Empty line
        if not stripped:
            return LineType.EMPTY

        if stripped in ("---", "- ---"):
            return LineType.SEPARATOR

        # Check if it's a list item (starts with -)
        is_list_item = stripped.startswith("- ")

        # List items
        if is_list_item:
            # Extract content after - (content already has checkbox removed)
            list_content = content
            if list_content.startswith("- "):
                list_content = list_content[2:].strip()

            # Only check patterns at indent 0

            # TaskItem: exactly 2 digits
            if list_content.isdigit() and len(list_content) == 2:
                if indent > 0:
                    logger.warning(f"Found task item with indent {indent} - ignoring")
                    return LineType.LIST_ITEM
                return LineType.TASK_ITEM

            # DumpItem: exactly 3 digits
            if list_content.isdigit() and len(list_content) == 3:
                if indent > 0:
                    logger.warning(f"Found task item with indent {indent} - ignoring")
                    return LineType.LIST_ITEM
                return LineType.DUMP_ITEM

            # TodoItem: 1-2 letters (case insensitive)
            if list_content.isalpha() and 1 <= len(list_content) <= 2:
                if indent > 0:
                    logger.warning(f"Found task item with indent {indent} - ignoring")
                    return LineType.LIST_ITEM
                return LineType.TODO_ITEM

            # Everything else is a ListItem
            return LineType.LIST_ITEM
        if stripped.startswith("#"):
            assert "#######" not in stripped, "Too many #s"
            return LineType.HEADER
        assert not stripped.startswith("```"), (
            "Code block found - should have been handled earlier"
        )

        # Everything else is plain text
        return LineType.PLAIN_TEXT

    def _build_tree(self, lines: list[ParsedLine]) -> list[Item]:
        indent_stack: list[Item] = []
        top_level_items: list[Item] = []

        for parsed_line in lines:
            item = self._create_item(parsed_line)

            self._update_indent_stack(indent_stack, item)

            # Attach to parent or top level
            if len(indent_stack) > 1:
                item.parent = indent_stack[-2]
                item.parent.children.append(item)
            else:
                top_level_items.append(item)

        return top_level_items

    def _create_item(self, parsed_line: ParsedLine) -> Item:
        return ITEM_TYPES[parsed_line.line_type](
            indent_level=parsed_line.indent_level,
            content=parsed_line.content,
            checked=parsed_line.checked,
        )

    def _update_indent_stack(self, indent_stack: list[Item], item: Item):
        """Update indent stack for future children"""
        indent_level = item.indent_level
        # Pop items at same or deeper level
        if not isinstance(item, EmptyItem):
            while indent_stack and indent_stack[-1].indent_level > indent_level:
                indent_stack.pop()

            # now, if it's at the same level, but is NOT a stronger header - pop it
            while indent_stack and (
                (indent_stack[-1].indent_level > indent_level)
                or (
                    indent_stack[-1].indent_level == indent_level
                    and indent_stack[-1].header_level >= item.header_level
                )
            ):
                indent_stack.pop()

        # Push current item
        indent_stack.append(item)


def parse_note(text: str, cls: type["Note"]) -> "Note":
    parser = Parser()
    return parser.parse_note(text, cls)


def parse_items(text: str) -> list[Item]:
    parser = Parser()
    return parser.parse_items(text)
