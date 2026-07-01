export type FlowRateUnit = 'per_second' | 'per_minute' | 'per_hour';

export interface ProductionTarget {
    nodeId: string;
    slotType: 'output';
    itemIndex: number;
    itemId: string;
    ratePerMinute: number;
}

export interface ProductionStage {
    recipe_node_id: string;
    recipe_id: string;
    machine_id: string;
    machine_count: number;
    machine_limit_applied?: boolean;
    input_rates: Record<string, number>;
    output_rates: Record<string, number>;
}

export interface ProductionPlan {
    target_item_id: string;
    target_rate_per_minute: number;
    effective_target_rate_per_minute: number;
    stages: ProductionStage[];
    total_raw_items: Record<string, number>;
    constraint_errors?: string[];
}

export interface CalculateProductionRequest {
    target_item_id?: string;
    target_rate_per_minute?: number;
    graph: {
        item_nodes: Array<{
            node_id: string;
            item_id: string;
            amount: number;
            x: number;
            y: number;
        }>;
        recipe_nodes: Array<{
            node_id: string;
            recipe_id: string;
            kind?: string | null;
            duration_ticks?: number | null;
            machine_limit?: number | null;
            output_rate_limit_per_minute?: number | null;
            speed_percent?: number;
            auto_round?: boolean;
            x: number;
            y: number;
        }>;
        edges: Array<{
            edge_id: string;
            source_node_id: string;
            target_node_id: string;
            item_id: string;
            amount: number;
        }>;
    };
    version: string;
    profile_id?: string;
    include_mods?: boolean;
    include_synthetic?: boolean;
}
