
import argparse
import time
from paddleocr import TextRecognition

parser = argparse.ArgumentParser()
parser.add_argument("--image", required=True)
args = parser.parse_args()

print("Loading recognition model...", flush=True)
start = time.perf_counter()

model = TextRecognition(
    model_name="PP-OCRv6_medium_rec",
    device="cpu",
    enable_mkldnn=False,
    cpu_threads=2,
)

print(
    f"Model loaded in {time.perf_counter() - start:.2f}s",
    flush=True,
)

start = time.perf_counter()
results = model.predict(input=args.image, batch_size=1)

for result in results:
    data = result.json
    info = data.get("res", data)
    print("OCR text:", info.get("rec_text"))
    print("OCR confidence:", info.get("rec_score"))

print(
    f"Inference time: {time.perf_counter() - start:.2f}s",
    flush=True,
)
