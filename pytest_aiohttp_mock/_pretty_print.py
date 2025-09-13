from pytest_aiohttp_mock._request import AioHttpRequest
from pytest_aiohttp_mock._request_matcher import _RequestMatcher


class RequestDescription:
    def __init__(
        self,
        request: AioHttpRequest,
        matchers: list[_RequestMatcher],
    ):
        self.request = request

        self.expected_headers = {
            # httpx uses lower cased header names as internal key
            header.lower().encode()
            for matcher in matchers
            if matcher.headers
            for header in matcher.headers
        }

    def __str__(self) -> str:
        request_description = f"{self.request.method} request on {self.request.url}"
        if extra_description := self.extra_request_description():
            request_description += f" with {extra_description}"
        return request_description

    def extra_request_description(self) -> str:
        extra_description = []

        if self.expected_headers:
            extra_description.append(f"{self.request.headers} headers")

        # if self.expect_body:
        #     extra_description.append(f"{self.request.body} body")

        # if self.expected_extensions:
        #     present_extensions = {
        #         name: value
        #         for name, value in self.request.extensions.items()
        #         if name in self.expected_extensions
        #     }
        #     extra_description.append(f"{present_extensions} extensions")

        return " and ".join(extra_description)
