#!/usr/bin/env bash
# =====================================================================
# Campagne d'évaluation complète (à lancer le soir — tourne ~5-6 h).
#
#   Phase 1 — REFORMULATION : 4 modèles pour l'agent 1, SANS juge (rapide).
#             Synthèse fixée à qwen2.5:7b. On compare la RÉCUPÉRATION (recall@k).
#   Phase 2 — SYNTHÈSE      : 4 modèles pour l'agent 3, AVEC juge (lent).
#             Reformulation fixée à qwen2.5:7b. On compare la QUALITÉ (faithfulness...).
#
# Usage (depuis code/) :
#   bash run_eval_campaign.sh > eval_campaign.log 2>&1 &
#
# Chaque run écrit un JSON dans backend/eval/results/ et pousse ses scores
# dans Langfuse (tag = label du run).
# =====================================================================
set -u
cd "$(dirname "$0")"

MODELS="llama3.2:3b qwen2.5:7b mistral:7b qwen2.5:14b"

# --- Pré-vol : vérifie que tous les modèles sont bien téléchargés dans Ollama ---
echo "### Vérification des modèles Ollama ($(date '+%H:%M'))"
AVAIL="$(docker compose exec -T ollama ollama list 2>/dev/null)"
MISSING=""
for m in $MODELS; do
  echo "$AVAIL" | grep -q "$m" || MISSING="$MISSING $m"
done
if [ -n "$MISSING" ]; then
  echo "!!! Modèles manquants :$MISSING"
  echo "!!! Lance d'abord : make pull-models   (puis relance ce script)"
  exit 1
fi
echo "Tous les modèles sont présents."

short() { echo "$1" | sed 's/qwen2.5:14b/14b/;s/qwen2.5:7b/7b/;s/llama3.2:3b/3b/;s/mistral:7b/mistral/'; }

echo ""
echo "########## PHASE 1 — REFORMULATION (sans juge) ##########"
for m in $MODELS; do
  s="$(short "$m")"
  echo ">>> [$(date '+%H:%M')] reformulation=$m  (synthèse=llama3.2:3b rapide, sans juge)"
  EVAL_UNDERSTAND_MODEL="$m" EVAL_SYNTHESIZE_MODEL="llama3.2:3b" \
    EVAL_LABEL="reform_$s" EVAL_SKIP_JUDGE=1 make eval
done

echo ""
echo "########## PHASE 2 — SYNTHÈSE (avec juge) ##########"
for m in $MODELS; do
  s="$(short "$m")"
  echo ">>> [$(date '+%H:%M')] synthèse=$m  (reformulation fixe=qwen2.5:7b)"
  EVAL_SYNTHESIZE_MODEL="$m" EVAL_UNDERSTAND_MODEL="qwen2.5:7b" \
    EVAL_LABEL="synth_$s" make eval
done

echo ""
echo "########## CAMPAGNE TERMINÉE ($(date '+%H:%M')) ##########"
echo "Résultats JSON : backend/eval/results/    |    Scores : Langfuse (Dashboard/Scores)"
