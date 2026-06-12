import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const STORAGE_DIR =
  process.env.MPT_STORAGE_DIR ||
  path.resolve(process.cwd(), "..", "MoneyPrinterTurbo", "storage");
const TASKS_DIR = path.join(STORAGE_DIR, "tasks");
const CACHE_DIR = path.join(STORAGE_DIR, "cache_videos");

export interface VideoItem {
  taskId: string;
  filename: string;
  sizeBytes: number;
  createdAt: number;
  streamUrl: string;
  downloadUrl: string;
  script?: string;
  chapters?: string;  // texto listo para pegar en YouTube
}

// GET /api/library  → list all completed videos
// GET /api/library?action=cache-info  → get cache folder size
export async function GET(req: NextRequest) {
  const action = req.nextUrl.searchParams.get("action");

  // Cache info
  if (action === "cache-info") {
    try {
      if (!fs.existsSync(CACHE_DIR)) return NextResponse.json({ count: 0, sizeBytes: 0 });
      const files = fs.readdirSync(CACHE_DIR);
      let sizeBytes = 0;
      for (const f of files) {
        try { sizeBytes += fs.statSync(path.join(CACHE_DIR, f)).size; } catch { /* skip */ }
      }
      return NextResponse.json({ count: files.length, sizeBytes });
    } catch (e) {
      return NextResponse.json({ error: String(e) }, { status: 500 });
    }
  }

  // List videos
  try {
    if (!fs.existsSync(TASKS_DIR)) return NextResponse.json({ videos: [] });

    const entries = fs.readdirSync(TASKS_DIR, { withFileTypes: true });
    const videos: VideoItem[] = [];

    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const taskId = entry.name;
      const taskPath = path.join(TASKS_DIR, taskId);

      let files: string[];
      try { files = fs.readdirSync(taskPath); } catch { continue; }

      const finalFiles = files.filter(
        (f) => f.startsWith("final-") && f.endsWith(".mp4") && !f.includes("TEMP")
      );

      for (const filename of finalFiles) {
        const filePath = path.join(taskPath, filename);
        let stat: fs.Stats;
        try { stat = fs.statSync(filePath); } catch { continue; }

        let script: string | undefined;
        const scriptPath = path.join(taskPath, "script.json");
        if (fs.existsSync(scriptPath)) {
          try {
            const raw = JSON.parse(fs.readFileSync(scriptPath, "utf-8"));
            script = raw?.script?.slice(0, 120);
          } catch { /* ignore */ }
        }

        let chapters: string | undefined;
        const chaptersPath = path.join(taskPath, "chapters.txt");
        if (fs.existsSync(chaptersPath)) {
          try {
            chapters = fs.readFileSync(chaptersPath, "utf-8").trim();
          } catch { /* ignore */ }
        }

        videos.push({
          taskId,
          filename,
          sizeBytes: stat.size,
          createdAt: stat.birthtimeMs || stat.mtimeMs,
          streamUrl: `/api/mpt/v1/stream/${taskId}/${filename}`,
          downloadUrl: `/api/mpt/v1/download/${taskId}/${filename}`,
          script,
          chapters,
        });
      }
    }

    videos.sort((a, b) => b.createdAt - a.createdAt);
    return NextResponse.json({ videos });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

// DELETE /api/library?taskId=xxx  → delete task folder from disk
// DELETE /api/library?action=clear-cache  → delete all cache_videos
export async function DELETE(req: NextRequest) {
  const action = req.nextUrl.searchParams.get("action");

  // Clear cache
  if (action === "clear-cache") {
    try {
      if (!fs.existsSync(CACHE_DIR)) return NextResponse.json({ ok: true, deleted: 0 });
      const files = fs.readdirSync(CACHE_DIR);
      let deleted = 0;
      for (const f of files) {
        try {
          fs.rmSync(path.join(CACHE_DIR, f), { force: true });
          deleted++;
        } catch { /* skip locked files */ }
      }
      return NextResponse.json({ ok: true, deleted });
    } catch (e) {
      return NextResponse.json({ error: String(e) }, { status: 500 });
    }
  }

  // Delete task folder
  const taskId = req.nextUrl.searchParams.get("taskId");
  if (!taskId) return NextResponse.json({ error: "missing taskId or action" }, { status: 400 });

  // Validate taskId looks like a UUID to prevent path traversal
  if (!/^[0-9a-f-]{36}$/i.test(taskId)) {
    return NextResponse.json({ error: "invalid taskId" }, { status: 400 });
  }

  try {
    // 1. Tell the Python backend to release the task (frees file handles on Windows)
    try {
      const apiUrl = process.env.MPT_API_URL || "http://localhost:8080";
      await fetch(`${apiUrl}/api/v1/tasks/${taskId}`, { method: "DELETE" });
    } catch { /* backend may be offline — continue anyway */ }

    // 2. Small delay to let Windows release file locks
    await new Promise((r) => setTimeout(r, 500));

    // 3. Delete the folder from disk
    const taskPath = path.join(TASKS_DIR, taskId);
    if (!fs.existsSync(taskPath)) {
      return NextResponse.json({ ok: true, note: "already deleted" });
    }
    fs.rmSync(taskPath, { recursive: true, force: true });

    if (fs.existsSync(taskPath)) {
      return NextResponse.json({ error: "No se pudo eliminar la carpeta — puede que el backend tenga el archivo en uso. Detén el backend e inténtalo de nuevo." }, { status: 500 });
    }
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
