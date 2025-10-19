import asyncio
import copy
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from loguru import logger
from pydantic import BaseModel, Field
from pymongo import MongoClient

from calmlib.obsidian.note_parser.models import Header, ListItem, Note, TodoItem
from calmlib.obsidian.note_parser.parser import Parser
from calmlib.utils import find_calmmage_env_key
from calmlib.utils.user_interactions import ask_user


def confirm_title(title, silent=False):
    """Confirm task title"""

    if silent:
        return title
    else:
        user_input = asyncio.run(ask_user(question=f"Task title [{title}]"))
        return user_input.strip() if user_input and user_input.strip() else title


class TaskMetadata(BaseModel):
    """Task metadata stored in MongoDB"""

    key: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    cue: str | None = None  # What made you think of this task (trigger/inspiration)
    title: str | None = None
    description: str | None = None
    created: datetime | None = Field(default_factory=datetime.now)
    finished_at: datetime | None = (
        None  # Timestamp when task reached terminal state (done/cancelled)
    )
    mentions: list[tuple[datetime, str]] = Field(default_factory=list)
    conversation_id: str | None = None  # Claude Code conversation ID
    # todo: rework this to reference calmmage projects system instead - ~/calmmage/data/projects.json
    project_path: str | None = None  # Project location for conversation
    task_file: str | None = None  # Path to the tasks.md file where this task is stored
    research_mode: bool = False  # If True, AI should only research/plan, not write code
    idea: bool = (
        False  # If True, task is just an idea/brainstorm, not ready to implement
    )
    simple: bool = False  # If True, task is straightforward/clear, good starter task
    # Explicit status override - if set, overrides checkbox-based heuristics
    status: Literal["todo", "in_progress", "done", "cancelled", "selected"] | None = (
        None
    )
    # Postpone and backlog support
    postponed_until: datetime | None = None  # If set, hide task until this date
    backlog: bool = (
        False  # If True, task is in backlog (low priority, hidden by default)
    )
    # Follow-up task support
    parent_task_key: str | None = None  # Key of parent task if this is a follow-up
    last_message: str | None = (
        None  # Last message from Claude conversation when task was marked done
    )

    class Config:
        arbitrary_types_allowed = True


def get_default_tasks_file() -> Path:
    """Get tasks file path from env or use default"""
    try:
        path = find_calmmage_env_key("CALMMAGE_CODING_TASKS_FILE")
        return Path(path)
    except Exception:
        logger.warning("CALMMAGE_CODING_TASKS_FILE not set, using default")
        return Path.home() / "calmmage/obsidian/task_tracking/coding_tasks.md"


