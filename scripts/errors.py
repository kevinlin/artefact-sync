from __future__ import annotations

from pathlib import PurePosixPath


class ArtefactSyncError(Exception):
    """Anything this tool raises on purpose."""


class ConfigError(ArtefactSyncError):
    """The pointer file or the manifest's site block is missing or malformed."""


class ValidationError(ArtefactSyncError):
    """A manifest, a source file, or a destination tree failed a check."""


class TransformationError(ArtefactSyncError):
    """A source file could not be turned into its published bytes."""


class UnlistedSources(ArtefactSyncError):
    """Approved source files with no manifest entry. Stops the run and asks."""

    def __init__(self, sources: tuple[PurePosixPath, ...]) -> None:
        super().__init__(f"{len(sources)} approved source(s) have no manifest entry")
        self.sources = sources


class PublishError(ArtefactSyncError):
    """A publish step failed. The message carries recovery for that exact state."""
