#!/usr/bin/env python3
"""Local preparation, evidence lookup, and technical QA for Jianying templates.

Does not operate Jianying, register projects, modify source drafts, or decrypt files.
The prepare command needs Pillow in the current Python environment.
FFmpeg tools are discovered from CLI options, environment variables, PATH,
or an optional JY_EDITOR_SKILL/bin directory; no account-specific path is used.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import time


SKILL = Path(__file__).resolve().parents[1]


class ToolError(Exception):
    pass


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as src:
        for block in iter(lambda: src.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_file(value):
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ToolError(f"Expected a file: {path}")
    return path


def executable(name, explicit=None):
    configured = explicit or os.environ.get(name.upper())
    if configured:
        candidate = os.path.expandvars(os.path.expanduser(configured))
        found = shutil.which(candidate)
        if not found:
            raise ToolError(f"Configured {name} is not executable: {candidate}")
        return str(Path(found).resolve())
    found = shutil.which(name)
    editor = os.environ.get("JY_EDITOR_SKILL")
    if not found and editor:
        candidate = Path(os.path.expandvars(editor)).expanduser() / "bin" / name
        found = shutil.which(str(candidate))
    if not found:
        raise ToolError(f"Cannot find {name}; install FFmpeg, supply --{name}, set {name.upper()}, or set JY_EDITOR_SKILL")
    return str(Path(found).resolve())


def run(args, timeout=600):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise ToolError(f"{Path(args[0]).name} failed: {result.stderr[-4000:].strip()}")
    return result.stdout


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".template-report-",
                                     dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def positive_number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and number > 0 else None
    except (ValueError, TypeError):
        return None


def rate(stream):
    for key in ("avg_frame_rate", "r_frame_rate"):
        try:
            value = Fraction(stream.get(key, "0/1"))
            if value > 0:
                return {"exact": str(value), "numerator": value.numerator,
                        "denominator": value.denominator, "value": float(value), "source": key}
        except (ValueError, ZeroDivisionError):
            pass
    return None


def probe(path, ffprobe, count=False):
    command = [ffprobe, "-v", "error"]
    if count:
        command.append("-count_frames")
    raw = json.loads(run(command + ["-show_streams", "-show_format", "-of", "json", str(path)]))
    streams = raw.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    if video is None:
        raise ToolError(f"No video stream: {path}")
    fps = rate(video)
    duration = positive_number(video.get("duration")) or positive_number(raw.get("format", {}).get("duration"))
    frames = None
    for key, certainty in (("nb_read_frames", "decoded"), ("nb_frames", "container")):
        try:
            n = int(video.get(key, 0))
            if n > 0:
                frames = {"value": n, "certainty": certainty, "source": key}
                break
        except (TypeError, ValueError):
            pass
    if frames is None and fps and duration:
        frames = {"value": max(1, round(duration * fps["value"])),
                  "certainty": "estimated", "source": "duration_times_fps"}
    rotation = video.get("tags", {}).get("rotate", 0)
    for item in video.get("side_data_list", []):
        if "rotation" in item:
            rotation = item["rotation"]
    try:
        rotation = int(float(rotation)) % 360
    except (ValueError, TypeError):
        rotation = 0
    width, height = video.get("width"), video.get("height")
    return {"path": str(path), "codec": video.get("codec_name"), "width": width, "height": height,
            "display_size": [height, width] if rotation in (90, 270) else [width, height],
            "rotation_degrees": rotation, "fps": fps, "frame_count": frames,
            "video_duration_seconds": duration,
            "format_duration_seconds": positive_number(raw.get("format", {}).get("duration")),
            "audio": [{"codec": s.get("codec_name"), "sample_rate": s.get("sample_rate"),
                       "channels": s.get("channels"), "duration_seconds": positive_number(s.get("duration"))}
                      for s in streams if s.get("codec_type") == "audio"]}


def registry_path(name):
    variable = {"case-index.json": "JY_CASE_INDEX",
                "resource-registry.json": "JY_RESOURCE_REGISTRY"}.get(name)
    configured = os.environ.get(variable) if variable else None
    if configured:
        return Path(os.path.expandvars(configured)).expanduser().resolve()
    public = SKILL / "references" / name
    local = public.with_name(public.stem + ".local.json")
    return (local if local.exists() else public).resolve()


def records(name, key):
    path = registry_path(name)
    if not path.is_file():
        raise ToolError(f"Registry missing: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    result = obj if isinstance(obj, list) else obj.get(key, [])
    if not isinstance(result, list):
        raise ToolError(f"Expected an array at {path}:{key}")
    return result


def lookup(args):
    reference = source_file(args.reference)
    sha = digest(reference)
    matches = []
    for case in records("case-index.json", "cases"):
        if not isinstance(case, dict):
            continue
        fingerprint = case.get("reference_sha256")
        if not fingerprint and isinstance(case.get("reference"), dict):
            fingerprint = case["reference"].get("sha256")
        if fingerprint == sha:
            matches.append(case)
    return {"kind": "exact_reference_lookup", "reference": str(reference), "sha256": sha,
            "matched_by": "sha256", "matches": matches, "count": len(matches),
            "registry_source": str(registry_path("case-index.json"))}


def resources(args):
    terms = args.query.casefold().split()
    app_path = Path(os.path.expandvars(os.environ.get("JY_APP_PATH", "/Applications/VideoFusion-macOS.app"))).expanduser()
    try:
        with (app_path / "Contents" / "Info.plist").open("rb") as handle:
            app_version = plistlib.load(handle).get("CFBundleShortVersionString")
    except (OSError, ValueError, plistlib.InvalidFileException):
        app_version = None
    candidates = []
    for item in records("resource-registry.json", "resources"):
        if not isinstance(item, dict) or not all(term in json.dumps(item, ensure_ascii=False).casefold() for term in terms):
            continue
        candidate = dict(item)
        bundle = Path(os.path.expandvars(item["bundle_path"])).expanduser() if item.get("bundle_path") else None
        if bundle and not bundle.is_absolute():
            bundle = SKILL / bundle
        exists = bool(bundle and bundle.is_dir())
        config = bundle / "config.json" if bundle else None
        config_sha = digest(config) if config and config.is_file() else None
        matches = config_sha == item["config_sha256"] if config_sha and item.get("config_sha256") else None
        version_matches = app_version == item["last_verified_app_version"] if app_version and item.get("last_verified_app_version") else None
        candidate["current_availability"] = {"bundle_exists": exists, "config_sha256": config_sha,
            "config_matches_registry": matches, "app_version": app_version,
            "app_version_matches": version_matches, "catalog_only": bundle is None,
            "reprobe_required": not (exists and matches and version_matches)}
        candidates.append(candidate)
    return {"kind": "resource_candidates", "query": args.query, "count": len(candidates),
            "registry_source": str(registry_path("resource-registry.json")),
            "candidates": candidates, "evidence": "Keyword metadata only; does not prove a visual or original-source match."}


def prepare(args):
    started = time.perf_counter()
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        install = shlex.join([sys.executable, "-m", "pip", "install", "Pillow"])
        raise ToolError(f"Pillow is required in this Python environment. Install with: {install}; or use a virtual environment with Pillow installed.") from exc

    reference, photo = source_file(args.reference), source_file(args.photo)
    out = Path(args.out).expanduser().resolve()
    ref_sha, photo_sha = digest(reference), digest(photo)
    if out.exists():
        session_path = out / "session.json"
        if session_path.is_file():
            saved = json.loads(session_path.read_text(encoding="utf-8"))
            if saved.get("reference", {}).get("sha256") == ref_sha and saved.get("photo", {}).get("sha256") == photo_sha:
                if saved.get("status") != "ready":
                    raise ToolError(f"Existing preparation is not ready ({saved.get('status')}); inspect it or choose a fresh --out: {out}")
                options = {"thumbs": args.thumbs, "no_audio": args.no_audio}
                if saved.get("prepare_options") != options:
                    raise ToolError(f"Existing preparation options differ; choose a fresh --out for different thumbnails/audio options: {out}")
                required = [saved.get("photo", {}).get("path"), saved.get("contact_sheet")]
                required.extend(item.get("path") for item in saved.get("thumbnails", []))
                if not saved.get("thumbnails"):
                    required.append(None)
                needs_audio = saved.get("reference", {}).get("probe", {}).get("audio") and not args.no_audio
                if needs_audio:
                    required.append((saved.get("audio") or {}).get("path"))
                if any(not item or not Path(item).is_file() for item in required):
                    raise ToolError(f"Existing session assets are missing; inspect it or choose a fresh --out, without overwriting this session: {out}")
                return {"kind": "prepared_session", "reused": True, "session_path": str(session_path), "session": saved}
        raise ToolError(f"Output already exists with different or unrecognized inputs; nothing changed: {out}")
    ffmpeg = executable("ffmpeg", args.ffmpeg)
    metadata = probe(reference, executable("ffprobe", args.ffprobe))
    if not metadata["frame_count"] or not metadata["fps"]:
        raise ToolError("Cannot select meaningful thumbnails without a frame-count estimate and FPS")
    with Image.open(photo) as source:
        photo_size = list(source.size)
        source.verify()
    assets, thumbs_dir = out / "assets", out / "analysis" / "thumbnails"
    out.mkdir(parents=True, exist_ok=False)
    assets.mkdir()
    thumbs_dir.mkdir(parents=True)
    suffix = photo.suffix.lower() or ".img"
    stable_photo = assets / ("replacement_photo" + suffix)
    shutil.copy2(photo, stable_photo)
    session_path = out / "session.json"
    session = {"version": 1, "status": "preparing", "workspace": str(out),
               "reference": {"path": str(reference), "sha256": ref_sha, "probe": metadata},
               "photo": {"source_path": str(photo), "path": str(stable_photo), "sha256": photo_sha, "size": photo_size},
               "prepare_options": {"thumbs": args.thumbs, "no_audio": args.no_audio},
               "native_draft_modified": False}
    write_json(session_path, session)
    try:
        total = metadata["frame_count"]["value"]
        count = min(total, args.thumbs)
        selected = sorted(set(round(i * (total - 1) / max(1, count - 1)) for i in range(count)))
        selection = "+".join(f"eq(n\\,{n})" for n in selected)
        run([ffmpeg, "-v", "error", "-nostdin", "-y", "-i", str(reference), "-an", "-sn",
             "-vf", f"select={selection},scale=240:320:force_original_aspect_ratio=decrease",
             "-fps_mode", "vfr", "-frames:v", str(len(selected)), str(thumbs_dir / "thumb-%03d.jpg")])
        images = sorted(thumbs_dir.glob("thumb-*.jpg"))
        if not images:
            raise ToolError("FFmpeg produced no thumbnails")
        contact = Image.new("RGB", (4 * 256, math.ceil(len(images) / 4) * 360), "#202020")
        draw = ImageDraw.Draw(contact)
        thumbnails = []
        for i, image_path in enumerate(images):
            frame = selected[i]
            x, y = (i % 4) * 256, (i // 4) * 360
            with Image.open(image_path) as thumbnail:
                contact.paste(thumbnail, (x + (256 - thumbnail.width) // 2, y + 28))
            seconds = frame / metadata["fps"]["value"]
            draw.text((x + 8, y + 8), f"f{frame}  {seconds:.3f}s", fill="white")
            thumbnails.append({"frame": frame, "time_seconds": seconds, "path": str(image_path)})
        contact_path = out / "analysis" / "contact_sheet.jpg"
        contact.save(contact_path, quality=88)
        audio = None
        if metadata["audio"] and not args.no_audio:
            audio_path = assets / "reference_audio.m4a"
            original_aac = metadata["audio"][0]["codec"] == "aac"
            codec = ["-c:a", "copy"] if original_aac else ["-c:a", "aac", "-b:a", "192k"]
            run([ffmpeg, "-v", "error", "-nostdin", "-y", "-i", str(reference),
                 "-map", "0:a:0", "-vn", "-sn", *codec, str(audio_path)])
            audio = {"path": str(audio_path), "mode": "stream_copy" if original_aac else "transcoded_aac"}
        session.update(status="ready", thumbnails=thumbnails, thumbnail_count_requested=args.thumbs,
                       thumbnail_count_actual=len(images), thumbnail_frame_count_certainty=metadata["frame_count"]["certainty"],
                       thumbnail_selection_note="Frames are selected in increasing native-frame order. An estimated total can omit requested tail thumbnails; actual_count reports produced files.",
                       contact_sheet=str(contact_path), audio=audio,
                       prepare_elapsed_seconds=round(time.perf_counter() - started, 4))
        write_json(session_path, session)
    except Exception as exc:
        session.update(status="failed", error=str(exc))
        write_json(session_path, session)
        raise
    return {"kind": "prepared_session", "reused": False, "session_path": str(session_path), "session": session}


def verify(args):
    started = time.perf_counter()
    video = source_file(args.video)
    report_path = None
    if args.out:
        requested = Path(args.out).expanduser().resolve()
        if requested.is_file() and requested.suffix.lower() != ".json":
            raise ToolError("Verification --out is an existing non-JSON file; nothing changed")
        report_path = requested if requested.suffix.lower() == ".json" else requested / "verification.json"
        if report_path == video or (args.reference and report_path == source_file(args.reference)):
            raise ToolError("Verification output cannot overwrite an input")
        if report_path.exists():
            if not report_path.is_file():
                raise ToolError("Verification report path is a directory")
            try:
                json.loads(report_path.read_text(encoding="utf-8"))
            except (ValueError, UnicodeError) as exc:
                raise ToolError("Existing verification output is not valid JSON; nothing changed") from exc
    ffprobe = executable("ffprobe", args.ffprobe)
    actual = probe(video, ffprobe, count=True)
    expected = probe(source_file(args.reference), ffprobe, count=True) if args.reference else None
    differences = []
    if expected:
        for field in ("display_size",):
            if actual[field] != expected[field]:
                differences.append({"field": field, "expected": expected[field], "actual": actual[field]})
        expected_fps, actual_fps = expected["fps"], actual["fps"]
        if (expected_fps or {}).get("exact") != (actual_fps or {}).get("exact"):
            differences.append({"field": "fps", "expected": expected_fps, "actual": actual_fps})
        for field in ("frame_count",):
            if (actual[field] or {}).get("value") != (expected[field] or {}).get("value"):
                differences.append({"field": field, "expected": expected[field], "actual": actual[field]})
        if bool(actual["audio"]) != bool(expected["audio"]):
            differences.append({"field": "audio_presence", "expected": bool(expected["audio"]), "actual": bool(actual["audio"])})
        before, after = expected["format_duration_seconds"], actual["format_duration_seconds"]
        tolerance = max(0.04, 1 / expected_fps["value"]) if expected_fps else 0.04
        if before and after and abs(before - after) > tolerance:
            differences.append({"field": "duration_seconds", "expected": before, "actual": after, "tolerance": tolerance})
    decode = "not_requested"
    if args.decode:
        decoder = executable("ffmpeg", args.ffmpeg)
        try:
            run([decoder, "-v", "error", "-nostdin", "-i", str(video),
                 "-map", "0:v?", "-map", "0:a?", "-f", "null", "-"])
            decode = "passed"
        except ToolError as exc:
            decode = "failed"
            differences.append({"field": "decode", "error": str(exc)})
    result = {"kind": "technical_video_verification", "technical_pass": not differences,
              "visual_match_verified": False, "video_sha256": digest(video), "video": actual,
              "reference": expected, "decode": decode, "differences": differences,
              "verify_elapsed_seconds": round(time.perf_counter() - started, 4),
              "scope": "Stream properties and optional decode only; visual timing/style still require rendered-frame review."}
    if report_path:
        write_json(report_path, result)
        result["report_path"] = str(report_path)
    return result


def tree_fingerprint(root):
    result = {}
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root))
        if path.is_symlink():
            result[relative] = {"symlink": str(path.readlink())}
        elif path.is_file():
            result[relative] = {"size": path.stat().st_size, "sha256": digest(path)}
    return result


def snapshot(args):
    draft = Path(args.draft).expanduser().resolve(strict=True)
    out = Path(args.out).expanduser().resolve()
    if not draft.is_dir() or not (draft / "draft_info.json").is_file() or not (draft / "draft_meta_info.json").is_file():
        raise ToolError("Snapshot source must be an explicit native draft directory with draft_info.json and draft_meta_info.json")
    if out.exists():
        raise ToolError(f"Snapshot destination already exists; nothing changed: {out}")
    if out == draft or out.is_relative_to(draft) or draft.is_relative_to(out):
        raise ToolError("Snapshot source and destination must not be equal or nested")
    before = tree_fingerprint(draft)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".jianying-snapshot-", dir=out.parent) as temporary:
        staging = Path(temporary) / "draft"
        shutil.copytree(draft, staging, symlinks=True)
        if before != tree_fingerprint(draft) or before != tree_fingerprint(staging):
            raise ToolError("Draft changed during snapshot or copied bytes differ; no snapshot published. Let autosave finish and retry.")
        staging.rename(out)
    return {"kind": "opaque_native_draft_snapshot", "source": str(draft), "snapshot": str(out),
            "file_count": len(before), "byte_identical": True, "source_modified": False,
            "native_data_parsed_or_decrypted": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe")
    sub = parser.add_subparsers(dest="command", required=True)
    commands = {}
    for name in ("prepare", "lookup", "resources", "verify", "snapshot"):
        command = sub.add_parser(name)
        command.add_argument("--ffmpeg", default=argparse.SUPPRESS)
        command.add_argument("--ffprobe", default=argparse.SUPPRESS)
        commands[name] = command
    commands["prepare"].add_argument("--reference", required=True)
    commands["prepare"].add_argument("--photo", required=True)
    commands["prepare"].add_argument("--out", required=True)
    commands["prepare"].add_argument("--thumbs", type=int, default=12, choices=range(4, 25), metavar="4..24")
    commands["prepare"].add_argument("--no-audio", action="store_true")
    commands["lookup"].add_argument("--reference", required=True)
    commands["resources"].add_argument("--query", required=True)
    commands["verify"].add_argument("--video", required=True)
    commands["verify"].add_argument("--reference")
    commands["verify"].add_argument("--out")
    commands["verify"].add_argument("--decode", action="store_true")
    commands["snapshot"].add_argument("--draft", required=True)
    commands["snapshot"].add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        result = globals()[args.command](args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "verify" and not result["technical_pass"]:
            return 1
        if args.command == "prepare" and result["session"].get("status") != "ready":
            return 1
        return 0
    except (ToolError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "error", "command": args.command, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
