# 🤝 Contributing to Media Downloader Bot

First off, thank you for considering contributing! This project thrives on community contributions.

## 📋 Table of Contents
- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Coding Guidelines](#coding-guidelines)
- [Pull Request Process](#pull-request-process)
- [Bug Reports](#bug-reports)
- [Feature Requests](#feature-requests)

## Code of Conduct

### Our Pledge
- Be respectful and inclusive
- Welcome newcomers
- Accept constructive criticism
- Focus on what's best for the community

## How Can I Contribute?

### 1. Reporting Bugs 🐛
Found a bug? Help us fix it!

**Before submitting:**
- Check existing [Issues](https://github.com/yourusername/media-downloader-bot/issues)
- Test with the latest version
- Try updating yt-dlp: `pip install --upgrade yt-dlp`

**Good bug report includes:**
- Clear title and description
- Steps to reproduce
- Expected vs actual behavior
- Platform (Windows/Linux/Mac)
- Python version
- Bot logs (remove sensitive data!)

### 2. Suggesting Features 💡
Have an idea? We'd love to hear it!

**Good feature request includes:**
- Clear description of the feature
- Why it would be useful
- Example use cases
- Optional: How you think it could be implemented

### 3. Contributing Code 💻
Want to code? Awesome!

**Good first issues:**
- Look for `good first issue` label
- Documentation improvements
- Adding tests
- Fixing typos
- UI/UX improvements

## Development Setup

### 1. Fork & Clone

```bash
# Fork the repo on GitHub, then clone YOUR fork
git clone https://github.com/YOUR_USERNAME/media-downloader-bot.git
cd media-downloader-bot
```

### 2. Set Up Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure

```bash
# Create config file
cp config.example.py config.py

# Add your credentials
# Edit config.py with your BOT_TOKEN and ADMIN_ID
```

### 4. Create Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

## Coding Guidelines

### Python Style
- Follow [PEP 8](https://pep8.org/)
- Use meaningful variable names
- Add docstrings to functions
- Keep functions focused and small

### Code Example

```python
async def download_video(url: str, quality: str) -> Optional[str]:
    """
    Download video from URL with specified quality.

    Args:
        url: Video URL to download
        quality: Desired video quality (e.g., '720p', 'best')

    Returns:
        Path to downloaded file, or None if failed
    """
    try:
        # Implementation here
        pass
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return None
```

### Comments
- Explain WHY, not WHAT
- Update comments when code changes
- Remove commented-out code

### Commit Messages

**Format:**
```
type: Short description (50 chars max)

Longer description if needed (72 chars per line)

- Bullet points for details
- Fixes #issue_number
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**
```
feat: Add playlist download support

- Implement playlist detection
- Add download queue system
- Update UI to show progress

Fixes #42
```

```
fix: Handle TikTok private videos

Previously crashed on private videos.
Now shows user-friendly error message.

Fixes #89
```

## Pull Request Process

### 1. Test Your Changes

```bash
# Make sure bot starts without errors
python bot.py

# Test your specific changes
# - Send test messages
# - Try edge cases
# - Check error handling
```

### 2. Update Documentation

- Update README.md if needed
- Add/update code comments
- Update CHANGELOG.md
- Add examples in docstrings

### 3. Commit and Push

```bash
git add .
git commit -m "feat: Your feature description"
git push origin feature/your-feature-name
```

### 4. Create Pull Request

1. Go to GitHub repository
2. Click "Pull requests" → "New pull request"
3. Select your branch
4. Fill in the template:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Code refactoring

## Testing
- [ ] Tested locally
- [ ] No errors in console
- [ ] Checked edge cases

## Checklist
- [ ] Code follows style guidelines
- [ ] Added comments where needed
- [ ] Updated documentation
- [ ] No sensitive data in commits

## Screenshots (if applicable)
```

### 5. Review Process

- Maintainer will review your PR
- May request changes
- Be patient and responsive
- Once approved, will be merged!

## Project Structure

```
media-downloader-bot/
├── bot.py                 # Main bot logic
├── config.py              # Configuration (gitignored)
├── database.py            # User data management
├── music_recognition.py   # Music ID feature
├── music_handlers.py      # Music handlers
├── text_search.py         # Song search feature
└── requirements.txt       # Dependencies
```

### Adding New Features

**1. Create new module:**
```python
# my_feature.py
"""
My Cool Feature
Description of what it does
"""

class MyFeature:
    def __init__(self):
        pass

    async def do_something(self):
        pass
```

**2. Import in bot.py:**
```python
# In bot.py
from my_feature import MyFeature

# In main():
try:
    my_feature = MyFeature()
    # Add handlers
except Exception as e:
    logger.warning(f"My feature disabled: {e}")
```

**3. Make it optional:**
- Add config toggle: `ENABLE_MY_FEATURE = False`
- Bot should work without it
- Log when feature is enabled/disabled

## Testing

### Manual Testing Checklist

- [ ] Bot starts without errors
- [ ] Basic download works (YouTube)
- [ ] Quality selection works
- [ ] Audio extraction works
- [ ] Admin commands work
- [ ] Error messages are user-friendly
- [ ] No sensitive data in logs

### Testing New Features

- Test with multiple platforms
- Try edge cases (long URLs, special characters)
- Test error scenarios (invalid URLs, network errors)
- Check memory usage (no leaks)

## Bug Reports

**Use this template:**

```markdown
**Describe the bug**
Clear description of what happened

**To Reproduce**
Steps to reproduce:
1. Send URL: '...'
2. Click '...'
3. See error

**Expected behavior**
What should have happened

**Actual behavior**
What actually happened

**Screenshots**
If applicable

**Environment**
- OS: [e.g. Windows 10]
- Python version: [e.g. 3.10.0]
- Bot version: [e.g. v2.1]

**Logs**
```
Paste relevant logs here (remove sensitive data!)
```

**Additional context**
Any other info
```

## Feature Requests

**Use this template:**

```markdown
**Feature description**
Clear description of the feature

**Problem it solves**
What problem does this solve?

**Proposed solution**
How should it work?

**Alternatives considered**
Other ways to solve this?

**Additional context**
Mockups, examples, etc.
```

## Questions?

- 💬 [Discussions](https://github.com/yourusername/media-downloader-bot/discussions)
- 🐛 [Issues](https://github.com/yourusername/media-downloader-bot/issues)
- 📧 Contact maintainers

## Recognition

Contributors will be added to:
- README.md Credits section
- GitHub Contributors page
- Release notes

Thank you for contributing! 🎉
