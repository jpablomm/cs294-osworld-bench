# Contributing to Green Agent

Thank you for your interest in contributing to Green Agent! This document provides guidelines and instructions for contributing.

## 🎯 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a branch** for your changes: `git checkout -b feature/your-feature-name`
4. **Make your changes** following the guidelines below
5. **Test thoroughly** before submitting
6. **Submit a pull request** with a clear description

## 📋 Development Setup

### Prerequisites

- Python 3.11+
- Docker Desktop (for OSWorld testing)
- Google Cloud SDK (for GCP deployment testing)
- Git

### Local Setup

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/green-agent.git
cd green-agent

# Initialize submodules
git submodule update --init --recursive

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install OSWorld dependencies
cd vendor/OSWorld
pip install -r requirements.txt
cd ../..
```

### Testing

```bash
# Test fake mode (no VM needed)
export USE_FAKE_OSWORLD=1
uvicorn green_agent.app:app --port 8000

# In another terminal
curl http://localhost:8000/health
```

## 📝 Code Style

### Python

- Follow PEP 8 style guide
- Use type hints where appropriate
- Keep functions focused and small
- Add docstrings for public functions/classes
- Use meaningful variable names

### Example

```python
from typing import Dict, Any, Optional

def run_assessment(
    task_id: str,
    white_agent_url: str,
    max_steps: int = 15
) -> Dict[str, Any]:
    """
    Run an OSWorld assessment task.
    
    Args:
        task_id: Unique identifier for the task
        white_agent_url: URL of the white agent service
        max_steps: Maximum number of steps to execute
        
    Returns:
        Dictionary containing assessment results
        
    Raises:
        ValueError: If task_id is invalid
        ConnectionError: If white agent is unreachable
    """
    # Implementation here
    pass
```

## 🧪 Testing Guidelines

### Unit Tests

- Write tests for new features
- Aim for >80% code coverage
- Use descriptive test names
- Test both success and failure cases

### Integration Tests

- Test end-to-end workflows
- Use fake mode when possible (faster)
- Test with real OSWorld VMs for critical paths
- Document any required setup

### Example Test

```python
import pytest
from green_agent.osworld_client import OSWorldClient

def test_screenshot_endpoint():
    """Test that screenshot endpoint returns valid image."""
    client = OSWorldClient("http://localhost:5000")
    screenshot = client.screenshot()
    
    assert screenshot is not None
    assert len(screenshot) > 0
    assert screenshot.startswith(b'\x89PNG')  # PNG magic bytes
```

## 📚 Documentation

### Code Documentation

- Add docstrings to all public functions/classes
- Include parameter descriptions and return types
- Document exceptions that may be raised
- Add usage examples for complex functions

### Documentation Files

- Update relevant `.md` files in `docs/`
- Add new guides for major features
- Keep examples up-to-date
- Include troubleshooting tips

### Documentation Structure

```
docs/
├── getting-started/    # Setup and usage guides
├── architecture/       # System design documents
├── deployment/         # Deployment guides
├── api/               # API references
└── troubleshooting/    # Common issues and solutions
```

## 🐛 Bug Reports

When reporting bugs, please include:

1. **Description**: Clear description of the issue
2. **Steps to Reproduce**: Minimal steps to reproduce
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Environment**: OS, Python version, dependencies
6. **Logs**: Relevant error messages or logs
7. **Screenshots**: If applicable

### Bug Report Template

```markdown
**Description**
Brief description of the bug

**Steps to Reproduce**
1. Step one
2. Step two
3. Step three

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happens

**Environment**
- OS: macOS 14.0
- Python: 3.11.5
- Green Agent version: 0.2.0

**Logs**
```
Paste relevant logs here
```

**Additional Context**
Any other relevant information
```

## ✨ Feature Requests

When requesting features:

1. **Describe the feature** clearly
2. **Explain the use case** and motivation
3. **Propose implementation** approach (if you have ideas)
4. **Consider alternatives** and trade-offs

### Feature Request Template

```markdown
**Feature Description**
Clear description of the feature

**Use Case**
Why is this feature needed? What problem does it solve?

**Proposed Solution**
How should this feature work?

**Alternatives Considered**
Other approaches you've considered

**Additional Context**
Any other relevant information
```

## 🔄 Pull Request Process

### Before Submitting

1. **Update tests** - Add tests for new features
2. **Update documentation** - Update relevant docs
3. **Run tests** - Ensure all tests pass
4. **Check linting** - Fix any linting issues
5. **Test manually** - Test the feature end-to-end

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Tests added/updated and passing
- [ ] Documentation updated
- [ ] No breaking changes (or documented if intentional)
- [ ] Commit messages are clear and descriptive

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How was this tested?

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] No breaking changes
```

## 🏗️ Architecture Guidelines

### Adding New Components

1. **Follow existing patterns** - Match the style of existing code
2. **Keep it simple** - Prefer simple solutions over complex ones
3. **Document decisions** - Add comments for non-obvious choices
4. **Consider performance** - Think about scalability and performance
5. **Plan for errors** - Handle errors gracefully

### Code Organization

```
green_agent/
├── __init__.py
├── app.py              # FastAPI application
├── models.py           # Data models
├── osworld_adapter.py  # OSWorld integration
├── osworld_client.py   # OSWorld REST API client
└── storage.py          # Database layer

orchestrator/
├── app.py              # Cloud Run orchestrator
├── vm_manager.py       # VM lifecycle management
├── task_executor.py    # Task execution logic
└── webui_server.py     # Web UI server
```

## 🔒 Security Considerations

- **Never commit secrets** - Use environment variables or secret managers
- **Validate inputs** - Always validate user inputs
- **Use parameterized queries** - Prevent SQL injection
- **Sanitize URLs** - Prevent SSRF attacks
- **Follow principle of least privilege** - Minimal permissions

## 📊 Performance Considerations

- **Minimize API calls** - Batch operations when possible
- **Use async/await** - For I/O-bound operations
- **Cache when appropriate** - Reduce redundant computations
- **Profile before optimizing** - Measure first, optimize second

## 🎓 Learning Resources

- [OSWorld Documentation](https://github.com/xlang-ai/OSWorld)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Google Cloud Documentation](https://cloud.google.com/docs)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)

## 💬 Communication

- **GitHub Issues** - For bugs and feature requests
- **Pull Requests** - For code contributions
- **Discussions** - For questions and ideas

## 📜 License

By contributing, you agree that your contributions will be licensed under the same license as the project.

## 🙏 Thank You!

Your contributions make this project better for everyone. Thank you for taking the time to contribute!

