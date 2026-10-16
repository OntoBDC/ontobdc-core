import sys
import urllib.error
import urllib.request
from typing import ClassVar, List, Optional

from ontobdc.container.domain.port.access import RemoteAccessError, RemoteAccessProbePort


class UrllibRemoteAccessProbe(RemoteAccessProbePort):
    """
    Asks the remote container, with a ``HEAD`` request, whether it can be
    accessed. The token, when there is one, goes as a bearer token.
    """

    TIMEOUT_SECONDS: ClassVar[float] = 30.0

    def probe(self, url: str, api_token: Optional[str] = None) -> None:
        headers = {"Accept": "text/turtle"}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

        request = urllib.request.Request(url, method="HEAD", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.TIMEOUT_SECONDS):
                return
        except urllib.error.HTTPError as error:
            raise RemoteAccessError(
                f"The remote container answered HTTP {error.code} ({error.reason}) at {url}."
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise RemoteAccessError(
                f"The remote container could not be reached at {url}: {error}"
            ) from error


class PyodideRemoteAccessProbe(RemoteAccessProbePort):
    """
    Placeholder for the browser: the standard library has no sockets in
    Pyodide, so the access cannot be probed there yet.
    """

    def probe(self, url: str, api_token: Optional[str] = None) -> None:
        raise RemoteAccessError("Probing the remote access is not implemented in Pyodide yet.")


class RemoteAccessProbe:
    """
    Resolves the access probe for the current runtime and uses it to find
    an address, among those published, that answers.
    """

    @staticmethod
    def for_runtime() -> RemoteAccessProbePort:
        if sys.platform == "emscripten":
            return PyodideRemoteAccessProbe()

        return UrllibRemoteAccessProbe()

    @classmethod
    def probe_any_address(cls, addresses: List[str], api_token: Optional[str] = None) -> None:
        """
        Succeeds as soon as one of the addresses answers; raises only when
        none does, telling why each one failed.
        """
        probe: RemoteAccessProbePort = cls.for_runtime()
        failures: List[str] = []
        address: str
        for address in addresses:
            try:
                probe.probe(address, api_token)
                return
            except RemoteAccessError as error:
                failures.append(str(error))

        raise RemoteAccessError(
            " ".join(failures) if failures else "The remote.ttl publishes no address to access."
        )
