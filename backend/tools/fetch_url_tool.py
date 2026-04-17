from __future__ import annotations

import re
from urllib.request import urlopen


def fetch_url(url: str) -> str:
    with urlopen(url, timeout=10) as response:  # noqa: S310
        content = response.read().decode("utf-8", errors="ignore")
    text = re.sub(r"<[^>]+>", " ", content)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:5000]

