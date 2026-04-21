"""Sandbox lifecycle manager for the Claw Engine.

Builds, runs, and tears down isolated Docker containers that execute
analysis scripts against mounted datasets.  Falls back to local
subprocess execution when the Docker SDK is unavailable.
"""

from __future__ import annotations

import io
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Docker SDK import
# ---------------------------------------------------------------------------
try:
    import docker
    from docker.errors import BuildError, ContainerError, ImageNotFound

    _DOCKER_AVAILABLE = True
except ImportError:
    _DOCKER_AVAILABLE = False
    logger.warning(
        "docker SDK is not installed – only local sandbox execution "
        "(run_sandbox_local) is available."
    )

# Path to the Dockerfile and entrypoint that live next to this module.
_MODULE_DIR = Path(__file__).resolve().parent
_DOCKERFILE_PATH = _MODULE_DIR / "Dockerfile"
_ENTRYPOINT_PATH = _MODULE_DIR / "entrypoint.sh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_allowlist(allowlist_path: str) -> list[str]:
    """Return a sorted, deduplicated list of packages from *allowlist_path*.

    Blank lines and lines starting with ``#`` are ignored.
    """
    packages: list[str] = []
    with open(allowlist_path, encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if line and not line.startswith("#"):
                packages.append(line)
    return sorted(set(packages))


def _generate_requirements(allowlist_path: str, dest: Path) -> None:
    """Write a pip ``requirements.txt`` derived from the allowlist."""
    packages = _parse_allowlist(allowlist_path)
    dest.write_text("\n".join(packages) + "\n", encoding="utf-8")
    logger.debug("Generated %s with %d packages", dest, len(packages))


def _make_image_tag() -> str:
    """Return a unique, timestamp-based Docker image tag."""
    ts = int(time.time() * 1000)
    return f"claw-sandbox:{ts}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_sandbox(allowlist_path: str) -> str:
    """Build a fresh sandbox Docker image and return its tag.

    The image is **always** rebuilt from scratch so that each run is fully
    reproducible and never reuses stale layers from a previous run.

    Parameters
    ----------
    allowlist_path:
        Path to ``config/allowlist.txt`` (one package name per line).

    Returns
    -------
    str
        The Docker image tag, e.g. ``claw-sandbox:1713580800000``.

    Raises
    ------
    RuntimeError
        If the Docker SDK is not installed or the build fails.
    """
    if not _DOCKER_AVAILABLE:
        raise RuntimeError(
            "Cannot build sandbox image: the 'docker' Python package is not "
            "installed. Install it with: pip install docker"
        )

    image_tag = _make_image_tag()

    # We build inside a temporary directory that contains the Dockerfile,
    # entrypoint, and the generated requirements.txt.
    with tempfile.TemporaryDirectory(prefix="claw-sandbox-build-") as build_ctx:
        build_dir = Path(build_ctx)

        # Copy Dockerfile and entrypoint into the build context.
        (build_dir / "Dockerfile").write_bytes(_DOCKERFILE_PATH.read_bytes())
        (build_dir / "entrypoint.sh").write_bytes(_ENTRYPOINT_PATH.read_bytes())

        # Generate requirements.txt from the allowlist.
        _generate_requirements(allowlist_path, build_dir / "requirements.txt")

        client = docker.from_env()
        logger.info("Building sandbox image %s ...", image_tag)
        try:
            _image, build_logs = client.images.build(
                path=str(build_dir),
                tag=image_tag,
                nocache=True,
                rm=True,
            )
        except BuildError as exc:
            log_lines = "\n".join(
                chunk.get("stream", chunk.get("error", ""))
                for chunk in exc.build_log
            )
            raise RuntimeError(
                f"Docker build failed for {image_tag}:\n{log_lines}"
            ) from exc

        logger.info("Sandbox image %s built successfully.", image_tag)
        return image_tag


def run_sandbox(
    image_tag: str,
    analysis_script: str,
    dataset_path: str,
    output_dir: str,
    timeout: int = 300,
) -> tuple[int, str]:
    """Run an analysis script inside a sandbox container.

    Parameters
    ----------
    image_tag:
        Docker image tag returned by :func:`build_sandbox`.
    analysis_script:
        The full Python source code to execute inside the container.
    dataset_path:
        Host path to the dataset directory.  Mounted read-only at
        ``/workspace/data`` inside the container.
    output_dir:
        Host path where the container can write results.  Mounted at
        ``/workspace/output``.
    timeout:
        Maximum wall-clock seconds before the container is killed.

    Returns
    -------
    tuple[int, str]
        ``(exit_code, combined_stdout_stderr_log)``.
    """
    if not _DOCKER_AVAILABLE:
        raise RuntimeError(
            "Cannot run sandbox: the 'docker' Python package is not installed."
        )

    client = docker.from_env()

    # Resolve to absolute paths so Docker bind-mounts work correctly.
    dataset_path = str(Path(dataset_path).resolve())
    output_dir = str(Path(output_dir).resolve())
    os.makedirs(output_dir, exist_ok=True)

    # Write the analysis script to a temp file that we will copy into the
    # container after creation (avoids needing it in the image).
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix="analysis_",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(analysis_script)
        tmp_script_path = tmp.name

    container = None
    try:
        # Create (but do not start) the container.
        container = client.containers.create(
            image=image_tag,
            command=["/workspace/analysis.py"],
            volumes={
                dataset_path: {"bind": "/workspace/data", "mode": "ro"},
                output_dir: {"bind": "/workspace/output", "mode": "rw"},
            },
            working_dir="/workspace",
            detach=True,
        )

        # Copy the script file into the container at /workspace/analysis.py.
        import tarfile

        script_tar_buf = io.BytesIO()
        with tarfile.open(fileobj=script_tar_buf, mode="w") as tar:
            info = tarfile.TarInfo(name="analysis.py")
            script_bytes = analysis_script.encode("utf-8")
            info.size = len(script_bytes)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(script_bytes))
        script_tar_buf.seek(0)
        container.put_archive("/workspace", script_tar_buf)

        # Start and wait.
        container.start()
        result = container.wait(timeout=timeout)
        exit_code: int = result.get("StatusCode", -1)

        # Capture combined logs (stdout + stderr interleaved).
        logs: str = container.logs(stdout=True, stderr=True).decode(
            "utf-8", errors="replace"
        )

        return exit_code, logs

    except Exception as exc:
        # If the container is still running, try to kill it.
        if container is not None:
            try:
                container.kill()
            except Exception:
                pass

        # Attempt to grab whatever logs we can.
        log_output = ""
        if container is not None:
            try:
                log_output = container.logs(stdout=True, stderr=True).decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                pass

        logger.error("Sandbox run failed: %s", exc)
        return 1, log_output or f"Sandbox run error: {exc}"

    finally:
        # Always clean up the temp file.
        try:
            os.unlink(tmp_script_path)
        except OSError:
            pass

        # Remove the container regardless of outcome.
        if container is not None:
            try:
                container.remove(force=True)
            except Exception as rm_exc:
                logger.warning("Failed to remove container: %s", rm_exc)


