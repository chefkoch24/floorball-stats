from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


RETRYABLE_STATUS_CODES = (403, 408, 409, 415, 425, 429, 500, 502, 503, 504, 520, 522, 524)


def build_retry_session(
    *,
    retries: int = 4,
    backoff_factor: float = 1.0,
    status_forcelist: tuple[int, ...] = RETRYABLE_STATUS_CODES,
) -> requests.Session:
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=None,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def request_with_retries(
    method: str,
    url: str,
    *,
    timeout: int = 30,
    session: requests.Session | None = None,
    **kwargs: Any,
) -> requests.Response:
    managed_session = session is None
    sess = session or build_retry_session()
    try:
        response = sess.request(method=method, url=url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response
    finally:
        if managed_session:
            sess.close()
