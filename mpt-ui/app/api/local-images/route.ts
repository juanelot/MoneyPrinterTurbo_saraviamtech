import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const STORAGE_DIR =
  process.env.MPT_STORAGE_DIR ||
  path.resolve(process.cwd(), "..", "MoneyPrinterTurbo", "storage");
const LOCAL_VIDEOS_DIR = path.join(STORAGE_DIR, "local_videos");

const ALLOWED_EXT = new Set([".jpg", ".jpeg", ".png", ".bmp", ".webp"]);

// DELETE /api/local-images?action=clear-all  → borra todas las imágenes de local_videos
// DELETE /api/local-images?file=xxx.png      → borra un archivo específico
export async function DELETE(req: NextRequest) {
  const action = req.nextUrl.searchParams.get("action");
  const file = req.nextUrl.searchParams.get("file");

  if (action === "clear-all") {
    try {
      if (!fs.existsSync(LOCAL_VIDEOS_DIR))
        return NextResponse.json({ ok: true, deleted: 0 });

      const files = fs.readdirSync(LOCAL_VIDEOS_DIR);
      let deleted = 0;
      for (const f of files) {
        const ext = path.extname(f).toLowerCase();
        if (!ALLOWED_EXT.has(ext)) continue; // solo borrar imágenes, no videos
        try {
          fs.rmSync(path.join(LOCAL_VIDEOS_DIR, f), { force: true });
          deleted++;
        } catch { /* skip locked */ }
      }
      return NextResponse.json({ ok: true, deleted });
    } catch (e) {
      return NextResponse.json({ error: String(e) }, { status: 500 });
    }
  }

  if (file) {
    // Validar que es solo nombre de archivo (sin path traversal)
    const safe = path.basename(file);
    const ext = path.extname(safe).toLowerCase();
    if (!ALLOWED_EXT.has(ext))
      return NextResponse.json({ error: "not an image file" }, { status: 400 });

    const fullPath = path.join(LOCAL_VIDEOS_DIR, safe);
    if (!fs.existsSync(fullPath))
      return NextResponse.json({ ok: true, note: "already deleted" });

    try {
      fs.rmSync(fullPath, { force: true });
      return NextResponse.json({ ok: true });
    } catch (e) {
      return NextResponse.json({ error: String(e) }, { status: 500 });
    }
  }

  return NextResponse.json({ error: "missing action or file param" }, { status: 400 });
}
