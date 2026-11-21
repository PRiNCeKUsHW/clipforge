class PipelineError(Exception):
    """An expected failure with a message that is safe and useful to show the user. Not retried."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


class TransientError(Exception):
    """A temporary failure (network blip, rate limit, 5xx). Celery retries these with backoff."""
