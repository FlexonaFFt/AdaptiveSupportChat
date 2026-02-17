import asyncio
import json
import ssl
import time
import uuid
from typing import Optional
from urllib import error, parse, request


class LLMApiError(Exception):
    pass


class LLMApiClient:
    def __init__(
        self,
        provider: str,
        model: str,
        timeout_seconds: int,
        openai_api_url: str = "",
        openai_api_key: str = "",
        gigachat_api_url: str = "",
        gigachat_auth_url: str = "",
        gigachat_auth_key: str = "",
        gigachat_scope: str = "GIGACHAT_API_PERS",
        gigachat_verify_ssl: bool = True,
    ):
        self._provider = provider.strip().lower()
        self._model = model
        self._timeout_seconds = timeout_seconds

        self._openai_api_url = openai_api_url
        self._openai_api_key = openai_api_key

        self._gigachat_api_url = gigachat_api_url
        self._gigachat_auth_url = gigachat_auth_url
        self._gigachat_auth_key = gigachat_auth_key
        self._gigachat_scope = gigachat_scope
        self._gigachat_verify_ssl = gigachat_verify_ssl

        self._gigachat_access_token: str = ""
        self._gigachat_token_expiry_ts: float = 0.0

    @property
    def model(self) -> str:
        return self._model

    async def ask(
        self,
        user_text: str,
        context: str = "",
        chat_history: Optional[list[dict[str, str]]] = None,
    ) -> str:
        if not user_text.strip():
            raise LLMApiError("Empty question.")
        return await asyncio.to_thread(self._ask_sync, user_text, context, chat_history)

    def _ask_sync(
        self,
        user_text: str,
        context: str,
        chat_history: Optional[list[dict[str, str]]],
    ) -> str:
        if self._provider == "gigachat":
            return self._ask_gigachat_sync(user_text, context, chat_history)
        return self._ask_openai_compatible_sync(user_text, context, chat_history)

    def _ask_openai_compatible_sync(
        self,
        user_text: str,
        context: str,
        chat_history: Optional[list[dict[str, str]]],
    ) -> str:
        if not self._openai_api_key:
            raise LLMApiError("LLM_API_KEY is not configured.")
        if not self._openai_api_url:
            raise LLMApiError("LLM_API_URL is not configured.")
        return self._chat_completion_request(
            api_url=self._openai_api_url,
            bearer_token=self._openai_api_key,
            user_text=user_text,
            context=context,
            chat_history=chat_history,
            ssl_context=None,
        )

    def _ask_gigachat_sync(
        self,
        user_text: str,
        context: str,
        chat_history: Optional[list[dict[str, str]]],
    ) -> str:
        if not self._gigachat_api_url:
            raise LLMApiError("GIGACHAT_API_URL is not configured.")
        access_token = self._ensure_gigachat_access_token()
        ssl_context = None
        if not self._gigachat_verify_ssl:
            ssl_context = ssl._create_unverified_context()
        return self._chat_completion_request(
            api_url=self._gigachat_api_url,
            bearer_token=access_token,
            user_text=user_text,
            context=context,
            chat_history=chat_history,
            ssl_context=ssl_context,
        )

    def _chat_completion_request(
        self,
        api_url: str,
        bearer_token: str,
        user_text: str,
        context: str,
        chat_history: Optional[list[dict[str, str]]],
        ssl_context: ssl.SSLContext | None,
    ) -> str:
        system_prompt = (
            "Ты ассистент службы поддержки. Отвечай кратко и по делу. "
            "Используй только факты из блока КОНТЕКСТ. "
            "Учитывай историю диалога при формировании ответа. "
            "Если в вопросе не хватает критичных деталей (товар, номер заказа, регион, срок), "
            "сначала задай один короткий уточняющий вопрос, а не давай предположений. "
            "Если фактов недостаточно, предложи подключить оператора. "
            "Не упоминай слова 'контекст', 'база знаний', 'retrieval', 'RAG', "
            "'источник документа' или внутреннюю логику системы."
        )
        user_payload = user_text
        if context.strip():
            user_payload = f"КОНТЕКСТ:\n{context}\n\nВОПРОС:\n{user_text}"
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]
        for item in chat_history or []:
            role = str(item.get("role", "")).strip()
            content = str(item.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_payload})
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(api_url, data=body, headers=headers, method="POST")
        raw = self._send_request(req=req, ssl_context=ssl_context)
        try:
            parsed = json.loads(raw)
            content = parsed["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMApiError("LLM API returned unexpected response format.") from exc

        answer = str(content).strip()
        if not answer:
            raise LLMApiError("LLM API returned empty answer.")
        return answer

    def _ensure_gigachat_access_token(self) -> str:
        now = time.time()
        if self._gigachat_access_token and now < self._gigachat_token_expiry_ts - 30:
            return self._gigachat_access_token
        self._refresh_gigachat_access_token()
        if not self._gigachat_access_token:
            raise LLMApiError("Failed to get GigaChat access token.")
        return self._gigachat_access_token

    def _refresh_gigachat_access_token(self) -> None:
        if not self._gigachat_auth_key:
            raise LLMApiError("GIGACHAT_AUTH_KEY is not configured.")
        if not self._gigachat_auth_url:
            raise LLMApiError("GIGACHAT_AUTH_URL is not configured.")

        payload = parse.urlencode({"scope": self._gigachat_scope}).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._gigachat_auth_key}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        req = request.Request(
            self._gigachat_auth_url,
            data=payload,
            headers=headers,
            method="POST",
        )
        ssl_context = None
        if not self._gigachat_verify_ssl:
            ssl_context = ssl._create_unverified_context()
        raw = self._send_request(req=req, ssl_context=ssl_context)
        try:
            parsed = json.loads(raw)
            access_token = str(parsed.get("access_token", "")).strip()
            expires_at_ms = int(parsed.get("expires_at", 0))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise LLMApiError("Invalid GigaChat OAuth response.") from exc

        if not access_token:
            raise LLMApiError("GigaChat OAuth response has empty access_token.")

        if expires_at_ms > 0:
            self._gigachat_token_expiry_ts = expires_at_ms / 1000.0
        else:
            self._gigachat_token_expiry_ts = time.time() + 1500
        self._gigachat_access_token = access_token

    def _send_request(
        self,
        req: request.Request,
        ssl_context: ssl.SSLContext | None,
    ) -> str:
        try:
            with request.urlopen(
                req,
                timeout=self._timeout_seconds,
                context=ssl_context,
            ) as resp:
                return resp.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise LLMApiError(f"LLM API HTTP {exc.code}: {details}") from exc
        except error.URLError as exc:
            raise LLMApiError(f"LLM API connection error: {exc}") from exc
