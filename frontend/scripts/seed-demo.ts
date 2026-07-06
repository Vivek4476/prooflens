/**
 * Seed the demo by pushing the repository's demo images through the REAL
 * scoring API (POST /v1/score). No fake data — History, Analytics and the
 * Review Queue are populated with genuine verdicts.
 *
 * Prerequisites:
 *   1. python scripts/generate_demo_images.py        # writes ../demo_images
 *   2. backend running (docker compose up) on a FRESH db for a clean spread:
 *        docker compose -f deploy/docker-compose.yml down -v && ... up
 *
 * Run:  cd frontend && npm run seed:demo
 */
import { readFileSync, readdirSync } from "node:fs";
import { basename, join, resolve } from "node:path";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const DIR = resolve(process.cwd(), "..", "demo_images");

function orderedFiles(): string[] {
  const files = readdirSync(DIR).filter((f) => f.endsWith(".jpg"));
  // Score everything before the intentional re-upload so it reads as recycled.
  return files.sort((a, b) => {
    const ra = a.startsWith("reupload") ? 1 : 0;
    const rb = b.startsWith("reupload") ? 1 : 0;
    return ra - rb || a.localeCompare(b);
  });
}

async function scoreOne(file: string) {
  const buf = readFileSync(join(DIR, file));
  const form = new FormData();
  form.append("image", new Blob([buf], { type: "image/jpeg" }), file);
  const res = await fetch(`${API}/v1/score`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`${file}: HTTP ${res.status} ${await res.text()}`);
  return (await res.json()) as { band: string; score: number; reason: string };
}

async function main() {
  let files: string[];
  try {
    files = orderedFiles();
  } catch {
    console.error(`No demo images at ${DIR}. Run: python scripts/generate_demo_images.py`);
    process.exit(1);
  }
  if (files.length === 0) {
    console.error(`No .jpg files in ${DIR}. Run: python scripts/generate_demo_images.py`);
    process.exit(1);
  }

  console.log(`Seeding ${files.length} images through ${API}/v1/score …\n`);
  const bands: Record<string, number> = {};
  for (const file of files) {
    try {
      const v = await scoreOne(file);
      bands[v.band] = (bands[v.band] || 0) + 1;
      console.log(`  ${basename(file).padEnd(26)} ${v.band.padEnd(9)} ${String(v.score).padStart(5)}  ${v.reason}`);
    } catch (e) {
      console.error(`  ${file}: ${(e as Error).message}`);
    }
  }
  console.log(`\nDone. Band spread: ${JSON.stringify(bands)}`);
  console.log("Open the Dashboard, History and Analytics to see the seeded verdicts.");
}

main();
