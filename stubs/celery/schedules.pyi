from typing import Any

class crontab:
    def __init__(
        self,
        minute: str | int = "*",
        hour: str | int = "*",
        day_of_week: str | int = "*",
        day_of_month: str | int = "*",
        month_of_year: str | int = "*",
        **kwargs: Any,
    ) -> None: ...
