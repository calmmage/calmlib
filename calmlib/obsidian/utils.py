from pathlib import Path

import yaml


def get_note_metadata(file_path: Path) -> dict:
    """Extract YAML frontmatter metadata from markdown file."""
    try:
        content = file_path.read_text()
        if content.startswith("---"):
            end_marker = content.find("---", 3)
            if end_marker > 0:
                yaml_content = content[3:end_marker].strip()
                metadata = yaml.safe_load(yaml_content)
                return metadata if isinstance(metadata, dict) else {}
    except Exception:
        pass
    return {}


def format_note_metadata(data: dict) -> str:
    """
    ---
    email:
    telegram: "@cloud_el"
    phone: "+41793580917"
    birthday:
    type: person_contact
    ---
    """
    result = "---\n"
    result += yaml.dump(data)
    result += "---\n"
    return result
