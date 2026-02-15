#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

ACTIVE_DOCS=(
  README.md
  docs/README.md
  docs/overview/executive_overview.md
  docs/overview/technical_overview.md
  docs/overview/market_positioning.md
  docs/overview/research_sources.md
  docs/product/production_readiness.md
  docs/product/roadmap.md
  docs/product/known_issues.md
  docs/product/decision_log.md
  docs/engineering/api_contracts.md
  docs/engineering/data_contract_spec.md
  docs/engineering/model_readiness.md
  docs/engineering/model_tuning_and_dataset_readiness.md
  docs/engineering/ml_effectiveness.md
  docs/operations/smb_onboarding_runbook.md
  docs/operations/slo_policy.md
  docs/operations/integration_incident_runbook.md
  docs/demo/recruiter_demo_runbook.md
  docs/evidence/README.md
  docs/evidence/snapshots/README.md
)

DOCS_WITH_METADATA=(
  docs/README.md
  docs/overview/executive_overview.md
  docs/overview/technical_overview.md
  docs/overview/market_positioning.md
  docs/overview/research_sources.md
  docs/product/production_readiness.md
  docs/product/roadmap.md
  docs/product/known_issues.md
  docs/product/decision_log.md
  docs/engineering/api_contracts.md
  docs/engineering/data_contract_spec.md
  docs/engineering/model_readiness.md
  docs/engineering/model_tuning_and_dataset_readiness.md
  docs/engineering/ml_effectiveness.md
  docs/operations/smb_onboarding_runbook.md
  docs/operations/slo_policy.md
  docs/operations/integration_incident_runbook.md
  docs/demo/recruiter_demo_runbook.md
  docs/evidence/README.md
  docs/evidence/snapshots/README.md
)

for f in "${ACTIVE_DOCS[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "Missing active doc: $f"
    exit 1
  fi
done

echo "[ok] Active docs exist"

for f in "${DOCS_WITH_METADATA[@]}"; do
  grep -q "^- Last verified date:" "$f" || { echo "Missing metadata in $f: Last verified date"; exit 1; }
  grep -q "^- Audience:" "$f" || { echo "Missing metadata in $f: Audience"; exit 1; }
  grep -q "^- Scope:" "$f" || { echo "Missing metadata in $f: Scope"; exit 1; }
  grep -q "^- Source of truth:" "$f" || { echo "Missing metadata in $f: Source of truth"; exit 1; }
done

echo "[ok] Metadata contract present"

TMP_LINKS="$(mktemp)"
trap 'rm -f "$TMP_LINKS"' EXIT

rg -n "\[[^]]+\]\(([^)]+)\)" "${ACTIVE_DOCS[@]}" > "$TMP_LINKS" || true
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  file="${line%%:*}"
  target="$(echo "$line" | sed -E 's/.*\(([^)]+)\).*/\1/')"

  case "$target" in
    http://*|https://*|mailto:*|\#*)
      continue
      ;;
  esac

  target="${target%%#*}"
  [[ -z "$target" ]] && continue

  if [[ "$target" == /* ]]; then
    candidate="${target#/}"
  else
    candidate="$(dirname "$file")/$target"
  fi

  if [[ ! -e "$candidate" ]]; then
    echo "Broken link in $file: $target (resolved: $candidate)"
    exit 1
  fi
done < "$TMP_LINKS"

echo "[ok] Local markdown links resolve"

if rg -n "docs/archive/" docs/README.md docs/overview docs/product docs/engineering docs/operations docs/demo docs/evidence >/dev/null; then
  echo "Active docs may not link docs/archive/"
  rg -n "docs/archive/" docs/README.md docs/overview docs/product docs/engineering docs/operations docs/demo docs/evidence
  exit 1
fi

echo "[ok] Archive link hygiene"

if rg -n -i "cloud run|vertex|feature store|bigquery|gcp cloud|google cloud run" README.md docs/overview docs/product docs/engineering docs/operations docs/demo >/dev/null; then
  echo "Forbidden unsupported infrastructure claims found in active docs"
  rg -n -i "cloud run|vertex|feature store|bigquery|gcp cloud|google cloud run" README.md docs/overview docs/product docs/engineering docs/operations docs/demo
  exit 1
fi

echo "[ok] Unsupported-claim audit"

# Basic API parity checks for explicitly documented endpoints.
rg -q '@router.get\("/backtests"\)' backend/api/v1/routers/ml_ops.py
rg -q '@router.get\("/health"\)' backend/api/v1/routers/ml_ops.py
rg -q '@router.get\("/effectiveness"\)' backend/api/v1/routers/ml_ops.py
rg -q '@router.get\("/health"\)' backend/api/v1/routers/models.py
rg -q '@router.get\("/history"\)' backend/api/v1/routers/models.py
rg -q '@router.post\("/\{version\}/promote"\)' backend/api/v1/routers/models.py
rg -q '@router.get\("/sync-health"\)' backend/api/v1/routers/integrations.py

echo "[ok] API parity checks"

rg -q "ModelRetrainingLog" backend/workers/retrain.py
echo "[ok] Retraining event logging parity"

rg -q "def sync_registry_with_runtime_state" backend/ml/experiment.py
rg -q "sync_registry_with_runtime_state" backend/workers/retrain.py
rg -q "sync_registry_with_runtime_state" backend/api/v1/routers/models.py
echo "[ok] Registry sync parity"

ALLOWLIST="docs/evidence/snapshots/allowlist.txt"
if [[ ! -f "$ALLOWLIST" ]]; then
  echo "Missing artifact allowlist: $ALLOWLIST"
  exit 1
fi

EXTRA_TRACKED="$(comm -23 <(git ls-files docs/productization_artifacts | sort) <(sort "$ALLOWLIST") || true)"
if [[ -n "$EXTRA_TRACKED" ]]; then
  echo "Non-curated tracked artifacts found:"
  echo "$EXTRA_TRACKED"
  exit 1
fi

MISSING_ALLOWED="$(comm -13 <(git ls-files docs/productization_artifacts | sort) <(sort "$ALLOWLIST") || true)"
if [[ -n "$MISSING_ALLOWED" ]]; then
  echo "Allowlisted artifacts missing from tracking:"
  echo "$MISSING_ALLOWED"
  exit 1
fi

echo "[ok] Artifact allowlist matches tracked set"

echo "Documentation validation passed"
