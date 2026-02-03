from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    embedding: List[float]
    model: str
    provider: str
    tokens_used: int = 0
    cached: bool = False


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: List[str], model: Optional[str] = None) -> List[EmbeddingResult]:
        pass

    @abstractmethod
    async def embed_batch(
        self, texts: List[str], batch_size: int = 32, model: Optional[str] = None
    ) -> List[EmbeddingResult]:
        pass

    @abstractmethod
    def get_model_info(self, model: Optional[str] = None) -> Dict[str, Any]:
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "text-embedding-3-small",
        timeout_sec: int = 60,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout_sec = timeout_sec
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout_sec)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def embed(self, texts: List[str], model: Optional[str] = None) -> List[EmbeddingResult]:
        if not texts:
            return []

        model_name = model or self.default_model
        results = await self._call_api(texts, model_name)
        return results

    async def embed_batch(
        self, texts: List[str], batch_size: int = 32, model: Optional[str] = None
    ) -> List[EmbeddingResult]:
        if not texts:
            return []

        all_results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_results = await self.embed(batch, model)
            all_results.extend(batch_results)

        return all_results

    async def _call_api(self, texts: List[str], model: str) -> List[EmbeddingResult]:
        client = await self._get_client()

        payload = {
            "input": texts,
            "model": model,
            "encoding_format": "float",
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/embeddings"

        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            results = []
            for idx, item in enumerate(data["data"]):
                result = EmbeddingResult(
                    embedding=item["embedding"],
                    model=model,
                    provider="openai",
                    tokens_used=data.get("usage", {}).get("total_tokens", 0) // len(texts),
                )
                results.append(result)

            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI embedding API error: {e.response.text}")
            raise ValueError(f"OpenAI API error: {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            raise ValueError(f"OpenAI embedding failed: {e}") from e

    def get_model_info(self, model: Optional[str] = None) -> Dict[str, Any]:
        model_name = model or self.default_model
        model_info = {
            "text-embedding-3-small": {"dims": 1536, "max_tokens": 8191},
            "text-embedding-3-large": {"dims": 3072, "max_tokens": 8191},
            "text-embedding-ada-002": {"dims": 1536, "max_tokens": 8191},
        }
        return model_info.get(model_name, {"dims": 1536, "max_tokens": 8191})


class GLMEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://open.bigmodel.cn/api/paas/v4",
        default_model: str = "embedding-2",
        timeout_sec: int = 60,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout_sec = timeout_sec
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout_sec)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def embed(self, texts: List[str], model: Optional[str] = None) -> List[EmbeddingResult]:
        if not texts:
            return []

        model_name = model or self.default_model
        results = await self._call_api(texts, model_name)
        return results

    async def embed_batch(
        self, texts: List[str], batch_size: int = 32, model: Optional[str] = None
    ) -> List[EmbeddingResult]:
        all_results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_results = await self.embed(batch, model)
            all_results.extend(batch_results)
        return all_results

    async def _call_api(self, texts: List[str], model: str) -> List[EmbeddingResult]:
        client = await self._get_client()

        results = []
        for text in texts:
            payload = {
                "model": model,
                "input": text,
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            url = f"{self.base_url}/embeddings"

            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                result = EmbeddingResult(
                    embedding=data["data"][0]["embedding"],
                    model=model,
                    provider="glm",
                    tokens_used=data.get("usage", {}).get("total_tokens", 0),
                )
                results.append(result)

            except httpx.HTTPStatusError as e:
                logger.error(f"GLM embedding API error: {e.response.text}")
                raise ValueError(f"GLM API error: {e.response.status_code}") from e
            except Exception as e:
                logger.error(f"GLM embedding error: {e}")
                raise ValueError(f"GLM embedding failed: {e}") from e

        return results

    def get_model_info(self, model: Optional[str] = None) -> Dict[str, Any]:
        model_name = model or self.default_model
        model_info = {
            "embedding-2": {"dims": 1024, "max_tokens": 8192},
            "embedding-3": {"dims": 1024, "max_tokens": 8192},
        }
        return model_info.get(model_name, {"dims": 1024, "max_tokens": 8192})


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        model_path: str = "BAAI/bge-small-zh-v1.5",
        device: str = "cpu",
        default_model: Optional[str] = None,
    ):
        self.model_path = model_path
        self.device = device
        self.default_model = default_model or model_path
        self._model = None
        self._tokenizer = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_path, device=self.device)
                logger.info(f"Loaded local embedding model: {self.model_path}")
            except ImportError:
                logger.error("sentence-transformers not installed")
                raise ValueError("sentence-transformers is required for local embeddings")
            except Exception as e:
                logger.error(f"Failed to load local model: {e}")
                raise ValueError(f"Failed to load local embedding model: {e}") from e

    async def embed(self, texts: List[str], model: Optional[str] = None) -> List[EmbeddingResult]:
        if not texts:
            return []

        self._load_model()

        embeddings = self._model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        results = [
            EmbeddingResult(
                embedding=embedding.tolist(),
                model=self.default_model,
                provider="local",
            )
            for embedding in embeddings
        ]

        return results

    async def embed_batch(
        self, texts: List[str], batch_size: int = 32, model: Optional[str] = None
    ) -> List[EmbeddingResult]:
        return await self.embed(texts, model)

    def get_model_info(self, model: Optional[str] = None) -> Dict[str, Any]:
        if self._model:
            dims = self._model.get_sentence_embedding_dimension()
        else:
            dims = 512
        return {"dims": dims, "max_tokens": 512}


async def create_embedding_provider(
    provider_type: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> EmbeddingProvider:
    provider_type = provider_type.lower()

    if provider_type == "openai":
        if not api_key:
            raise ValueError("OpenAI API key is required")
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1",
            default_model=model or "text-embedding-3-small",
            **kwargs,
        )

    elif provider_type == "glm":
        if not api_key:
            raise ValueError("GLM API key is required")
        return GLMEmbeddingProvider(
            api_key=api_key,
            base_url=base_url or "https://open.bigmodel.cn/api/paas/v4",
            default_model=model or "embedding-2",
            **kwargs,
        )

    elif provider_type == "local":
        return LocalEmbeddingProvider(
            model_path=kwargs.get("model_path", "BAAI/bge-small-zh-v1.5"),
            device=kwargs.get("device", "cpu"),
            default_model=model,
        )

    else:
        raise ValueError(f"Unknown embedding provider: {provider_type}")
