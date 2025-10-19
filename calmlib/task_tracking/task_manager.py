"""TaskManager - manages both local and global task stores"""

from pathlib import Path

from loguru import logger

from calmlib.task_tracking.task_store import TaskStore


class TaskManager:
    """Manages task stores with automatic local/global detection"""

    def __init__(self, force_global: bool = False):
        self.force_global = force_global
        self._store: TaskStore | None = None

    def _detect_project_root(self) -> Path | None:
        """Detect if we're in a project directory"""
        cwd = Path.cwd()

        # First check: if current dir has 'dev' subfolder, assume it's a project dir
        if (cwd / "dev").exists():
            logger.debug(f"Found dev/ folder in current dir: {cwd}")
            return cwd

        # Fallback: check if we're in a git repo
        current = cwd
        while current != current.parent:
            if (current / ".git").exists():
                logger.debug(f"Found git repo at {current}")
                return current
            current = current.parent

        return None

    def _get_local_tasks_file(self, project_root: Path) -> Path:
        """Get local tasks file path for project"""
        # Always use dev/notes/tasks.md for projects with dev/ folder
        dev_notes = project_root / "dev" / "notes" / "tasks.md"

        # Create the directory structure if it doesn't exist
        dev_notes.parent.mkdir(parents=True, exist_ok=True)

        # Create symlink in Obsidian vault for easy access
        self._create_obsidian_symlink(project_root, dev_notes)

        return dev_notes

    def _create_obsidian_symlink(self, project_root: Path, tasks_file: Path) -> None:
        """Create symlink in Obsidian vault to local tasks file

        Args:
            project_root: Project root directory
            tasks_file: Path to the tasks.md file
        """
        # Obsidian vault location
        obsidian_vault = Path.home() / "calmmage" / "obsidian"
        obsidian_tasks = obsidian_vault / "task_tracking" / "coding_projects"

        # Create directory if needed
        obsidian_tasks.mkdir(parents=True, exist_ok=True)

        # Generate symlink name from project path
        project_name = project_root.name
        symlink_name = f"{project_name}_tasks.md"
        symlink_path = obsidian_tasks / symlink_name

        # Create symlink if it doesn't exist
        if not symlink_path.exists():
            try:
                symlink_path.symlink_to(tasks_file)
                logger.debug(
                    f"Created Obsidian symlink: {symlink_path} -> {tasks_file}"
                )
            except Exception as e:
                logger.warning(f"Could not create Obsidian symlink: {e}")
        elif not symlink_path.is_symlink():
            logger.warning(f"File exists but is not a symlink: {symlink_path}")

    def get_store(self) -> TaskStore:
        """Get appropriate task store (local or global)"""
        if self._store is None:
            if self.force_global:
                logger.debug("Using global task store (forced)")
                self._store = TaskStore()
            else:
                project_root = self._detect_project_root()
                if project_root:
                    tasks_file = self._get_local_tasks_file(project_root)
                    logger.debug(f"Using local task store at {tasks_file}")
                    self._store = TaskStore(file_path=tasks_file)
                else:
                    logger.debug("No project detected, using global task store")
                    self._store = TaskStore()

        return self._store
