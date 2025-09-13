# Inspired by pytest_httpx

import copy
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Any, NoReturn

import aiohttp
import orjson
from aiohttp.typedefs import LooseHeaders
from multidict import CIMultiDict, CIMultiDictProxy, MultiDict, MultiDictProxy

from pytest_aiohttp_mock._options import _AioHttpMockOptions
from pytest_aiohttp_mock._pretty_print import RequestDescription
from pytest_aiohttp_mock._request import AioHttpRequest
from pytest_aiohttp_mock._request_matcher import _RequestMatcher

HeaderTypes = CIMultiDict[str] | Mapping[str, str] | Sequence[tuple[str, str]]


class NotFoundError(Exception): ...


def _prepare_headers(headers: LooseHeaders | None) -> CIMultiDict[str]:
    """Add default headers and transform it to CIMultiDict"""
    # Convert headers to MultiDict
    result = CIMultiDict({})
    if headers:
        if not isinstance(headers, MultiDictProxy | MultiDict):
            headers = CIMultiDict(headers)
        added_names: set[str] = set()
        for key, value in headers.items():
            if key in added_names:
                result.add(key, value)
            else:
                result[key] = value
                added_names.add(key)
    return result


class AioHttpMock:
    """Inspired by httpx_mock"""

    def __init__(self, options: _AioHttpMockOptions) -> None:
        self._options = options
        self._requests: list[AioHttpRequest] = []
        self._callbacks: list[
            tuple[
                _RequestMatcher,
                Callable[
                    [AioHttpRequest],
                    MockedClientResponse | Awaitable[MockedClientResponse | None] | None,
                ],
            ]
        ] = []
        self._requests_not_matched: list[AioHttpRequest] = []

    def add_response(
        self,
        status_code: int = 200,
        http_version: str = "HTTP/1.1",
        headers: HeaderTypes | None = None,
        content: bytes | None = None,
        text: str | None = None,
        html: str | None = None,
        stream: Any = None,
        json: Any = None,
        **matchers: Any,
    ) -> None:
        """
        Mock the response that will be sent if a request match.

        :param status_code: HTTP status code of the response to send. Default to 200 (OK).
        :param http_version: HTTP protocol version of the response to send. Default to HTTP/1.1
        :param headers: HTTP headers of the response to send. Default to no headers.
        :param content: HTTP body of the response (as bytes).
        :param text: HTTP body of the response (as string).
        :param html: HTTP body of the response (as HTML string content).
        :param stream: HTTP body of the response (as httpx.SyncByteStream or httpx.AsyncByteStream) as stream content.
        :param json: HTTP body of the response (if JSON should be used as content type) if data is not provided.
        :param url: Full URL identifying the request(s) to match.
        Can be a str, a re.Pattern instance or a httpx.URL instance.
        :param method: HTTP method identifying the request(s) to match.
        :param proxy_url: Full proxy URL identifying the request(s) to match.
        Can be a str, a re.Pattern instance or a httpx.URL instance.
        :param match_headers: HTTP headers identifying the request(s) to match. Must be a dictionary.
        :param match_content: Full HTTP body identifying the request(s) to match. Must be bytes.
        :param match_json: JSON decoded HTTP body identifying the request(s) to match. Must be JSON encodable.
        :param match_data: Multipart data (excluding files) identifying the request(s) to match. Must be a dictionary.
        :param match_files: Multipart files identifying the request(s) to match. Refer to httpx documentation for more information on supported values: https://www.python-httpx.org/advanced/clients/#multipart-file-encoding
        :param is_optional: True will mark this response as optional, False will expect a request matching it. Must be a boolean. Default to the opposite of assert_all_responses_were_requested option value (itself defaulting to True, meaning this parameter default to False).
        :param is_reusable: True will allow re-using this response even if it already matched, False prevent re-using it. Must be a boolean. Default to the can_send_already_matched_responses option value (itself defaulting to False).
        """  # noqa: E501

        json = copy.deepcopy(json) if json is not None else None

        if text is not None:
            content = text.encode()
        elif json is not None:
            content = orjson.dumps(json)
        elif html is not None:
            content = html.encode()
        elif stream is not None:
            raise NotImplementedError("Not yet implemented")

        def response_callback(request: AioHttpRequest) -> "MockedClientResponse":
            return MockedClientResponse(
                status=status_code,
                raw_content=content or b"",
                request_info=aiohttp.RequestInfo(
                    request.URL,
                    request.method,
                    request.ci_headers,
                    request.URL,
                ),
                headers=dict(headers) if headers else None,
                # extensions={"http_version": http_version.encode("ascii")},
            )

        self.add_callback(response_callback, **matchers)

    def add_callback(
        self,
        callback: Callable[
            [AioHttpRequest],
            "MockedClientResponse | Awaitable[MockedClientResponse | None] | None",
        ],
        **matchers: Any,
    ) -> None:
        """
        Mock the action that will take place if a request match.

        :param callback: The callable that will be called upon reception of the matched request.
        It must expect one parameter, the received httpx.Request and should return a httpx.Response.
        :param url: Full URL identifying the request(s) to match.
        Can be a str, a re.Pattern instance or a httpx.URL instance.
        :param method: HTTP method identifying the request(s) to match.
        :param proxy_url: Full proxy URL identifying the request(s) to match.
        Can be a str, a re.Pattern instance or a httpx.URL instance.
        :param match_headers: HTTP headers identifying the request(s) to match. Must be a dictionary.
        :param match_content: Full HTTP body identifying the request(s) to match. Must be bytes.
        :param match_json: JSON decoded HTTP body identifying the request(s) to match. Must be JSON encodable.
        :param match_data: Multipart data (excluding files) identifying the request(s) to match. Must be a dictionary.
        :param match_files: Multipart files identifying the request(s) to match. Refer to httpx documentation for more information on supported values: https://www.python-httpx.org/advanced/clients/#multipart-file-encoding
        :param match_extensions: Extensions identifying the request(s) to match. Must be a dictionary.
        :param is_optional: True will mark this callback as optional, False will expect a request matching it. Must be a boolean. Default to the opposite of assert_all_responses_were_requested option value (itself defaulting to True, meaning this parameter default to False).
        :param is_reusable: True will allow re-using this callback even if it already matched, False prevent re-using it. Must be a boolean. Default to the can_send_already_matched_responses option value (itself defaulting to False).
        """  # noqa: E501
        self._callbacks.append((_RequestMatcher(self._options, **matchers), callback))

    def _get_callback(
        self,
        request: AioHttpRequest,
    ) -> (
        Callable[
            [AioHttpRequest],
            "MockedClientResponse | Awaitable[MockedClientResponse | None] | None",
        ]
        | None
    ):
        callbacks = [
            (matcher, callback)  #
            for matcher, callback in self._callbacks
            if matcher.match(request)
        ]

        # No callback match this request
        if not callbacks:
            return None

        matcher = callback = None
        # Callbacks match this request
        for matcher, callback in callbacks:
            # Return the first not yet called
            if not matcher.nb_calls:
                matcher.nb_calls += 1
                return callback

        # Or the last registered (if it can be reused)
        if matcher and matcher.is_reusable:
            matcher.nb_calls += 1
            return callback

        # All callbacks have already been matched and last registered cannot be reused
        return None

    def _handle_request(
        self,
        request: AioHttpRequest,
    ) -> "MockedClientResponse":
        # Store the content in request for future matching
        self._requests.append(request)

        callback = self._get_callback(request)
        if callback:
            response = callback(request)

            if response:
                return response  # pyright: ignore

        self._request_not_matched(request)

    def _request_not_matched(
        self,
        request: AioHttpRequest,
    ) -> NoReturn:
        self._requests_not_matched.append(request)
        raise NotFoundError(
            self._explain_that_no_response_was_found(request),
            # request=request,
        )

    def _explain_that_no_response_was_found(
        self,
        request: AioHttpRequest,
    ) -> str:
        matchers = [matcher for matcher, _ in self._callbacks]

        message = f"No response can be found for {RequestDescription(request, matchers)}"

        already_matched = []
        unmatched = []
        for matcher in matchers:
            if matcher.nb_calls:
                already_matched.append(matcher)
            else:
                unmatched.append(matcher)

        matchers_description = "\n".join(
            [f"- {matcher}" for matcher in unmatched + already_matched],
        )
        if matchers_description:
            message += f" amongst:\n{matchers_description}"
            # If we could not find a response, but we have already matched responses
            # it might be that user is expecting one of those responses to be reused
            if any(not matcher.is_reusable for matcher in already_matched):
                message += (
                    "\n\nIf you wanted to reuse an already matched response instead of registering it again"
                )

        return message

    def reset(self) -> None:
        self._requests.clear()
        self._callbacks.clear()
        self._requests_not_matched.clear()

    def _assert_options(self) -> None:
        callbacks_not_executed = [matcher for matcher, _ in self._callbacks if matcher.should_have_matched()]
        matchers_description = "\n".join(
            [f"- {matcher}" for matcher in callbacks_not_executed],
        )

        assert not callbacks_not_executed, (
            f"The following responses are mocked but not requested:\n{matchers_description}\n\n"
            # "If this is on purpose, refer to https://github.com/Colin-b/pytest_httpx/blob/master/README.md#allow-to-register-more-responses-than-what-will-be-requested"
        )

        if self._options.assert_all_requests_were_expected:
            requests_description = "\n".join(
                [f"- {request.method} request on {request.url}" for request in self._requests_not_matched],
            )
            assert not self._requests_not_matched, (
                f"The following requests were not expected:\n{requests_description}\n\n"
                # "If this is on purpose, refer to https://github.com/Colin-b/pytest_httpx/blob/master/README.md#allow-to-not-register-responses-for-every-request"
            )


@dataclass
class MockedClientResponse:
    request_info: aiohttp.RequestInfo

    status: int
    raw_content: bytes
    cookies: SimpleCookie | None = None

    # optional error reason
    reason: str | None = None
    headers: dict[str, str] | None = None

    @property
    def ok(self) -> bool:
        return self.status < 400

    def raise_for_status(self) -> None:
        if not self.ok:
            assert self.reason is not None

            raise aiohttp.ClientResponseError(
                self.request_info,
                (),
                status=self.status,
                message=self.reason,
                headers=CIMultiDictProxy(CIMultiDict(self.headers)),
            )

    @property
    def url(self):
        return self.request_info.url

    @property
    async def content(self):
        return self.raw_content

    async def read(self) -> bytes:
        return self.raw_content

    async def text(self, encoding: str = "UTF8", errors: str = "strict") -> str:
        return self.raw_content.decode(encoding=encoding, errors=errors)

    async def json(self) -> Any:
        return orjson.loads(self.raw_content)

    @property
    def raw_headers(self) -> tuple[tuple[bytes, bytes], ...]:
        return (
            tuple(
                [(key.encode(), value.encode()) for key, value in self.headers.items()],
            )
            if self.headers
            else ()
        )
