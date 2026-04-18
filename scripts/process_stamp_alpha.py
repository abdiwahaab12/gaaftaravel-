"""Make gaaf-stamp.png: remove dark frame + outer matte via flood from edges."""
from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
STAMP = ROOT / "static" / "gaaf-stamp.png"
BACKUP = Path(
    r"C:\Users\cabdi\.cursor\projects\c-Users-cabdi-Downloads-wanaaagtravel-main"
    r"\assets\c__Users_cabdi_AppData_Roaming_Cursor_User_workspaceStorage_c4aebb31b630c26faee4a66e94497c02_images_image-8c9d7d4a-59fd-4985-af23-3eb8042977e2.png"
)


def is_frame(r: int, g: int, b: int) -> bool:
    return max(r, g, b) < 92


def is_bg(r: int, g: int, b: int) -> bool:
    if r < 218 or g < 218 or b < 218:
        return False
    return (max(r, g, b) - min(r, g, b)) <= 22


def removable(r: int, g: int, b: int) -> bool:
    return is_frame(r, g, b) or is_bg(r, g, b)


def main() -> None:
    if BACKUP.is_file():
        import shutil

        shutil.copy2(BACKUP, STAMP)

    im = Image.open(STAMP).convert("RGBA")
    w, h = im.size
    px = im.load()

    q: deque[tuple[int, int]] = deque()
    queued: set[tuple[int, int]] = set()

    def enqueue(x: int, y: int) -> None:
        t = (x, y)
        if t in queued:
            return
        queued.add(t)
        q.append(t)

    for x in range(w):
        enqueue(x, 0)
        enqueue(x, h - 1)
    for y in range(h):
        enqueue(0, y)
        enqueue(w - 1, y)

    filled: set[tuple[int, int]] = set()
    while q:
        x, y = q.popleft()
        r, g, b, _ = px[x, y]
        if not removable(r, g, b):
            continue
        filled.add((x, y))
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                enqueue(nx, ny)

    for x, y in filled:
        r, g, b, _ = px[x, y]
        px[x, y] = (r, g, b, 0)

    # Inner oval / remaining near-white (same rule as is_bg): no matte behind HTML date
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a and is_bg(r, g, b):
                px[x, y] = (r, g, b, 0)

    im.save(STAMP, optimize=True)
    print("Wrote", STAMP)


if __name__ == "__main__":
    main()
