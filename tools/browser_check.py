#!/usr/bin/env python3
"""Exercise the published static site in a real Chrome or Chromium browser."""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import mimetypes
import os
import queue
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE_ROOT = ROOT / "site"
DEFAULT_BASE_PATH = "/aidlc-v2-engine/"
EXPECTED_ASSETS = (
    "",
    "architecture.html",
    "styles.css",
    "app.js",
    "architecture.js",
    "assets/aidlc-v2-engine-icon.svg",
    "assets/aidlc-v2-engine-logo.svg",
    "assets/architecture.dot",
    "assets/architecture.drawio",
    "assets/architecture.png",
    "assets/architecture.svg",
    "assets/aws-services-architecture.drawio",
    "assets/aws-services-architecture.png",
)


class BrowserCheckError(RuntimeError):
    """Raised when the public site fails deterministic browser verification."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BrowserCheckError(message)


class StaticSiteHandler(BaseHTTPRequestHandler):
    """Serve one repository-owned site beneath the exact GitHub Pages base."""

    site_root = DEFAULT_SITE_ROOT
    base_path = DEFAULT_BASE_PATH
    requests: list[dict[str, object]] = []

    def do_HEAD(self) -> None:  # noqa: N802
        self._serve(include_body=False)

    def do_GET(self) -> None:  # noqa: N802
        self._serve(include_body=True)

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _finish(
        self,
        status: int,
        body: bytes,
        content_type: str,
        *,
        include_body: bool,
    ) -> None:
        self.requests.append(
            {
                "method": self.command,
                "path": urllib.parse.urlsplit(self.path).path,
                "status": status,
            }
        )
        self.send_response(status)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def _serve(self, *, include_body: bool) -> None:
        try:
            request_path = urllib.parse.unquote(
                urllib.parse.urlsplit(self.path).path
            )
            if request_path in {
                self.base_path,
                self.base_path.removesuffix("/"),
            }:
                relative_path = "index.html"
            elif request_path.startswith(self.base_path):
                relative_path = request_path[len(self.base_path) :]
            else:
                self._finish(
                    404,
                    b"Not found\n",
                    "text/plain; charset=utf-8",
                    include_body=include_body,
                )
                return

            candidate = (self.site_root / relative_path).resolve()
            if not candidate.is_relative_to(self.site_root) or not candidate.is_file():
                self._finish(
                    404,
                    b"Not found\n",
                    "text/plain; charset=utf-8",
                    include_body=include_body,
                )
                return
            body = candidate.read_bytes()
            content_type = (
                mimetypes.guess_type(candidate.name)[0]
                or "application/octet-stream"
            )
            if content_type.startswith("text/") or candidate.suffix in {
                ".dot",
                ".drawio",
                ".js",
                ".svg",
            }:
                content_type = f"{content_type}; charset=utf-8"
            self._finish(
                200,
                body,
                content_type,
                include_body=include_body,
            )
        except (OSError, UnicodeError):
            self._finish(
                500,
                b"Server error\n",
                "text/plain; charset=utf-8",
                include_body=include_body,
            )


@contextlib.contextmanager
def local_site(site_root: Path, base_path: str) -> Iterator[tuple[str, list[dict[str, object]]]]:
    handler = type("ConfiguredStaticSiteHandler", (StaticSiteHandler,), {})
    handler.site_root = site_root.resolve()
    handler.base_path = base_path
    handler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}{base_path}", handler.requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def request_status(url: str) -> int:
    request = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "aidlc-v2-engine-browser-check/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def request_json(url: str, method: str = "GET") -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": "aidlc-v2-engine-browser-check/1"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def find_chrome() -> str:
    candidates = (
        os.environ.get("CHROME_BIN"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    for command in (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    ):
        candidate = shutil.which(command)
        if candidate:
            return candidate
    raise BrowserCheckError(
        "Chrome or Chromium is required; set CHROME_BIN when it is not on PATH"
    )


@contextlib.contextmanager
def chrome_process() -> Iterator[tuple[subprocess.Popen[str], str, list[str]]]:
    profile_directory = Path(
        tempfile.mkdtemp(prefix="aidlc-v2-engine-browser-check-")
    )
    command = [
        find_chrome(),
        "--headless=new",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--disable-gpu",
        "--disable-sync",
        "--metrics-recording-only",
        "--no-default-browser-check",
        "--no-first-run",
        "--remote-allow-origins=*",
        "--remote-debugging-address=127.0.0.1",
        "--remote-debugging-port=0",
        f"--user-data-dir={profile_directory}",
        "--window-size=1440,1000",
        "about:blank",
    ]
    if sys.platform.startswith("linux"):
        command.insert(1, "--no-sandbox")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    output: list[str] = []
    lines: queue.Queue[str] = queue.Queue()

    def collect_output() -> None:
        if process.stdout is None:
            return
        for line in process.stdout:
            output.append(line.rstrip())
            del output[:-200]
            lines.put(line)

    collector = threading.Thread(target=collect_output, daemon=True)
    collector.start()
    websocket_url = ""
    deadline = time.monotonic() + 20
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                line = lines.get(timeout=0.1)
            except queue.Empty:
                continue
            match = re.search(r"DevTools listening on (ws://\S+)", line)
            if match:
                websocket_url = match.group(1)
                break
        if not websocket_url:
            detail = "\n".join(output[-20:])
            raise BrowserCheckError(
                "Chrome did not expose its DevTools endpoint"
                + (f":\n{detail}" if detail else "")
            )
        yield process, websocket_url, output
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        collector.join(timeout=1)
        shutil.rmtree(profile_directory, ignore_errors=True)


class WebSocketConnection:
    """Small RFC 6455 client sufficient for local Chrome DevTools traffic."""

    def __init__(self, url: str) -> None:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "ws" or not parsed.hostname or not parsed.port:
            raise BrowserCheckError(f"unsupported DevTools WebSocket URL: {url}")
        self.socket = socket.create_connection(
            (parsed.hostname, parsed.port),
            timeout=10,
        )
        self.buffer = bytearray()
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        target = parsed.path or "/"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        request = (
            f"GET {target} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port}\r\n"
            "Connection: Upgrade\r\n"
            "Upgrade: websocket\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        self.socket.sendall(request.encode("ascii"))
        response = self._read_until(b"\r\n\r\n").decode("iso-8859-1")
        status_line, *header_lines = response.split("\r\n")
        require(
            status_line.startswith("HTTP/1.1 101"),
            f"DevTools WebSocket upgrade failed: {status_line}",
        )
        headers = {}
        for line in header_lines:
            if ":" not in line:
                continue
            name, value = line.split(":", 1)
            headers[name.casefold()] = value.strip()
        expected_accept = base64.b64encode(
            hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest()
        ).decode("ascii")
        require(
            headers.get("sec-websocket-accept") == expected_accept,
            "DevTools WebSocket returned an invalid accept digest",
        )

    def _read_until(self, marker: bytes) -> bytes:
        while marker not in self.buffer:
            chunk = self.socket.recv(65536)
            if not chunk:
                raise BrowserCheckError("DevTools WebSocket closed during handshake")
            self.buffer.extend(chunk)
        end = self.buffer.index(marker) + len(marker)
        result = bytes(self.buffer[:end])
        del self.buffer[:end]
        return result

    def _read_exact(self, length: int) -> bytes:
        while len(self.buffer) < length:
            chunk = self.socket.recv(65536)
            if not chunk:
                raise BrowserCheckError("DevTools WebSocket closed unexpectedly")
            self.buffer.extend(chunk)
        result = bytes(self.buffer[:length])
        del self.buffer[:length]
        return result

    def _send_frame(self, opcode: int, payload: bytes = b"") -> None:
        first = 0x80 | opcode
        length = len(payload)
        if length < 126:
            header = bytes((first, 0x80 | length))
        elif length < 65536:
            header = bytes((first, 0x80 | 126)) + struct.pack("!H", length)
        else:
            header = bytes((first, 0x80 | 127)) + struct.pack("!Q", length)
        mask = secrets.token_bytes(4)
        masked = bytes(
            value ^ mask[index % 4] for index, value in enumerate(payload)
        )
        self.socket.sendall(header + mask + masked)

    def send_json(self, value: dict[str, Any]) -> None:
        self._send_frame(
            0x1,
            json.dumps(value, separators=(",", ":")).encode("utf-8"),
        )

    def receive_json(self, timeout: float) -> dict[str, Any]:
        self.socket.settimeout(timeout)
        fragments = bytearray()
        message_opcode: int | None = None
        while True:
            first, second = self._read_exact(2)
            final = bool(first & 0x80)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]
            mask = self._read_exact(4) if masked else b""
            payload = self._read_exact(length)
            if masked:
                payload = bytes(
                    value ^ mask[index % 4]
                    for index, value in enumerate(payload)
                )
            if opcode == 0x8:
                raise BrowserCheckError("DevTools WebSocket closed")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode in {0x1, 0x2}:
                message_opcode = opcode
                fragments = bytearray(payload)
            elif opcode == 0x0 and message_opcode is not None:
                fragments.extend(payload)
            else:
                raise BrowserCheckError(
                    f"unsupported DevTools WebSocket opcode: {opcode}"
                )
            if not final:
                continue
            require(message_opcode == 0x1, "DevTools returned a non-text message")
            return json.loads(fragments.decode("utf-8"))

    def close(self) -> None:
        with contextlib.suppress(OSError):
            self._send_frame(0x8)
        with contextlib.suppress(OSError):
            self.socket.close()


class CdpSession:
    def __init__(self, websocket_url: str) -> None:
        self.websocket = WebSocketConnection(websocket_url)
        self.next_id = 1
        self.responses: dict[int, dict[str, Any]] = {}
        self.events: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
        self.browser_exceptions: list[str] = []
        self.console_errors: list[str] = []
        self.loading_failures: list[dict[str, Any]] = []
        self.request_urls: list[str] = []
        self.responses_seen: list[dict[str, object]] = []
        self.websockets: list[str] = []

    def _record(self, message: dict[str, Any]) -> None:
        if "id" in message:
            self.responses[int(message["id"])] = message
            return
        method = message.get("method")
        if not isinstance(method, str):
            return
        params = message.get("params") or {}
        self.events[method].append(params)
        if method == "Runtime.exceptionThrown":
            details = params.get("exceptionDetails") or {}
            exception = details.get("exception") or {}
            self.browser_exceptions.append(
                exception.get("description")
                or details.get("text")
                or "unknown browser exception"
            )
        elif method == "Runtime.consoleAPICalled" and params.get("type") == "error":
            values = []
            for argument in params.get("args") or []:
                values.append(
                    str(argument.get("value") or argument.get("description") or "")
                )
            self.console_errors.append(" ".join(values))
        elif method == "Network.loadingFailed":
            self.loading_failures.append(params)
        elif method == "Network.requestWillBeSent":
            request = params.get("request") or {}
            url = request.get("url")
            if isinstance(url, str):
                self.request_urls.append(url)
        elif method == "Network.responseReceived":
            response = params.get("response") or {}
            url = response.get("url")
            status = response.get("status")
            if isinstance(url, str) and isinstance(status, (int, float)):
                self.responses_seen.append({"url": url, "status": status})
        elif method == "Network.webSocketCreated":
            url = params.get("url")
            if isinstance(url, str):
                self.websockets.append(url)

    def _receive(self, timeout: float) -> None:
        self._record(self.websocket.receive_json(timeout))

    def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 10,
    ) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        self.websocket.send_json(
            {
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )
        deadline = time.monotonic() + timeout
        while request_id not in self.responses:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BrowserCheckError(f"timed out waiting for Chrome command {method}")
            try:
                self._receive(remaining)
            except socket.timeout as error:
                raise BrowserCheckError(
                    f"timed out waiting for Chrome command {method}"
                ) from error
        response = self.responses.pop(request_id)
        if "error" in response:
            raise BrowserCheckError(
                f"Chrome command {method} failed: {response['error']}"
            )
        return response.get("result") or {}

    def discard_events(self, method: str) -> None:
        self.events[method].clear()

    def wait_event(self, method: str, *, timeout: float = 10) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while not self.events[method]:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BrowserCheckError(f"timed out waiting for Chrome event {method}")
            try:
                self._receive(remaining)
            except socket.timeout as error:
                raise BrowserCheckError(
                    f"timed out waiting for Chrome event {method}"
                ) from error
        return self.events[method].popleft()

    def evaluate(self, expression: str) -> Any:
        result = self.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
        )
        if result.get("exceptionDetails"):
            details = result["exceptionDetails"]
            exception = details.get("exception") or {}
            raise BrowserCheckError(
                exception.get("description")
                or details.get("text")
                or "browser evaluation failed"
            )
        return (result.get("result") or {}).get("value")

    def wait_for(
        self,
        expression: str,
        description: str,
        *,
        timeout: float = 10,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                value = self.evaluate(expression)
                if value:
                    return value
            except BrowserCheckError as error:
                last_error = error
            time.sleep(0.05)
        detail = f": {last_error}" if last_error else ""
        raise BrowserCheckError(f"timed out waiting for {description}{detail}")

    def navigate(self, url: str) -> None:
        self.discard_events("Page.loadEventFired")
        result = self.send("Page.navigate", {"url": url})
        require(not result.get("errorText"), f"navigation failed: {result.get('errorText')}")
        self.wait_event("Page.loadEventFired", timeout=15)
        self.wait_for(
            "document.readyState === 'complete'",
            f"{url} to reach complete ready state",
        )

    def click(self, selector: str) -> None:
        serialized = json.dumps(selector)
        clicked = self.evaluate(
            "(() => {"
            f"const element = document.querySelector({serialized});"
            "if (!element || element.disabled) return false;"
            "element.click();"
            "return true;"
            "})()"
        )
        require(bool(clicked), f"missing or disabled control: {selector}")

    def close(self) -> None:
        self.websocket.close()


def normalize_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    require(parsed.scheme in {"http", "https"}, "base URL must use HTTP or HTTPS")
    require(bool(parsed.netloc), "base URL must include a host")
    path = parsed.path or "/"
    if not path.endswith("/"):
        path += "/"
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, path, "", "")
    )


def assert_mobile_layout(session: CdpSession, page_name: str) -> None:
    session.send(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": 390,
            "height": 844,
            "deviceScaleFactor": 1,
            "mobile": True,
        },
    )
    time.sleep(0.15)
    require(
        bool(
            session.evaluate(
                "document.documentElement.scrollWidth "
                "<= document.documentElement.clientWidth + 1"
            )
        ),
        f"{page_name} overflows a 390-pixel mobile viewport",
    )
    session.send("Emulation.clearDeviceMetricsOverride")


def verify_browser(base_url: str) -> dict[str, object]:
    base_url = normalize_base_url(base_url)
    parsed_base = urllib.parse.urlsplit(base_url)
    expected_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
    base_path = parsed_base.path
    for asset in EXPECTED_ASSETS:
        url = urllib.parse.urljoin(base_url, asset)
        require(
            request_status(url) == 200,
            f"public asset did not resolve with HTTP 200: {url}",
        )

    with chrome_process() as (chrome, browser_websocket_url, chrome_output):
        devtools = urllib.parse.urlsplit(browser_websocket_url)
        devtools_origin = f"http://{devtools.hostname}:{devtools.port}"
        request_json(f"{devtools_origin}/json/version")
        target = request_json(
            f"{devtools_origin}/json/new?"
            + urllib.parse.quote("about:blank", safe=""),
            method="PUT",
        )
        session = CdpSession(target["webSocketDebuggerUrl"])
        try:
            session.send("Page.enable")
            session.send("Runtime.enable")
            session.send("Network.enable")
            session.send("Network.setCacheDisabled", {"cacheDisabled": True})

            session.navigate(base_url)
            session.wait_for(
                "document.querySelectorAll('#stage-list li').length === 6",
                "the synthetic lifecycle status",
            )
            landing = session.evaluate(
                """(() => {
                  const image = document.querySelector(
                    'img[src="assets/architecture.svg"]'
                  );
                  const links = [...document.querySelectorAll("a")].map(
                    (anchor) => ({
                      href: anchor.getAttribute("href"),
                      resolved: anchor.href,
                      text: anchor.textContent.trim(),
                    })
                  );
                  return {
                    title: document.title,
                    pathname: document.location.pathname,
                    copy: document.body.textContent,
                    imageComplete: Boolean(
                      image && image.complete && image.naturalWidth > 0
                    ),
                    imageUrl: image ? image.src : "",
                    stageCount: document.querySelectorAll("#stage-list li").length,
                    summary: document.querySelector("#stage-summary")?.textContent,
                    metrics: document.querySelector("#audit-summary")?.textContent,
                    links,
                  };
                })()"""
            )
            require(
                landing["title"]
                == "AI-DLC v2 Engine | Human-governed lifecycle automation",
                "landing page title is incorrect",
            )
            require(
                landing["pathname"] == base_path,
                "landing page did not retain the exact project base path",
            )
            require(
                "Automate AI-DLC v2. Keep authority human." in landing["copy"],
                "landing page headline is missing",
            )
            require(
                "Synthetic parser repair completed the bugfix plan"
                in landing["summary"],
                "synthetic status did not render",
            )
            require(
                "66" in landing["metrics"] and "valid" in landing["metrics"],
                "synthetic audit metrics did not render",
            )
            require(landing["imageComplete"], "landing architecture image did not load")
            require(
                urllib.parse.urlsplit(landing["imageUrl"]).path
                == f"{base_path}assets/architecture.svg",
                "landing architecture image resolved outside the Pages base",
            )
            require(
                not any(
                    isinstance(link["href"], str)
                    and link["href"].startswith("/")
                    for link in landing["links"]
                ),
                "landing page contains a root-relative link",
            )
            require(
                any(
                    link["text"] == "Explore the architecture"
                    and urllib.parse.urlsplit(link["resolved"]).path
                    == f"{base_path}architecture.html"
                    for link in landing["links"]
                ),
                "landing page architecture link does not resolve under the Pages base",
            )
            assert_mobile_layout(session, "landing page")

            architecture_url = urllib.parse.urljoin(base_url, "architecture.html")
            session.navigate(architecture_url)
            session.wait_for(
                "document.querySelectorAll('#architecture-steps li').length === 6",
                "the interactive architecture steps",
            )
            architecture = session.evaluate(
                """(() => {
                  const image = document.querySelector(
                    'img[src="assets/architecture.png"]'
                  );
                  const awsImage = document.querySelector(
                    'img[src="assets/aws-services-architecture.png"]'
                  );
                  const downloads = [...document.querySelectorAll(
                    ".download-grid a"
                  )].map((anchor) => anchor.href);
                  return {
                    title: document.title,
                    pathname: document.location.pathname,
                    heading: document.querySelector("#scenario-title")?.textContent,
                    position: document.querySelector("#step-position")?.textContent,
                    step: document.querySelector("#step-title")?.textContent,
                    imageComplete: Boolean(
                      image && image.complete && image.naturalWidth > 0
                    ),
                    awsImageComplete: Boolean(
                      awsImage && awsImage.complete && awsImage.naturalWidth > 0
                    ),
                    rootRelativeCount: [...document.querySelectorAll("a")]
                      .filter((anchor) => anchor.getAttribute("href")?.startsWith("/"))
                      .length,
                    downloads,
                  };
                })()"""
            )
            require(
                architecture["title"]
                == "AI-DLC v2 Engine | Architecture explorer",
                "architecture page title is incorrect",
            )
            require(
                architecture["pathname"]
                == f"{base_path}architecture.html",
                "architecture page did not retain the exact project base path",
            )
            require(
                architecture["heading"]
                == "Intent becomes an exact 33-stage execute/skip plan",
                "initial architecture scenario did not render",
            )
            require(
                architecture["position"] == "Step 1 of 6 · Interface",
                "initial architecture step position is incorrect",
            )
            require(
                architecture["step"] == "Capture intent",
                "initial architecture step is incorrect",
            )
            require(
                architecture["imageComplete"],
                "architecture PNG did not load in Chrome",
            )
            require(
                architecture["awsImageComplete"],
                "AWS services architecture PNG did not load in Chrome",
            )
            require(
                architecture["rootRelativeCount"] == 0,
                "architecture page contains a root-relative link",
            )
            require(
                len(architecture["downloads"]) == 6,
                "architecture download set is incomplete",
            )
            require(
                all(
                    urllib.parse.urlsplit(url).path.startswith(base_path)
                    for url in architecture["downloads"]
                ),
                "architecture download resolved outside the Pages base",
            )

            session.click("#next-step")
            session.wait_for(
                "document.querySelector('#step-position')?.textContent "
                "=== 'Step 2 of 6 · Scope router'",
                "the Next interaction",
            )
            require(
                session.evaluate(
                    "document.querySelector('#step-title')?.textContent"
                )
                == "Resolve scope",
                "Next did not advance the architecture detail",
            )
            session.click('[data-scenario="governance"]')
            session.wait_for(
                "document.querySelector('#scenario-title')?.textContent "
                "=== 'Declared work becomes a reviewed, human-governed decision'",
                "the Stage gate scenario interaction",
            )
            require(
                session.evaluate(
                    "document.querySelector('[data-scenario=\"governance\"]')"
                    "?.getAttribute('aria-selected')"
                )
                == "true",
                "Stage gate scenario did not expose selected state",
            )
            assert_mobile_layout(session, "architecture page")

            attempted_external = []
            for url in session.request_urls:
                parsed = urllib.parse.urlsplit(url)
                if parsed.scheme in {"about", "data", "blob"}:
                    continue
                origin = f"{parsed.scheme}://{parsed.netloc}"
                if origin != expected_origin or not parsed.path.startswith(base_path):
                    attempted_external.append(url)
            require(
                not attempted_external,
                f"page attempted prohibited network requests: {attempted_external}",
            )
            require(
                not session.websockets,
                f"page opened WebSocket connections: {session.websockets}",
            )
            failed_responses = [
                response
                for response in session.responses_seen
                if float(response["status"]) >= 400
            ]
            require(
                not failed_responses,
                f"browser received failed responses: {failed_responses}",
            )
            require(
                not session.loading_failures,
                f"browser loading failures: {session.loading_failures}",
            )
            require(
                not session.browser_exceptions,
                f"browser exceptions: {session.browser_exceptions}",
            )
            require(
                not session.console_errors,
                f"browser console errors: {session.console_errors}",
            )
        except Exception:
            if chrome.poll() is not None and chrome_output:
                print(
                    "Chrome output (tail):\n" + "\n".join(chrome_output[-20:]),
                    file=sys.stderr,
                )
            raise
        finally:
            session.close()
    return {
        "ok": True,
        "base_url": base_url,
        "asset_count": len(EXPECTED_ASSETS),
        "pages": ["index.html", "architecture.html"],
        "interaction_count": 2,
        "mobile_width": 390,
        "external_request_count": 0,
        "browser_exception_count": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-root",
        type=Path,
        default=DEFAULT_SITE_ROOT,
        help="Local static-site directory to serve.",
    )
    parser.add_argument(
        "--base-path",
        default=DEFAULT_BASE_PATH,
        help="Local project base path, including leading and trailing slash.",
    )
    parser.add_argument(
        "--base-url",
        help="Verify an already-published site instead of starting a local server.",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.base_url:
            result = verify_browser(args.base_url)
        else:
            base_path = args.base_path
            require(
                base_path.startswith("/") and base_path.endswith("/"),
                "base path must start and end with '/'",
            )
            site_root = args.site_root.resolve()
            require(
                (site_root / "index.html").is_file(),
                f"site root has no index.html: {site_root}",
            )
            with local_site(site_root, base_path) as (base_url, requests):
                result = verify_browser(base_url)
                failed = [
                    request
                    for request in requests
                    if int(request["status"]) >= 400
                ]
                require(
                    not failed,
                    f"local static server returned failed responses: {failed}",
                )
                result["local_request_count"] = len(requests)
    except (
        BrowserCheckError,
        json.JSONDecodeError,
        OSError,
        UnicodeError,
        urllib.error.URLError,
    ) as error:
        result = {"ok": False, "error": str(error)}
    json.dump(
        result,
        sys.stdout,
        indent=2 if args.pretty else None,
        sort_keys=True,
        separators=None if args.pretty else (",", ":"),
    )
    sys.stdout.write("\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
