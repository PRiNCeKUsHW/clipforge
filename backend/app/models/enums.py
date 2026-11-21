from enum import StrEnum


class SourceType(StrEnum):
    youtube = "youtube"
    upload = "upload"


class ProjectStatus(StrEnum):
    queued = "queued"
    downloading = "downloading"
    transcribing = "transcribing"
    finding_highlights = "finding_highlights"
    reframing = "reframing"
    rendering = "rendering"
    ready = "ready"
    failed = "failed"


TERMINAL_STATUSES = frozenset({ProjectStatus.ready, ProjectStatus.failed})


class ClipStatus(StrEnum):
    pending = "pending"
    rendering = "rendering"
    ready = "ready"
    failed = "failed"


class Platform(StrEnum):
    youtube = "youtube"
    instagram = "instagram"


class PublishStatus(StrEnum):
    queued = "queued"
    uploading = "uploading"
    published = "published"
    failed = "failed"
