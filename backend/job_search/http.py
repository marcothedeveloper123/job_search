"""HTTP wrapper utilities for Job Search API client."""

from typing import Optional

import requests

URL = "http://localhost:8000"


def _make_request(method: str, path: str, timeout: int, error_code: Optional[str], **kwargs) -> dict:
    """Generic request with error handling."""
    try:
        resp = getattr(requests, method)(f"{URL}{path}", timeout=timeout, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError:
        body = resp.text[:200] if resp.text else "(empty)"
        err = {"status": "error", "error": f"Server returned {resp.status_code}: {body}"}
        if error_code:
            err["code"] = error_code
        return err
    except requests.exceptions.JSONDecodeError:
        body = resp.text[:200] if resp.text else "(empty)"
        err = {"status": "error", "error": f"Invalid response ({resp.status_code}): {body}"}
        if error_code:
            err["code"] = error_code
        return err
    except requests.RequestException as e:
        err = {"status": "error", "error": str(e)}
        if error_code:
            err["code"] = error_code
        return err


def get(path: str, timeout: int = 10, error_code: Optional[str] = None, **kwargs) -> dict:
    return _make_request("get", path, timeout, error_code, **kwargs)


def post(path: str, timeout: int = 10, error_code: Optional[str] = None, **kwargs) -> dict:
    return _make_request("post", path, timeout, error_code, **kwargs)


def put(path: str, timeout: int = 10, error_code: Optional[str] = None, **kwargs) -> dict:
    return _make_request("put", path, timeout, error_code, **kwargs)


def patch(path: str, timeout: int = 10, error_code: Optional[str] = None, **kwargs) -> dict:
    return _make_request("patch", path, timeout, error_code, **kwargs)


def delete(path: str, timeout: int = 10, error_code: Optional[str] = None, **kwargs) -> dict:
    return _make_request("delete", path, timeout, error_code, **kwargs)
