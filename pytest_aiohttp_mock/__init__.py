__version__ = "0.1.0"

# Inspired by pytest_httpx

from collections.abc import Mapping, Sequence
from operator import methodcaller
from typing import Any

import aiohttp
import pytest
from aiohttp.typedefs import LooseCookies, LooseHeaders, Query, StrOrURL
from multidict import CIMultiDict

from pytest_aiohttp_mock._aiohttp_mock import AioHttpMock, _AioHttpMockOptions
from pytest_aiohttp_mock._request import AioHttpRequest

HeaderTypes = CIMultiDict[str] | Mapping[str, str] | Sequence[tuple[str, str]]

__all__ = (
    "AioHttpMock",
    "__version__",
)


@pytest.fixture
def aiohttp_mock(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
):
    options = {}
    for marker in request.node.iter_markers("httpx_mock"):
        options = marker.kwargs | options
    __tracebackhide__ = methodcaller("errisinstance", TypeError)
    options = _AioHttpMockOptions(**options)

    mock = AioHttpMock(options)

    real_handle_request = aiohttp.ClientSession._request

    async def mocked_request(
        self,
        method: str,
        str_or_url: StrOrURL,
        *,
        params: Query = None,
        data: Any = None,
        json: Any = None,
        cookies: LooseCookies | None = None,
        headers: LooseHeaders | None = None,
        **kwargs,
    ):
        request = AioHttpRequest(
            method=method,
            url=str_or_url,
            params=params,
            data=data,
            json=json,
            cookies=cookies,
            headers=headers,
        )
        if options.should_mock(request):
            return mock._handle_request(request)

        return real_handle_request(
            self,
            method,
            str_or_url,
            params=params,
            data=data,
            json=json,
            cookies=cookies,
            headers=headers,
            **kwargs,
        )

    monkeypatch.setattr(
        aiohttp.ClientSession,
        "_request",
        mocked_request,
    )

    yield mock
    try:
        mock._assert_options()
    finally:
        mock.reset()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "aiohttp_mock(*, assert_all_responses_were_requested=True, assert_all_requests_were_expected=True, can_send_already_matched_responses=False, should_mock=lambda request: True): Configure httpx_mock fixture.",  # noqa: E501
    )
