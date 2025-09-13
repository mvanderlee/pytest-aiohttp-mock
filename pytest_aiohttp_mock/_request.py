from dataclasses import dataclass
from typing import Any

import orjson
import yarl
from aiohttp.typedefs import LooseCookies, LooseHeaders, Query
from multidict import CIMultiDict, CIMultiDictProxy


@dataclass
class AioHttpRequest:
    method: str
    url: str | yarl.URL
    params: Query = None
    data: Any = None
    json: Any = None
    cookies: LooseCookies | None = None
    headers: LooseHeaders | None = None

    @property
    def URL(self) -> yarl.URL:  # noqa: N802
        return yarl.URL(self.url) if isinstance(self.url, str) else self.url

    @property
    def ci_headers(self) -> CIMultiDictProxy[str]:
        return CIMultiDictProxy(CIMultiDict(self.headers))

    @property
    def body(self) -> bytes | str:
        if self.json:
            return orjson.dumps(self.json)
        else:
            return str(self.data) or ""
