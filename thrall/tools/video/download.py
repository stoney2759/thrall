from __future__ import annotations
import asyncio
import json
import os
import subprocess
import time
from uuid import UUID
from bootstrap import state
from schemas.tool import ToolCall, ToolResult
from constants.tools import MAX_OUTPUT

_DEFAULT_TIMEOUT = 600  # 10 minutes default for video operations


def _run_ytdlp(args: list[str], cwd: str | None, timeout: int, env: dict) -> tuple[int, str, str]:
    cmd = ["yt-dlp"] + args
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=timeout,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    
    # Extract parameters
    url = call.args.get("url", "").strip()
    operation = call.args.get("operation", "download")
    format_id = call.args.get("format_id", "best")
    output_path = call.args.get("output_path", "%(title)s.%(ext)s")
    extract_audio = call.args.get("extract_audio", False)
    audio_format = call.args.get("audio_format", "mp3")
    timeout = int(call.args.get("timeout", _DEFAULT_TIMEOUT))
    
    if not url:
        return _result(call.id, error="url is required", start=start)
    
    # Build yt-dlp arguments
    args = []
    
    if operation == "info":
        args.extend(["--dump-json", "--no-warnings", url])
    elif operation == "formats":
        args.extend(["--list-formats", "--no-warnings", url])
    elif operation == "download":
        args.extend(["--format", format_id])
        
        if extract_audio:
            args.extend(["--extract-audio", "--audio-format", audio_format])
        
        # Set output template
        args.extend(["-o", output_path])
        
        # Add progress and no-warnings flags
        args.extend(["--no-warnings", "--newline", url])
    else:
        return _result(call.id, error=f"unknown operation: {operation}", start=start)
    
    # Prepare environment — use system PATH as-is so the yt-dlp binary
    # resolves from wherever it is actually installed, not from sys.executable's
    # Scripts directory (which may be the wrong venv).
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    cwd = None
    if operation == "download" and not os.path.isabs(output_path):
        workspace_dir = state.get_workspace_dir()
        if workspace_dir:
            cwd = workspace_dir

    try:
        returncode, out, err = await asyncio.to_thread(_run_ytdlp, args, cwd, timeout, env)
    except subprocess.TimeoutExpired:
        return _result(call.id, error=f"operation timed out after {timeout}s", start=start)
    except Exception as e:
        return _result(call.id, error=f"failed to execute yt-dlp: {str(e)}", start=start)
    
    # Process results based on operation
    if operation == "info":
        try:
            # Parse JSON output
            info = json.loads(out.strip().split('\n')[0])
            result_output = json.dumps(info, indent=2)
        except:
            result_output = out
    elif operation == "formats":
        result_output = out or err
    else:  # download
        result_output = out or err
    
    if returncode != 0:
        error_msg = f"yt-dlp exited with code {returncode}"
        if err:
            error_msg += f"\n{err[:2000]}"  # Limit error output
        return _result(call.id, error=error_msg, start=start)
    
    return _result(call.id, output=result_output[:MAX_OUTPUT], start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    duration = int((time.monotonic() - start) * 1000)
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=duration)


NAME = "video_download"
DESCRIPTION = "Download videos or extract information using yt-dlp. Supports downloading videos, extracting audio, listing available formats, and getting video metadata."
PARAMETERS = {
    "url": {
        "type": "string",
        "required": True,
        "description": "Video URL to process (YouTube, Vimeo, etc.)"
    },
    "operation": {
        "type": "string",
        "required": False,
        "default": "download",
        "description": "Operation to perform: 'download' (download video/audio), 'info' (get metadata), or 'formats' (list available formats)"
    },
    "format_id": {
        "type": "string",
        "required": False,
        "default": "best",
        "description": "Video format ID to download (e.g., 'best', 'worst', '22', '136+140'). Use 'formats' operation to see available options."
    },
    "output_path": {
        "type": "string",
        "required": False,
        "default": "%(title)s.%(ext)s",
        "description": "Output filename template. Can use variables like %(title)s, %(ext)s, %(id)s. If relative path, saves to workspace."
    },
    "extract_audio": {
        "type": "boolean",
        "required": False,
        "default": False,
        "description": "Extract audio from video instead of downloading the full video"
    },
    "audio_format": {
        "type": "string",
        "required": False,
        "default": "mp3",
        "description": "Audio format when extract_audio is true: mp3, wav, m4a, flac, etc."
    },
    "timeout": {
        "type": "integer",
        "required": False,
        "default": 600,
        "description": "Timeout in seconds for the operation. Default 600 (10 minutes). Increase for large downloads."
    }
}