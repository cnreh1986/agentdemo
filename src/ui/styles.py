"""Static CSS for workshop dashboard. No user HTML injection."""

APP_CSS = """
<style>
.main-header h1 { margin-bottom: 0.15rem; color: #0F172A; }
.tagline { color: #0D9488; font-weight: 600; font-size: 1.05rem; margin-bottom: 0.5rem; }
.explainer { color: #334155; margin-bottom: 1rem; }
.status-chip {
  display: inline-block; padding: 0.2rem 0.55rem; border-radius: 999px;
  font-size: 0.8rem; font-weight: 600; margin-right: 0.35rem;
}
.chip-ok { background: #D1FAE5; color: #065F46; }
.chip-wait { background: #E2E8F0; color: #334155; }
.chip-run { background: #DBEAFE; color: #1E40AF; }
.chip-warn { background: #FEF3C7; color: #92400E; }
.chip-err { background: #FEE2E2; color: #991B1B; }
.agent-card {
  border: 1px solid #CBD5E1; border-radius: 12px; padding: 0.85rem 1rem;
  background: white; min-height: 118px;
}
.agent-card.active { border-color: #0D9488; box-shadow: 0 0 0 2px rgba(13,148,136,0.2); }
.agent-card.done { border-color: #10B981; }
.agent-card.fail { border-color: #EF4444; }
.agent-card.warn { border-color: #F59E0B; }
.pipeline {
  display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center;
  margin: 0.5rem 0 1rem 0; font-size: 0.9rem;
}
.pipe-node {
  padding: 0.35rem 0.65rem; border-radius: 8px; background: #E2E8F0; color: #334155;
  font-weight: 600;
}
.pipe-node.Running, .pipe-node.Queued { background: #DBEAFE; color: #1E40AF; }
.pipe-node.Completed { background: #D1FAE5; color: #065F46; }
.pipe-node.Failed { background: #FEE2E2; color: #991B1B; }
.pipe-node.Needs\\ revision, .pipe-node.needs-revision {
  background: #FEF3C7; color: #92400E;
}
.warn-box {
  background: #FFF7ED; border-left: 4px solid #F59E0B; padding: 0.75rem 1rem;
  border-radius: 6px; margin: 0.5rem 0 1rem 0;
}
.agent-activity-overlay {
  border: 1px solid #CBD5E1;
  border-radius: 14px;
  padding: 1rem 1.15rem 1.25rem 1.15rem;
  margin: 0.35rem 0 1.25rem 0;
  background: linear-gradient(180deg, #F8FAFC 0%, #FFFFFF 42%);
  font-size: 1.05rem;
}
.agent-activity-overlay h3, .agent-activity-overlay h4 {
  color: #0F172A;
}
.overlay-pipeline .pipe-node {
  font-size: 0.95rem;
  min-width: 7.5rem;
  text-align: center;
}
.overlay-pipeline .pipe-node.active-node {
  box-shadow: 0 0 0 2px rgba(13,148,136,0.35);
  border: 1px solid #0D9488;
  font-size: 1.02rem;
}
.overlay-expand-chip {
  display: inline-block;
  padding: 0.45rem 0.85rem;
  border-radius: 10px;
  background: #ECFDF5;
  color: #065F46;
  font-weight: 700;
  border: 1px solid #6EE7B7;
  margin: 0.35rem 0 0.85rem 0;
}
</style>
"""


def chip_class(status: str) -> str:
    s = (status or "").lower()
    if s in {"completed", "ok", "human_approved", "approved"}:
        return "chip-ok"
    if s in {"running", "queued", "revision_running"}:
        return "chip-run"
    if s in {"needs revision", "revision_required", "awaiting", "awaiting_human_approval"}:
        return "chip-warn"
    if s in {"failed", "error", "human_rejected", "rejected"}:
        return "chip-err"
    return "chip-wait"
