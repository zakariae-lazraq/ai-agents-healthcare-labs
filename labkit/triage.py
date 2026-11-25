"""Lab 4: image triage — a tissue classifier as an agent tool, routing by confidence, a human review queue.

The routing rule (automatic vs human review) is plain code written by the participant; the agent runs the triage,
queues uncertain images with a reason, and summarises. Every image id is IMG001…IMG200.
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import numpy as np

CLASSES = ["adipose", "background", "debris", "lymphocytes", "mucus", "smooth muscle",
           "normal colon mucosa", "cancer-associated stroma", "colorectal adenocarcinoma epithelium"]


def make_net():
    from torch import nn

    def block(cin, cout):
        return [nn.Conv2d(cin, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU()]

    return nn.Sequential(*block(3, 32), *block(32, 32), nn.MaxPool2d(2),
                         *block(32, 64), *block(64, 64), nn.MaxPool2d(2),
                         *block(64, 128), nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Dropout(0.2), nn.Linear(128, 9))


def to_model_input(images: np.ndarray) -> np.ndarray:
    """uint8 (N,28,28,3) → float32 (N,3,28,28) in 0..1."""
    x = np.asarray(images, dtype=np.float32) / 255.0
    return np.ascontiguousarray(x.transpose(0, 3, 1, 2))


class TriageData:
    def __init__(self, folder):
        import torch

        folder = Path(folder)
        d = np.load(folder / "images.npz")
        self.images, self.labels = d["images"], d["labels"]
        self.extra = {k: d[k] for k in ("blank", "blurred", "colour_shifted")}
        self.card = json.loads((folder / "model_card.json").read_text(encoding="utf-8"))
        self.net = make_net()
        self.net.load_state_dict(torch.load(folder / "model.pt", map_location="cpu"))
        self.net.eval()
        self.ids = [f"IMG{i + 1:03d}" for i in range(len(self.images))]
        self.probs = self.predict(self.images)

    def predict(self, images: np.ndarray) -> np.ndarray:
        import torch

        with torch.no_grad():
            return torch.softmax(self.net(torch.tensor(to_model_input(images))), 1).numpy()

    def index(self, image_id: str) -> int:
        return self.ids.index(image_id)


def load(folder) -> TriageData:
    return TriageData(folder)


def top2(p: np.ndarray) -> tuple[int, float, int, float]:
    order = np.argsort(p)[::-1]
    return int(order[0]), float(p[order[0]]), int(order[1]), float(p[order[1]])


def reference_route(top_p: float, second_p: float, threshold: float = 0.80, margin: float = 0.20) -> str:
    """Automatic only if the top class is confident enough AND clearly ahead of the second."""
    return "auto" if top_p >= threshold and (top_p - second_p) >= margin else "review"


def sweep(data: TriageData, thresholds, route=reference_route) -> list[dict]:
    """For each threshold: share of images sent to humans, and accuracy of the automatically sorted ones."""
    out = []
    for t in thresholds:
        auto_ok = auto_n = 0
        for p, y in zip(data.probs, data.labels):
            c, p1, _, p2 = top2(p)
            if route(p1, p2, threshold=t) == "auto":
                auto_n += 1
                auto_ok += int(c == y)
        out.append({"threshold": round(float(t), 2), "to_humans_pct": round(100 * (1 - auto_n / len(data.labels)), 1),
                    "auto_accuracy_pct": round(100 * auto_ok / auto_n, 1) if auto_n else None,
                    "auto_errors": auto_n - auto_ok})
    return out


def sweep_chart(rows: list[dict], mark: float | None = None):
    import matplotlib.pyplot as plt

    t = [r["threshold"] for r in rows]
    fig, ax = plt.subplots(figsize=(7.5, 3.4), dpi=110)
    ax.plot(t, [r["auto_accuracy_pct"] for r in rows], color="#1E7A3C", marker="o", ms=3,
            label="accuracy of automatically sorted images")
    ax.plot(t, [r["to_humans_pct"] for r in rows], color="#B7791F", marker="o", ms=3, label="images sent to humans")
    if mark is not None:
        ax.axvline(mark, color="#1F3A5F", lw=1, ls="--")
    ax.set_xlabel("confidence threshold")
    ax.set_ylabel("%")
    ax.set_ylim(0, 101)
    ax.legend(frameon=False, fontsize=9, loc="center left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    return fig


def quality_problem(image: np.ndarray) -> str:
    """Reference image-quality check (challenge): '' if usable, else the reason.
    Blank: almost no contrast. Blurred: little pixel-to-pixel change relative to the contrast — real 'background'
    tiles are smooth but low-contrast, so sharpness is judged relative to contrast, not in absolute terms."""
    g = np.asarray(image, dtype=np.float32).mean(axis=2)
    if g.std() < 1.0:
        return "blank or nearly uniform image"
    sharpness = np.abs(np.diff(g, axis=0)).mean() + np.abs(np.diff(g, axis=1)).mean()
    if sharpness / g.std() < 0.3:
        return "image too blurred"
    return ""


def png_b64(image: np.ndarray, scale: int = 4) -> str:
    import matplotlib.image as mpimg

    img = np.kron(np.asarray(image, dtype=np.uint8), np.ones((scale, scale, 1), dtype=np.uint8))
    buf = io.BytesIO()
    mpimg.imsave(buf, img, format="png")
    return base64.b64encode(buf.getvalue()).decode()


def make_triage_tools(data: TriageData, router, queue: list) -> dict:
    """Tools for the agent. `router(top_p, second_p)` is the participant's rule; `queue` collects review items."""

    def triage_images(image_ids: list[str]) -> dict:
        """Classify tissue tiles (ids like 'IMG001') with the CNN and apply the laboratory's routing rule.
        Returns, per image, the top class, its probability, the runner-up and the route: 'auto' or 'review'."""
        rows, unknown = [], []
        for i in image_ids:
            if i not in data.ids:
                unknown.append(i)
                continue
            c, p1, c2, p2 = top2(data.probs[data.index(i)])
            rows.append({"image_id": i, "top_class": CLASSES[c], "probability": round(p1, 3),
                         "runner_up": CLASSES[c2], "runner_up_probability": round(p2, 3),
                         "route": router(p1, p2)})
        out = {"results": rows, "auto": sum(r["route"] == "auto" for r in rows),
               "review": sum(r["route"] == "review" for r in rows)}
        if unknown:
            out["unknown_ids"] = unknown
        return out

    def add_to_review_queue(image_id: str, reason: str) -> dict:
        """Send one image to the pathologist's review queue with a short reason (e.g. 'top class 0.62, close to
        runner-up'). Use it for every image whose route is 'review'."""
        if image_id not in data.ids:
            return {"status": "error", "message": f"Unknown image '{image_id}'."}
        if image_id not in [q["image_id"] for q in queue]:
            queue.append({"image_id": image_id, "reason": reason})
        return {"status": "queued", "image_id": image_id, "queue_length": len(queue)}

    return {f.__name__: f for f in (triage_images, add_to_review_queue)}