def cleanup_sandbox(image_tag: str) -> None:
    """Remove a previously built sandbox Docker image.

    Parameters
    ----------
    image_tag:
        The image tag to remove (as returned by :func:`build_sandbox`).
    """
    if not _DOCKER_AVAILABLE:
        logger.warning(
            "Docker SDK unavailable; cannot remove image %s.", image_tag
        )
        return

    client = docker.from_env()
    try:
        client.images.remove(image=image_tag, force=True)
        logger.info("Removed sandbox image %s.", image_tag)
    except ImageNotFound:
        logger.debug("Image %s already removed or never existed.", image_tag)
    except Exception as exc:
        logger.warning("Failed to remove image %s: %s", image_tag, exc)


def run_sandbox_local(
    analysis_script: str,
    dataset_path: str,
    output_dir: str,
    timeout: int = 300,
) -> tuple[int, str]:
    """Run an analysis script locally as a subprocess (no Docker).

    This is the fallback used in demo/test mode or when the Docker SDK is
    not available.  The subprocess inherits the current Python interpreter
    and has unrestricted filesystem access, so it should only be used in
    trusted environments.

    The script receives two environment variables so it can locate data
    and output directories the same way the containerised version does:

    * ``SANDBOX_DATA_DIR``  -- equivalent to ``/workspace/data``
    * ``SANDBOX_OUTPUT_DIR`` -- equivalent to ``/workspace/output``

    Parameters
    ----------
    analysis_script:
        Full Python source to execute.
    dataset_path:
        Path to the dataset directory.
    output_dir:
        Path where results should be written.
    timeout:
        Maximum wall-clock seconds.

    Returns
    -------
    tuple[int, str]
        ``(exit_code, combined_stdout_stderr_log)``.
    """
    dataset_path = str(Path(dataset_path).resolve())
    output_dir = str(Path(output_dir).resolve())
    os.makedirs(output_dir, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix="analysis_local_",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(analysis_script)
        tmp_script = tmp.name

    env = os.environ.copy()
    env["SANDBOX_DATA_DIR"] = dataset_path
    env["SANDBOX_OUTPUT_DIR"] = output_dir

    try:
        proc = subprocess.run(
            [sys.executable, tmp_script],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=output_dir,
            env=env,
        )
        combined = ""
        if proc.stdout:
            combined += proc.stdout
        if proc.stderr:
            combined += proc.stderr
        return proc.returncode, combined

    except subprocess.TimeoutExpired as exc:
        output_parts: list[str] = []
        if exc.stdout:
            out = exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode("utf-8", errors="replace")
            output_parts.append(out)
        if exc.stderr:
            err = exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode("utf-8", errors="replace")
            output_parts.append(err)
        output_parts.append(
            f"\n[TIMEOUT] Process killed after {timeout}s.\n"
        )
        return 1, "".join(output_parts)

    except Exception as exc:
        return 1, f"Local sandbox error: {exc}"

    finally:
        try:
            os.unlink(tmp_script)
        except OSError:
            pass
