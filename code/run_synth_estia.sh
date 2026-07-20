#!/usr/bin/env bash
# =====================================================================
# Phase 2 (SYNTHÈSE) sur le NOUVEL index ESTIA-only, avec JUGE CROISÉ.
#
# Design anti auto-jugement : le juge n'est JAMAIS le modèle évalué.
#   - 3b, 7b, mistral  -> jugés par le 14b  (neutre pour eux)
#   - 14b              -> jugé par le 7b    (neutre pour lui)
#
#   reformulation FIXÉE = qwen2.5:7b (on isole la synthèse)
#   labels suffixés "_jXX_estia" -> encode le juge + l'index, n'écrase rien.
#
# Mémoire (Docker 18,59 Go) : pic ~16-17 Go (synth + juge + backend). OK, mais
# ferme les apps lourdes. Le 14b reste chargé pendant tout le groupe 1.
#
# Usage (depuis code/) :
#   bash run_synth_estia.sh > synth_estia.log 2>&1 &
# =====================================================================
set -u
cd "$(dirname "$0")"

set_judge() {
  echo "### [$(date '+%H:%M')] Bascule juge -> $1"
  docker compose exec -T backend deepeval set-local-model \
    --model-name "$1" --base-url http://ollama:11434/v1 --api-key ollama >/dev/null 2>&1
  docker compose exec -T backend cat /app/.deepeval | tr ',' '\n' | grep MODEL_NAME
}

run_synth() {  # $1=modèle synthèse  $2=label court  $3=juge court
  echo ""
  echo ">>> [$(date '+%H:%M')] synthèse=$1  (reform=qwen2.5:7b, juge court=$3)"
  EVAL_SYNTHESIZE_MODEL="$1" EVAL_UNDERSTAND_MODEL="qwen2.5:7b" \
    EVAL_LABEL="synth_${2}_j${3}_estia" make eval
}

echo "########## SYNTHÈSE index ESTIA — juge croisé (anti auto-jugement) ##########"

# --- Groupe 1 : 3b / 7b / mistral, jugés par le 14b ---
set_judge "qwen2.5:14b"
run_synth "llama3.2:3b" "3b"      "14b"
run_synth "qwen2.5:7b"  "7b"      "14b"
run_synth "mistral:7b"  "mistral" "14b"

# --- Groupe 2 : 14b, jugé par le 7b ---
set_judge "qwen2.5:7b"
run_synth "qwen2.5:14b" "14b" "7b"

# Remet le juge par défaut sur 7b (état de repos)
docker compose exec -T backend deepeval set-local-model \
  --model-name qwen2.5:7b --base-url http://ollama:11434/v1 --api-key ollama >/dev/null 2>&1

echo ""
echo "########## TERMINÉ ($(date '+%H:%M')) ##########"
echo "Résultats : backend/eval/results/eval_synth_*_estia_*.json"
