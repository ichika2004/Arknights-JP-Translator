from __future__ import annotations
import numpy as np
from paddleocr import PaddleOCR


class JapaneseOCR:
    def __init__(self) -> None:
        self.engine = PaddleOCR(
            lang="japan",
            device="cpu",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def recognize(self, bgr_image: np.ndarray) -> str:
        results = self.engine.predict(bgr_image)
        lines: list[str] = []
        for item in results:
            data = item.json
            data = data.get("res", data)
            texts = data.get("rec_texts", [])
            scores = data.get("rec_scores", [])
            for index, value in enumerate(texts):
                score = float(scores[index]) if index < len(scores) else 1.0
                if score >= 0.45 and str(value).strip():
                    lines.append(str(value).strip())
        return "\n".join(lines)
