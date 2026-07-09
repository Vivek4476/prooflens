import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";

/** Band definitions — score → meaning. The band WORD always accompanies the colour dot
 *  (verdict colour is never conveyed alone), per BRAND.md / VERDICT_COPY.md. */
const BANDS: { band: string; score: string; meaning: string; dot: string }[] = [
  { band: "Clear", score: "70–100", meaning: "No capture-integrity issues found.", dot: "bg-verdict-clear" },
  { band: "Doubtful", score: "40–69", meaning: "A quality or soft signal warrants a second look.", dot: "bg-verdict-doubtful" },
  { band: "Suspect", score: "0–39", meaning: "A hard integrity signal fired — recapture, duplicate, or wrong content.", dot: "bg-verdict-suspect" },
];

/** The checks, in plain language — the evidence each names, never an internal check name. */
const CHECKS: [string, string][] = [
  ["Recycled image", "Matches a photo already submitted for this account."],
  ["Photo of another screen", "Screen edge and glare detected — a recapture, not a live photo."],
  ["Designed graphic or screenshot", "Not a photo of a live scene."],
  ["No people or relevant scene", "The expected subject isn't present in the photo."],
  ["Too blurred to assess", "Not sharp enough to judge — retake in better light."],
  ["Scored without content check", "The vision check was unavailable, so the image was scored fail-open."],
];

export default function MethodologyPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="How scores work"
        description="ProofLens scores and flags capture integrity. It never blocks an upload, never stores your images, and never claims to prove a meeting happened."
      />

      <Card>
        <CardHeader title="Bands" subtitle="Every image gets one of three bands, written back to LeadSquared first." />
        <div className="divide-y divide-border">
          {BANDS.map((b) => (
            <div key={b.band} className="flex items-baseline gap-4 px-5 py-4">
              <span className="flex w-28 shrink-0 items-center gap-2">
                <span className={`h-2 w-2 shrink-0 rounded-full ${b.dot}`} aria-hidden />
                <span className="text-body font-semibold text-text">{b.band}</span>
              </span>
              <span className="w-20 shrink-0 text-body-sm tabular-nums text-text-secondary">{b.score}</span>
              <span className="text-body-sm text-text-secondary">{b.meaning}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="What the checks look for" subtitle="Each flag names the evidence, in plain language." />
        <div className="divide-y divide-border">
          {CHECKS.map(([name, desc]) => (
            <div key={name} className="grid gap-1 px-5 py-4 sm:grid-cols-[220px_1fr] sm:gap-4">
              <span className="text-body-sm font-medium text-text">{name}</span>
              <span className="text-body-sm text-text-secondary">{desc}</span>
            </div>
          ))}
        </div>
      </Card>

      <p className="max-w-2xl text-caption text-text-muted">
        ProofLens describes what was observed in the image, not a judgement about the person. A “Suspect” band
        describes the <em>image</em>, never the rep. Scores are advisory — a reviewer always makes the call.
      </p>
    </div>
  );
}
