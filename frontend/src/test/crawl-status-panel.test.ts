import { describe, it, expect } from 'vitest';

// Pure logic: should the skipped warning be shown?
function shouldShowSkippedWarning(docsSkipped: number): boolean {
  return docsSkipped > 0;
}

describe('CrawlStatusPanel skipped warning', () => {
  it('shows warning when docs_skipped > 0', () => {
    expect(shouldShowSkippedWarning(1)).toBe(true);
    expect(shouldShowSkippedWarning(5)).toBe(true);
  });

  it('does not show warning when docs_skipped is 0', () => {
    expect(shouldShowSkippedWarning(0)).toBe(false);
  });
});
