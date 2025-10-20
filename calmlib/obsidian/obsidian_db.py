from pathlib import Path

from pydantic import BaseModel

from calmlib.obsidian.utils import format_note_metadata, get_note_metadata


class ObsidianNote:
    """Represents a single note in an Obsidian vault"""

    def __init__(self, path: Path, vault_path: Path):
        self.path = path
        self.vault_path = vault_path
        self._metadata_cache = None
        self._content_cache = None

    def _load_file(self):
        """Load and parse file content and metadata once"""
        # todo: add ttl and refresh file content
        if self._metadata_cache is None or self._content_cache is None:
            self._metadata_cache = get_note_metadata(self.path)

            full_text = self.path.read_text(encoding="utf-8")
            lines = full_text.split("\n")

            # Check if file starts with frontmatter
            if lines and lines[0].strip() == "---":
                # Find end of frontmatter
                end_idx = 0
                for i, line in enumerate(lines[1:], 1):
                    if line.strip() == "---":
                        end_idx = i + 1
                        break
                # Content is everything after frontmatter
                self._content_cache = "\n".join(lines[end_idx:])
            else:
                # No frontmatter, entire file is content
                self._content_cache = full_text

    @property
    def metadata(self) -> dict:
        """Lazy-loaded metadata with caching"""
        self._load_file()
        return self._metadata_cache

    @property
    def content(self) -> str:
        """Get note content (body text below YAML frontmatter)"""
        self._load_file()
        return self._content_cache.strip()

    @property
    def tags(self) -> list:
        """Get note tags from metadata"""
        tags = self.metadata.get("tags", [])
        if isinstance(tags, str):
            return [tags]
        return tags or []

    @property
    def status(self) -> str | None:
        """Get note status from metadata"""
        return self.metadata.get("status")

    @property
    def type(self) -> str | None:
        """Get note type from metadata"""
        return self.metadata.get("type")

    def is_completed(self) -> bool:
        """Check if note is marked as completed (✅ prefix or status=done)"""
        return self.path.name.startswith("✅") or self.status == "done"


class ObsidianCollectionRules(BaseModel):
    type: str | None = None
    folders: set[str] = set("")
    tags: set[str] = set()

    # todo: add date filter?
    # todo: add status filter?


class ObsidianDBConfig(BaseModel):
    vault_path: Path
    collections: dict[str, ObsidianCollectionRules]


class ObsidianCollection:
    def __init__(self, name: str, rules: ObsidianCollectionRules, vault_path: Path):
        self.name = name
        self.rules = rules
        self.vault_path = vault_path

    def _get_all_notes(self):
        for folder in self.rules.folders:
            parent = self.vault_path / folder
            yield from parent.rglob("*.md")

    def get_notes(self):
        for note_path in self._get_all_notes():
            note = ObsidianNote(note_path, self.vault_path)
            if self.rules.type and note.type != self.rules.type:
                continue
            if self.rules.tags:
                if not self.rules.tags.issubset(set(note.tags)):
                    continue
            yield note

    def add_note(self, name: str, data: dict):
        content = data.pop("content", "")
        # todo: use template, if exists

        metadata = {}
        if self.rules.type:
            metadata["type"] = self.rules.type
        if self.rules.folders:
            target_dir = self.vault_path / list(self.rules.folders)[0]
        else:
            target_dir = self.vault_path / "Inbox"

        # Merge additional metadata from data first
        metadata.update(data)

        # Then append collection tags to user tags
        if self.rules.tags:
            existing_tags = metadata.get("tags", [])
            collection_tags = list(self.rules.tags)
            # Append collection tags and deduplicate
            metadata["tags"] = list(set(existing_tags + collection_tags))

        content = format_note_metadata(metadata) + content

        filename = name
        if not filename.endswith(".md"):
            filename += ".md"
        note_path = target_dir / filename
        note_path.parent.mkdir(parents=True, exist_ok=True)
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(content)

        return note_path

    def remove_note(self, name: str):
        """Remove a note by name"""
        if not name.endswith(".md"):
            name += ".md"

        # Search in collection folders for the note
        for note_path in self._get_all_notes():
            if note_path.name == name:
                note_path.unlink()
                return True
        return False


class ObsidianDB:
    def __init__(
        self, vault_path: Path, collections: dict[str, ObsidianCollectionRules]
    ):
        self.config = ObsidianDBConfig(vault_path=vault_path, collections=collections)
        self.collections = {}
        for name, rules in self.config.collections.items():
            self.collections[name] = ObsidianCollection(
                name, rules, self.config.vault_path
            )

    def get_collection(self, name: str) -> ObsidianCollection:
        return self.collections[name]

    def add_collection(
        self,
        name: str,
        type: str | None = None,
        folders: set[str] | None = None,
        tags: set[str] | None = None,
    ):
        """Add a new collection to the database"""
        if folders is None:
            folders = set()
        if tags is None:
            tags = set()

        rules = ObsidianCollectionRules(type=type, folders=folders, tags=tags)
        self._create_collection_prerequisites(name, rules)
        self.collections[name] = ObsidianCollection(name, rules, self.config.vault_path)

    @property
    def vault_path(self):
        return self.config.vault_path

    def _create_collection_prerequisites(
        self, name: str, rules: ObsidianCollectionRules
    ):
        """Create necessary folders and templates for the collection"""
        # Create template folder if it doesn't exist
        template_folder = self.config.vault_path / "templates"
        template_folder.mkdir(exist_ok=True)

        # Create template file for this collection
        template_path = template_folder / f"{name}_template.md"
        if not template_path.exists():
            template_content = self._generate_template_content(rules)
            template_path.write_text(template_content, encoding="utf-8")

        # if collection has folder filters -> create those folders
        for folder in rules.folders:
            folder_path = self.config.vault_path / folder
            folder_path.mkdir(parents=True, exist_ok=True)

    def _generate_template_content(self, rules: ObsidianCollectionRules) -> str:
        """Generate template content with appropriate metadata fields"""
        metadata = {}

        if rules.type:
            metadata["type"] = rules.type

        if rules.tags:
            metadata["tags"] = list(rules.tags)

        # Add common fields
        metadata["status"] = "todo"

        template_content = format_note_metadata(metadata)

        return template_content


def get_obsidiandb(vault_path: str | None = None) -> ObsidianDB:
    """Get ObsidianDB instance with default configuration using env vault path"""
    from calmlib.utils.env_discovery import find_calmmage_env_key

    if vault_path is None:
        vault_path = Path(find_calmmage_env_key("CALMMAGE_OBSIDIAN_VAULT"))

    # Default collections for calmmage
    collections = {
        "tasks": ObsidianCollectionRules(
            type="action", tags={"task_store"}, folders={"actions"}
        )
    }

    return ObsidianDB(vault_path=vault_path, collections=collections)
