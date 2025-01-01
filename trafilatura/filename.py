from datetime import datetime
import re
import os
from base64 import urlsafe_b64encode
from string import Formatter
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse, unquote

from .deduplication import generate_bow_hash

CLEAN_XML = re.compile(r"<[^<]+?>")

# Characters that are unsafe everywhere - templates and filenames
ALWAYS_UNSAFE_CHARS = r'[<>:"|?*\\]'
# Additional characters unsafe in filenames (`/` is allowed in templates)
FILENAME_UNSAFE_CHARS = r'[<>:"|?*\\\s]'

# Maximum total path length
DEFAULT_PATH_LENGTH = 250

NO_PARAMS_KEY = "__no_params"
TRUNCATE_KEY = "_ttt_"
DOT_KEY_UNIT = "d"


def generate_hash_filename(content: str) -> str:
    """Create a filename-safe string by hashing the given content
    after deleting potential XML tags."""
    return urlsafe_b64encode(generate_bow_hash(CLEAN_XML.sub("", content), 12)).decode()


class FilenameTemplate:
    """Handle template-based filename generation with variables."""

    def __init__(
        self,
        template: str = "{hash}.{ext}",
        ext: str = "txt",
        lang: Optional[str] = None,
        max_length: Optional[int] = None,
        output_dir: Optional[str] = None,
        date: Optional[str] = None,
    ):
        self.template = template
        self.ext = ext
        self.lang = lang
        self.max_length = max_length or DEFAULT_PATH_LENGTH
        self.output_dir = output_dir or None
        self.content = None
        self.date = date or datetime.now().strftime("%Y-%m-%d")
        self._validate_template(template)

    def _validate_template(self, template: str) -> None:
        """Ensure template only uses allowed variables and is filesystem safe.

        Forward slashes are allowed in templates as directory separators, but
        other unsafe characters are still forbidden.
        """
        allowed_vars = {
            "domain",
            "path",
            "path_dirs",
            "params",
            "hash",
            "ext",
            "lang",
            "date",
            "filename",
            "url",
            "file_basepath",
            "file_basename",
            "file_ext",
        }
        used_vars = {v[1] for v in Formatter().parse(template) if v[1] is not None}

        invalid_vars = used_vars - allowed_vars
        if invalid_vars:
            raise ValueError(f"Invalid template variables: {invalid_vars}")

        # Check for always-unsafe characters, allowing forward slashes
        if re.search(ALWAYS_UNSAFE_CHARS, template):
            raise ValueError("Template contains unsafe characters")

    def generate(
        self,
        content: str,
        url: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Generate filename from template and return both the directory path and full path.

        Args:
            content: The content to generate a hash from
            url: Optional URL to extract components from
            filename: Optional filename to use (assumed valid)

        Returns:
            Tuple[str, str]: (output_path, destination_dir)
            - output_path: Path where the file will be written
            - destination_dir: Complete path including filename and eventual extension

        Raises:
            ValueError: If template requirements aren't met or paths exceed length limits
        """
        # Validate we have required data based on template variables
        self._validate_requirements(url, filename)

        # Get template variables
        variables = self._get_variables(content, url, filename)

        # Generate the path from template
        path = self.template.format(**variables)

        # Calculate available space for path components
        available_length = self._get_available_length()

        # Split into directory and filename components
        dirname, basename = os.path.split(path)

        # If no directory specified in template and no output_dir, return empty string
        if not dirname and not self.output_dir:
            return ("", f"{variables['hash']}.{variables['ext']}")

        # Handle output directory if specified
        if self.output_dir:
            dirname = (
                os.path.join(self.output_dir, dirname) if dirname else self.output_dir
            )

        # Truncate path if needed while preserving structure
        if available_length and len(os.path.join(dirname, basename)) > available_length:
            dirname, basename = self._truncate_path(
                dirname, basename, available_length, variables["hash"], variables["ext"]
            )

        # Normalize paths
        output_path = os.path.join(dirname, basename) if dirname else basename
        destination_dir = os.path.normpath(dirname) if dirname else ""

        return (output_path, destination_dir)

    def _validate_requirements(
        self, url: Optional[str], filename: Optional[str]
    ) -> None:
        """Validate that we have the data required by the template variables."""
        required_vars = {v[1] for v in Formatter().parse(self.template) if v[1]}

        # Check URL-dependent variables
        url_vars = {"domain", "path", "path_dirs", "params", "url"}
        if url_vars & required_vars and not url:
            missing = url_vars & required_vars
            raise ValueError(f"URL is required for template variables: {missing}")

        # Check filename-dependent variables
        filename_vars = {"filename", "file_basepath", "file_basename", "file_ext"}
        if filename_vars & required_vars and not filename:
            missing = filename_vars & required_vars
            raise ValueError(f"Filename is required for template variables: {missing}")

    def _get_variables(
        self, content: str, url: Optional[str], filename: Optional[str]
    ) -> Dict[str, str]:
        """Get all variables that can be used in the template."""
        variables = {
            "hash": generate_hash_filename(content or ""),
            "ext": self.ext.lstrip("."),
            "lang": self.lang or "",
            "date": self.date or "",
            "filename": filename or "",
            "url": url or "",
        }

        # Handle filename components if provided
        if filename:
            # Split into directory and name parts
            dirname, basename = os.path.split(filename)
            # Split basename into name and extension
            name, ext = os.path.splitext(basename)

            variables.update(
                {
                    "file_basepath": dirname,
                    "file_basename": name,
                    "file_ext": ext.lstrip("."),  # Remove leading dot for consistency
                }
            )

        # Add URL components if URL provided
        if url:
            url_vars = self._get_url_parts(url)
            variables.update(url_vars)
        else:
            variables.update({"domain": "", "path": "", "path_dirs": "", "params": ""})

        return variables

    def _get_url_parts(self, url: str) -> dict:
        if not url:
            return {"domain": "", "path": "", "path_dirs": "", "params": ""}

        parsed = urlparse(url)

        # Handle domain and port
        domain = parsed.netloc.split(":")[0]
        domain = self._sanitize_component(domain)

        # Get both flat and structured paths
        path_segments = self._sanitize_path(parsed.path)
        flat_path = "_".join(path_segments)
        structured_path = "/".join(path_segments)

        # Handle query parameters
        params = self._get_params(parsed.query)

        return {
            "domain": domain,
            "path": flat_path,
            "path_dirs": structured_path,
            "params": params,
        }

    def _get_params(self, query: str) -> str:
        params = ""
        if query:
            try:
                param_dict = parse_qs(query)
                # Sort for consistency and take first value of each parameter
                param_pairs = sorted((k, v[0]) for k, v in param_dict.items() if v)
                params = "_".join(f"{k}-{v}" for k, v in param_pairs)
                params = self._sanitize_component(params)
            except (IndexError, KeyError):
                params = NO_PARAMS_KEY
        else:
            params = NO_PARAMS_KEY

        return params

    def _sanitize_component(self, part: str) -> str:
        """Create safe filename component.

        All unsafe characters, including forward slashes, are replaced with
        underscores in actual filenames.
        """
        if not part:
            return ""
        safe = re.sub(FILENAME_UNSAFE_CHARS, "_", part)
        safe = re.sub(r"_+", "_", safe)
        return safe.strip("_")

    def _sanitize_path(self, path: str) -> list[str]:
        """Sanitize path into list of clean segments."""
        # First replace %2F with _
        raw_path = path.replace("%2F", "_")
        # Then decode other URL-encoded characters
        path = unquote(raw_path)
        # Remove common endings
        path = re.sub(r"/(index|default)\.(html?|php)$", "", path)

        segments = []
        for segment in path.split("/"):
            if not segment:
                continue
            sanitized = self._sanitize_path_segment(segment)
            if sanitized:
                segments.append(sanitized)

        return segments

    def _sanitize_path_segment(self, segment: str) -> str:
        """Sanitize individual path segments, with special handling only for '.' and '..'."""
        if not segment or segment.isspace():
            return ""
        if segment and all(c == "." for c in segment):
            return "_" + DOT_KEY_UNIT * len(segment) + "_"
        return self._sanitize_component(segment)

    def _get_available_length(self) -> Optional[int]:
        """Calculate available length for path components."""
        if not self.max_length:
            return None

        # If output_dir specified, subtract its length
        if self.output_dir:
            output_dir_len = len(self.output_dir) + 1  # +1 for separator
            if output_dir_len >= self.max_length:
                raise ValueError(
                    f"Output directory length ({output_dir_len}) exceeds "
                    f"maximum path length ({self.max_length})"
                    f"for '{self.output_dir}'"
                )
            return self.max_length - output_dir_len

        return self.max_length

    def _truncate_path(
        self,
        dirname: str,
        basename: str,
        available_length: int,
        content_hash: str,
        extension: str,
    ) -> Tuple[str, str]:
        """Truncate path components while preserving structure and essential information.

        Args:
            dirname: Directory path components
            basename: Original filename
            available_length: Maximum allowed length
            content_hash: Content hash for uniqueness
            extension: File extension without dot

        Returns:
            Tuple of (directory_path, filename)
        """
        # Check if extension is required in template
        ext_in_template = "{ext}" in self.template
        extension_part = f".{extension}" if ext_in_template else ""

        # Minimum filename configuration
        min_filename = f"{TRUNCATE_KEY}{content_hash}{extension_part}"

        # If path fits as-is, return unmodified
        full_path = os.path.join(dirname, basename) if dirname else basename
        if len(full_path) <= available_length:
            return dirname, basename

        # Remove output_dir if present from dirname
        if self.output_dir and dirname.startswith(self.output_dir):
            dirname = dirname[len(self.output_dir) :].lstrip(os.sep)

        # Split path into segments
        segments = dirname.split(os.sep) if dirname else []

        # Try to preserve as many path segments as possible
        preserved_segments: list[str] = []
        remaining_length = available_length - len(min_filename)

        # Add segments while they fit
        for segment in segments:
            # Account for path separator
            segment_len = len(segment) + (1 if preserved_segments else 0)
            if remaining_length - segment_len > 0:
                preserved_segments.append(segment)
                remaining_length -= segment_len
            else:
                break

        # Build final paths
        final_dirname = (
            os.path.join(self.output_dir, *preserved_segments)
            if self.output_dir
            else os.path.join(*preserved_segments)
            if preserved_segments
            else ""
        )
        final_basename = min_filename

        return final_dirname, final_basename
