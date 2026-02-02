from __future__ import annotations

import base64
import io
import logging
import math
import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx

logger = logging.getLogger(__name__)

try:  # optional dependency
    from PIL import Image
except ImportError as e:  # pragma: no cover - optional dependency
    logger.warning(f"PIL not available for image processing: {e}")
    Image = None
except Exception as e:
    logger.error(f"Unexpected error importing PIL: {e}")
    Image = None

try:  # optional dependency
    import numpy as np
except ImportError as e:  # pragma: no cover - optional dependency
    logger.warning(f"NumPy not available: {e}")
    np = None
except Exception as e:
    logger.error(f"Unexpected error importing NumPy: {e}")
    np = None


@dataclass
class VisionConfig:
    face_model_path: str = ""
    object_model_path: str = ""
    device: str = "cpu"
    face_backend: str = "auto"
    face_match_threshold: float = 0.35
    face_min_confidence: float = 0.5
    object_min_confidence: float = 0.25
    max_faces: int = 5


def _error(code: str, detail: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"error": code}
    if detail:
        payload["detail"] = detail
    return payload


def decode_image_input(image: Any) -> Optional["Image.Image"]:
    if Image is None:
        return None
    if image is None:
        return None
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    if isinstance(image, bytes):
        return _decode_image_bytes(image)
    if isinstance(image, dict):
        if isinstance(image.get("base64"), str):
            return _decode_image_base64(image["base64"])
        if isinstance(image.get("data"), str):
            return _decode_image_base64(image["data"])
        if isinstance(image.get("url"), str):
            return _download_image(image["url"])
        if isinstance(image.get("path"), str):
            return _read_image(image["path"])
        return None
    if isinstance(image, str):
        if image.startswith("http://") or image.startswith("https://"):
            return _download_image(image)
        if os.path.isfile(image):
            return _read_image(image)
        return _decode_image_base64(image)
    return None


def _decode_image_bytes(data: bytes) -> Optional["Image.Image"]:
    if Image is None:
        return None
    try:
        return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return None


def _decode_image_base64(value: str) -> Optional["Image.Image"]:
    if not value:
        return None
    if "," in value and value.strip().startswith("data:"):
        value = value.split(",", 1)[1]
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception:
        return None
    return _decode_image_bytes(raw)


def _download_image(url: str) -> Optional["Image.Image"]:
    try:
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
        return _decode_image_bytes(resp.content)
    except Exception:
        return None


def _read_image(path: str) -> Optional["Image.Image"]:
    try:
        with open(path, "rb") as handle:
            return _decode_image_bytes(handle.read())
    except Exception:
        return None


def _resolve_model_path(path: str) -> str:
    if not path:
        return path
    if os.path.isfile(path):
        return path
    cwd_candidate = os.path.join(os.getcwd(), path)
    if os.path.isfile(cwd_candidate):
        return cwd_candidate
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_candidate = os.path.join(here, os.pardir, path)
    repo_candidate = os.path.normpath(repo_candidate)
    if os.path.isfile(repo_candidate):
        return repo_candidate
    return path


def _tensor_to_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, list):
        return value
    return list(value)


def _clip_box(box: Sequence[float], width: int, height: int) -> Tuple[int, int, int, int]:
    if len(box) < 4:
        return 0, 0, width, height
    x1, y1, x2, y2 = box[:4]
    x1 = max(0, min(int(round(x1)), width - 1))
    x2 = max(0, min(int(round(x2)), width - 1))
    y1 = max(0, min(int(round(y1)), height - 1))
    y2 = max(0, min(int(round(y2)), height - 1))
    if x2 <= x1:
        x2 = min(width - 1, x1 + 1)
    if y2 <= y1:
        y2 = min(height - 1, y1 + 1)
    return x1, y1, x2, y2


def _cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 1.0
    if len(a) != len(b):
        return 1.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for av, bv in zip(a, b):
        dot += float(av) * float(bv)
        norm_a += float(av) ** 2
        norm_b += float(bv) ** 2
    denom = math.sqrt(norm_a) * math.sqrt(norm_b)
    if denom <= 0:
        return 1.0
    return 1.0 - (dot / denom)


