// Python 3's round() uses round-half-to-even ("banker's rounding") for
// floats; JS's Math.round() rounds half up (toward +Infinity) always. The
// agent formulas ported from Python call round() on float arithmetic, and
// with parameters like beta=0.25/theta=0.3 an exact .5 tie is a real
// possibility (0.5 is exactly representable in binary floating point), so
// silently using Math.round() here would risk a byte-for-byte mismatch
// against the Python reference on some week/echelon. This replicates
// Python's tie-to-even behavior exactly.
export function pythonRound(x) {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff < 0.5) return floor;
  if (diff > 0.5) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1;
}
