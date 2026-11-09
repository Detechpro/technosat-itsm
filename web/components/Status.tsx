const TONE: Record<string, string> = {
  resolved: "b-ok", closed: "b-ok", done: "b-ok", approved: "b-ok",
  rejected: "b-bad", cancelled: "b-bad", overdue: "b-bad",
  pending_approval: "b-warn", waiting_for_user: "b-warn", on_hold: "b-warn", pending: "b-warn",
};

export function StatusBadge({ value, label }: { value: string; label: string }) {
  return <span className={`badge ${TONE[value] ?? ""}`}>{label}</span>;
}
