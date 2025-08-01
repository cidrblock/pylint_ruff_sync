# Pylint-Ruff Sync

> **CAUTION: This project needs a maintainer!**
>
> This repository was created as a proof-of-concept and demonstration project. **Do not use this repository directly** as it may be removed or archived without notice.
>
> If you're interested in using this tool:
>
> - **Fork this repository** to create your own maintained version
> - **Consider becoming the maintainer** by reaching out to [@cidrblock](https://github.com/cidrblock)
> - **Check for community forks** that may have active maintenance
>
> This codebase includes comprehensive tests and documentation, but requires ongoing maintenance for GitHub API changes, ruff updates, and dependency management.

A precommit hook that automatically synchronizes your `pyproject.toml` pylint configuration with ruff's implementation status. This tool eliminates rule duplication between pylint and ruff by maintaining an optimal configuration that leverages the strengths of both tools.

## Core Functionality

This tool performs two primary operations:

1. **Configuration Synchronization**: Updates `pyproject.toml` to enable only pylint rules not implemented in ruff
2. **Code Cleanup**: Removes unnecessary pylint disable comments from your codebase

The configuration is automatically synchronized based on real-time data from the [ruff pylint implementation tracking issue](https://github.com/astral-sh/ruff/issues/970), ensuring your setup remains current as ruff evolves.

## Pylint Command and Configuration

### Command Execution

The tool runs pylint with the following command to detect unnecessary disable comments:

```bash
pylint --output-format=parseable --rcfile {config_file} $(git ls-files '*.py')
```

This command:

- Uses your existing pylint configuration file (`--rcfile`) with all your normal rules
- Only checks Python files tracked by git (`git ls-files '*.py'`)
- Outputs results in parseable format for processing
- The `useless-suppression` rule is automatically enabled via the tool's configuration synchronization

### Configuration Requirements

**All pylint configuration must be in your config file** (typically `pyproject.toml`). The tool automatically ensures that `useless-suppression` is enabled in your configuration during the synchronization process, so you don't need to manually enable it.

The tool does not modify pylint's behavior beyond updating the `disable` and `enable` lists in your configuration file. Settings like:

- Line length limits
- Naming conventions
- Plugin configurations
- Custom rule settings
- Output formats

Should all be configured in your `[tool.pylint]` sections in `pyproject.toml`.

## Key Features

### Configuration Management

- **Always Current**: References live GitHub issue data for accurate rule status
- **Enable-Only Strategy**: Maintains shorter, more manageable rule lists that shrink over time
- **Format Preservation**: Preserves existing formatting, comments, and custom configurations
- **Mypy Integration**: Optionally excludes rules that overlap with mypy functionality

### Code Cleanup (PylintCleaner)

- **Comment Removal**: Identifies and removes unnecessary pylint disable comments
- **Multi-Format Support**: Handles various pylint disable comment patterns
- **Tool Preservation**: Maintains comments for other tools (noqa, type: ignore, etc.)
- **Selective Removal**: Removes only unnecessary rules while preserving necessary ones

### Operational Features

- **Error Handling**: Graceful fallback to cached data when network unavailable
- **Logging**: Detailed operation reporting for debugging and monitoring
- **Type Safety**: Full type annotations throughout codebase
- **CI/CD Ready**: Designed for automated pipeline integration

## Installation

Add to your precommit configuration:

```yaml
repos:
  - repo: https://github.com/cidrblock/pylint-ruff-sync
    rev: v1.0.0
    hooks:
      - id: pylint-ruff-sync
```

## Usage

### Basic Operation

```bash
# Update configuration with current ruff implementation status
pylint-ruff-sync

# Preview changes without modifying files
pylint-ruff-sync --dry-run

# Update specific configuration file
pylint-ruff-sync --config-file path/to/pyproject.toml

# Disable automatic pylint comment cleanup
pylint-ruff-sync --disable-pylint-cleaner
```

### Advanced Options

```bash
# Enable verbose logging for debugging
pylint-ruff-sync --verbose

# Include rules that overlap with mypy
pylint-ruff-sync --disable-mypy-overlap

# Update local cache from GitHub
pylint-ruff-sync --update-cache

# Use custom cache location
pylint-ruff-sync --cache-path /custom/cache/path.json
```

### Rule Format and Comment Options

Control how rules appear in your pyproject.toml:

```bash
# Use rule codes (C0103, W0613) instead of names - default
pylint-ruff-sync --rule-format code

# Use rule names (invalid-name, unused-argument) instead of codes
pylint-ruff-sync --rule-format name

# Add documentation URLs as comments (default)
pylint-ruff-sync --rule-comment doc_url

# Add rule codes as comments
pylint-ruff-sync --rule-comment code

# Add rule names as comments
pylint-ruff-sync --rule-comment name

# Add short descriptions as comments
pylint-ruff-sync --rule-comment short_description

# No comments at all
pylint-ruff-sync --rule-comment none

# Combine different formats - use names with code comments
pylint-ruff-sync --rule-format name --rule-comment code

# Use codes with no comments for minimal output
pylint-ruff-sync --rule-format code --rule-comment none
```

### Array Formatting

Arrays in the pyproject.toml file automatically use multiline format when:

- The array contains comments, OR
- The single-line format would exceed 88 characters

This ensures readability while keeping short arrays compact:

```toml
# Short arrays stay single-line
disable = ["all"]

# Arrays with comments become multiline
disable = [
  "all",  # All rules
  "R0903", # https://pylint.readthedocs.io/en/stable/user_guide/messages/refactor/too-few-public-methods.html
]

# Long arrays become multiline even without comments
disable = [
  "very-long-rule-name-01",
  "very-long-rule-name-02",
  "very-long-rule-name-03"
]
```

## PylintCleaner: Automated Comment Cleanup

The PylintCleaner component automatically removes unnecessary pylint disable comments after updating your configuration. This feature:

### Detection Process

1. Runs pylint with `useless-suppression` enabled to identify unnecessary disables
2. Parses various pylint disable comment formats
3. Determines which specific rules are no longer needed

### Supported Comment Formats

```python
# Single rule disable
x = eval("1 + 2")  # pylint: disable=eval-used

# Multiple rules
def foo(bar):  # pylint: disable=unused-argument,missing-function-docstring

# Mixed with other tools
z = eval("5 + 6")  # noqa: E501  # pylint: disable=eval-used

# File-level disables
# pylint: skip-file

# Code and name formats
y = eval("3 + 4")  # pylint: disable=W0123
```

### Processing Behavior

- **Partial Removal**: Removes only unnecessary rules while preserving necessary ones
- **Tool Preservation**: Maintains comments for ruff, mypy, type checkers, etc.
- **Format Preservation**: Maintains original comment structure and spacing
- **Testing**: Includes test coverage for comment processing functionality

### Configuration

PylintCleaner is enabled by default but can be controlled:

```bash
# Disable cleaner functionality
pylint-ruff-sync --disable-pylint-cleaner

# Preview cleaner actions in dry-run mode
pylint-ruff-sync --dry-run  # Shows both config and cleaner changes
```

## Configuration Optimization: Removing Unnecessary Disable Rules

This tool employs an **"enable-only strategy"** that automatically removes unnecessary disable rules from your `pyproject.toml` configuration, creating cleaner and more maintainable pylint setups.

### How the Enable-Only Strategy Works

Instead of maintaining long lists of individually disabled rules, the tool:

1. **Sets `disable = ["all"]`** - Disables all pylint rules by default
2. **Populates `enable = [...]`** - Only enables rules that pylint should check (those not implemented in ruff)
3. **Removes redundant disable entries** - Eliminates the need to explicitly disable rules that ruff handles

### Example Transformation

**Before optimization:**

```toml
[tool.pylint.messages_control]
disable = [
  "C0103",  # invalid-name (implemented in ruff)
  "W0613",  # unused-argument (implemented in ruff)
  "C0116",  # missing-function-docstring (not in ruff)
  "E1101",  # no-member (overlaps with mypy)
  "locally-disabled",
  "suppressed-message"
]
```

**After optimization:**

```toml
[tool.pylint.messages_control]
disable = [
  "all",
  "locally-disabled",   # I0011 - Preserved user preference
  "suppressed-message"  # I0020 - Preserved user preference
]
enable = [
  "C0116",  # https://pylint.readthedocs.io/en/stable/user_guide/messages/convention/missing-function-docstring.html
]
```

### Why Rules Are Removed

The tool removes disable entries for three categories of rules:

#### 1. **Ruff-Implemented Rules** ✅

- **Removed because**: Ruff already checks these rules more efficiently
- **Examples**: `invalid-name` (C0103), `unused-argument` (W0613)
- **Result**: No need to explicitly disable them since ruff handles the functionality

#### 2. **Mypy Overlap Rules** 🔄 _(when `--disable-mypy-overlap` not used)_

- **Removed because**: Mypy provides superior type checking for these issues
- **Examples**: `no-member` (E1101), `assignment-from-none` (E1128)
- **Result**: Avoids duplicate checking between pylint and mypy

#### 3. **Redundant Disable Entries** 🧹

- **Removed because**: `disable = ["all"]` already covers them
- **Examples**: Any rule that would be disabled anyway
- **Result**: Cleaner configuration without redundant entries

### Benefits of This Approach

#### **Shorter Configuration Files**

- Rule lists shrink over time as ruff implements more pylint rules
- Less configuration maintenance required
- Easier to understand what pylint is actually checking

#### **Automatic Optimization**

- No manual rule list management needed
- Configuration stays current with ruff development
- Prevents configuration drift and bloat

#### **Preserved Customizations**

- Unknown/custom disabled rules are preserved
- User preferences like `locally-disabled` remain intact
- Tool-specific rules are handled intelligently

### What Gets Preserved

The tool carefully preserves certain disable entries:

- **Unknown rules**: Custom or plugin-specific rules not in the standard pylint set
- **User preferences**: Rules like `locally-disabled`, `suppressed-message`
- **Explicitly enabled rules**: Rules in your enable list take precedence

### Viewing the Optimization Process

Use verbose logging to see exactly what optimizations are performed:

```bash
pylint-ruff-sync --verbose
```

**Example output:**

```
INFO: Total pylint rules: 425
INFO: Rules implemented in ruff: 187
INFO: Rules to enable (not implemented in ruff): 238
INFO: Rules to keep disabled: 12
INFO: Unknown disabled rules preserved: 2
INFO: Disabled rules removed (optimization): 45
```

This shows 45 unnecessary disable entries were removed, streamlining your configuration while maintaining functionality.

## Configuration Examples

### Before Synchronization

```toml
[tool.pylint.messages_control]
disable = [
  "C0103",  # invalid-name (implemented in ruff)
  "W0613",  # unused-argument (implemented in ruff)
  "C0116",  # missing-function-docstring (not in ruff)
]
```

### After Synchronization (Default: --rule-format=code --rule-comment=doc_url)

```toml
[tool.pylint.messages_control]
disable = ["all"]
enable = [
  "C0116",  # https://pylint.readthedocs.io/en/stable/user_guide/messages/convention/missing-function-docstring.html
]
```

### Alternative Formats

**Using rule names with short descriptions (--rule-format=name --rule-comment=short_description):**

```toml
[tool.pylint.messages_control]
disable = ["all"]
enable = [
  "missing-function-docstring",  # Missing function or method docstring
]
```

**Using rule codes with no comments (--rule-format=code --rule-comment=none):**

```toml
[tool.pylint.messages_control]
disable = ["all"]
enable = [
  "C0116"
]
```

**Using rule names with code comments (--rule-format=name --rule-comment=code):**

```toml
[tool.pylint.messages_control]
disable = ["all"]
enable = [
  "missing-function-docstring",  # C0116
]
```

## Technical Architecture

### Data Collection Pipeline

```
pylint --list-msgs → GitHub Issue Parsing → Mypy Overlap Analysis → Rule Synchronization
```

### Components

- **PylintExtractor**: Extracts available rules from pylint installation
- **RuffPylintExtractor**: Parses ruff implementation status from GitHub
- **MypyOverlapExtractor**: Identifies rules that overlap with mypy
- **PyprojectUpdater**: Manages TOML configuration updates
- **PylintCleaner**: Removes unnecessary disable comments
- **TomlFile/TomlRegex**: TOML editing with format preservation

### Caching Strategy

- Local cache for offline operation
- Automatic fallback when network unavailable
- Configurable cache paths for CI/CD environments
- GitHub CLI integration for authenticated access

## Cache File and Data Management

### Rule Status Lookup

**Want to know the status of any pylint rule?** Check the cache file directly:

👉 **[`src/pylint_ruff_sync/data/ruff_implemented_rules.json`](src/pylint_ruff_sync/data/ruff_implemented_rules.json)** 👈

This file contains the complete status of every pylint rule, including:

- Whether it's implemented in ruff
- Whether it overlaps with mypy functionality
- The corresponding ruff rule code (if any)
- Links to documentation

**Example**: Curious about rule `E0401` (import-error)? Search for `"E0401"` in the cache file to see its complete status.

### Cache File Structure

**Cache File Contents**:

```json
{
  "metadata": {},
  "rules": [
    {
      "pylint_id": "C0103",
      "pylint_name": "invalid-name",
      "description": "%s name \"%s\" doesn't conform to %s",
      "is_implemented_in_ruff": true,
      "is_in_ruff_issue": true,
      "is_mypy_overlap": false,
      "ruff_rule": "N815",
      "pylint_category": "C",
      "pylint_docs_url": "https://pylint.readthedocs.io/...",
      "source": "pylint_list",
      "user_comment": ""
    }
  ]
}
```

### Understanding Rule Status Fields

- **`pylint_id`**: Pylint rule identifier (e.g., "C0103", "E0401") - **search for this**
- **`pylint_name`**: Human-readable rule name (e.g., "invalid-name")
- **`description`**: Rule description from pylint documentation
- **`is_implemented_in_ruff`**: ✅ `true` = ruff has this rule, ❌ `false` = pylint only
- **`is_in_ruff_issue`**: Whether rule is tracked in [ruff issue #970](https://github.com/astral-sh/ruff/issues/970)
- **`is_mypy_overlap`**: ✅ `true` = also handled by mypy, ❌ `false` = pylint unique
- **`ruff_rule`**: Corresponding ruff rule code (empty if not implemented)
- **`pylint_category`**: Rule category (C=Convention, E=Error, W=Warning, etc.)
- **`source`**: How the rule was discovered (pylint_list, ruff_issue, etc.)

### Cache Management Commands

```bash
# Update cache from latest GitHub data
pylint-ruff-sync --update-cache

# Use custom cache location
pylint-ruff-sync --cache-path /path/to/custom/cache.json

# View current cache status (shows rule counts)
pylint-ruff-sync --verbose
```

### Troubleshooting Rule Behavior

**Step 1**: Check the [cache file](src/pylint_ruff_sync/data/ruff_implemented_rules.json) for your rule
**Step 2**: Verify the status flags match your expectations
**Step 3**: If incorrect, run `pylint-ruff-sync --update-cache`

**Common Questions & Solutions**:

- **"Why is my rule disabled?"** → Check `is_implemented_in_ruff: true` in cache
- **"Why is my rule missing from config?"** → Check `is_mypy_overlap: true` (filtered by default)
- **"What's the ruff equivalent?"** → Look at `ruff_rule` field in cache
- **"Is this rule outdated?"** → Run `--update-cache` to refresh from GitHub

## Network and Authentication

### GitHub Access

- **Preferred**: GitHub CLI (`gh`) for authenticated access
- **Fallback**: Public API access (rate-limited)
- **Offline**: Local cache for continued operation

### Requirements

- **Network**: Internet connection for live data updates
- **Authentication**: None required (reads public issue data)
- **Fallback**: Cached data enables offline operation

## Integration Patterns

### Precommit Hook

```yaml
repos:
  - repo: https://github.com/cidrblock/pylint-ruff-sync
    rev: v1.0.0
    hooks:
      - id: pylint-ruff-sync
        args: ["--config-file", "pyproject.toml"]
```

### CI/CD Pipeline

```yaml
- name: Sync Pylint Configuration
  run: |
    pylint-ruff-sync --verbose
    git diff --exit-code pyproject.toml || {
      echo "Configuration updated - review changes"
      exit 1
    }
```

### Development Workflow

```bash
# Daily development
pylint-ruff-sync

# Before releases
pylint-ruff-sync --update-cache --verbose

# Debugging
pylint-ruff-sync --dry-run --verbose
```

## Performance Characteristics

### Execution Time

- **Cached Operation**: < 1 second
- **Network Update**: 2-5 seconds
- **Comment Cleanup**: Variable based on codebase size

### Resource Usage

- **Memory**: Minimal (processes TOML and rule data)
- **Network**: Single GitHub API call when updating
- **Disk**: Small cache file (typically < 100KB)

## Error Handling and Reliability

### Graceful Degradation

- Network failures fall back to cached data
- Malformed TOML preserves original files
- GitHub API rate limits trigger cache usage
- Missing dependencies skip optional features

### Validation

- TOML syntax validation before writing
- Rule identifier validation against known pylint rules
- Backup creation for critical operations
- Comprehensive test coverage (>95%)

## Development and Contribution

### Code Quality Standards

- **Type Safety**: Full mypy compliance
- **Testing**: Comprehensive unit and integration tests
- **Documentation**: Complete docstring coverage
- **Code Style**: Black, ruff, and pylint compliance

### Architecture Principles

- **Single Responsibility**: Each class has one clear purpose
- **Dependency Injection**: Configurable components for testing
- **Error Isolation**: Failures in one component don't affect others
- **Immutable Operations**: No unexpected side effects

## License and Attribution

This project was developed through collaborative human-AI pair programming between [Bradley Thornton (cidrblock)](https://github.com/cidrblock) and Claude 4 Sonnet AI.

Licensed under the MIT License. See LICENSE file for details.
