import type { CalculateProductionRequest, ProductionPlan } from '../types/production';

export async function calculateProduction(
    request: CalculateProductionRequest,
): Promise<ProductionPlan> {
    const response = await fetch('/graph/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail ?? `Calculation failed (${response.status})`);
    }

    return response.json() as Promise<ProductionPlan>;
}
