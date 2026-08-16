import json
from pathlib import Path

from fenix_default_navdata.llamacpp_ocr import run_llamacpp_ocr


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_bounded_llamacpp_ocr_sends_reusable_generation_limits(
    tmp_path: Path,
    monkeypatch,
) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"png")
    received: dict[str, object] = {}

    def fake_urlopen(request, *, timeout: int):
        received["url"] = request.full_url
        received["timeout"] = timeout
        received["payload"] = json.loads(request.data.decode("utf-8"))
        return _Response({
            "choices": [{"message": {"content": "OCR text"}}],
        })

    monkeypatch.setattr(
        "fenix_default_navdata.llamacpp_ocr.urlopen",
        fake_urlopen,
    )

    result = run_llamacpp_ocr(
        image,
        mode="ocr",
        timeout_seconds=120,
        max_tokens=4096,
    )

    assert received["url"] == "http://127.0.0.1:8090/v1/chat/completions"
    assert received["timeout"] == 120
    assert received["payload"]["model"] == "ocr"
    assert received["payload"]["temperature"] == 0.0
    assert received["payload"]["seed"] == 2608
    assert received["payload"]["top_k"] == 1
    assert received["payload"]["max_tokens"] == 4096
    assert result["data"]["documents"][0]["markdown"] == "OCR text"
