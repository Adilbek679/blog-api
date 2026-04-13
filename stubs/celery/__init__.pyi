from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

class Celery:
    def __init__(self, main: str = "") -> None: ...
    def config_from_object(self, obj: Any, namespace: str = "") -> None: ...
    def autodiscover_tasks(self) -> None: ...
    conf: Any

def shared_task(
    *args: Any,
    bind: bool = False,
    autoretry_for: tuple[type[Exception], ...] = (),
    retry_backoff: bool = False,
    max_retries: int = 3,
    **kwargs: Any,
) -> Callable[[F], F]: ...
