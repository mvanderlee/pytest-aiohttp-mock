import re
from re import Pattern
from typing import Any

from yarl import URL

from pytest_aiohttp_mock._options import _AioHttpMockOptions
from pytest_aiohttp_mock._request import AioHttpRequest


def _url_match(
    url_to_match: Pattern[str] | URL,
    received: URL,
) -> bool:
    if isinstance(url_to_match, re.Pattern):
        return url_to_match.match(str(received)) is not None

    # Compare query parameters apart as order of parameters should not matter
    received_params = dict(received.query)
    params = dict(url_to_match.query)

    # Remove the query parameters from the original URL to compare everything besides query parameters
    received_url = received.with_query(None)
    url = url_to_match.with_query(None)

    return (received_params == params) and (url == received_url)


class _RequestMatcher:
    def __init__(
        self,
        options: _AioHttpMockOptions,
        url: str | Pattern[str] | URL | None = None,
        method: str | None = None,
        proxy_url: str | Pattern[str] | URL | None = None,
        match_headers: dict[str, Any] | None = None,
        is_optional: bool | None = None,
        is_reusable: bool | None = None,
    ):
        self._options = options
        self.nb_calls = 0
        self.url = URL(url) if url and isinstance(url, str) else url if url != "" else None
        self.method = method.upper() if method else method
        self.headers = match_headers
        self.proxy_url = URL(proxy_url) if proxy_url and isinstance(proxy_url, str) else proxy_url
        self.is_optional = (
            not options.assert_all_responses_were_requested if is_optional is None else is_optional
        )
        self.is_reusable = options.can_send_already_matched_responses if is_reusable is None else is_reusable

    def match(
        self,
        request: AioHttpRequest,
    ) -> bool:
        return self._url_match(request) and self._method_match(request) and self._headers_match(request)

    def _url_match(self, request: AioHttpRequest) -> bool:
        if not self.url:
            return True

        return _url_match(self.url, request.URL)

    def _method_match(self, request: AioHttpRequest) -> bool:
        if not self.method:
            return True

        return request.method == self.method

    def _headers_match(self, request: AioHttpRequest) -> bool:
        if not self.headers:
            return True

        request_headers = {}
        # Can be cleaned based on the outcome of https://github.com/encode/httpx/discussions/2841
        for raw_name, raw_value in request.ci_headers:
            if raw_name in request_headers:
                request_headers[raw_name] += ", " + raw_value
            else:
                request_headers[raw_name] = raw_value

        return all(
            request_headers.get(header_name.encode()) == header_value.encode()
            for header_name, header_value in self.headers.items()
        )

    def should_have_matched(self) -> bool:
        """Return True if the matcher did not serve its purpose."""
        return not self.is_optional and not self.nb_calls

    def __str__(self) -> str:
        if self.is_reusable:
            matcher_description = f"Match {self.method or 'every'} request"
        else:
            matcher_description = "Already matched" if self.nb_calls else "Match"
            matcher_description += f" {self.method or 'any'} request"
        if self.url:
            matcher_description += f" on {self.url}"
        if extra_description := self._extra_description():
            matcher_description += f" with {extra_description}"
        return matcher_description

    def _extra_description(self) -> str:
        extra_description = []

        if self.headers:
            extra_description.append(f"{self.headers} headers")

        return " and ".join(extra_description)
