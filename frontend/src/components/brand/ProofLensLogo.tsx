/**
 * ProofLens logomark — "Aperture & check" (Direction C). A single lens ring opened at the
 * top-right (an aperture/shutter gap with a light glint) around a proof checkmark. Drawn in
 * `currentColor` so it inherits its colour from context: white on the accent tile in the
 * masthead, or the accent itself on a transparent ground. Scales cleanly from a 16px favicon
 * to a print header.
 */
export function ProofLensLogo({
  className,
  title = "ProofLens",
}: {
  className?: string;
  title?: string;
}) {
  return (
    <svg viewBox="0 0 32 32" fill="none" role="img" aria-label={title} className={className}>
      <title>{title}</title>
      {/* aperture ring — near-full circle with a shutter gap at the top-right */}
      <path d="M27.6 11.3A12.4 12.4 0 1 1 22.4 5.4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      {/* proof check, seated in the aperture */}
      <path
        d="M11.6 16.4l3.2 3.2 6.6-7.1"
        stroke="currentColor"
        strokeWidth="2.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* lens glint at the aperture opening */}
      <circle cx="24.7" cy="8.2" r="1.5" fill="currentColor" />
    </svg>
  );
}