class VisionClient:
    def __init__(self, config: VisionConfig, db: Optional[object] = None) -> None:
        self.config = config
        self.db = db
        self._face_detector = None
        self._object_detector = None
        self._embedder = None
        self._embedder_backend = ""

    def detect(
        self,
        image: Any,
        model: str = "object",
        min_conf: Optional[float] = None,
        max_det: Optional[int] = None,
        match_faces: bool = False,
        top_k: int = 3,
    ) -> Dict[str, Any]:
        img = decode_image_input(image)
        if img is None:
            return _error("image_invalid")

        model = (model or "object").lower()
        if model == "face":
            detections = self._detect_faces(img, min_conf=min_conf, max_det=max_det)
            if "error" in detections:
                return detections
            response: Dict[str, Any] = {
                "model": "face",
                "detections": detections,
            }
            if match_faces:
                response["matches"] = self.identify_faces(img, detections, top_k=top_k)
            return response

        detections = self._detect_objects(img, min_conf=min_conf, max_det=max_det)
        if "error" in detections:
            return detections
        return {"model": "object", "detections": detections}

    def enroll_face(self, label: str, image: Any, face_index: int = 0) -> Dict[str, Any]:
        if not label:
            return _error("label_required")
        if self.db is None:
            return _error("db_not_available")
        img = decode_image_input(image)
        if img is None:
            return _error("image_invalid")

        detections = self._detect_faces(img, max_det=self.config.max_faces)
        if "error" in detections:
            return detections
        if not detections:
            return _error("face_not_found")

        index = max(0, min(int(face_index), len(detections) - 1))
        faces = self._crop_faces(img, detections)
        if not faces:
            return _error("face_crop_failed")
        embedding = self._embed_faces(faces)[index]
        if embedding is None:
            return _error("face_embedding_failed")

        record = {
            "faceprint_id": str(uuid.uuid4()),
            "label": label,
            "embedding": embedding,
            "created_ts": int(math.floor(self._now_ts())),
            "meta": {
                "source": "face_enroll",
                "model": self._embedder_backend,
                "detector": "yolo",
                "bbox": detections[index].get("bbox"),
                "confidence": detections[index].get("confidence"),
            },
        }
        self.db.insert_faceprint(record)
        return {
            "faceprint_id": record["faceprint_id"],
            "label": label,
            "confidence": detections[index].get("confidence"),
        }

    def verify_face(
        self,
        image: Any,
        label: Optional[str] = None,
        faceprint_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self.db is None:
            return _error("db_not_available")
        img = decode_image_input(image)
        if img is None:
            return _error("image_invalid")

        detections = self._detect_faces(img, max_det=1)
        if "error" in detections:
            return detections
        if not detections:
            return _error("face_not_found")
        faces = self._crop_faces(img, detections)
        if not faces:
            return _error("face_crop_failed")
        embedding = self._embed_faces(faces)[0]
        if embedding is None:
            return _error("face_embedding_failed")

        records = self._select_faceprints(label=label, faceprint_id=faceprint_id)
        if not records:
            return _error("faceprint_not_found")

        best = self._best_match(embedding, records)
        threshold = float(self.config.face_match_threshold or 0.35)
        match = best["distance"] <= threshold
        return {
            "match": match,
            "threshold": threshold,
            "distance": best["distance"],
            "label": best["label"],
            "faceprint_id": best["faceprint_id"],
        }

    def identify_faces(
        self,
        image: Any,
        detections: Optional[List[Dict[str, Any]]] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        img = decode_image_input(image)
        if img is None:
            return []
        records = self._select_faceprints()
        if not records:
            return []
        if detections is None:
            detections = self._detect_faces(img, max_det=self.config.max_faces)
            if "error" in detections:
                return []
        if not detections:
            return []
        faces = self._crop_faces(img, detections)
        embeddings = self._embed_faces(faces)
        output: List[Dict[str, Any]] = []
        for idx, embedding in enumerate(embeddings):
            if embedding is None:
                output.append({"index": idx, "matches": []})
                continue
            matches = self._rank_matches(embedding, records, top_k=max(1, int(top_k)))
            threshold = float(self.config.face_match_threshold or 0.35)
            best = matches[0] if matches else None
            output.append(
                {
                    "index": idx,
                    "bbox": detections[idx].get("bbox"),
                    "confidence": detections[idx].get("confidence"),
                    "matches": matches,
                    "best": best,
                    "threshold": threshold,
                }
            )
        return output

    def _detect_faces(
        self, img: "Image.Image", min_conf: Optional[float] = None, max_det: Optional[int] = None
    ) -> List[Dict[str, Any]] | Dict[str, Any]:
        detector = self._load_face_detector()
        if detector is None:
            return _error("face_detector_not_available")
        result = self._run_detector(
            detector,
            img,
            min_conf=min_conf if min_conf is not None else self.config.face_min_confidence,
            max_det=max_det if max_det is not None else self.config.max_faces,
        )
        if isinstance(result, list):
            for det in result:
                label = str(det.get("label") or "")
                if label.isdigit() or label == "0":
                    det["label"] = "face"
        return result

    def _detect_objects(
        self, img: "Image.Image", min_conf: Optional[float] = None, max_det: Optional[int] = None
    ) -> List[Dict[str, Any]] | Dict[str, Any]:
        detector = self._load_object_detector()
        if detector is None:
            return _error("object_detector_not_available")
        return self._run_detector(
            detector,
            img,
            min_conf=min_conf if min_conf is not None else self.config.object_min_confidence,
            max_det=max_det,
        )

    def _run_detector(
        self,
        model: Any,
        img: "Image.Image",
        min_conf: float,
        max_det: Optional[int],
    ) -> List[Dict[str, Any]] | Dict[str, Any]:
        if np is None:
            return _error("numpy_not_installed")
        try:
            image_np = np.array(img.convert("RGB"))
        except Exception:
            return _error("image_decode_failed")

        kwargs: Dict[str, Any] = {"conf": float(min_conf)}
        if max_det is not None:
            kwargs["max_det"] = int(max_det)
        if self.config.device:
            kwargs["device"] = self.config.device
        kwargs["verbose"] = False

        try:
            results = model.predict(source=image_np, **kwargs)
        except Exception:
            try:
                results = model(image_np, **kwargs)
            except Exception as exc:
                return _error("detector_failed", str(exc))

        if not results:
            return []
        res = results[0]
        boxes = getattr(res, "boxes", None)
        if boxes is None:
            return []

        xyxy_list = _tensor_to_list(getattr(boxes, "xyxy", []))
        conf_list = _tensor_to_list(getattr(boxes, "conf", []))
        cls_list = _tensor_to_list(getattr(boxes, "cls", []))
        names = getattr(res, "names", None) or getattr(model, "names", None) or {}

        detections: List[Dict[str, Any]] = []
        for idx, box in enumerate(xyxy_list):
            conf = float(conf_list[idx]) if idx < len(conf_list) else None
            cls_idx = int(cls_list[idx]) if idx < len(cls_list) else 0
            label = _resolve_label(names, cls_idx)
            detections.append(
                {
                    "label": label,
                    "confidence": conf,
                    "bbox": [float(value) for value in box[:4]],
                }
            )
        return detections

    def _load_face_detector(self) -> Optional[Any]:
        if self._face_detector is not None:
            return self._face_detector
        model_path = _resolve_model_path(self.config.face_model_path)
        if not model_path:
            return None
        self._face_detector = self._load_yolo(model_path)
        return self._face_detector

    def _load_object_detector(self) -> Optional[Any]:
        if self._object_detector is not None:
            return self._object_detector
        model_path = self.config.object_model_path or "yolov8n.pt"
        model_path = _resolve_model_path(model_path)
        self._object_detector = self._load_yolo(model_path)
        return self._object_detector

    def _load_yolo(self, model_path: str) -> Optional[Any]:
        try:
            from ultralytics import YOLO
        except Exception:
            return None
        try:
            model = YOLO(model_path)
        except Exception:
            return None
        return model

    def _crop_faces(
        self, img: "Image.Image", detections: List[Dict[str, Any]]
    ) -> List["Image.Image"]:
        width, height = img.size
        faces: List["Image.Image"] = []
        for det in detections:
            bbox = det.get("bbox") or []
            x1, y1, x2, y2 = _clip_box(bbox, width, height)
            try:
                faces.append(img.crop((x1, y1, x2, y2)).convert("RGB"))
            except Exception:
                continue
        return faces

    def _embed_faces(self, faces: List["Image.Image"]) -> List[Optional[List[float]]]:
        if not faces:
            return []
        backend = self._ensure_embedder()
        if backend is None:
            return [None for _ in faces]
        if backend == "face_recognition":
            return self._embed_faces_face_recognition(faces)
        if backend == "facenet_pytorch":
            return self._embed_faces_facenet(faces)
        return [None for _ in faces]

    def _ensure_embedder(self) -> Optional[str]:
        if self._embedder is not None:
            return self._embedder_backend
        backend = (self.config.face_backend or "auto").lower()
        if backend in {"auto", "facenet", "facenet_pytorch"}:
            embedder = self._init_facenet_embedder()
            if embedder is not None:
                self._embedder = embedder
                self._embedder_backend = "facenet_pytorch"
                return self._embedder_backend
        if backend in {"auto", "face_recognition", "dlib"}:
            embedder = self._init_face_recognition()
            if embedder is not None:
                self._embedder = embedder
                self._embedder_backend = "face_recognition"
                return self._embedder_backend
        return None

    def _init_facenet_embedder(self) -> Optional[Any]:
        try:
            from facenet_pytorch import InceptionResnetV1
            import torch
        except Exception:
            return None
        try:
            model = InceptionResnetV1(pretrained="vggface2").eval()
            if self.config.device and self.config.device != "cpu":
                model = model.to(self.config.device)
        except Exception:
            return None
        return model

    def _init_face_recognition(self) -> Optional[Any]:
        try:
            import face_recognition
        except Exception:
            return None
        return face_recognition

    def _embed_faces_facenet(self, faces: List["Image.Image"]) -> List[Optional[List[float]]]:
        try:
            import torch
        except Exception:
            return [None for _ in faces]
        if np is None:
            return [None for _ in faces]
        if self._embedder is None:
            return [None for _ in faces]
        tensors: List["torch.Tensor"] = []
        for face in faces:
            try:
                resized = face.resize((160, 160))
                arr = np.asarray(resized).astype("float32")
                if arr.ndim == 2:
                    arr = np.repeat(arr[:, :, None], 3, axis=2)
                arr = (arr - 127.5) / 128.0
                tensor = torch.from_numpy(arr).permute(2, 0, 1)
                tensors.append(tensor)
            except Exception:
                tensors.append(None)
        if not tensors:
            return []
        valid = [t for t in tensors if t is not None]
        if not valid:
            return [None for _ in faces]
        batch = torch.stack(valid)
        if self.config.device:
            batch = batch.to(self.config.device)
        with torch.no_grad():
            embeddings = self._embedder(batch)
        embeddings = embeddings.cpu().numpy().tolist()
        output: List[Optional[List[float]]] = []
        emb_index = 0
        for t in tensors:
            if t is None:
                output.append(None)
            else:
                output.append([float(v) for v in embeddings[emb_index]])
                emb_index += 1
        return output

    def _embed_faces_face_recognition(self, faces: List["Image.Image"]) -> List[Optional[List[float]]]:
        if self._embedder is None or np is None:
            return [None for _ in faces]
        face_recognition = self._embedder
        output: List[Optional[List[float]]] = []
        for face in faces:
            try:
                arr = np.array(face)
                enc = face_recognition.face_encodings(arr)
                if not enc:
                    output.append(None)
                else:
                    output.append([float(v) for v in enc[0]])
            except Exception:
                output.append(None)
        return output

    def _select_faceprints(
        self, label: Optional[str] = None, faceprint_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        records = self.db.list_faceprints()
        if faceprint_id:
            return [rec for rec in records if rec.get("faceprint_id") == faceprint_id]
        if label:
            return [rec for rec in records if rec.get("label") == label]
        return records

    def _best_match(self, embedding: List[float], records: List[Dict[str, Any]]) -> Dict[str, Any]:
        best = None
        best_distance = 1.0
        for record in records:
            dist = _cosine_distance(embedding, record.get("embedding") or [])
            if dist < best_distance:
                best_distance = dist
                best = record
        if best is None:
            return {"distance": 1.0, "label": None, "faceprint_id": None}
        return {
            "distance": best_distance,
            "label": best.get("label"),
            "faceprint_id": best.get("faceprint_id"),
        }

    def _rank_matches(
        self, embedding: List[float], records: List[Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        scored = []
        for record in records:
            dist = _cosine_distance(embedding, record.get("embedding") or [])
            scored.append(
                {
                    "label": record.get("label"),
                    "faceprint_id": record.get("faceprint_id"),
                    "distance": dist,
                }
            )
        scored.sort(key=lambda item: item["distance"])
        return scored[:top_k]

    @staticmethod
    def _now_ts() -> float:
        try:
            import time

            return time.time()
        except Exception:
            return 0.0


def _resolve_label(names: Any, cls_idx: int) -> str:
    if isinstance(names, dict):
        return str(names.get(cls_idx, cls_idx))
    if isinstance(names, (list, tuple)) and cls_idx < len(names):
        return str(names[cls_idx])
    return str(cls_idx)
