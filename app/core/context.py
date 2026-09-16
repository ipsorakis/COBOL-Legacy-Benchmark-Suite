from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
program_id_var: ContextVar[str | None] = ContextVar("program_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


@contextmanager
def log_context(
    *,
    correlation_id: str | None = None,
    program_id: str | None = None,
    user_id: str | None = None,
) -> Iterator[None]:
    """Bind ERRLOG-equivalent context to every log record emitted in this scope."""
    correlation_token = correlation_id_var.set(correlation_id or correlation_id_var.get())
    program_token = program_id_var.set(program_id or program_id_var.get())
    user_token = user_id_var.set(user_id or user_id_var.get())
    try:
        yield
    finally:
        correlation_id_var.reset(correlation_token)
        program_id_var.reset(program_token)
        user_id_var.reset(user_token)
