"""PylintCleaner class for removing unnecessary pylint disable comments."""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .rule import Rules

# Configure logging
logger = logging.getLogger(__name__)

# Constants for regex group indices
GROUP_BEFORE_PYLINT = 2
GROUP_RULES_TEXT = 3
GROUP_AFTER_PYLINT = 4
MIN_GROUPS_FOR_DISABLE = 3


@dataclass
class DisableComment:
    """Represents a pylint disable comment with its context.

    Attributes:
        file_path: Path to the file containing the comment.
        line_number: Line number of the comment.
        original_line: Original line content.
        pylint_rules: List of pylint rule identifiers in the disable comment.
        other_tools_content: Non-pylint content in the comment (e.g., noqa).
        comment_format: Format of the disable comment (inline, block, etc.).

    """

    file_path: Path
    line_number: int
    original_line: str
    pylint_rules: list[str]
    other_tools_content: str
    comment_format: str


class PylintCleaner:
    """Removes unnecessary pylint disable comments.

    Uses useless-suppression analysis to identify disable comments that are no
    longer necessary, then surgically removes them while preserving other tool
    comments and maintaining code formatting.
    """

    def __init__(
        self,
        *,
        config_file: Path,
        dry_run: bool,
        project_root: Path,
        rules: Rules,
    ) -> None:
        """Initialize the PylintCleaner.

        Args:
            config_file: Path to the configuration file (e.g., pyproject.toml).
            dry_run: Whether to run in dry-run mode.
            project_root: Root directory of the project to clean.
            rules: Rules instance containing all rule information.

        """
        self.config_file = config_file
        self.dry_run = dry_run
        self.project_root = project_root
        self.rules = rules
        self._disable_patterns = self._compile_disable_patterns()

    def run(self) -> dict[Path, int]:
        """Run the PylintCleaner to remove unnecessary disable comments.

        Returns:
            Dictionary mapping file paths to number of lines modified.

        """
        logger.info("Running PylintCleaner to remove unnecessary disable comments")

        try:
            modifications = self.clean_files(dry_run=self.dry_run)

            if modifications:
                total_lines = sum(modifications.values())
                if self.dry_run:
                    logger.info(
                        "PylintCleaner would modify %d lines across %d files",
                        total_lines,
                        len(modifications),
                    )
                else:
                    logger.info(
                        "PylintCleaner cleaned %d lines across %d files",
                        total_lines,
                        len(modifications),
                    )
            else:
                logger.info("PylintCleaner found no unnecessary disable comments")

        except (subprocess.CalledProcessError, OSError, ValueError) as e:
            logger.warning("PylintCleaner failed: %s", e)
            if not self.dry_run:
                logger.info("Operation completed despite cleaner failure")
            return {}
        else:
            return modifications

    def _compile_disable_patterns(self) -> list[re.Pattern[str]]:
        """Compile regex patterns for detecting pylint disable comments.

        Returns:
            List of compiled regex patterns for different disable comment formats.

        """
        return [
            # Single line with rule name or code
            re.compile(
                r"^(.*?)\s*#\s*(.*)?\s*pylint:\s*disable=([a-zA-Z0-9_,-]+)\s*(.*?)$"
            ),
            # Multiple rules by name or code
            re.compile(
                r"^(.*?)\s*#\s*(.*)?\s*pylint:\s*disable=([A-Z]\d+(?:,[A-Z]\d+)*)\s*(.*?)$"
            ),
            # Mixed with other tools
            re.compile(
                r"^(.*?)\s*#\s*(.*?)\s*pylint:\s*disable=([a-zA-Z0-9_,-]+)\s*(.*?)$"
            ),
            # File-level disable
            re.compile(r"^#\s*pylint:\s*skip-file\s*(.*)$"),
            # General pylint disable pattern (catch-all)
            re.compile(
                r"^(.*?)\s*#\s*(.*?)\s*pylint:\s*disable=([a-zA-Z0-9_,\s-]+)\s*(.*?)$"
            ),
        ]

    def _detect_useless_suppressions(self) -> dict[Path, list[tuple[int, str]]]:
        """Detect useless pylint suppressions using pylint's built-in check.

        Returns:
            Dictionary mapping file paths to lists of (line_number, rule_name) tuples
            for useless suppressions.

        """
        logger.info(
            "Running pylint with useless-suppression to detect unnecessary disables"
        )

        try:
            # Run pylint with user's config on git-tracked Python files
            # Note: useless-suppression is now always enabled via RuffPylintExtractor
            cmd = (
                f"python -m pylint --output-format=parseable "
                f"--rcfile {self.config_file} $(git ls-files '*.py')"
            )

            # Run pylint with the user's configuration
            # Note: Using trusted pylint command from user's environment
            result = subprocess.run(  # noqa: S602
                cmd,
                capture_output=True,
                check=False,  # Don't raise on non-zero exit (expected)
                cwd=self.project_root,
                shell=True,
                text=True,
                timeout=120,
            )

            return self._parse_pylint_output(output=result.stdout)

        except subprocess.TimeoutExpired:
            logger.exception("Pylint command timed out after 120 seconds")
            return {}
        except Exception:
            logger.exception("Error running pylint to detect useless suppressions")
            return {}

    def _parse_pylint_output(self, *, output: str) -> dict[Path, list[tuple[int, str]]]:
        """Parse pylint output to extract useless suppression information.

        Args:
            output: Pylint output in parseable format.

        Returns:
            Dictionary mapping file paths to lists of (line_number, rule_name) tuples.

        """
        useless_suppressions: dict[Path, list[tuple[int, str]]] = {}

        # Parse pylint output format (can be different based on config):
        # Format 1: file.py:302: [I0021(useless-suppression), ] Useless suppression
        # Format 2: file.py:302:0: I0021: Useless suppression of 'X'
        patterns = [
            # Format 1: with brackets and parentheses
            re.compile(
                r"^([^:]+):(\d+):\s*\[I0021\([^)]+\),\s*\]\s*"
                r"Useless suppression of '([^']+)'"
            ),
            # Format 2: simple format
            re.compile(
                r"^([^:]+):(\d+):\d+:\s*I0021:\s*Useless suppression of '([^']+)'"
            ),
        ]

        for line in output.strip().split("\n"):
            if not line.strip():
                continue

            # Try both patterns
            for pattern in patterns:
                match = pattern.match(line)
                if match:
                    file_path = Path(match.group(1))
                    line_number = int(match.group(2))
                    rule_name = match.group(3)

                    # Make file path absolute relative to project root
                    # Handles cases where tool runs from different working directory
                    if not file_path.is_absolute():
                        file_path = self.project_root / file_path

                    if file_path not in useless_suppressions:
                        useless_suppressions[file_path] = []
                    useless_suppressions[file_path].append((line_number, rule_name))
                    break  # Found a match, no need to try other patterns

        logger.info("Found useless suppressions in %d files", len(useless_suppressions))
        return useless_suppressions

    def _parse_disable_comment(
        self, *, file_path: Path, line_content: str, line_number: int
    ) -> DisableComment | None:
        """Parse a line to extract pylint disable comment information.

        Args:
            file_path: Path to the file containing the line.
            line_content: Content of the line to parse.
            line_number: Line number in the file.

        Returns:
            DisableComment object if a pylint disable is found, None otherwise.

        """
        for pattern in self._disable_patterns:
            match = pattern.match(line_content)
            if match:
                # Extract components based on pattern groups
                if "skip-file" in line_content:
                    return DisableComment(
                        file_path=file_path,
                        line_number=line_number,
                        original_line=line_content,
                        pylint_rules=["skip-file"],
                        other_tools_content=match.group(1)
                        if match.lastindex and match.lastindex >= 1
                        else "",
                        comment_format="skip-file",
                    )

                # For regular disable patterns
                if match.lastindex and match.lastindex >= MIN_GROUPS_FOR_DISABLE:
                    before_pylint = (
                        match.group(GROUP_BEFORE_PYLINT)
                        if match.lastindex >= GROUP_BEFORE_PYLINT
                        else ""
                    )
                    rules_text = match.group(GROUP_RULES_TEXT)
                    after_pylint = (
                        match.group(GROUP_AFTER_PYLINT)
                        if match.lastindex >= GROUP_AFTER_PYLINT
                        else ""
                    )

                    # Parse comma-separated rules
                    pylint_rules = [
                        rule.strip() for rule in rules_text.split(",") if rule.strip()
                    ]

                    return DisableComment(
                        file_path=file_path,
                        line_number=line_number,
                        original_line=line_content,
                        pylint_rules=pylint_rules,
                        other_tools_content=f"{before_pylint}{after_pylint}".strip(),
                        comment_format="inline",
                    )

        return None

    def _is_rule_useless(self, *, rule: str, useless_rules: list[str]) -> bool:
        """Check if a rule should be considered useless.

        Handles matching between rule codes (E0401) and rule names (import-error).

        Args:
            rule: Rule identifier to check.
            useless_rules: List of useless rule identifiers.

        Returns:
            True if the rule is useless and should be removed.

        """
        for useless_rule in useless_rules:
            # Check direct match first
            if rule == useless_rule:
                return True
            # Check if they're the same rule (by ID or name)
            rule_obj = self.rules.get_by_identifier(identifier=rule)
            useless_rule_obj = self.rules.get_by_identifier(identifier=useless_rule)
            if (
                rule_obj
                and useless_rule_obj
                and rule_obj.pylint_id == useless_rule_obj.pylint_id
            ):
                return True
        return False

    def _remove_useless_rules_from_comment(  # noqa: PLR0911
        self, *, disable_comment: DisableComment, useless_rules: list[str]
    ) -> str | None:
        """Remove useless rules from a disable comment, preserving necessary ones.

        Args:
            disable_comment: The disable comment to modify.
            useless_rules: List of rule identifiers that are useless.

        Returns:
            Modified line content, or None if the entire comment should be removed.

        """
        if disable_comment.comment_format == "skip-file":
            # Handle skip-file comments separately
            if "skip-file" in useless_rules:
                # Remove entire skip-file comment
                return None
            return disable_comment.original_line

        # Filter out useless rules, keeping necessary ones
        remaining_rules = [
            rule
            for rule in disable_comment.pylint_rules
            if not self._is_rule_useless(rule=rule, useless_rules=useless_rules)
        ]

        if not remaining_rules:
            # All pylint rules are useless
            if disable_comment.other_tools_content.strip():
                # Preserve other tool comments
                code_part = disable_comment.original_line.split("#")[0]
                return f"{code_part}# {disable_comment.other_tools_content}".rstrip()
            # Remove entire comment line if no code before it
            code_part = disable_comment.original_line.split("#")[0]
            if not code_part.strip():
                return None
            return code_part.rstrip()

        # Reconstruct the comment with remaining rules
        code_part = disable_comment.original_line.split("#")[0]
        remaining_rules_text = ",".join(remaining_rules)

        if disable_comment.other_tools_content.strip():
            # Preserve other tool comments
            return (
                f"{code_part}# {disable_comment.other_tools_content}  "
                f"# pylint: disable={remaining_rules_text}"
            )
        return f"{code_part}# pylint: disable={remaining_rules_text}"

    def _remove_useless_disables(
        self,
        content: str,
        file_path: Path,
        useless_suppressions: list[tuple[int, str]],
    ) -> tuple[str, int]:
        """Remove useless pylint disable comments from a single file's content.

        Args:
            content: The original content of the file.
            file_path: The path to the file.
            useless_suppressions: A list of (line_number, rule_name) tuples for
                useless suppressions to remove.

        Returns:
            A tuple of (modified_content, lines_modified_count).

        """
        # Group useless suppressions by line number
        useless_by_line: dict[int, list[str]] = {}
        for line_num, rule_name in useless_suppressions:
            if line_num not in useless_by_line:
                useless_by_line[line_num] = []
            useless_by_line[line_num].append(rule_name)

        # Read file content and preserve trailing newline behavior
        try:
            content_lines = content.splitlines()
            # Check if original content ended with a newline
            original_has_trailing_newline = content.endswith(("\n", "\r\n", "\r"))
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Failed to read file %s: %s", file_path, e)
            return content, 0

        new_content_lines = []
        lines_modified = 0

        # Process each line
        for line_num, line_content in enumerate(content_lines, 1):
            if line_num in useless_by_line:
                # This line has useless suppressions
                disable_comment = self._parse_disable_comment(
                    file_path=file_path,
                    line_content=line_content,
                    line_number=line_num,
                )

                if disable_comment:
                    useless_rules = useless_by_line[line_num]
                    new_line = self._remove_useless_rules_from_comment(
                        disable_comment=disable_comment,
                        useless_rules=useless_rules,
                    )

                    if new_line is not None:
                        new_content_lines.append(new_line)
                        # Count as modified if the line content changed
                        if new_line != line_content:
                            lines_modified += 1
                    else:
                        # Line was completely removed
                        lines_modified += 1
                    # If new_line is None, skip this line (remove it)
                else:
                    # Failed to parse, keep original
                    new_content_lines.append(line_content)
            else:
                # No useless suppressions on this line
                new_content_lines.append(line_content)

        # Rejoin lines and preserve original trailing newline behavior
        result = "\n".join(new_content_lines)
        if original_has_trailing_newline and not result.endswith("\n"):
            result += "\n"
        return result, lines_modified

    def clean_files(self, *, dry_run: bool = False) -> dict[Path, int]:
        """Clean unnecessary pylint disable comments from project files.

        Args:
            dry_run: If True, only report what would be changed without modifying files.

        Returns:
            Dictionary mapping file paths to number of lines modified.

        """
        logger.info("Starting pylint disable comment cleanup")

        # Step 1: Detect useless suppressions
        useless_suppressions = self._detect_useless_suppressions()

        if not useless_suppressions:
            logger.info("No useless suppressions found")
            return {}

        modifications: dict[Path, int] = {}

        # Step 2: Process each file with useless suppressions
        for file_path, useless_list in useless_suppressions.items():
            if not file_path.exists():
                logger.warning("File not found: %s", file_path)
                continue

            # Read file content
            try:
                content = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Failed to read file %s: %s", file_path, e)
                continue

            # Remove useless suppressions from the content
            new_content, modified_lines = self._remove_useless_disables(
                content=content,
                file_path=file_path,
                useless_suppressions=useless_list,
            )

            if new_content != content:
                modifications[file_path] = modified_lines

                if not dry_run:
                    # Write modified content back to file
                    try:
                        file_path.write_text(new_content, encoding="utf-8")
                        logger.info("Cleaned %d lines in %s", modified_lines, file_path)
                    except OSError:
                        logger.exception("Failed to write file %s", file_path)

        total_modified = sum(modifications.values())
        if dry_run:
            logger.info(
                "DRY RUN: Would modify %d lines across %d files",
                total_modified,
                len(modifications),
            )
        else:
            logger.info(
                "Successfully cleaned %d lines across %d files",
                total_modified,
                len(modifications),
            )

        return modifications
