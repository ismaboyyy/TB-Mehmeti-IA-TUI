#!/usr/bin/env bash
# =====================================================================
# Phase 2 (SYNTHÈSE) RE-JOUÉE avec un JUGE UNIQUE = qwen2.5:14b.
#
# But : homogénéiser l'évaluation. Les runs précédents étaient jugés par
# qwen2.5:7b (juge léger -> couverture partielle). Ici les 4 modèles de
# synthèse sont notés par LE MÊME juge 14b -> comparaison valable.
#
# Reformulation fixée à qwen2.5:7b (on isole la synthèse).
# Labels suffixés "_j14b" -> ne PAS écraser les anciens runs (juge 7b).
#
# Mémoire (Docker = 15,67 Go) : juge 14b = 9 Go, + modèle de synthèse.
#   synth=3b (2)  -> 11 Go    OK
#   synth=14b (9) -> 9 Go     OK (même modèle réutilisé)
#   synth=mistral (4,4) / 7b (4,7) -> ~13,4-13,7 Go  LIMITE (risque OOM)
# -> on lance les runs SÛRS d'abord (3b, 14b), les risqués ensuite (mistral, 7b),
#    pour garder un maximum de résultats si un run tombe en OOM.
#
# Usage (depuis code/) :
#   bash run_synth_judge14b.sh > synth_judge14b.log 2>&1 &
# =====================================================================
set -u
cd "$(dirname "$0")"

JUDGE="qwen2.5:14b"

echo "### [$(date '+%H:%M')] Configuration du juge DeepEval -> $JUDGE"
docker compose exec -T backend deepeval set-local-model \
  --model-name "$JUDGE" --base-url http://ollama:11434/v1 --api-key ollama
echo "--- .deepeval effectif ---"
docker compose exec -T backend cat /app/.deepeval
echo ""

# Ordre volontaire : sûrs (3b, 14b) puis risqués (mistral, 7b).
SYNTH_MODELS="llama3.2:3b qwen2.5:14b mistral:7b qwen2.5:7b"
short() { echo "$1" | sed 's/qwen2.5:14b/14b/;s/qwen2.5:7b/7b/;s/llama3.2:3b/3b/;s/mistral:7b/mistral/'; }

echo "########## SYNTHÈSE — juge unique = $JUDGE ##########"
for m in $SYNTH_MODELS; do
  s="$(short "$m")"
  echo ""
  echo ">>> [$(date '+%H:%M')] synthèse=$m  (reformulation=qwen2.5:7b, juge=$JUDGE)"
  EVAL_SYNTHESIZE_MODEL="$m" EVAL_UNDERSTAND_MODEL="qwen2.5:7b" \
    EVAL_LABEL="synth_${s}_j14b" make eval
done

echo ""
echo "########## TERMINÉ ($(date '+%H:%M')) ##########"
echo "Résultats JSON : backend/eval/results/eval_synth_*_j14b_*.json"
echo "Langfuse : tags synth_3b_j14b / synth_14b_j14b / synth_mistral_j14b / synth_7b_j14b"