@dataclass
class Task:
    """Wrapper around TodoItem with convenience methods"""

    item: TodoItem
    task_store: "TaskStore"

    def __repr__(self) -> str:
        status = "✓" if self.item.checked else "☐"
        return f"Task({status} {self.key}: {self.title})"

    @property
    def key(self) -> str:
        """Get task UUID key from markdown"""
        # Look for `key: value` format in children
        for child in self.item.children:
            if isinstance(child, ListItem) and child.content.startswith("`key:"):
                return child.content.strip("`").split(":", 1)[1].strip()
        # Fallback to letter for backward compatibility
        return self.item.letter

    @key.setter
    def key(self, value: str):
        """Set task UUID key in markdown"""
        for child in self.item.children:
            if isinstance(child, ListItem) and child.content.startswith("`key:"):
                child.content = f"`key: {value}`"
                return
        # Add key as first child
        key_item = ListItem(
            indent_level=4, content=f"`key: {value}`", _note=self.item._note
        )
        self.item.children.insert(0, key_item)

    @property
    def cue(self) -> str | None:
        """Get task cue from markdown"""
        # Look for `cue: value` format in children
        for child in self.item.children:
            if isinstance(child, ListItem) and child.content.startswith("`cue:"):
                return child.content.strip("`").split(":", 1)[1].strip()
        return None

    @cue.setter
    def cue(self, value: str | None):
        """Set task cue in markdown"""
        # Remove existing cue if present
        for i, child in enumerate(self.item.children):
            if isinstance(child, ListItem) and child.content.startswith("`cue:"):
                if value is None:
                    # Remove the cue
                    self.item.children.pop(i)
                else:
                    # Update existing cue
                    child.content = f"`cue: {value}`"
                return

        # Add new cue after key (if value is not None)
        if value is not None:
            cue_item = ListItem(
                indent_level=4, content=f"`cue: {value}`", _note=self.item._note
            )
            # Find key position and insert after it
            key_index = -1
            for i, child in enumerate(self.item.children):
                if isinstance(child, ListItem) and child.content.startswith("`key:"):
                    key_index = i
                    break
            if key_index >= 0:
                self.item.children.insert(key_index + 1, cue_item)
            else:
                # No key found, add at beginning
                self.item.children.insert(0, cue_item)

    @property
    def letter(self) -> str:
        """Task letter ID (a-z, aa-zz) - backward compatibility"""
        return self.item.letter

    @property
    def text(self) -> str:
        """Get all text content from task item"""
        return self.item.text

    @property
    def metadata(self) -> TaskMetadata | None:
        """Get task metadata from MongoDB"""
        return self.task_store.get_metadata(self.key)

    @property
    def title(self) -> str:
        """Get title from MongoDB metadata"""
        meta = self.metadata
        if meta and meta.title:
            return meta.title
        # Fallback to markdown
        for child in self.item.children:
            if isinstance(child, ListItem) and child.content.startswith("Title:"):
                return child.content[6:].strip()
        return self.item.text[:50]

    @title.setter
    def title(self, value: str):
        """Set title in MongoDB"""
        meta = self.metadata
        if meta:
            meta.title = value
            self.task_store.save_metadata(meta)

    @property
    def status(self) -> str:
        """Get status using explicit override or heuristics

        Priority:
        1. Explicit metadata.status (if set) → use that
        2. checked = True ([x]) → "done"
        3. checked = False ([ ]) and has conversation_id → "in_progress"
        4. checked = False ([ ]) and no conversation_id → "todo"
        5. checked = None (no checkbox) → "todo"
        """
        meta = self.metadata

        # If explicitly set, use that
        if meta and meta.status:
            return meta.status

        # Fall back to heuristics
        if self.item.checked is True:
            return "done"
        if meta and meta.conversation_id:
            return "in_progress"
        return "todo"

    @property
    def conversation_id(self) -> str | None:
        """Get Claude Code conversation ID from MongoDB"""
        meta = self.metadata
        return meta.conversation_id if meta else None

    @conversation_id.setter
    def conversation_id(self, value: str):
        """Set conversation ID in MongoDB"""
        meta = self.metadata
        if meta:
            meta.conversation_id = value
            self.task_store.save_metadata(meta)

    @property
    def project_path(self) -> str | None:
        """Get project path from MongoDB"""
        meta = self.metadata
        return meta.project_path if meta else None

    @project_path.setter
    def project_path(self, value: str):
        """Set project path in MongoDB"""
        meta = self.metadata
        if meta:
            meta.project_path = value
            self.task_store.save_metadata(meta)

    @property
    def research_mode(self) -> bool:
        """Get research mode flag from MongoDB"""
        meta = self.metadata
        return meta.research_mode if meta else False

    @research_mode.setter
    def research_mode(self, value: bool):
        """Set research mode flag in MongoDB"""
        meta = self.metadata
        if meta:
            meta.research_mode = value
            self.task_store.save_metadata(meta)

    @property
    def idea(self) -> bool:
        """Get idea flag from MongoDB"""
        meta = self.metadata
        return meta.idea if meta else False

    @idea.setter
    def idea(self, value: bool):
        """Set idea flag in MongoDB"""
        meta = self.metadata
        if meta:
            meta.idea = value
            self.task_store.save_metadata(meta)

    @property
    def simple(self) -> bool:
        """Get simple flag from MongoDB"""
        meta = self.metadata
        return meta.simple if meta else False

    @simple.setter
    def simple(self, value: bool):
        """Set simple flag in MongoDB"""
        meta = self.metadata
        if meta:
            meta.simple = value
            self.task_store.save_metadata(meta)

    @property
    def postponed_until(self) -> datetime | None:
        """Get postponed_until date from MongoDB"""
        meta = self.metadata
        return meta.postponed_until if meta else None

    @postponed_until.setter
    def postponed_until(self, value: datetime | None):
        """Set postponed_until date in MongoDB"""
        meta = self.metadata
        if meta:
            meta.postponed_until = value
            self.task_store.save_metadata(meta)

    @property
    def backlog(self) -> bool:
        """Get backlog flag from MongoDB"""
        meta = self.metadata
        return meta.backlog if meta else False

    @backlog.setter
    def backlog(self, value: bool):
        """Set backlog flag in MongoDB"""
        meta = self.metadata
        if meta:
            meta.backlog = value
            self.task_store.save_metadata(meta)

    def is_stale(self, stale_days: int = 7) -> bool:
        """Check if task is stale (created long ago but not done)

        Args:
            stale_days: Number of days after which a task is considered stale (default: 7)

        Returns:
            True if task is stale (created > stale_days ago and not in terminal state)
        """

        meta = self.metadata
        if not meta or not meta.created:
            return False

        # Only mark non-terminal tasks as stale
        if self.status in ["done", "cancelled"]:
            return False

        # Check if created more than stale_days ago
        age = datetime.now() - meta.created
        return age > timedelta(days=stale_days)

    def get_flags(self) -> list[str]:
        """Get list of active flag names for this task

        Returns:
            List of flag names (e.g., ["simple", "stale"])
        """
        flags = []
        if self.research_mode:
            flags.append("plan")
        if self.simple:
            flags.append("clear")
        if self.idea:
            flags.append("idea")
        if self.is_stale():
            flags.append("stale")
        return flags

    def mark_done(self):
        """Mark task as complete"""
        self.item.checked = True
        # Update MongoDB metadata
        meta = self.metadata
        if meta:
            meta.status = "done"
            meta.finished_at = datetime.now()
            self.task_store.save_metadata(meta)

    def mark_todo(self):
        """Mark task as incomplete"""
        self.item.checked = False
        # Update MongoDB metadata
        meta = self.metadata
        if meta:
            meta.status = None  # Clear explicit status, rely on heuristics
            meta.finished_at = None
            self.task_store.save_metadata(meta)

    def mark_cancelled(self):
        """Mark task as cancelled"""
        # Check the box so it's treated as finished everywhere
        self.item.checked = True
        meta = self.metadata
        if meta:
            meta.status = "cancelled"
            meta.finished_at = datetime.now()
            self.task_store.save_metadata(meta)

    def mark_selected(self):
        """Mark task as selected (shortlisted)"""
        meta = self.metadata
        if meta:
            meta.status = "selected"
            self.task_store.save_metadata(meta)

    def sync(self):
        """Save changes to disk"""
        self.task_store.sync()


