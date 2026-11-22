"""Pure-stdlib Streamable HTTP JSON-RPC client for Meko Cloud MCP (v3.2.4+)."""

from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from meko_adlc.config import MekoConfig


class MekoToolError(RuntimeError):
    """Raised when Meko MCP returns an HTTP, JSON-RPC, or tool-level error."""


def parse_mcp_http_payload(raw_bytes: bytes, content_type: str = "") -> dict[str, Any]:
    """Parse either JSON or SSE (`data: ...`) Streamable HTTP MCP responses."""
    text = raw_bytes.decode("utf-8", errors="replace").strip()
    if not text:
        return {}
    if "text/event-stream" in (content_type or "").lower() or text.startswith("event:") or text.startswith("data:"):
        events: list[dict[str, Any]] = []
        for line in text.splitlines():
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload and payload != "[DONE]":
                    try:
                        parsed = json.loads(payload)
                        if isinstance(parsed, dict):
                            events.append(parsed)
                    except json.JSONDecodeError:
                        continue
        if not events:
            raise MekoToolError(f"Unparseable SSE payload from Meko MCP: {text[:240]}")
        return events[-1]
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise MekoToolError(f"Expected JSON object from Meko MCP, got {type(parsed).__name__}")
    return parsed


def unwrap_tool_result(rpc_response: dict[str, Any]) -> Any:
    """Extract tool result JSON and raise MekoToolError if inner payload contains `error`."""
    if "error" in rpc_response and rpc_response["error"]:
        raise MekoToolError(f"JSON-RPC error: {rpc_response['error']}")

    result = rpc_response.get("result")
    if result is None:
        return {}
    if result.get("isError"):
        raise MekoToolError(f"MCP tool returned isError=true: {json.dumps(result)[:400]}")

    candidate: Any = None
    sc = result.get("structuredContent")
    if isinstance(sc, dict) and "result" in sc:
        candidate = sc["result"]
    elif isinstance(sc, dict) and sc:
        candidate = sc

    if candidate is None:
        content = result.get("content") or []
        if content and isinstance(content[0], dict):
            candidate = content[0].get("text")

    if isinstance(candidate, str):
        stripped = candidate.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
            try:
                candidate = json.loads(stripped)
            except json.JSONDecodeError:
                pass

    if isinstance(candidate, dict) and candidate.get("error"):
        raise MekoToolError(f"Meko tool error: {json.dumps(candidate)[:500]}")

    return candidate if candidate is not None else result


