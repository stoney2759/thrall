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
        
        elif operation == "extract_frames":
            output_dir = call.args.get("output_dir", "")
            interval = int(call.args.get("interval", 30))
            scale_width = int(call.args.get("scale_width", 1280))
            frame_format = call.args.get("frame_format", "jpg")

            if not output_dir:
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                output_dir = os.path.join(os.path.dirname(input_path), f"{base_name}_frames")
            elif workspace_dir and not os.path.isabs(output_dir):
                output_dir = os.path.join(workspace_dir, output_dir)

            os.makedirs(output_dir, exist_ok=True)
            output_pattern = os.path.join(output_dir, f"frame_%04d.{frame_format}")
            vf_filter = f"fps=1/{interval},scale={scale_width}:-1"

            args = ["-i", input_path, "-vf", vf_filter, output_pattern]
            returncode, out, err = await asyncio.to_thread(_run_ffmpeg, args, None, timeout, env)

            if returncode != 0:
                return _result(call.id, error=f"ffmpeg extract_frames failed (code {returncode})\n{err[:2000]}", start=start)

            frame_files = sorted(f for f in os.listdir(output_dir) if f.startswith("frame_"))
            return _result(call.id, output=f"Extracted {len(frame_files)} frames to {output_dir}\nFiles: {', '.join(frame_files)}", start=start)

        elif operation == "concat":
            input_paths = call.args.get("input_paths", [])
            if not input_paths:
                return _result(call.id, error="input_paths is required for concat", start=start)
            if not output_path:
                return _result(call.id, error="output_path is required for concat", start=start)

            resolved = []
            for p in input_paths:
                if workspace_dir and not os.path.isabs(p):
                    p = os.path.join(workspace_dir, p)
                resolved.append(p)

            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                for p in resolved:
                    f.write(f"file '{p}'\n")
                concat_file = f.name

            try:
                args = ["-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output_path]
                returncode, out, err = await asyncio.to_thread(_run_ffmpeg, args, None, timeout, env)
            finally:
                os.unlink(concat_file)

            if returncode != 0:
                return _result(call.id, error=f"ffmpeg concat failed (code {returncode})\n{err[:2000]}", start=start)

            return _result(call.id, output=f"Concatenated {len(resolved)} files to {output_path}", start=start)

        elif operation == "compress":
            if not output_path:
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                ext = os.path.splitext(input_path)[1]
                output_path = os.path.join(os.path.dirname(input_path), f"{base_name}_compressed{ext}")

            video_crf = int(call.args.get("video_crf", 28))
            audio_bitrate = call.args.get("audio_bitrate", "128k")
            scale_width = call.args.get("scale_width", None)

            args = ["-i", input_path]
            if scale_width:
                args.extend(["-vf", f"scale={scale_width}:-1"])
            args.extend(["-c:v", "libx264", "-crf", str(video_crf), "-c:a", "aac", "-b:a", audio_bitrate, output_path])

            returncode, out, err = await asyncio.to_thread(_run_ffmpeg, args, None, timeout, env)

            if returncode != 0:
                return _result(call.id, error=f"ffmpeg compress failed (code {returncode})\n{err[:2000]}", start=start)

            try:
                orig = os.path.getsize(input_path)
                comp = os.path.getsize(output_path)
                pct = 100 - (comp / orig * 100)
                return _result(call.id, output=f"Compressed to {output_path}\n{orig // 1024}KB → {comp // 1024}KB ({pct:.0f}% reduction)", start=start)
            except Exception:
                return _result(call.id, output=f"Compressed {input_path} to {output_path}", start=start)

        elif operation == "gif":
            if not output_path:
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                output_path = os.path.join(os.path.dirname(input_path), f"{base_name}.gif")

            gif_fps = int(call.args.get("gif_fps", 10))
            gif_width = int(call.args.get("gif_width", 480))
            gif_start = call.args.get("start_time", "00:00:00")
            gif_duration = call.args.get("duration", "5")

            vf_filter = f"fps={gif_fps},scale={gif_width}:-1:flags=lanczos"
            args = ["-i", input_path, "-ss", str(gif_start), "-t", str(gif_duration), "-vf", vf_filter, output_path]

            returncode, out, err = await asyncio.to_thread(_run_ffmpeg, args, None, timeout, env)

            if returncode != 0:
                return _result(call.id, error=f"ffmpeg gif failed (code {returncode})\n{err[:2000]}", start=start)

            return _result(call.id, output=f"Created GIF at {output_path}", start=start)

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
DESCRIPTION = "Process video and audio files using ffmpeg. Operations: probe, convert, extract_audio, trim, thumbnail, extract_frames, concat, compress, gif."
PARAMETERS = {
    "input_path": {
        "type": "string",
        "required": True,
        "description": "Path to input video/audio file. Relative paths resolve to workspace. Not required for concat (use input_paths instead).",
    },
    "operation": {
        "type": "string",
        "required": False,
        "default": "probe",
        "description": (
            "probe — stream/format metadata as JSON | "
            "convert — transcode to another format | "
            "extract_audio — strip video, keep audio | "
            "trim — cut clip by start_time/duration | "
            "thumbnail — extract single frame | "
            "extract_frames — bulk frame extraction at interval (for vision analysis) | "
            "concat — join multiple clips into one file | "
            "compress — reduce filesize with H.264/AAC | "
            "gif — create animated GIF from a clip"
        ),
    },
    "output_path": {
        "type": "string",
        "required": False,
        "description": "Output file path. Relative paths resolve to workspace. Auto-generated for extract_audio, thumbnail, compress, and gif if omitted.",
    },
    "output_dir": {
        "type": "string",
        "required": False,
        "description": "Output directory for extract_frames. Auto-generated next to input file if omitted.",
    },
    "input_paths": {
        "type": "array",
        "required": False,
        "description": "List of file paths for concat operation.",
    },
    "video_codec": {
        "type": "string",
        "required": False,
        "description": "Video codec for convert (e.g. 'libx264', 'libx265', 'copy'). Default: copy.",
    },
    "audio_codec": {
        "type": "string",
        "required": False,
        "description": "Audio codec for convert (e.g. 'aac', 'libmp3lame', 'copy'). Default: copy.",
    },
    "audio_format": {
        "type": "string",
        "required": False,
        "default": "mp3",
        "description": "Audio format for extract_audio: mp3, wav, flac, m4a.",
    },
    "start_time": {
        "type": "string",
        "required": False,
        "description": "Start time for trim or gif (HH:MM:SS or seconds).",
    },
    "duration": {
        "type": "string",
        "required": False,
        "description": "Duration for trim or gif (HH:MM:SS or seconds).",
    },
    "timestamp": {
        "type": "string",
        "required": False,
        "default": "00:00:01",
        "description": "Timestamp for thumbnail extraction (HH:MM:SS).",
    },
    "interval": {
        "type": "integer",
        "required": False,
        "default": 30,
        "description": "Seconds between frames for extract_frames. Default: 30.",
    },
    "scale_width": {
        "type": "integer",
        "required": False,
        "description": "Resize width in pixels for extract_frames and compress. Height auto-scales. Default for frames: 1280.",
    },
    "frame_format": {
        "type": "string",
        "required": False,
        "default": "jpg",
        "description": "Image format for extract_frames: jpg or png.",
    },
    "video_crf": {
        "type": "integer",
        "required": False,
        "default": 28,
        "description": "H.264 quality for compress (18=high, 28=medium, 35=low). Default: 28.",
    },
    "audio_bitrate": {
        "type": "string",
        "required": False,
        "default": "128k",
        "description": "Audio bitrate for compress (e.g. '128k', '64k'). Default: 128k.",
    },
    "gif_fps": {
        "type": "integer",
        "required": False,
        "default": 10,
        "description": "Frames per second for gif output. Default: 10.",
    },
    "gif_width": {
        "type": "integer",
        "required": False,
        "default": 480,
        "description": "Width in pixels for gif output. Default: 480.",
    },
    "extra_args": {
        "type": "array",
        "required": False,
        "description": "Additional ffmpeg arguments as a list of strings for convert operation.",
    },
    "timeout": {
        "type": "integer",
        "required": False,
        "default": 600,
        "description": "Timeout in seconds. Default: 600 (10 minutes).",
    },
}
