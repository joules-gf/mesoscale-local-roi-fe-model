"""Cross-platform helpers for running the simulation pipeline.

The project can generate MicroStructPy/Abaqus input files in WSL/Linux, but
Abaqus itself is usually installed on Windows.  This module keeps the bridge
logic isolated so the original research scripts can stay mostly unchanged.
"""

from __future__ import annotations

import os
import platform
import shutil
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence


class AbaqusUnavailableError(RuntimeError):
    """Raised when Abaqus cannot be found from the current environment."""


def is_wsl() -> bool:
    """Return True when running inside Windows Subsystem for Linux."""
    if "microsoft" in platform.release().lower():
        return True
    try:
        return "microsoft" in Path("/proc/version").read_text(errors="ignore").lower()
    except OSError:
        return False


def is_truthy(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def noninteractive_enabled() -> bool:
    """Whether GUI prompts/plots should be skipped for command-line runs."""
    return is_truthy(os.environ.get("MICROSTRUCTURE_NONINTERACTIVE"))


def find_windows_cmd_exe() -> str | None:
    """Return the WSL path to Windows cmd.exe, if available."""
    cmd_exe = shutil.which("cmd.exe")
    if cmd_exe:
        return cmd_exe
    fallback = Path("/mnt/c/Windows/System32/cmd.exe")
    if fallback.exists():
        return str(fallback)
    return None


def wsl_to_windows_path(path: str | os.PathLike[str]) -> str:
    """Convert a WSL path to a Windows path using wslpath when available."""
    path_str = str(Path(path).resolve())
    if not is_wsl():
        return path_str
    if shutil.which("wslpath") is None:
        return path_str
    result = subprocess.run(
        ["wslpath", "-w", path_str],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def find_abaqus_command() -> list[str]:
    """Return a command prefix that can launch Abaqus.

    Preference order:
    1. MICROSTRUCTURE_ABAQUS_CMD, if set. This may be a normal executable name
       such as ``abaqus`` or a full command path.
    2. Native ``abaqus`` in the current PATH.
    3. From WSL, Windows ``cmd.exe /C abaqus`` if cmd.exe is exposed.
    """
    configured = os.environ.get("MICROSTRUCTURE_ABAQUS_CMD")
    if configured:
        return shlex.split(configured)

    abaqus_command = shutil.which("abaqus")
    if abaqus_command:
        # On Windows, Abaqus is normally exposed as abaqus.bat.  Launching a
        # batch file by the bare name through subprocess.run(..., shell=False)
        # can fail with WinError 2 even when `where abaqus` finds it, so run the
        # resolved batch file through cmd.exe.
        if platform.system().lower() == "windows" and abaqus_command.lower().endswith((".bat", ".cmd")):
            cmd_exe = find_windows_cmd_exe() or "cmd.exe"
            return [cmd_exe, "/C", abaqus_command]
        return [abaqus_command]

    if is_wsl():
        cmd_exe = find_windows_cmd_exe()
        if cmd_exe:
            return [cmd_exe, "/C", "abaqus"]

    raise AbaqusUnavailableError(
        "Abaqus was not found. Install/configure Abaqus, add it to PATH, or set "
        "MICROSTRUCTURE_ABAQUS_CMD. In WSL, expose Windows cmd.exe/abaqus or run "
        "the generated .inp file manually on Windows."
    )


def run_command(command: Sequence[str], cwd: str | os.PathLike[str]) -> subprocess.CompletedProcess[str]:
    """Run a subprocess, streaming output, and raise on failure."""
    print("Running:", " ".join(command))
    print("Working directory:", cwd)
    return subprocess.run(command, cwd=str(cwd), check=True, text=True)


def _is_cmd_abaqus_bridge(command: Sequence[str]) -> bool:
    """Return True when Abaqus will be launched through Windows cmd.exe."""
    lowered = [part.lower() for part in command]
    return len(lowered) >= 3 and lowered[0].endswith("cmd.exe") and lowered[1] == "/c" and lowered[2] == "abaqus"


def _windows_safe_cwd() -> str | None:
    r"""Return a WSL path that resolves to a normal Windows drive path.

    Windows cmd.exe cannot start with a WSL UNC path as its current directory
    (for example ``\\wsl.localhost\Ubuntu\...``).  Starting cmd.exe from a
    real Windows path avoids the "UNC paths are not supported" fallback.
    """
    for candidate in (Path("/mnt/c/Windows/Temp"), Path("/mnt/c/Users/Public")):
        if candidate.exists():
            return str(candidate)
    return None


def _cmd_quote(value: str) -> str:
    """Quote a Windows cmd.exe argument."""
    return '"' + value.replace('"', '\\"') + '"'


def _windows_stage_root() -> Path:
    # Return a Windows-backed staging root visible to Windows Abaqus.
    candidates = (
        Path("/mnt/c/Users/Public/mesoscale_local_roi_fe_model_abaqus"),
        Path("/mnt/c/Windows/Temp/mesoscale_local_roi_fe_model_abaqus"),
    )
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        return candidate
    return Path(tempfile.mkdtemp(prefix="mesoscale_local_roi_fe_model_abaqus_"))


def _copy_one_file(src: Path, dst: Path) -> None:
    # Copy through the system cp command when available.  On WSL, Python
    # shutil.copy2 can use kernel fast-copy paths that fail with Errno 12
    # for large files copied from /mnt/c into the Linux filesystem.  GNU cp
    # streams the same files with very low memory use.
    dst.parent.mkdir(parents=True, exist_ok=True)
    cp_command = shutil.which("cp")
    if cp_command:
        subprocess.run([cp_command, "-p", str(src), str(dst)], check=True)
        return
    shutil.copy2(src, dst)


def _copy_tree_contents(src: Path, dst: Path) -> None:
    # Copy all files/directories from src into dst, preserving new outputs.
    # Walk recursively instead of using shutil.copytree so one large ODB file
    # is copied through _copy_one_file rather than Python's bulk tree copier.
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            _copy_tree_contents(item, target)
        else:
            _copy_one_file(item, target)


def _cmd_arg(value: str) -> str:
    # Quote a cmd.exe argument only when needed. Keep option=value tokens
    # unquoted because Abaqus parses quoted forms like "job=name" as
    # option "job name".
    if "=" in value:
        return value
    if any(char in value for char in " \t&()[]{}^;!'+,`~"):
        return _cmd_quote(value)
    return value


def run_cmd_abaqus_in_wsl_directory(
    abaqus_args: Sequence[str],
    cwd: str | os.PathLike[str],
    script_path: str | os.PathLike[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    r"""Run Windows Abaqus for a WSL-generated case.

    Some WSL installations expose paths like ``\\wsl.localhost\\Ubuntu`` via
    ``wslpath -w`` but Windows ``cmd.exe`` cannot actually access those UNC paths
    from a WSL-launched process (``The specified path is invalid``).  To avoid
    UNC fragility, stage the whole simulation case on ``C:`` before launching
    Abaqus, then copy generated results back into the WSL output directory.
    """
    workdir = Path(cwd).resolve()
    source_case_dir = workdir.parent
    relative_workdir = workdir.relative_to(source_case_dir)

    stage_case_dir = _windows_stage_root() / source_case_dir.name
    if stage_case_dir.exists():
        shutil.rmtree(stage_case_dir)
    _copy_tree_contents(source_case_dir, stage_case_dir)
    stage_workdir = stage_case_dir / relative_workdir

    staged_args = list(abaqus_args)
    if script_path is not None:
        script = Path(script_path).resolve()
        staged_script_dir = stage_case_dir / "_abaqus_scripts"
        staged_script_dir.mkdir(parents=True, exist_ok=True)
        staged_script = staged_script_dir / script.name
        shutil.copy2(script, staged_script)
        staged_script_arg = wsl_to_windows_path(staged_script)
        staged_args = [
            f"noGUI={staged_script_arg}" if str(arg).startswith("noGUI=") else str(arg)
            for arg in staged_args
        ]

    cmd_exe = find_windows_cmd_exe() or "cmd.exe"
    command_text = "abaqus " + " ".join(_cmd_arg(str(arg)) for arg in staged_args)
    command = [cmd_exe, "/C", command_text]

    print("Running:", " ".join(command))
    print("Working directory:", cwd)
    print("Windows staging directory:", stage_workdir)
    try:
        return subprocess.run(command, cwd=str(stage_workdir), check=True, text=True)
    finally:
        _copy_tree_contents(stage_case_dir, source_case_dir)


def run_abaqus_job(abaqus_simulation_directory: str | os.PathLike[str], simulation_name: str) -> None:
    """Run ``abaqus job=<simulation_name> interactive`` in a portable way."""
    workdir = Path(abaqus_simulation_directory).resolve()
    abaqus_args = [f"job={simulation_name}", "interactive"]
    command = find_abaqus_command() + abaqus_args
    if is_wsl() and _is_cmd_abaqus_bridge(command):
        run_cmd_abaqus_in_wsl_directory(abaqus_args, workdir)
        return
    run_command(command, workdir)


def run_abaqus_cae_no_gui(
    abaqus_output_directory: str | os.PathLike[str],
    script_path: str | os.PathLike[str],
) -> None:
    """Run an Abaqus/CAE noGUI postprocessing script portably."""
    workdir = Path(abaqus_output_directory).resolve()
    script = Path(script_path).resolve()

    script_arg = str(script)

    command = find_abaqus_command() + ["cae", f"noGUI={script_arg}"]
    if is_wsl() and _is_cmd_abaqus_bridge(command):
        run_cmd_abaqus_in_wsl_directory(["cae", f"noGUI={script_arg}"], workdir, script_path=script)
        return
    run_command(command, workdir)