def encode_multipart_form_data(
    fields: dict[str, Any],
    file_field_name: str,
    filename: str,
    file_bytes: bytes,
    boundary: str | None = None,
) -> tuple[bytes, str]:
    """Encode presigned S3 POST multipart/form-data keeping `fields` in order and `file` last."""
    b = boundary or f"----mekoadlc{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for k, v in fields.items():
        parts.append(
            (
                f"--{b}\r\n"
                f'Content-Disposition: form-data; name="{k}"\r\n\r\n'
                f"{v}\r\n"
            ).encode("utf-8")
        )
    parts.append(
        (
            f"--{b}\r\n"
            f'Content-Disposition: form-data; name="{file_field_name}"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(file_bytes)
    parts.append(f"\r\n--{b}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={b}"


def _as_json_str(value: dict[str, Any] | list[Any] | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _as_str_list(value: list[str] | str | None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(x) for x in value]
    return [str(value)]


class MekoMCPClient:
    """Synchronous, zero-dependency Streamable HTTP Meko MCP client."""

    def __init__(self, config: MekoConfig, timeout_s: float = 35.0) -> None:
        self.config = config
        self.timeout_s = timeout_s
        self._req_id = 0
        self._session_id: str | None = None
        self._initialized = False
        self._default_conversation_id: str | None = None

    def _mask(self, text: str) -> str:
        if self.config.api_key and self.config.api_key in text:
            return text.replace(self.config.api_key, "***REDACTED***")
        return text

    def _post_rpc(self, method: str, params: dict[str, Any] | None = None, *, is_notification: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if not is_notification:
            self._req_id += 1
            payload["id"] = self._req_id
        if params is not None:
            payload["params"] = params

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        req = urllib.request.Request(
            self.config.mcp_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                ct = resp.headers.get("Content-Type", "")
                sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
                if sid:
                    self._session_id = sid
                raw = resp.read()
                if is_notification or not raw:
                    return {}
                return parse_mcp_http_payload(raw, ct)
        except urllib.error.HTTPError as exc:
            body = self._mask(exc.read().decode("utf-8", errors="replace"))
            raise MekoToolError(f"Meko HTTP {exc.code}: {body[:500]}") from exc
        except urllib.error.URLError as exc:
            raise MekoToolError(f"Meko network error: {self._mask(str(exc))}") from exc

    def initialize(self) -> dict[str, Any]:
        if self._initialized:
            return {}
        resp = self._post_rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "contextcon-adlc", "version": "0.1.0"},
            },
        )
        self._initialized = True
        try:
            self._post_rpc("notifications/initialized", is_notification=True)
        except MekoToolError:
            pass
        return resp.get("result") or resp

    def tools_list(self) -> list[dict[str, Any]]:
        self.initialize()
        resp = self._post_rpc("tools/list", {})
        return (resp.get("result") or {}).get("tools") or []

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None, *, require_conv: bool = True) -> Any:
        self.initialize()
        args = {k: v for k, v in (arguments or {}).items() if v is not None and k != "scope"}
        if "datapack_id" not in args and name not in ("project_list",):
            args["datapack_id"] = self.config.datapack_id

        if require_conv and name != "conversation_create" and "conversation_id" not in args:
            args["conversation_id"] = self.ensure_conversation()

        resp = self._post_rpc("tools/call", {"name": name, "arguments": args})
        return unwrap_tool_result(resp)

    def ensure_conversation(self, title: str = "contextcon-adlc-session", agent_id: str = "contextcon-orchestrator") -> str:
        if not self._default_conversation_id:
            created = self.conversation_create(title=title, agent_id=agent_id)
            cid = created.get("conversation_id") or created.get("id")
            if not cid:
                raise MekoToolError(f"conversation_create did not return conversation_id: {created}")
            self._default_conversation_id = str(cid)
        return self._default_conversation_id

    def conversation_create(
        self,
        title: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        metadata: dict[str, Any] | str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        res = self.call_tool(
            "conversation_create",
            {
                "title": title,
                "agent_id": agent_id,
                "run_id": run_id,
                "metadata": _as_json_str(metadata),
                "session_id": session_id,
                "datapack_id": self.config.datapack_id,
            },
            require_conv=False,
        )
        return res if isinstance(res, dict) else {"raw": res}

    def conversation_add_message(
        self,
        conversation_id: str,
        user_input: str,
        assistant_output: str,
        agent_id: str | None = None,
        reasoning: str | None = None,
        plan: list[str] | str | None = None,
        metadata: dict[str, Any] | str | None = None,
        seed: str | None = None,
    ) -> dict[str, Any]:
        return self.call_tool(
            "conversation_add_message",
            {
                "conversation_id": conversation_id,
                "input": user_input,
                "output": assistant_output,
                "agent_id": agent_id,
                "reasoning": reasoning,
                "plan": _as_str_list(plan),
                "metadata": _as_json_str(metadata),
                "seed": seed,
            },
        )

    def conversation_get(
        self,
        conversation_id: str,
        include_messages: bool = True,
        limit: int = 50,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        return self.call_tool(
            "conversation_get",
            {
                "conversation_id": conversation_id,
                "include_messages": include_messages,
                "limit": limit,
                "agent_id": agent_id,
            },
        )

    def conversation_list(self, conversation_id: str | None = None, limit: int = 25, agent_id: str | None = None) -> Any:
        return self.call_tool(
            "conversation_list",
            {
                "conversation_id": conversation_id or self.ensure_conversation(),
                "limit": limit,
                "agent_id": agent_id,
            },
        )

    def context_search(
        self,
        query: str,
        conversation_id: str,
        agent_id: str | None = None,
        limit: int = 5,
        force_source: str | None = None,
        prompt: str | None = None,
    ) -> Any:
        return self.call_tool(
            "context_search",
            {
                "query": query,
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "limit": limit,
                "force_source": force_source,
                "prompt": prompt,
            },
        )

    def knowledgebase_search(self, query: str, conversation_id: str, agent_id: str | None = None, limit: int = 5) -> Any:
        return self.call_tool(
            "knowledgebase_search",
            {
                "query": query,
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "limit": limit,
            },
        )

    def knowledgebase_delete_document(self, document_id: str, conversation_id: str) -> Any:
        return self.call_tool(
            "knowledgebase_delete_document",
            {"document_id": document_id, "conversation_id": conversation_id},
        )

    def knowledgebase_upload_document(
        self,
        filename: str,
        raw_bytes: bytes,
        conversation_id: str,
        agent_id: str | None = None,
        poll_timeout_s: float = 90.0,
        wait_for_index: bool = True,
    ) -> dict[str, Any]:
        sha_hex = hashlib.sha256(raw_bytes).hexdigest()
        head_b64 = base64.b64encode(raw_bytes[:3072]).decode("ascii")
        init_res = self.call_tool(
            "knowledgebase_upload_document",
            {
                "filename": filename,
                "size": len(raw_bytes),
                "content_hash": sha_hex,
                "conversation_id": conversation_id,
                "content_head_base64": head_b64,
                "agent_id": agent_id,
            },
        )
        if not isinstance(init_res, dict):
            raise MekoToolError(f"Unexpected knowledgebase_upload_document response: {init_res}")

        doc_key = init_res.get("key") or init_res.get("document_key")
        already_uploaded = bool(init_res.get("already_uploaded"))
        post_url = init_res.get("url") or init_res.get("upload_url")
        fields = init_res.get("fields")

        if post_url and not already_uploaded:
            if isinstance(fields, dict) and fields:
                body, content_type = encode_multipart_form_data(fields, "file", filename, raw_bytes)
                req = urllib.request.Request(
                    post_url,
                    data=body,
                    headers={"Content-Type": content_type, "Content-Length": str(len(body))},
                    method="POST",
                )
            else:
                req = urllib.request.Request(post_url, data=raw_bytes, method="PUT")
            try:
                with urllib.request.urlopen(req, timeout=45.0) as resp:
                    if resp.status not in (200, 201, 204):
                        raise MekoToolError(f"S3 upload failed with HTTP {resp.status}")
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="replace")[:400]
                raise MekoToolError(f"S3 upload HTTP {exc.code}: {err_body}") from exc

        status_res: Any = init_res
        if wait_for_index and doc_key:
            status_res = self.wait_for_document_indexed(str(doc_key), conversation_id, agent_id=agent_id, timeout_s=poll_timeout_s)

        return {"init": init_res, "document_key": doc_key, "already_uploaded": already_uploaded, "status": status_res}

    def wait_for_document_indexed(
        self,
        document_key: str,
        conversation_id: str,
        agent_id: str | None = None,
        timeout_s: float = 90.0,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        last: Any = {}
        while time.monotonic() < deadline:
            last = self.call_tool(
                "knowledgebase_document_status",
                {
                    "document_key": document_key,
                    "conversation_id": conversation_id,
                    "agent_id": agent_id,
                },
            )
            state = str((last or {}).get("state") or (last or {}).get("status") or "").lower()
            if state in ("indexed", "completed", "ready", "success", "done"):
                return last
            if state in ("failed", "error"):
                raise MekoToolError(f"KB indexing failed for {document_key}: {last}")
            time.sleep(3.0)
        return last

    def memory_add(
        self,
        text: str,
        conversation_id: str,
        agent_id: str | None = None,
        run_id: str | None = None,
        metadata: dict[str, Any] | str | None = None,
        messages: list[dict[str, str]] | str | None = None,
    ) -> Any:
        return self.call_tool(
            "memory_add",
            {
                "text": text,
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "run_id": run_id,
                "metadata": _as_json_str(metadata),
                "messages": _as_json_str(messages),
            },
        )

    def memory_search(
        self,
        query: str,
        conversation_id: str,
        agent_id: str | None = None,
        limit: int = 5,
        run_id: str | None = None,
    ) -> Any:
        return self.call_tool(
            "memory_search",
            {
                "query": query,
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "limit": limit,
                "run_id": run_id,
            },
        )

    def memory_get_all(self, conversation_id: str, page: int = 1, page_size: int = 50, promoted: bool | None = None) -> Any:
        return self.call_tool(
            "memory_get_all",
            {
                "conversation_id": conversation_id,
                "page": page,
                "page_size": page_size,
                "promoted": promoted,
            },
        )

    def memory_promote(self, memory_ids: list[str], conversation_id: str, agent_id: str | None = None) -> Any:
        return self.call_tool(
            "memory_promote",
            {
                "memory_ids": memory_ids,
                "conversation_id": conversation_id,
                "agent_id": agent_id,
            },
        )

    def track_token_usage(
        self,
        conversation_id: str,
        name: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
        message_id: str | None = None,
    ) -> Any:
        return self.call_tool(
            "track_token_usage",
            {
                "conversation_id": conversation_id,
                "name": name,
                "input_tokens": int(input_tokens),
                "output_tokens": int(output_tokens),
                "total_tokens": int(input_tokens) + int(output_tokens),
                "model": model,
                "message_id": message_id,
            },
        )

    def artifact_put(
        self,
        filename: str,
        raw_bytes: bytes,
        conversation_id: str,
        content_type: str = "text/plain",
        agent_id: str | None = None,
    ) -> Any:
        return self.call_tool(
            "artifact_put",
            {
                "filename": filename,
                "content_base64": base64.b64encode(raw_bytes).decode("ascii"),
                "content_type": content_type,
                "conversation_id": conversation_id,
                "agent_id": agent_id,
            },
        )

    def artifact_get(self, content_hash: str, conversation_id: str, agent_id: str | None = None) -> Any:
        return self.call_tool(
            "artifact_get",
            {
                "content_hash": content_hash,
                "conversation_id": conversation_id,
                "agent_id": agent_id,
            },
        )

    def datapack_describe(self, conversation_id: str, include_status: bool = True) -> Any:
        return self.call_tool(
            "datapack_describe",
            {
                "datapack_id": self.config.datapack_id,
                "include_status": include_status,
                "conversation_id": conversation_id,
            },
        )

    def amp_core_budget(self, conversation_id: str) -> Any:
        return self.call_tool("amp_core_budget", {"conversation_id": conversation_id})

    def amp_cluster_delete(self, cluster_id: str, conversation_id: str) -> Any:
        return self.call_tool("amp_cluster_delete", {"cluster_id": cluster_id, "conversation_id": conversation_id})

    def amp_cluster_list(self, conversation_id: str) -> Any:
        return self.call_tool("amp_cluster_list", {"conversation_id": conversation_id})

    def amp_cluster_create(self, name: str, conversation_id: str, **kwargs: Any) -> Any:
        args = {"name": name, "conversation_id": conversation_id, **kwargs}
        return self.call_tool("amp_cluster_create", args)

    def amp_branch_list(self, cluster_id: str, conversation_id: str) -> Any:
        return self.call_tool("amp_branch_list", {"cluster_id": cluster_id, "conversation_id": conversation_id})

    def amp_branch_create(self, cluster_id: str, name: str, conversation_id: str, **kwargs: Any) -> Any:
        args = {"cluster_id": cluster_id, "name": name, "conversation_id": conversation_id, **kwargs}
        return self.call_tool("amp_branch_create", args)

    def amp_compute_create(self, cluster_id: str, branch_id: str, conversation_id: str, **kwargs: Any) -> Any:
        args = {"cluster_id": cluster_id, "branch_id": branch_id, "conversation_id": conversation_id, **kwargs}
        return self.call_tool("amp_compute_create", args)

    def amp_compute_list(self, cluster_id: str, branch_id: str, conversation_id: str) -> Any:
        return self.call_tool(
            "amp_compute_list",
            {"cluster_id": cluster_id, "branch_id": branch_id, "conversation_id": conversation_id},
        )

    def amp_compute_get(self, cluster_id: str, branch_id: str, compute_id: str, conversation_id: str) -> Any:
        return self.call_tool(
            "amp_compute_get",
            {"cluster_id": cluster_id, "branch_id": branch_id, "compute_id": compute_id, "conversation_id": conversation_id},
        )

    def amp_compute_delete(self, cluster_id: str, branch_id: str, compute_id: str, conversation_id: str) -> Any:
        return self.call_tool(
            "amp_compute_delete",
            {"cluster_id": cluster_id, "branch_id": branch_id, "compute_id": compute_id, "conversation_id": conversation_id},
        )

    def amp_branch_delete(self, cluster_id: str, branch_id: str, conversation_id: str) -> Any:
        return self.call_tool(
            "amp_branch_delete",
            {"cluster_id": cluster_id, "branch_id": branch_id, "conversation_id": conversation_id},
        )

    def selflearning_status(self, conversation_id: str, last: str = "7d") -> Any:
        return self.call_tool("selflearning_status", {"conversation_id": conversation_id, "last": str(last)})

    def selflearning_query_log(self, conversation_id: str, band: str = "low", page: int = 1, last: str = "7d") -> Any:
        return self.call_tool(
            "selflearning_query_log",
            {"conversation_id": conversation_id, "band": band, "page": int(page), "last": str(last)},
        )

    def selflearning_shortfalls(self, todo_id: str, conversation_id: str, page: int = 1, last: str = "7d") -> Any:
        return self.call_tool(
            "selflearning_shortfalls",
            {"todo_id": todo_id, "conversation_id": conversation_id, "page": int(page), "last": str(last)},
        )

    def selflearning_verify(self, conversation_id: str, log_id: str | None = None, test_prompt_id: str | None = None) -> Any:
        return self.call_tool(
            "selflearning_verify",
            {"conversation_id": conversation_id, "log_id": log_id, "test_prompt_id": test_prompt_id},
        )
