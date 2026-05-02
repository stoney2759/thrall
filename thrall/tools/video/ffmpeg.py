from __future__ import annotations
import asyncio
import json
import os
import subprocess
import time
from uuid import UUID
from bootstrap import state
from schemas.tool import ToolCall, ToolResult

_DEFAULT_TIMEOUT = 600  # 10 minutes default for ffmpeg operations
_MAX_OUTPUT = 16_000


def _run_ffmpeg(args: list[str], cwd: str | None, timeout: int, env: dict) -> tuple[int, str, str]:
    result = subprocess.run(
        ["ffmpeg", "-y"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=timeout,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def _run_ffprobe(args: list[str], cwd: str | None, timeout: int, env: dict) -> tuple[int, str, str]:
    result = subprocess.run(
        ["ffprobe"] + args,
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
    input_path = call.args.get("input_path", "").strip()
    operation = call.args.get("operation", "probe")
    output_path = call.args.get("output_path", "")
    video_codec = call.args.get("video_codec", None)
    audio_codec = call.args.get("audio_codec", None)
    audio_format = call.args.get("audio_format", "mp3")
    start_time = call.args.get("start_time", None)
    duration = call.args.get("duration", None)
    timestamp = call.args.get("timestamp", "00:00:01")
    extra_args = call.args.get("extra_args", [])
    timeout = int(call.args.get("timeout", _DEFAULT_TIMEOUT))
    
    if not input_path:
        return _result(call.id, error="input_path is required", start=start)
    
    # Resolve workspace paths
    workspace_dir = state.get_workspace_dir()
    if workspace_dir:
        if not os.path.isabs(input_path):
            input_path = os.path.join(workspace_dir, input_path)
        if output_path and not os.path.isabs(output_path):
            output_path = os.path.join(workspace_dir, output_path)
    
    env = os.environ.copy()
    
    try:
        if operation == "probe":
            args = ["-print_format", "json", "-show_format", "-show_streams", input_path]
            returncode, out, err = await asyncio.to_thread(_run_ffprobe, args, None, timeout, env)
            
            if returncode != 0:
                error_msg = f"ffprobe exited with code {returncode}"
                if err:
                    error_msg += f"\n{err[:2000]}"
                return _result(call.id, error=error_msg, start=start)
            
            try:
                # Parse JSON output
                probe_data = json.loads(out.strip())
                result_output = json.dumps(probe_data, indent=2)
            except:
                result_output = out
            
            return _result(call.id, output=result_output[:_MAX_OUTPUT], start=start)
        
        elif operation == "convert":
            if not output_path:
                return _result(call.id, error="output_path is required for convert operation", start=start)
            
            args = ["-i", input_path]
            
            if video_codec:
                args.extend(["-c:v", video_codec])
            else:
                args.extend(["-c:v", "copy"])
            
            if audio_codec:
                args.extend(["-c:a", audio_codec])
            else:
                args.extend(["-c:a", "copy"])
            
            if extra_args:
                args.extend(extra_args)
            
            args.append(output_path)
            
            returncode, out, err = await asyncio.to_thread(_run_ffmpeg, args, None, timeout, env)
            
            if returncode != 0:
                error_msg = f"ffmpeg exited with code {returncode}"
                if err:
                    error_msg += f"\n{err[:2000]}"
                return _result(call.id, error=error_msg, start=start)
            
            return _result(call.id, output=f"Converted {input_path} to {output_path}", start=start)
        
        elif operation == "extract_audio":
            if not output_path:
                # Generate output path from input
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                output_path = os.path.join(os.path.dirname(input_path), f"{base_name}_audio.{audio_format}")
            
            args = ["-i", input_path, "-vn", "-acodec", "copy"]
            
            if audio_format == "mp3":
                args[-1] = "libmp3lame"
                args.extend(["-q:a", "2"])
            elif audio_format == "wav":
                args[-1] = "pcm_s16le"
            elif audio_format == "flac":
                args[-1] = "flac"
            elif audio_format == "m4a":
                args[-1] = "aac"
                args.extend(["-b:a", "192k"])
            
            args.append(output_path)
            
            returncode, out, err = await asyncio.to_thread(_run_ffmpeg, args, None, timeout, env)
            
            if returncode != 0:
                error_msg = f"ffmpeg exited with code {returncode}"
                if err:
                    error_msg += f"\n{err[:2000]}"
                return _result(call.id, error=error_msg, start=start)
            
            return _result(call.id, output=f"Extracted audio from {input_path} to {output_path}", start=start)
        
        elif operation == "trim":
            if not output_path:
                return _result(call.id, error="output_path is required for trim operation", start=start)
            if not start_time:
                return _result(call.id, error="start_time is required for trim operation", start=start)
            
            args = ["-i", input_path, "-ss", str(start_time)]
            
            if duration:
                args.extend(["-t", str(duration)])
            
            args.extend(["-c", "copy", output_path])
            
            returncode, out, err = await asyncio.to_thread(_run_ffmpeg, args, None, timeout, env)
            
            if returncode != 0:
                error_msg = f"ffmpeg exited with code {returncode}"
                if err:
                    error_msg += f"\n{err[:2000]}"
                return _result(call.id, error=error_msg, start=start)
            
            return _result(call.id, output=f"Trimmed {input_path} from {start_time} to {output_path}", start=start)
        
        elif operation == "thumbnail":
            if not output_path:
                # Generate output path from input
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                output_path = os.path.join(os.path.dirname(input_path), f"{base_name}_thumb.jpg")
            
            args = ["-i", input_path, "-ss", str(timestamp), "-vframes", "1", output_path]
            
            returncode, out, err = await asyncio.to_thread(_run_ffmpeg, args, None, timeout, env)
            
            if returncode != 0:
                error_msg = f"ffmpeg exited with code {returncode}"
                if err:
                    error_msg += f"\n{err[:2000]}"
                return _result(call.id, error=error_msg, start=start)
            
            return _result(call.id, output=f"Extracted thumbnail from {input_path} at {timestamp} to {output_path}", start=start)
        
        else:
            return _result(call.id, error=f"unknown operation: {operation}", start=start)
    
    except subprocess.TimeoutExpired:
        return _result(call.id, error=f"operation timed out after {timeout}s", start=start)
    except Exception as e:
        return _result(call.id, error=f"failed to execute ffmpeg: {str(e)}", start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    duration = int((time.monotonic() - start) * 1000)
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=duration)


NAME = "video_ffmpeg"
DESCRIPTION = "Process video and audio files using ffmpeg. Supports probing metadata, converting formats, extracting audio, trimming clips, and extracting thumbnails."
PARAMETERS = {
    "input_path": {
        "type": "string",
        "required": True,
        "description": "Path to the input video/audio file. If relative path, resolves to workspace."
    },
    "operation": {
        "type": "string",
        "required": False,
        "default": "probe",
        "description": "Operation to perform: 'probe' (get metadata), 'convert' (transcode), 'extract_audio' (strip video), 'trim' (cut clip), or 'thumbnail' (extract frame)"
    },
    "output_path": {
        "type": "string",
        "required": False,
        "description": "Output path for the operation. If relative path, resolves to workspace. Auto-generated for extract_audio and thumbnail if not provided."
    },
    "video_codec": {
        "type": "string",
        "required": False,
        "description": "Video codec for convert operation (e.g., 'libx264', 'libx265', 'copy'). If not specified, defaults to 'copy'."
    },
    "audio_codec": {
        "type": "string",
        "required": False,
        "description": "Audio codec for convert operation (e.g., 'aac', 'libmp3lame', 'copy'). If not specified, defaults to 'copy'."
    },
    "audio_format": {
        "type": "string",
        "required": False,
        "default": "mp3",
        "description": "Audio format for extract_audio operation: mp3, wav, flac, m4a."
    },
    "start_time": {
        "type": "string",
        "required": False,
        "description": "Start time for trim operation (format: HH:MM:SS or seconds)."
    },
    "duration": {
        "type": "string",
        "required": False,
        "description": "Duration for trim operation (format: HH:MM:SS or seconds). If not specified, trims to end of file."
    },
    "timestamp": {
        "type": "string",
        "required": False,
        "default": "00:00:01",
        "description": "Timestamp for thumbnail extraction (format: HH:MM:SS)."
    },
    "extra_args": {
        "type": "array",
        "required": False,
        "description": "Additional ffmpeg arguments as a list of strings for convert operation."
    },
    "timeout": {
        "type": "integer",
        "required": False,
        "default": 600,
        "description": "Timeout in seconds for the operation. Default 600 (10 minutes)."
    }
}
