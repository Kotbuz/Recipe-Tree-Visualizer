import '../styles/SlotQuantityBadge.css';

type SlotQuantityBadgeProps = {
    amount: number;
    slotType: 'input' | 'output';
};

export default function SlotQuantityBadge({ amount, slotType }: SlotQuantityBadgeProps) {
    if (amount <= 0) {
        return null;
    }

    return (
        <span
            className={`slot-quantity-badge slot-quantity-badge--${slotType}`}
            aria-label={`Количество: ${amount}`}
        >
            {formatAmount(amount)}
        </span>
    );
}

function formatAmount(amount: number): string {
    if (Number.isInteger(amount)) {
        return String(amount);
    }
    return amount.toFixed(2).replace(/\.?0+$/, '');
}
