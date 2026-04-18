export default function NavBadge({ count }: { count: number }) {
  if (count <= 0) return null;

  return (
    <span
      className="font-mono"
      style={{
        position: 'absolute',
        top: -6,
        right: -8,
        minWidth: 18,
        height: 18,
        borderRadius: 9,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 10,
        fontWeight: 600,
        lineHeight: 1,
        padding: '0 4px',
        background: 'var(--color-danger, #ef4444)',
        color: '#fff',
      }}
    >
      {count > 99 ? '99+' : count}
    </span>
  );
}
