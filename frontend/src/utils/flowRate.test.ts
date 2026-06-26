import { describe, expect, it } from 'vitest';

import { formatFlowRate, fromRatePerMinute, toRatePerMinute } from './flowRate';

describe('flowRate', () => {
    it('converts to and from per-minute baseline', () => {
        expect(toRatePerMinute(1, 'per_second')).toBe(60);
        expect(toRatePerMinute(60, 'per_hour')).toBe(1);
        expect(fromRatePerMinute(120, 'per_second')).toBe(2);
        expect(fromRatePerMinute(120, 'per_hour')).toBe(7200);
    });

    it('formats labels for display units', () => {
        expect(formatFlowRate(60, 'per_minute')).toBe('60/мин');
        expect(formatFlowRate(60, 'per_second')).toBe('1/с');
        expect(formatFlowRate(60, 'per_hour')).toBe('3600/ч');
    });
});
