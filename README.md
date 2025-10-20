# 🧘 Calmlib v2.0

> *A Python library for calm and productive development*

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://python.org)
[![Poetry](https://img.shields.io/badge/dependency%20management-poetry-blue.svg)](https://python-poetry.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Calmlib is a comprehensive Python utility library designed to make development more productive and less stressful. It provides clean, well-organized modules for common development tasks including LLM interactions, audio processing, logging, user interactions, Telegram bot development, and more.

## ✨ Features

### 🤖 LLM Integration (`calmlib.llm`)
- Simple, unified interface for multiple LLM providers via LiteLLM
- Support for both synchronous and asynchronous operations
- Structured output parsing with Pydantic
- Built-in validation and error handling

### 🎵 Audio Processing (`calmlib.audio`)
- Audio file manipulation and conversion
- Whisper integration for speech-to-text
- Audio utility functions for common operations

### 📝 Smart Logging (`calmlib.logging`)
- Enhanced logging with multiple output formats
- Structured logging support
- Easy configuration and setup

### 💬 User Interactions (`calmlib.user_interactions`)
- Interactive CLI prompts and confirmations
- Multiple input engines (CLI, GUI, etc.)
- Type-safe user input collection

### 🤖 Telegram Bot Tools (`calmlib.telegram`)
- Telegram bot development utilities
- Secure bot key management
- Telethon client integration
- Service bot templates

### 🌐 Translation (`calmlib.translate`)
- DeepL API integration
- Simple translation workflows
- Multi-language support

### 🛠️ Utilities (`calmlib.utils`)
- Path handling and file operations
- Environment variable discovery
- Check mode for safe operations
- DotDict for easy nested data access
- Enum casting and comparison utilities

## 🚀 Installation

### Using Poetry (Recommended)

```bash
# Clone the repository
git clone https://github.com/calmmage/calmlib.git
cd calmlib

# Install with poetry
poetry install

# For development with all extras
poetry install --with extras,test,dev
```

### Using pip

```bash
pip install git+https://github.com/calmmage/calmlib.git
```

## 📖 Quick Start

### LLM Queries

```python
import calmlib

# Simple text query
response = calmlib.query_llm_text("Explain quantum computing in simple terms")
print(response)

# Structured output
from pydantic import BaseModel

class Summary(BaseModel):
    title: str
    key_points: list[str]
    sentiment: str

summary = calmlib.query_llm_structured(
    "Summarize this text: ...", 
    response_model=Summary
)
print(f"Title: {summary.title}")
```

### User Interactions

```python
import calmlib

# Ask for user input
name = calmlib.ask_user("What's your name?")
age = calmlib.ask_user("What's your age?", int)

# Multiple choice
choice = calmlib.ask_user_choice(
    "Choose your preferred language:",
    ["Python", "JavaScript", "Rust", "Go"]
)

# Confirmation
if calmlib.ask_user_confirmation("Delete all files?"):
    print("Confirmed!")
```

### Logging Setup

```python
import calmlib

# Setup enhanced logging
logger = calmlib.setup_logger(
    name="my_app",
    mode=calmlib.LogMode.BOTH,  # Console + file
    format=calmlib.LogFormat.DETAILED
)

logger.info("Application started")
logger.error("Something went wrong", extra={"user_id": 123})
```

### Utilities

```python
import calmlib
from pathlib import Path

# Path handling
safe_path = calmlib.fix_path("~/documents/file.txt")

# Environment discovery
api_key = calmlib.find_env_key(["OPENAI_API_KEY", "OPENAI_TOKEN"])

# Check mode (safe operations)
from calmlib.utils.check_mode import check_mode

@check_mode.enabled
def dangerous_operation():
    # This will be skipped in check mode
    delete_important_files()
```

## 📂 Module Overview

### Core Modules

| Module | Description | Key Features |
|--------|-------------|--------------|
| `llm` | LLM integration and utilities | LiteLLM wrapper, structured outputs, async support |
| `audio` | Audio processing tools | Whisper integration, audio manipulation |
| `logging` | Enhanced logging capabilities | Multiple formats, structured logging |
| `user_interactions` | CLI and user input tools | Interactive prompts, type validation |
| `telegram` | Telegram bot development | Bot management, secure key storage |
| `translate` | Translation services | DeepL integration, multi-language support |
| `utils` | General utilities | Path handling, environment discovery, data structures |

## 🏗️ Architecture

Calmlib v2.0 features a clean, modular architecture:

```
calmlib/
├── llm/           # LLM integration (LiteLLM, structured outputs)
├── audio/         # Audio processing (Whisper, audio utils)  
├── logging/       # Enhanced logging capabilities
├── telegram/      # Telegram bot development tools
├── translate/     # Translation services (DeepL)
├── user_interactions/  # Interactive CLI tools
└── utils/         # Core utilities and helpers
```

## 🔧 Configuration

Calmlib uses environment variables for configuration. Create a `.env` file:

```bash
# LLM Configuration
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# Translation
DEEPL_AUTH_KEY=your_deepl_key

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
```

## 🧪 Testing

```bash
# Run tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=calmlib

# Run specific test module
poetry run pytest tests/test_llm.py
```

## 🛠️ Development

### Setting up development environment

```bash
# Clone the repository
git clone https://github.com/calmmage/calmlib.git
cd calmlib

# Install development dependencies
poetry install --with extras,test,dev

# Setup pre-commit hooks
poetry run pre-commit install

# Run code quality checks
poetry run ruff check .
poetry run black .
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run the test suite: `poetry run pytest`
5. Commit your changes: `git commit -m 'Add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Poetry](https://python-poetry.org/) for dependency management
- LLM integration powered by [LiteLLM](https://github.com/BerriAI/litellm)
- Audio processing using [Whisper](https://github.com/openai/whisper)
- Telegram integration via [Aiogram](https://github.com/aiogram/aiogram)

## 🔗 Links

- [GitHub Repository](https://github.com/calmmage/calmlib)
- [Documentation](https://github.com/calmmage/calmlib/wiki) (Coming Soon)
- [Issues & Bug Reports](https://github.com/calmmage/calmlib/issues)

---

*Made with ❤️ for productive and calm development*