def queue_html(data: TriageData, queue: list[dict]) -> str:
    """The review queue as a pathologist would see it: tile, model's guess, reason, true label (for teaching)."""
    td = "padding:4px 8px;text-align:left;vertical-align:middle;font-size:12px"
    rows = ""
    for q in queue:
        i = data.index(q["image_id"])
        c, p1, c2, p2 = top2(data.probs[i])
        rows += (f"<tr style='border-top:1px solid #C9D2DC'><td style='{td}'><img src='data:image/png;base64,"
                 f"{png_b64(data.images[i])}' width='112'></td><td style='{td}'><b>{q['image_id']}</b></td>"
                 f"<td style='{td}'>{CLASSES[c]} {p1:.2f}<br><span style='color:#5F6B7A'>{CLASSES[c2]} {p2:.2f}"
                 f"</span></td><td style='{td}'>{q['reason']}</td><td style='{td}'>{CLASSES[int(data.labels[i])]}</td></tr>")
    return ("<table style='border-collapse:collapse;font-family:Inter,Segoe UI,Roboto,sans-serif'>"
            f"<tr><th style='{td}'>Tile</th><th style='{td}'>Image</th><th style='{td}'>Model (top 2)</th>"
            f"<th style='{td}'>Reason given by the agent</th><th style='{td}'>True class (teaching)</th></tr>{rows}</table>")


def second_opinion(data: TriageData, image_id: str, model: str, client=None) -> dict:
    """Ask Gemini (vision) which of the 9 tissue classes a tile shows. One API call; errors come back as a message."""
    from google.genai import types

    from labkit.agents import BUSY_MESSAGE, QUOTA_MESSAGE, _error_kind

    png = base64.b64decode(png_b64(data.images[data.index(image_id)], scale=4))
    prompt = ("This is a small (28×28 pixel, shown enlarged) H&E-stained colorectal tissue tile. Which ONE of these classes is it most "
              f"likely: {', '.join(CLASSES)}? Answer with the class, then one sentence on what you see and how sure "
              "you are. This is a teaching exercise, not a diagnosis.")
    try:
        if client is None:
            from google import genai
            client = genai.Client()
        resp = client.models.generate_content(model=model, contents=[
            types.Part.from_bytes(data=png, mime_type="image/png"), prompt],
            config=types.GenerateContentConfig(temperature=0))
        return {"text": resp.text or "", "message": ""}
    except Exception as exc:
        kind = _error_kind(exc)
        msg = {"quota": QUOTA_MESSAGE, "busy": BUSY_MESSAGE}.get(kind, f"Gemini returned an error: {str(exc)[:160]}")
        return {"text": "", "message": msg}


def gallery_html(data: TriageData, per_class: int = 2) -> str:
    """A few tiles of each tissue class, enlarged, with their true class."""
    cells = ""
    for c, name in enumerate(CLASSES):
        for i in [i for i in range(len(data.labels)) if data.labels[i] == c][:per_class]:
            cells += (f"<div style='display:inline-block;margin:4px;text-align:center;width:120px;font-size:11px;"
                      f"font-family:sans-serif'><img src='data:image/png;base64,{png_b64(data.images[i])}' "
                      f"width='112'><br>{name}</div>")
    return f"<div>{cells}</div>"


def load_any_image(path) -> np.ndarray:
    """Any image file → a 28×28 RGB tile (the size the classifier expects)."""
    from PIL import Image

    return np.asarray(Image.open(path).convert("RGB").resize((28, 28)), dtype=np.uint8)


def describe(p: np.ndarray) -> str:
    c, p1, c2, p2 = top2(p)
    return f"{CLASSES[c]} {p1:.2f} (runner-up: {CLASSES[c2]} {p2:.2f})"
