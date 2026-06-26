import type { FlowRateUnit } from '../types/production';

export function toRatePerMinute(rate: number, unit: FlowRateUnit): number {
    switch (unit) {
        case 'per_second':
            return rate * 60;
        case 'per_hour':
            return rate / 60;
        default:
            return rate;
    }
}

export function fromRatePerMinute(ratePerMinute: number, unit: FlowRateUnit): number {
    switch (unit) {
        case 'per_second':
            return ratePerMinute / 60;
        case 'per_hour':
            return ratePerMinute * 60;
        default:
            return ratePerMinute;
    }
}

export function formatFlowRate(ratePerMinute: number, unit: FlowRateUnit): string {
    const value = fromRatePerMinute(ratePerMinute, unit);
    const suffix = unit === 'per_second' ? '/с' : unit === 'per_hour' ? '/ч' : '/мин';
    const formatted = Number.isInteger(value)
        ? String(value)
        : value >= 100
          ? Math.round(value).toString()
          : value.toFixed(value >= 10 ? 1 : 2);
    return `${formatted}${suffix}`;
}

export const FLOW_RATE_UNIT_LABELS: Record<FlowRateUnit, string> = {
    per_second: 'предметы / сек',
    per_minute: 'предметы / мин',
    per_hour: 'предметы / час',
};
