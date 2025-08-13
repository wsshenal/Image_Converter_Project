from PIL import Image, ImageDraw, ImageOps
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os, time, threading, shutil

# --- Settings (same look as before) ---
INPUT_DIR   = "input_images"
OUTPUT_DIR  = "output_images"
TARGET_SIZE = (1005, 1317)     # width, height
CORNER_RADIUS = 80
ADD_BORDER    = False
BORDER_WIDTH  = 2
BORDER_COLOR  = (0, 0, 0, 255)

# File handling after conversion
# If MOVE_TO_BACKUP is True, originals go to BACKUP_DIR.
# Otherwise, originals are deleted.
MOVE_TO_BACKUP = False
BACKUP_DIR     = "originals_backup"

VALID_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff")

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
if MOVE_TO_BACKUP:
    os.makedirs(BACKUP_DIR, exist_ok=True)

def rounded_mask(size, radius):
    w, h = size
    scale = 4
    big = (w*scale, h*scale)
    r = radius * scale
    m = Image.new("L", big, 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((0, 0, big[0], big[1]), r, fill=255)
    return m.resize((w, h), Image.LANCZOS)

def convert_one(src_path):
    """Convert a single image, save PNG to OUTPUT_DIR, then remove/move original."""
    if not os.path.isfile(src_path):
        return

    name = os.path.splitext(os.path.basename(src_path))[0]
    out_path = os.path.join(OUTPUT_DIR, name + ".png")

    try:
        img = Image.open(src_path).convert("RGBA")
        img = ImageOps.fit(img, TARGET_SIZE, Image.LANCZOS, centering=(0.5, 0.5))
        mask = rounded_mask(TARGET_SIZE, CORNER_RADIUS)
        img.putalpha(mask)

        if ADD_BORDER and BORDER_WIDTH > 0:
            border_layer = Image.new("RGBA", TARGET_SIZE, (0, 0, 0, 0))
            d = ImageDraw.Draw(border_layer)
            inset = BORDER_WIDTH / 2
            d.rounded_rectangle(
                (inset, inset, TARGET_SIZE[0]-inset, TARGET_SIZE[1]-inset),
                CORNER_RADIUS - inset,
                outline=BORDER_COLOR,
                width=BORDER_WIDTH
            )
            img = Image.alpha_composite(img, border_layer)

        img.save(out_path, "PNG")
        print(f"✅ Converted: {os.path.basename(src_path)} -> {os.path.basename(out_path)}")

        # --- remove or move the original ---
        if MOVE_TO_BACKUP:
            dest = os.path.join(BACKUP_DIR, os.path.basename(src_path))
            # If a file with same name exists in backup, append a timestamp
            if os.path.exists(dest):
                stem, ext = os.path.splitext(dest)
                dest = f"{stem}_{int(time.time())}{ext}"
            shutil.move(src_path, dest)
            print(f"📦 Moved original to backup: {os.path.basename(dest)}")
        else:
            os.remove(src_path)
            print(f"🗑️  Deleted original: {os.path.basename(src_path)}")

    except Exception as e:
        print(f"⚠️  Skipped {src_path}: {e}")

def convert_all_existing():
    files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(VALID_EXTS)]
    if not files:
        print("ℹ️  input_images is empty. Drop files here to convert automatically.")
        return
    for f in files:
        convert_one(os.path.join(INPUT_DIR, f))

class ConvertHandler(FileSystemEventHandler):
    def __init__(self):
        self._lock = threading.Lock()

    def on_any_event(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if not path.lower().endswith(VALID_EXTS):
            return

        # Debounce: give the OS a moment to finish copying the file
        def do_convert():
            time.sleep(0.6)
            convert_one(path)

        with self._lock:
            threading.Thread(target=do_convert, daemon=True).start()

if __name__ == "__main__":
    print("🚀 Auto converter running.")
    print("   Drop images into:", os.path.abspath(INPUT_DIR))
    print("   Results appear in:", os.path.abspath(OUTPUT_DIR))
    if MOVE_TO_BACKUP:
        print("   Originals backed up in:", os.path.abspath(BACKUP_DIR))
    else:
        print("   Originals will be deleted after conversion.")

    convert_all_existing()

    observer = Observer()
    handler = ConvertHandler()
    observer.schedule(handler, INPUT_DIR, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
