"""Fetch readable, public reference pages for faculty-reviewed quiz drafts."""

from html.parser import HTMLParser
from http.client import HTTPConnection, HTTPSConnection, HTTPException as HTTPProtocolError
from io import BytesIO
from ipaddress import ip_address
import socket
import ssl
from urllib.parse import urljoin, urlsplit

from pypdf import PdfReader


MAX_PAGE_BYTES = 1_500_000
MAX_PAGE_CHARS = 10_000
BLOCKED_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header"}


class ReferenceFetchError(ValueError):
    pass


class _ReadableHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in self.tags:
            self.tags = self.tags[:len(self.tags) - 1 - self.tags[::-1].index(tag)]

    def handle_data(self, data):
        if not any(tag in BLOCKED_TAGS for tag in self.tags):
            text = data.strip()
            if text:
                self.parts.append(text)


class _PinnedHTTPSConnection(HTTPSConnection):
    def __init__(self, hostname: str, address: str, port: int):
        super().__init__(hostname, port, timeout=7, context=ssl.create_default_context())
        self.resolved_address = address

    def connect(self):
        self.sock = socket.create_connection((self.resolved_address, self.port), timeout=7)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


def _public_address(hostname: str, port: int) -> str:
    try:
        answers = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        addresses = {answer[4][0] for answer in answers}
    except OSError as error:
        raise ReferenceFetchError("The reference website could not be resolved.") from error
    if not addresses or any(not ip_address(address).is_global for address in addresses):
        raise ReferenceFetchError("Reference links must resolve only to public websites.")
    return sorted(addresses)[0]


def _read_response(data: bytes, content_type: str, charset: str) -> str:
    if content_type == "application/pdf":
        try:
            text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages[:20])
        except (ValueError, KeyError, OSError) as error:
            raise ReferenceFetchError("The linked PDF could not be read.") from error
    elif content_type in {"text/html", "application/xhtml+xml"}:
        parser = _ReadableHTML()
        try:
            decoded = data.decode(charset, errors="replace")
        except LookupError:
            decoded = data.decode("utf-8", errors="replace")
        parser.feed(decoded)
        text = " ".join(parser.parts)
    elif content_type == "text/plain":
        try:
            text = data.decode(charset, errors="replace")
        except LookupError:
            text = data.decode("utf-8", errors="replace")
    else:
        raise ReferenceFetchError("The reference must link to an HTML, text, or PDF page.")
    text = " ".join(text.split())
    if len(text) < 80:
        raise ReferenceFetchError("The reference page has too little readable text for quiz generation.")
    return text[:MAX_PAGE_CHARS]


def fetch_reference_text(url: str) -> str:
    """Fetch at most three redirects, pinning every connection to a checked public IP."""
    if len(url) > 2048:
        raise ReferenceFetchError("The reference URL is too long.")
    current = url
    for _ in range(4):
        if len(current) > 2048:
            raise ReferenceFetchError("The reference redirect URL is too long.")
        try:
            parsed = urlsplit(current)
        except ValueError as error:
            raise ReferenceFetchError("The reference URL is invalid.") from error
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ReferenceFetchError("Use a public HTTP or HTTPS reference URL.")
        try:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError as error:
            raise ReferenceFetchError("The reference URL has an invalid port.") from error
        if port != (443 if parsed.scheme == "https" else 80):
            raise ReferenceFetchError("Reference URLs must use the standard HTTP or HTTPS port.")
        address = _public_address(parsed.hostname, port)
        connection = (_PinnedHTTPSConnection(parsed.hostname, address, port) if parsed.scheme == "https"
                      else HTTPConnection(address, port, timeout=7))
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        try:
            connection.request("GET", path, headers={
                "Host": parsed.hostname, "User-Agent": "LearnSync/1.0 (faculty reference reader)",
                "Accept": "text/html, text/plain, application/pdf", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise ReferenceFetchError("The reference redirected without a destination.")
                current = urljoin(current, location)
                continue
            if response.status != 200:
                raise ReferenceFetchError(f"The reference website returned HTTP {response.status}.")
            try:
                if int(response.getheader("Content-Length") or 0) > MAX_PAGE_BYTES:
                    raise ReferenceFetchError("The reference page is too large to read.")
            except ValueError as error:
                raise ReferenceFetchError("The reference returned an invalid response length.") from error
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise ReferenceFetchError("The reference website sent unsupported compressed content.")
            data = response.read(MAX_PAGE_BYTES + 1)
            if len(data) > MAX_PAGE_BYTES:
                raise ReferenceFetchError("The reference page is too large to read.")
            content_type = response.headers.get_content_type().lower()
            charset = response.headers.get_content_charset("utf-8")
            return _read_response(data, content_type, charset)
        except (OSError, HTTPProtocolError) as error:
            raise ReferenceFetchError("The reference website could not be reached securely.") from error
        finally:
            connection.close()
    raise ReferenceFetchError("The reference redirected too many times.")
