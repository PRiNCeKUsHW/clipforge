"""Redis pub/sub channel names shared by the API (subscriber) and the worker (publisher)."""


def project_channel(project_id: str) -> str:
    return f"clipforge:project:{project_id}"
