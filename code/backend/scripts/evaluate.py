"""Harnais d'évaluation du pipeline RAG, avec remontée des scores dans Langfuse.

Pour chaque question de référence (eval/questions.json) :
  1. on crée une trace Langfuse (les appels des agents y sont rattachés) ;
  2. on exécute le pipeline multi-agents ;
  3. on calcule un signal de récupération SANS LLM (rappel de mots-clés) ;
  4. on calcule les métriques DeepEval (si installé + juge local configuré) ;
  5. on POUSSE tous ces scores dans Langfuse → graphiques du dashboard.

Exécution (env d'éval, services Compose démarrés) :

    make eval-deepeval                                # une fois (installe DeepEval)
    docker compose exec backend deepeval set-local-model \
        --model-name qwen2.5:7b --base-url http://ollama:11434/v1 --api-key ollama   # juge local (optionnel)
    make eval                                         # lance l'évaluation

Les résultats sont aussi écrits dans eval/results/. Dans Langfuse, ouvre
Dashboard / Scores : un graphique par métrique (par modèle, via les tags).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.agents.graph import run_pipeline  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.observability.langfuse_tracing import get_langfuse_client  # noqa: E402

QUESTIONS_PATH = ROOT / "eval" / "questions.json"
RESULTS_DIR = ROOT / "eval" / "results"


def keyword_recall(context: str, keywords: list[str]) -> float | None:
    if not keywords:
        return None
    ctx = context.lower()
    return sum(1 for k in keywords if k.lower() in ctx) / len(keywords)


# Marqueurs d'un REFUS explicite (le système signale l'absence d'information au
# lieu d'inventer). Choisis pour NE PAS chevaucher le titre de section standard
# "(3) Limites / manques" (le mot « manque » apparaît dans TOUTE réponse) :
# on ne retient que des tournures propres à un aveu d'absence d'information.
REFUSAL_MARKERS = [
    "ne permet pas de conclure",
    "ne permet pas de répondre",
    "ne permettent pas de répondre",
    "aucune information",
    "aucun extrait",
    "aucune source",
    "aucun élément",
    "aucune donnée",
    "aucune mention",
    "ne contient aucune",
    "ne contient pas",
    "ne fournit aucun",
    "ne fournit pas",
    "n'aborde pas",
    "n'abordent pas",
    "ne traite pas",
    "ne traitent pas",
    "ne concerne pas",
    "ne figure pas",
    "ne mentionne pas",
    "hors du champ",
    "hors corpus",
    "hors sujet",
    "sans rapport",
    "n'est pas couvert",
    "n'est pas abordé",
    "pas d'information",
]


def refusal_score(answer: str) -> float:
    """Retourne 1.0 si la réponse signale explicitement l'absence d'information
    (refus attendu sur une question hors-corpus), 0.0 sinon (le système a
    probablement inventé une réponse -> hallucination). Déterministe, sans juge."""
    a = answer.lower()
    return 1.0 if any(m in a for m in REFUSAL_MARKERS) else 0.0


def retrieval_metrics(sources: list[dict], expected: list[str], k: int) -> dict:
    """Métriques de récupération SANS LLM, basées sur les documents attendus.
    `expected` : sous-chaînes de titres/fichiers considérés pertinents.
    - precision@k : part des passages récupérés qui sont pertinents.
    - recall@k    : part des documents attendus effectivement retrouvés."""
    if not expected:
        return {}
    retrieved = [(s.get("title") or s.get("filename") or "")[:200] for s in sources[:k]]
    if not retrieved:
        return {"context_precision@k": 0.0, "context_recall@k": 0.0}
    rel_retrieved = sum(1 for r in retrieved if any(e.lower() in r.lower() for e in expected))
    found = sum(1 for e in expected if any(e.lower() in r.lower() for r in retrieved))
    return {
        "context_precision@k": round(rel_retrieved / len(retrieved), 3),
        "context_recall@k": round(found / len(expected), 3),
    }


def load_deepeval_metrics():
    """Charge et instancie les métriques DeepEval, ou (None, None) si indisponible.
    L'instanciation échoue si aucun juge n'est configuré (DeepEval tente alors
    OpenAI). On capture l'erreur pour ne pas faire planter toute l'évaluation."""
    try:
        from deepeval.metrics import (
            AnswerRelevancyMetric,
            ContextualRelevancyMetric,
            FaithfulnessMetric,
        )
        from deepeval.test_case import LLMTestCase

        metrics = {
            "answer_relevancy": AnswerRelevancyMetric(threshold=0.5),
            "faithfulness": FaithfulnessMetric(threshold=0.5),
            "contextual_relevancy": ContextualRelevancyMetric(threshold=0.5),
        }
        return metrics, LLMTestCase
    except Exception as exc:  # noqa: BLE001
        print(
            f"[deepeval] métriques LLM ignorées ({exc}).\n"
            "  Pour les activer, configure un juge local DANS le conteneur :\n"
            "    docker compose exec backend deepeval set-local-model --model-name llama3.2:3b "
            "--base-url http://ollama:11434/v1 --api-key ollama"
        )
        return None, None


def main() -> None:
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    # EVAL_ONLY_REFUSAL=1 -> ne teste QUE les questions hors-corpus (refus).
    # Rapide : on saute les questions de récupération, scoring 100% déterministe.
    if os.getenv("EVAL_ONLY_REFUSAL"):
        questions = [q for q in questions if q.get("expected_refusal")]
    # Modèles par agent (optionnels) : comparer des configs sans toucher au .env.
    #   EVAL_UNDERSTAND_MODEL -> agent 1 (reformulation), affecte la RÉCUPÉRATION.
    #   EVAL_SYNTHESIZE_MODEL -> agent 3 (synthèse), affecte la QUALITÉ de réponse.
    understand_model = os.getenv("EVAL_UNDERSTAND_MODEL") or None
    synthesize_model = os.getenv("EVAL_SYNTHESIZE_MODEL") or None
    default_model = settings.ollama_llm_model
    u_disp = understand_model or default_model
    s_disp = synthesize_model or default_model
    label = os.getenv("EVAL_LABEL") or f"u={u_disp}_s={s_disp}"
    # EVAL_SKIP_JUDGE=1 -> métriques déterministes seulement (rapide, ex. comparer
    # les modèles de reformulation où seule la récupération compte).
    skip_judge = bool(os.getenv("EVAL_SKIP_JUDGE"))
    print(f"Évaluation de {len(questions)} questions — label : {label}")
    print(f"  reformulation : {u_disp} | synthèse : {s_disp} | "
          f"juge : {'OFF' if skip_judge else 'ON si dispo'}\n")

    lf = get_langfuse_client()
    if lf is None:
        print("[langfuse] désactivé : les scores ne seront pas envoyés (résultats en JSON seulement).")
    metrics, LLMTestCase = (None, None) if skip_judge else load_deepeval_metrics()

    results = []
    for q in questions:
        print(f"[{q['id']}] {q['question']}")

        # 1. Trace Langfuse (le pipeline s'y rattache)
        trace = None
        callbacks = []
        if lf is not None:
            trace = lf.trace(name="eval", session_id="evaluation",
                             input={"question": q["question"]},
                             metadata={"label": label, "understand_model": u_disp,
                                       "synthesize_model": s_disp, "question_id": q["id"]},
                             tags=[label, "eval"])
            callbacks = [trace.get_langchain_handler(update_parent=False)]

        # 2. Pipeline (modèles par agent optionnels)
        state = run_pipeline(q["question"], None, None, callbacks,
                             understand_model, synthesize_model)
        answer = state.get("answer", "")
        # Les sources sont regroupées par article : le texte est dans `passages`.
        # On aplatit tous les passages pour obtenir le contexte récupéré.
        contexts = [
            p.get("text", "")
            for s in state.get("sources", [])
            for p in s.get("passages", [])
        ]
        scores: dict[str, float] = {}

        # 3. Métriques SANS LLM : rappel de mots-clés + récupération (precision/recall@k)
        recall = keyword_recall("\n".join(contexts), q.get("expected_keywords", []))
        if recall is not None:
            scores["keyword_recall"] = round(recall, 3)
        scores.update(
            retrieval_metrics(state.get("sources", []), q.get("expected_documents", []), settings.retrieval_top_k)
        )

        # 3bis. Cas hors-corpus : on ne mesure pas la récupération (rien de
        # pertinent à retrouver) mais le REFUS. refusal_ok=1.0 -> le système
        # signale l'absence d'info ; 0.0 -> il a probablement halluciné.
        if q.get("expected_refusal"):
            scores["refusal_ok"] = refusal_score(answer)

        # 4. Métriques DeepEval
        if metrics and contexts and answer:
            tc = LLMTestCase(input=q["question"], actual_output=answer, retrieval_context=contexts)
            for name, metric in metrics.items():
                try:
                    metric.measure(tc)
                    scores[name] = round(float(metric.score), 3)
                except Exception as exc:  # noqa: BLE001
                    print(f"  ! {name} : {exc}")

        # 5. Remontée des scores dans Langfuse
        if trace is not None:
            trace.update(output={"answer": answer})
            for name, value in scores.items():
                try:
                    lf.score(trace_id=trace.id, name=name, value=value)
                except Exception as exc:  # noqa: BLE001
                    print(f"  ! score langfuse {name} : {exc}")

        print(f"  scores : {scores}\n")
        results.append({"id": q["id"], "question": q["question"], "answer": answer, "scores": scores})

    if lf is not None:
        lf.flush()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = label.replace(":", "_").replace("/", "_").replace(" ", "")
    out = RESULTS_DIR / f"eval_{safe_label}_{stamp}.json"
    config = {
        "label": label,
        "understand_model": u_disp,
        "synthesize_model": s_disp,
        "judge": "off" if skip_judge else "on",
        "retrieval_top_k": settings.retrieval_top_k,
        "retrieval_pool": settings.retrieval_pool,
        "chunk_strategy": settings.chunk_strategy,
        "exclude_references": settings.exclude_references,
    }
    out.write_text(
        json.dumps({"label": label, "config": config, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Résultats : {out}")
    if lf is not None:
        print("Scores envoyés à Langfuse → Dashboard / Scores pour les graphiques.")


if __name__ == "__main__":
    main()
