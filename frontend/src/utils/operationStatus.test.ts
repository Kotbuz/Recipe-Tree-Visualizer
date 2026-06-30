import { describe, expect, it } from 'vitest';

import { buildOperationStatusLines, formatElapsed } from './operationStatus';

describe('formatElapsed', () => {
    it('formats short and long durations', () => {
        expect(formatElapsed(15)).toBe('15 с');
        expect(formatElapsed(125)).toBe('2 мин 5 с');
        expect(formatElapsed(3720)).toBe('1 ч 2 мин');
    });
});

describe('buildOperationStatusLines', () => {
    it('shows running export with elapsed time', () => {
        const lines = buildOperationStatusLines({
            exportActive: true,
            exportElapsedSec: 90,
            exportDisabledReason: null,
            exportError: null,
            hasSnapshot: false,
            exportedAt: null,
            isDefaultProfile: false,
            assetProgress: null,
            iconsPartial: false,
            blocksPartial: false,
        });
        expect(lines[0].text).toContain('идёт');
        expect(lines[0].text).toContain('1 мин 30 с');
        expect(lines[0].active).toBe(true);
    });

    it('shows partial asset state', () => {
        const lines = buildOperationStatusLines({
            exportActive: false,
            exportElapsedSec: 0,
            exportDisabledReason: null,
            exportError: null,
            hasSnapshot: true,
            exportedAt: '2026-06-30T10:00:00+00:00',
            isDefaultProfile: false,
            assetProgress: {
                version: '1.21.1',
                profile_id: 'p',
                running: false,
                icons: { running: false, done: 10, total: 100, error: 'x' },
                blocks: { running: false, done: 5, total: 5, error: null },
            },
            iconsPartial: true,
            blocksPartial: false,
        });
        expect(lines[1].tone).toBe('error');
        expect(lines[2].tone).toBe('success');
    });
});
