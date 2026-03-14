
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Optional


_URL_RE = re.compile(r"^(https?://|git@)")

def is_url(target: str) -> bool:
    return bool(_URL_RE.match(target.strip()))

def _run(cmd: list[str], *, cwd: Optional[Path] = None) -> None:
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if p.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd[:3])} ...\n"
            f"stdout:\n{p.stdout}\n"
            f"stderr:\n{p.stderr}\n"
        )
    
def _looks_like_sha(ref: str) -> bool:
    r = ref.strip()
    return bool(re.fullmatch(r"[0-9a-fA-F]{7,40}", r))

def _build_authed_url(url: str, token: Optional[str]) -> str:
    # Example:
    # input: url="https://github.com/org/repo.git", token="MYTOKEN"
    # output: https://MYTOKEN@github.com/org/repo.git
    if not token:
        return url
    u = url.strip()
    if u.startswith("https://"):
        return "https://" + token + "@" + u[len("https://") :]
    if u.startswith("http://"):
        return "http://" + token + "@" + u[len("http://") :]
    return u

@dataclass
class ResolvedTarget:
    path: Path
    cleanup_dir: Optional[Path] = None  # remove after scan unless keep=True

def resolve_target_to_path(
    target: str,
    *,
    ref: Optional[str] = None,
    depth: int = 1,
    token: Optional[str] = None,
    keep: bool = False,
    workdir: Optional[Path] = None,
) -> ResolvedTarget:
    t = target.strip()

    # Local directory
    if not is_url(t):
        p = Path(t).expanduser().resolve()
        if not p.exists() or not p.is_dir():
            raise ValueError(f"Local path does not exist or is not a directory: {p}")
        return ResolvedTarget(path=p)

    # URL → clone to temp
    if workdir:
        base = workdir.expanduser().resolve()
        base.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix="pipescope-", dir=str(base)))
    else:
        tmp = Path(tempfile.mkdtemp(prefix="pipescope-"))

    repo_dir = tmp / "repo"
    authed_url = _build_authed_url(t, token)

    cmd = ["git", "clone", "--depth", str(depth)]
    if ref and not _looks_like_sha(ref):
        cmd += ["--branch", ref]
    cmd += [authed_url, str(repo_dir)]

    try:
        _run(cmd)
        if ref and _looks_like_sha(ref):
            _run(["git", "checkout", ref], cwd=repo_dir)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise

    if keep:
        return ResolvedTarget(path=repo_dir)
    return ResolvedTarget(path=repo_dir, cleanup_dir=tmp)

def cleanup_resolved_target(resolved: ResolvedTarget) -> None:
    if resolved.cleanup_dir:
        shutil.rmtree(resolved.cleanup_dir, ignore_errors=True)


