"""Historical element sets from Space-Track.org.

CelesTrak serves only *current* elements, and its historical archive stops at
2004 by law (US PL 108-136 Sec. 913). Space-Track's ``gp_history`` class is the
only authoritative source of past element sets, and it needs a free account.

Two experiments depend on this:

* Element-set ageing. Measuring how prediction degrades with epoch age requires
  two element sets for the same object at different epochs, with the fresher one
  serving as truth. One catalogue snapshot cannot provide that.
* Retrospective evaluation. Scoring a planner over a past window should use the
  elements that were *current then*, not today's propagated backwards.

Credentials
-----------
Never written to the repository. Supply them by environment variable::

    export SPACETRACK_USER='you@example.com'
    export SPACETRACK_PASS='...'

or in a git-ignored ``.spacetrack`` file at the project root, as two lines
(username, then password), or as ``user=...`` / ``pass=...`` pairs.

Rate limits
-----------
Space-Track asks for fewer than 30 requests per minute and 300 per hour, and
asks that clients batch queries rather than looping per object. This client
enforces the per-minute limit itself and caches every response on disk, so a
re-run of an experiment costs nothing.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Sequence, Tuple

from .paths import SPACETRACK_CACHE_DIR
from .tle import TleRecord, parse_tle_text

BASE = "https://www.space-track.org"
LOGIN_URL = f"{BASE}/ajaxauth/login"
QUERY_URL = f"{BASE}/basicspacedata/query"

DEFAULT_CACHE = SPACETRACK_CACHE_DIR
#: Space-Track asks for <30 requests/min; stay well under it.
MIN_INTERVAL_S = 2.5


class SpaceTrackError(RuntimeError):
    pass


class CredentialsMissing(SpaceTrackError):
    """Raised when no usable credentials were found."""


#: Files searched for credentials, in order. All are git-ignored.
CRED_FILES = (".env.local", ".env", ".spacetrack")

_USER_KEYS = ("SPACETRACK_USER", "SPACETRACK_USERNAME", "SPACETRACK_IDENTITY")
_PASS_KEYS = ("SPACETRACK_PASS", "SPACETRACK_PASSWORD")


def _clean(value: str) -> str:
    """Strip surrounding quotes and trailing comments from a dotenv value."""
    v = value.strip()
    if v[:1] in ("'", '"') and v[-1:] == v[:1] and len(v) >= 2:
        return v[1:-1]
    return v.split(" #", 1)[0].strip()


def _parse_env_file(path: str) -> Dict[str, str]:
    """Read KEY=VALUE pairs, tolerating the shapes people actually write.

    Accepts ``KEY=v``, ``export KEY=v`` and the PowerShell ``$env:KEY = v``
    form, since a Windows user setting this up will naturally paste the latter.
    """
    out: Dict[str, str] = {}
    with open(path, encoding="utf-8-sig") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            for prefix in ("export ", "set ", "$env:", "env:"):
                if key.lower().startswith(prefix.lower()):
                    key = key[len(prefix):].strip()
            out[key.strip().upper()] = _clean(value)
    return out


def load_credentials(root: str = ".") -> Tuple[str, str]:
    """Find credentials in the environment or a git-ignored credentials file."""
    user = next((os.environ[k] for k in _USER_KEYS if os.environ.get(k)), None)
    pwd = next((os.environ[k] for k in _PASS_KEYS if os.environ.get(k)), None)
    if user and pwd:
        return user, pwd

    # Search the given directory and its ancestors, plus the package's own
    # project root. Experiments run from experiments/, so a credentials file
    # sitting at the project root must still be found.
    seen, search = set(), []
    here = os.path.abspath(root)
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for base in (here, pkg_root):
        d = base
        while d and d not in seen:
            seen.add(d)
            search.append(d)
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent

    for directory, name in ((d, n) for d in search for n in CRED_FILES):
        path = os.path.join(directory, name)
        if not os.path.exists(path):
            continue
        env = _parse_env_file(path)
        user = next((env[k] for k in _USER_KEYS if env.get(k)), None)
        pwd = next((env[k] for k in _PASS_KEYS if env.get(k)), None)
        if user and pwd:
            return user, pwd
        # Bare two-line form: username, then password.
        if name == ".spacetrack":
            with open(path, encoding="utf-8") as fh:
                lines = [ln.strip() for ln in fh
                         if ln.strip() and not ln.startswith("#")
                         and "=" not in ln]
            if len(lines) >= 2:
                return lines[0], lines[1]

    raise CredentialsMissing(
        "No Space-Track credentials. Set SPACETRACK_USER and SPACETRACK_PASS, "
        f"or put them in one of {', '.join(CRED_FILES)}. "
        "Register free at https://www.space-track.org/auth/createAccount")


class SpaceTrack:
    """Minimal authenticated client for the ``gp_history`` class."""

    def __init__(self, user: Optional[str] = None, password: Optional[str] = None,
                 cache_dir: str = DEFAULT_CACHE, root: str = ".",
                 verbose: bool = True):
        if user is None or password is None:
            user, password = load_credentials(root)
        self._user = user
        self._password = password
        self.cache_dir = cache_dir
        self.verbose = verbose
        self._opener: Optional[urllib.request.OpenerDirector] = None
        self._last_request = 0.0
        os.makedirs(self.cache_dir, exist_ok=True)

    # -- plumbing ---------------------------------------------------------
    def _throttle(self) -> None:
        wait = MIN_INTERVAL_S - (time.time() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.time()

    def login(self) -> None:
        if self._opener is not None:
            return
        cj = __import__("http.cookiejar", fromlist=["CookieJar"]).CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj))
        data = urllib.parse.urlencode(
            {"identity": self._user, "password": self._password}).encode()
        self._throttle()
        try:
            with opener.open(LOGIN_URL, data, timeout=60) as r:
                body = r.read().decode("utf-8", "replace")
        except Exception as exc:                       # noqa: BLE001
            raise SpaceTrackError(f"login request failed: {exc}") from None
        # A failed login returns 200 with a JSON error body, not an HTTP error.
        if "failed" in body.lower() or "invalid" in body.lower():
            raise SpaceTrackError(
                "Space-Track rejected the credentials (check user/password).")
        self._opener = opener
        if self.verbose:
            print("  [space-track] authenticated")

    def _cache_path(self, query: str) -> str:
        h = hashlib.sha256(query.encode()).hexdigest()[:24]
        return os.path.join(self.cache_dir, f"st-{h}.tle")

    def query(self, path: str, use_cache: bool = True) -> str:
        """Run a raw query path and return the response body."""
        cache = self._cache_path(path)
        if use_cache and os.path.exists(cache):
            with open(cache, encoding="utf-8") as fh:
                return fh.read()
        self.login()
        # Space-Track predicates contain spaces ("orderby/EPOCH asc"), which
        # urllib refuses to send raw. Encode them but keep the path separators.
        url = f"{QUERY_URL}/{urllib.parse.quote(path, safe='/,-:=')}"
        self._throttle()
        assert self._opener is not None
        try:
            with self._opener.open(url, timeout=180) as r:
                body = r.read().decode("utf-8", "replace")
        except Exception as exc:                       # noqa: BLE001
            raise SpaceTrackError(f"query failed ({path[:80]}): {exc}") from None
        with open(cache, "w", encoding="utf-8") as fh:
            fh.write(body)
        return body

    # -- products ---------------------------------------------------------
    def gp_history(self, norad_ids: Sequence[int], start: dt.date, end: dt.date,
                   ) -> Dict[int, List[TleRecord]]:
        """Every element set published for these objects in ``[start, end]``.

        Objects are batched into one query (Space-Track explicitly asks clients
        not to loop one request per object).
        """
        ids = ",".join(str(int(n)) for n in sorted(set(norad_ids)))
        path = (f"class/gp_history/NORAD_CAT_ID/{ids}"
                f"/EPOCH/{start.isoformat()}--{end.isoformat()}"
                f"/orderby/NORAD_CAT_ID,EPOCH asc/format/tle")
        body = self.query(path)
        recs = parse_tle_text(_pair_to_three_line(body), source="space-track")
        out: Dict[int, List[TleRecord]] = {}
        for r in recs:
            out.setdefault(r.norad_id, []).append(r)
        for v in out.values():
            v.sort(key=lambda r: r.epoch)
        if self.verbose:
            n = sum(len(v) for v in out.values())
            print(f"  [space-track] {n} element sets for {len(out)} objects "
                  f"({start} .. {end})")
        return out

    def latest_before(self, norad_ids: Sequence[int], when: dt.datetime,
                      lookback_days: int = 30) -> Dict[int, TleRecord]:
        """The element set that was current for each object at ``when``.

        This is what a planner would actually have held on that date, and using
        it removes the back-propagation error from a retrospective evaluation.
        """
        start = (when - dt.timedelta(days=lookback_days)).date()
        hist = self.gp_history(norad_ids, start, when.date())
        out: Dict[int, TleRecord] = {}
        for nid, recs in hist.items():
            usable = [r for r in recs if r.epoch <= when]
            if usable:
                out[nid] = usable[-1]
        return out


def _pair_to_three_line(body: str) -> str:
    """Space-Track ``format/tle`` returns bare 2-line pairs; add a name line.

    Our parser expects the 3-line form. The NORAD id is recoverable from line 1,
    so a synthetic name loses nothing that matters downstream.
    """
    lines = [ln.rstrip() for ln in body.splitlines() if ln.strip()]
    out: List[str] = []
    i = 0
    while i + 1 < len(lines):
        l1, l2 = lines[i], lines[i + 1]
        if l1.startswith("1 ") and l2.startswith("2 "):
            out += [f"NORAD {l1[2:7].strip()}", l1, l2]
            i += 2
        else:
            i += 1
    return "\n".join(out)


def available(root: str = ".") -> bool:
    """True when credentials are present, without contacting the service."""
    try:
        load_credentials(root)
        return True
    except CredentialsMissing:
        return False
