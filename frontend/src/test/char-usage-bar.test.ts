import { describe, it, expect } from 'vitest';

function barColor(pct: number): string {
  if (pct >= 95) return 'bg-red-500';
  if (pct >= 80) return 'bg-amber-500';
  return 'bg-green-500';
}

describe('CharUsageBar color thresholds', () => {
  it('is green below 80%', () => {
    expect(barColor(0)).toBe('bg-green-500');
    expect(barColor(50)).toBe('bg-green-500');
    expect(barColor(79)).toBe('bg-green-500');
  });

  it('is amber from 80% to 94%', () => {
    expect(barColor(80)).toBe('bg-amber-500');
    expect(barColor(90)).toBe('bg-amber-500');
    expect(barColor(94)).toBe('bg-amber-500');
  });

  it('is red at 95% and above', () => {
    expect(barColor(95)).toBe('bg-red-500');
    expect(barColor(100)).toBe('bg-red-500');
  });
});