class TaskStore:
    """Task storage using Obsidian Note format with MongoDB metadata"""

    def __init__(
        self,
        file_path: Path | None = None,
        mongo_uri: str = "mongodb://localhost:27017",
    ):
        self.file_path = file_path or get_default_tasks_file()

        # Create file and directory if needed
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("")

        # Load note
        self.raw_text = self.file_path.read_text()
        self.note = Note.from_text(self.raw_text)

        # MongoDB setup - check connection first
        try:
            self.mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
            # Test connection
            self.mongo_client.admin.command("ping")
            self.db = self.mongo_client["coding_tasks"]
            self.collection = self.db["tasks"]
        except Exception as e:
            raise RuntimeError(
                f"MongoDB not available at {mongo_uri}. "
                "Please start MongoDB: docker start mongodb"
            ) from e

        # Cache tasks
        self._tasks: list[Task] = []
        self._init_tasks()
        self.normalize()
        self.sync()

    def get_metadata(self, key: str) -> TaskMetadata | None:
        """Get task metadata from MongoDB"""
        doc = self.collection.find_one({"key": key})
        if doc:
            # Remove MongoDB _id field
            doc.pop("_id", None)
            return TaskMetadata(**doc)
        return None

    def save_metadata(self, metadata: TaskMetadata):
        """Save task metadata to MongoDB"""
        self.collection.update_one(
            {"key": metadata.key}, {"$set": metadata.model_dump()}, upsert=True
        )

    def _init_tasks(self):
        """Initialize Task wrappers for all TodoItems and ensure keys exist"""
        self._tasks = []
        for item in self.note.get_items(item_type=TodoItem):
            assert isinstance(item, TodoItem)
            task = Task(item, self)

            # Ensure task has a UUID key in markdown
            has_key = any(
                isinstance(c, ListItem) and c.content.startswith("`key:")
                for c in item.children
            )
            if not has_key:
                # Generate new UUID key
                task.key = uuid.uuid4().hex[:8]

            # Ensure task has metadata in MongoDB
            metadata = self.get_metadata(task.key)
            if not metadata:
                # Create initial metadata for existing task
                # Extract title from task content (first meaningful line)
                title = self._extract_title_from_task(task)
                metadata = TaskMetadata(
                    key=task.key,
                    title=title,
                    description=None,
                    created=datetime.now(),
                    task_file=str(self.file_path.absolute()),
                )
                self.save_metadata(metadata)
                logger.debug(f"Initialized metadata for task {task.key}: {title}")

            self._tasks.append(task)

    def _extract_title_from_task(self, task: Task) -> str:
        """Extract title from existing task content"""
        # Look for first non-key, non-cue child item
        for child in task.item.children:
            if (
                isinstance(child, ListItem)
                and not child.content.startswith("`key:")
                and not child.content.startswith("`cue:")
            ):
                # Use first meaningful line as title
                text = child.content.strip()
                if text:
                    # If short enough, use as-is; else truncate
                    words = text.split()
                    if len(words) <= 5:
                        return text
                    else:
                        return " ".join(words[:5]) + "..."

        # Fallback: use letter as title
        return f"Task {task.letter}"

    def get_tasks(self, status: str | None = None) -> list[Task]:
        """Get tasks with optional status filtering"""
        results = self._tasks

        if status:
            results = [t for t in results if t.status == status]

        return results

    def get_task(self, identifier: str) -> Task | None:
        """Get single task by key or letter"""
        for task in self._tasks:
            # Try matching by key first
            if task.key == identifier:
                return task
            # Fallback to letter for backward compatibility
            if task.letter == identifier.lower():
                return task
        return None

    def add_task(
        self,
        text: str,
        title: str | None = None,
        title_word_limit: int = 6,
        silent: bool = False,
        fast: bool = False,
    ) -> Task:
        """Add new task with MongoDB metadata and markdown content

        Args:
            text: Task text/content (will be parsed and added to markdown)
            title: Optional explicit title (auto-generated if not provided)
            title_word_limit: Max words for auto-title (default 6)
            silent: Skip user confirmation for auto-generated title
            fast: Skip AI calls (use simple heuristic for title generation)
        """

        # Generate UUID key
        key = uuid.uuid4().hex[:8]

        # Find next available letter
        letter = self.note.find_available_letter()

        # Determine title: use provided, or auto-generate
        if not title:
            from tools.task_management.dev_task_manager.task_utils import (
                generate_task_title,
            )

            generated_title = generate_task_title(
                text, fast=fast, word_limit=title_word_limit
            )

            # Ask user to confirm/override generated title (unless silent)
            title = confirm_title(generated_title, silent=silent)

        # Create TodoItem with letter
        item = TodoItem(
            indent_level=0,
            content=letter,
            _note=self.note,
        )

        # Add key as first child
        key_item = ListItem(indent_level=4, content=f"`key: {key}`", _note=self.note)
        item.children.append(key_item)

        # Parse text into markdown items and add as children
        parser = Parser()
        parsed_items = parser.parse_items(text)

        # Helper to recursively set indent levels preserving hierarchy
        def set_indent_recursive(items, base_indent=4):
            for item_obj in items:
                item_obj.indent_level = base_indent
                item_obj._note = self.note
                # Recursively process children with increased indent
                if hasattr(item_obj, "children") and item_obj.children:
                    set_indent_recursive(item_obj.children, base_indent + 4)

        # Add parsed items as children with proper indentation
        set_indent_recursive(parsed_items, base_indent=4)
        for parsed_item in parsed_items:
            item.children.append(parsed_item)

        # Add to note
        self.note.items.insert(0, item)
        self.note._refresh_indent_levels()

        # Create Task wrapper
        task = Task(item, self)
        self._tasks.append(task)

        # Create MongoDB metadata
        metadata = TaskMetadata(
            key=key,
            title=title,
            description=None,  # No longer using description
            created=datetime.now(),
            task_file=str(self.file_path.absolute()),
        )
        self.save_metadata(metadata)

        self.normalize()
        self.sync()

        return task

    def sync(self):
        """Save note to disk with backup if changed externally

        If file changed externally, attempts to merge changes first.
        Only creates backup if merge fails.
        """

        current_disk_text = self.file_path.read_text()

        if self.raw_text != current_disk_text:
            # File changed externally - try to merge first
            logger.info("Tasks file changed on disk, attempting merge...")

            try:
                # Import merge function (avoid circular import)
                from tools.task_management.dev_task_manager.lib import merge_two_notes

                # Parse both versions
                disk_note = Note.from_text(current_disk_text)
                memory_note = copy.deepcopy(self.note)

                # Attempt merge
                merged_note = merge_two_notes(memory_note, disk_note)

                # If merge succeeded, use merged result instead of overwriting
                self.note = merged_note
                logger.info("Successfully merged changes from disk")

            except (AssertionError, Exception) as e:
                # Merge failed - fall back to backup
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = self.file_path.with_suffix(f".{ts}.bak")
                logger.warning(f"Merge failed ({e}), backing up to {backup_path.name}")
                backup_path.write_text(current_disk_text)

        # Write and update cache
        rendered = self.note.render()
        self.file_path.write_text(rendered)
        self.raw_text = rendered

    def get_done_header(self):
        # find "## Done" header
        # if not found, create it

        for item in self.note.items:
            if isinstance(item, Header) and item.content.strip() == "## Done":
                return item

        # create it
        item = Header(content="## Done", indent_level=0)
        self.note.items.append(item)
        return item

    def normalize(self):
        # idea 1: move done tasks to Done header
        self._normalize_done_tasks()
        # idea 2: rename todo letters in alphabetical order
        self._normalize_todo_letters()
        # idea 3: generate missing titles
        self._normalize_titles()
        # idea 4: sync done status to MongoDB
        self._normalize_done_status()
        # idea 5: sync cue field between markdown and MongoDB
        self._normalize_cue_field()
        # idea 6: auto-promote stale+simple tasks to selected
        self._normalize_stale_simple_tasks()
        # idea 7: archive done tasks when more than 5
        self._archive_done_tasks()

    def _normalize_done_tasks(self):
        done_header = self.get_done_header()
        moved_to_done = []
        moved_to_todo = []

        for item in self.note.items:
            if isinstance(item, TodoItem) and item.checked:
                # Find the Task wrapper to get key/title
                task = next((t for t in self._tasks if t.item == item), None)
                task_info = f"{task.key}: {task.title}" if task else item.content
                done_header.add_child(item)
                self.note.items.remove(item)
                moved_to_done.append(task_info)
                logger.info(f"Moved done task to Done section: {task_info}")

        for item in done_header.children:
            if isinstance(item, TodoItem) and not item.checked:
                # Find the Task wrapper to get key/title
                task = next((t for t in self._tasks if t.item == item), None)
                task_info = f"{task.key}: {task.title}" if task else item.content
                done_header.remove_child(item)
                self.note.items.insert(0, item)
                moved_to_todo.append(task_info)
                logger.info(f"Moved unchecked task back to Todo section: {task_info}")

        if moved_to_done:
            logger.info(f"Total moved to Done: {len(moved_to_done)} task(s)")
        if moved_to_todo:
            logger.info(f"Total moved to Todo: {len(moved_to_todo)} task(s)")

    def iter_letters(self):
        for i in range(ord("a"), ord("z") + 1):
            yield chr(i)
        for i in range(ord("a"), ord("z") + 1):
            for j in range(ord("a"), ord("z") + 1):
                yield chr(i) + chr(j)

    def _normalize_todo_letters(self):
        letters = self.iter_letters()
        for item in self.note.get_items(item_type=TodoItem):
            assert isinstance(item, TodoItem)
            item.content = next(letters)

    def _normalize_titles(self):
        """Generate titles for tasks that don't have them in MongoDB"""
        generated_count = 0
        for task in self._tasks:
            metadata = self.get_metadata(task.key)
            if metadata and not metadata.title:
                # Generate title from task content
                title = self._extract_title_from_task(task)
                metadata.title = title
                self.save_metadata(metadata)
                logger.info(f"Generated title for task {task.key}: '{title}'")
                generated_count += 1

        if generated_count > 0:
            logger.info(f"Generated {generated_count} missing title(s)")

    def _normalize_done_status(self):
        """Sync done status from markdown to MongoDB"""
        synced_count = 0
        for task in self._tasks:
            metadata = self.get_metadata(task.key)
            if not metadata:
                continue

            # Check if task is marked done in markdown but not in MongoDB
            if task.status == "done" and metadata.status != "done":
                # Only set status if not already cancelled
                if metadata.status != "cancelled":
                    metadata.status = "done"
                # Only set finished_at if it's not already set
                if not metadata.finished_at:
                    metadata.finished_at = datetime.now()
                self.save_metadata(metadata)
                logger.info(
                    f"Synced done status to MongoDB for task {task.key}: {task.title}"
                )
                synced_count += 1
            # Check if task is marked todo in markdown but done in MongoDB
            elif (
                task.status == "todo"
                and metadata.finished_at
                and metadata.status == "done"
            ):
                metadata.status = None
                metadata.finished_at = None
                self.save_metadata(metadata)
                logger.info(
                    f"Cleared done status in MongoDB for task {task.key}: {task.title}"
                )
                synced_count += 1

        if synced_count > 0:
            logger.info(f"Synced {synced_count} task done status(es) to MongoDB")

    def _normalize_cue_field(self):
        """Sync cue field between markdown and MongoDB"""
        synced_count = 0
        for task in self._tasks:
            metadata = self.get_metadata(task.key)
            if not metadata:
                continue

            # Get cue from markdown
            cue_in_markdown = task.cue

            # Sync to MongoDB if different
            if cue_in_markdown != metadata.cue:
                metadata.cue = cue_in_markdown
                self.save_metadata(metadata)
                logger.info(
                    f"Synced cue to MongoDB for task {task.key}: {cue_in_markdown or '(removed)'}"
                )
                synced_count += 1

        if synced_count > 0:
            logger.info(f"Synced {synced_count} task cue(s) to MongoDB")

    def _normalize_stale_simple_tasks(self):
        """Auto-promote tasks that are stale AND simple to 'selected' status"""
        promoted_count = 0
        for task in self._tasks:
            metadata = self.get_metadata(task.key)
            if not metadata:
                continue

            # Skip if already in terminal or selected state
            if task.status in ["done", "cancelled", "selected"]:
                continue

            # Check if task is both stale and simple
            if task.is_stale() and task.simple:
                # Auto-promote to selected
                metadata.status = "selected"
                self.save_metadata(metadata)
                logger.info(
                    f"Auto-promoted stale+simple task to selected: {task.key} - {task.title}"
                )
                promoted_count += 1

        if promoted_count > 0:
            logger.info(
                f"Auto-promoted {promoted_count} stale+simple task(s) to selected"
            )

    def _archive_done_tasks(self, threshold: int = 5):
        """Archive done tasks to done.md when count exceeds threshold

        When there are more than `threshold` done tasks, moves older done tasks
        to a single done.md file organized by completion date headers.

        Args:
            threshold: Maximum number of done tasks to keep in main file (default: 5)
        """

        done_header = self.get_done_header()

        # Get all done tasks with metadata
        done_tasks_with_meta = []
        for item in done_header.children:
            if isinstance(item, TodoItem) and item.checked:
                task = next((t for t in self._tasks if t.item == item), None)
                if task:
                    metadata = self.get_metadata(task.key)
                    if metadata and metadata.finished_at:
                        done_tasks_with_meta.append((task, metadata))

        # If we have more than threshold done tasks, archive the older ones
        if len(done_tasks_with_meta) <= threshold:
            return

        # Sort by completion date (oldest first)
        done_tasks_with_meta.sort(key=lambda x: x[1].finished_at or datetime.min)

        # Keep the most recent `threshold` tasks in the main file
        tasks_to_archive = done_tasks_with_meta[:-threshold]

        if not tasks_to_archive:
            return

        # Single done.md file
        done_file = self.file_path.parent / "done.md"

        # Load existing archive or create new
        if done_file.exists():
            archive_note = Note.from_text(done_file.read_text())
        else:
            archive_note = Note.from_text("")

        # Group tasks by completion day
        tasks_by_day = defaultdict(list)
        for task, metadata in tasks_to_archive:
            if metadata.finished_at:
                day_key = metadata.finished_at.strftime("%Y-%m-%d")
                tasks_by_day[day_key].append(task)

        archived_count = 0
        # Add tasks to archive note organized by day (reverse chronological)
        for day_key in sorted(tasks_by_day.keys(), reverse=True):
            day_tasks = tasks_by_day[day_key]

            # Find or create header for this day
            day_header = None
            for item in archive_note.items:
                if isinstance(item, Header) and item.content.strip() == f"## {day_key}":
                    day_header = item
                    break

            if not day_header:
                day_header = Header(content=f"## {day_key}", indent_level=0)
                # Insert at the beginning to keep reverse chronological order
                archive_note.items.insert(0, day_header)

            # Add tasks to this day's header
            for task in day_tasks:
                # Remove from main file's done section
                if task.item in done_header.children:
                    done_header.remove_child(task.item)
                    # Add to archive
                    day_header.add_child(task.item)
                    archived_count += 1

        # Save archive file
        if archived_count > 0:
            done_file.write_text(archive_note.render())
            logger.info(f"Archived {archived_count} task(s) to done.md")

    def delete_task(self, key: str):
        """Delete a task from both markdown and MongoDB

        Args:
            key: Task key to delete
        """
        # Find task
        task = self.get_task(key)
        if not task:
            raise ValueError(f"Task not found: {key}")

        # Remove from note - check both top-level items and children of headers
        if task.item in self.note.items:
            self.note.items.remove(task.item)
        else:
            # Task might be under a header (e.g., "## Done")
            for item in self.note.items:
                if isinstance(item, Header) and task.item in item.children:
                    item.remove_child(task.item)
                    break

        # Remove from tasks cache
        self._tasks.remove(task)

        # Delete from MongoDB
        result = self.collection.delete_one({"key": key})
        if result.deleted_count > 0:
            logger.info(f"Deleted task {key} from MongoDB")

        # Save changes
        self.normalize()
        self.sync()

        logger.info(f"Deleted task: {key}")


if __name__ == "__main__":
    store = TaskStore()
    store.add_task("This is a test task for demo purposes")
    store.sync()
