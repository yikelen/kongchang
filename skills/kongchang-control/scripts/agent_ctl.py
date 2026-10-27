#!/usr/bin/env python3
"""Call the local Kongchang Agent service; output exactly one JSON response."""
from __future__ import annotations

import argparse
import json
import math
import os
import socket
import sys
import uuid
from pathlib import Path
from typing import Any

HOST = "127.0.0.1"
PROTOCOL = 1
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
SKILL_DIR = Path(__file__).resolve().parent.parent


def default_app_dir() -> Path | None:
    """Locate the installed app without depending on the working directory."""
    env_dir = os.environ.get("KONGCHANG_HOME")
    if env_dir:
        return Path(env_dir)
    config = SKILL_DIR / "app-location.json"
    if config.is_file():
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
            app_dir = data.get("app_dir") if isinstance(data, dict) else None
            if isinstance(app_dir, str) and app_dir:
                return Path(app_dir)
        except (OSError, ValueError, UnicodeError):
            pass
    # Source tree or portable archive: app/skills/kongchang-control/scripts/...
    parent = SKILL_DIR.parent.parent
    if (parent / "src" / "agent_api.py").is_file() and (parent / "scripts" / "run_app.py").is_file():
        return parent
    return None


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def error(code: str, message: str, request_id: str | None = None) -> dict[str, Any]:
    return {"id": request_id, "ok": False, "error": {"code": code, "message": message}}


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON 有重复字段")
        result[key] = value
    return result


def _invalid_constant(_value: str) -> None:
    raise ValueError("JSON 不允许非有限数字")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("JSON 数字必须是有限值")
    return number


def parse_object(text: str) -> dict[str, Any]:
    value = json.loads(text, object_pairs_hook=_reject_duplicates,
                       parse_constant=_invalid_constant, parse_float=_finite_float)
    if not isinstance(value, dict):
        raise ValueError("参数必须是 JSON 对象")
    return value


def call(method: str, params: dict[str, Any], discovery_path: Path,
         timeout: float = 30.0) -> dict[str, Any]:
    request_id = uuid.uuid4().hex
    if not math.isfinite(timeout) or timeout <= 0:
        return error("invalid_argument", "超时必须是大于零的有限数字", request_id)
    if not isinstance(method, str) or not method or len(method) > 128:
        return error("invalid_argument", "method 无效", request_id)
    if not isinstance(params, dict):
        return error("invalid_argument", "参数必须是 JSON 对象", request_id)
    try:
        discovery = parse_object(discovery_path.read_text(encoding="utf-8"))
        host, port, token = discovery.get("host"), discovery.get("port"), discovery.get("token")
        if (host != HOST or isinstance(port, bool) or not isinstance(port, int)
                or not 1 <= port <= 65535 or not isinstance(token, str) or not token
                or discovery.get("protocol") != PROTOCOL):
            return error("invalid_discovery", "Agent 服务信息无效", request_id)
    except FileNotFoundError:
        return error("not_running", "未找到 Agent 服务；请先启动简易控场", request_id)
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
        return error("invalid_discovery", "无法读取 Agent 服务信息", request_id)
    try:
        request = {"token": token, "id": request_id, "method": method, "params": params}
        payload = json.dumps(request, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if len(payload) > MAX_REQUEST_BYTES:
            return error("request_too_large", "请求超过大小限制", request_id)
        with socket.create_connection((HOST, port), timeout=timeout) as conn:
            conn.settimeout(timeout)
            conn.sendall(payload + b"\n")
            response = bytearray()
            while b"\n" not in response:
                chunk = conn.recv(min(65536, MAX_RESPONSE_BYTES + 1 - len(response)))
                if not chunk:
                    return error("connection_closed", "Agent 服务未返回完整响应", request_id)
                response.extend(chunk)
                if len(response) > MAX_RESPONSE_BYTES:
                    return error("response_too_large", "响应超过大小限制", request_id)
        first, _, rest = bytes(response).partition(b"\n")
        if rest:
            return error("invalid_response", "Agent 服务返回了多余数据", request_id)
        result = parse_object(first.decode("utf-8", errors="strict"))
        if result.get("id") != request_id or not isinstance(result.get("ok"), bool):
            return error("invalid_response", "Agent 服务响应格式无效", request_id)
        if result["ok"] and "result" not in result:
            return error("invalid_response", "Agent 服务响应缺少结果", request_id)
        if not result["ok"] and not isinstance(result.get("error"), dict):
            return error("invalid_response", "Agent 服务响应缺少错误信息", request_id)
        return result
    except (socket.timeout, TimeoutError):
        return error("timeout", "等待 Agent 服务响应超时", request_id)
    except OSError:
        return error("connection_failed", "无法连接 Agent 服务，请确认软件正在运行", request_id)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return error("invalid_response", "无法处理 Agent 请求或响应", request_id)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    parser = ArgumentParser(description="调用正在运行的简易控场 Agent 服务")
    subcommands = parser.add_subparsers(dest="command", required=True)
    command = subcommands.add_parser("call", help="发送一个命令")
    command.add_argument("method", help="接口方法名")
    inputs = command.add_mutually_exclusive_group()
    inputs.add_argument("--params", help="JSON 对象参数")
    inputs.add_argument("--params-file", help="从 UTF-8 文件读取 JSON 对象；- 表示标准输入")
    location = command.add_mutually_exclusive_group()
    location.add_argument("--app-dir", type=Path, default=None,
                          help="控场软件目录；默认读取 KONGCHANG_HOME、安装配置或便携包位置")
    location.add_argument("--discovery", type=Path, default=None, help="Agent 服务信息文件")
    command.add_argument("--timeout", type=float, default=30.0, help="连接和响应超时，单位秒")
    try:
        args = parser.parse_args(argv)
        if args.params_file:
            text = sys.stdin.read() if args.params_file == "-" else Path(args.params_file).read_text(encoding="utf-8-sig")
            params = parse_object(text)
        else:
            params = parse_object(args.params if args.params is not None else "{}")
        app_dir = args.app_dir or default_app_dir()
        if args.discovery is None and app_dir is None:
            response = error("not_configured", "找不到软件目录；请使用 --app-dir 指定，或重新安装 Skill")
        else:
            discovery = args.discovery or app_dir / "data" / "agent-control.json"
            response = call(args.method, params, discovery, args.timeout)
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
        response = error("invalid_argument", str(exc))
    print(json.dumps(response, ensure_ascii=False, allow_nan=False, separators=(",", ":")))
    return 0 if response["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
