import { describe, it, expect } from 'vitest';

// Chip text helpers — extracted for testability
function hostnameFromUrl(rawUrl: string): string {
  try {
    return new URL(rawUrl.startsWith("http") ? rawUrl : `https://${rawUrl}`)
      .hostname.replace(/^www\./, "");
  } catch {
    return rawUrl;
  }
}

describe('wizard chip text helpers', () => {
  describe('hostnameFromUrl', () => {
    it('strips www prefix', () => {
      expect(hostnameFromUrl('https://www.acme.com')).toBe('acme.com');
    });
    it('works without protocol', () => {
      expect(hostnameFromUrl('acme.com')).toBe('acme.com');
    });
    it('returns raw value if unparseable', () => {
      expect(hostnameFromUrl('not a url')).toBe('not a url');
    });
  });
});
