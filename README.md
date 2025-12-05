# CodeLab Workspace

CodeLab Workspace is an integrated development environment designed for efficient coding and AI assistance. This repository serves as the main workspace containing all necessary components of the CodeLab project.

## Project Structure

The workspace includes the following main components:

- **codelab-ai-service** - AI service backend implementation
- **codelab_ide** - Flutter-based IDE frontend

## Getting Started

### Prerequisites

- Git
- Flutter SDK
- Python 3.8+
- Docker and Docker Compose

### Installation

1. Clone the repository with submodules:
```bash
git clone --recursive git@github.com:pese-git/codelab-workspace.git
# or if you've already cloned the repository:
git submodule update --init --recursive
```

2. Follow the setup instructions in each submodule's README for specific component setup.

## Development

Each component (codelab-ai-service and codelab_ide) can be developed independently in their respective directories. Please refer to their individual documentation for development guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.