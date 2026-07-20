#!/usr/bin/env bash
# =====================================================================
# Tests SANS juge (métriques déterministes uniquement, PAS de DeepEval).
#
# Compare l'effet du modèle de REFORMULATION (agent 1) sur la RÉCUPÉRATION :
#   keyword_recall, context_precision@k, context_recall@k.
# Ces métriques ne dépendent QUE de la récupération -> donc du modèle de
# reformulation. La synthèse est fixée au modèle le plus rapide (llama3.2:3b)
# car elle n'affecte pas ces métriques (elle intervient après la récupération).
#
# Usage (depuis code/) :
#   bash run_eval_nojudge.sh > eval_nojudge.log 2>&1 &
# =====================================================================
set -u
cd "$(dirname "$0")"

MODELS="llama3.2:3b qwen2.5:7b mistral:7b qwen2.5:14b"
short() { echo "$1" | sed 's/qwen2.5:14b/14b/;s/qwen2.5:7b/7b/;s/llama3.2:3b/3b/;s/mistral:7b/mistral/'; }

echo "### Vérification des modèles Ollama ($(date '+%H:%M'))"
AVAIL="$(docker compose exec -T ollama ollama list 2>/dev/null)"
for m in $MODELS; do
  echo "$AVAIL" | grep -q "$m" || { echo "!!! Modèle manquant : $m  (fais 'make pull-models')"; exit 1; }
done
echo "Tous les modèles sont présents."
echo ""

for m in $MODELS; do
  s="$(short "$m")"
  echo ">>> [$(date '+%H:%M')] reformulation=$m  (synthèse=llama3.2:3b, SANS juge)"
  EVAL_UNDERSTAND_MODEL="$m" EVAL_SYNTHESIZE_MODEL="llama3.2:3b" \
    EVAL_LABEL="reform_$s" EVAL_SKIP_JUDGE=1 make eval
done

echo ""
echo "### TERMINÉ ($(date '+%H:%M'))"
echo "Résultats JSON : backend/eval/results/    |    Scores : Langfuse (tags reform_*)"
