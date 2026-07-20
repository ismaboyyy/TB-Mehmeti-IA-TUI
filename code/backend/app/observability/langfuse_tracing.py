"""Tracing optionnel via Langfuse.

Le tracing n'est actif que si LANGFUSE_PUBLIC_KEY et LANGFUSE_SECRET_KEY sont
fournis. Sinon, get_callback_handler renvoie None et le pipeline fonctionne
normalement, sans observabilité. On isole l'import de langfuse ici pour ne pas
le rendre obligatoire.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache

from app.core.config import settings


def langfuse_enabled() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


@lru_cache
def get_langfuse_client():
    """Client Langfuse (bas niveau), instancié UNE seule fois (singleton).
    Évite d'accumuler clients/threads à chaque requête. None si désactivé."""
    if not langfuse_enabled():
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host or None,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[langfuse] client indisponible : {exc}")
        return None


def get_callback_handler(session_id: str | None = None):
    """Renvoie un CallbackHandler Langfuse pour LangChain, ou None si désactivé.
    Le session_id regroupe, dans l'interface Langfuse, les traces d'une même
    conversation."""
    if not langfuse_enabled():
        return None
    try:
        from langfuse.callback import CallbackHandler

        return CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host or None,
            session_id=session_id,
        )
    except Exception as exc:  # noqa: BLE001 — le tracing ne doit jamais casser une requête
        print(f"[langfuse] désactivé (erreur d'initialisation : {exc})")
        return None


class PipelineTrace:
    """Trace Langfuse d'une exécution du pipeline RAG, prête à l'emploi.

    Toute la tuyauterie (création de la trace, spans, flush) et la gestion
    d'erreur sont encapsulées ici. Si Langfuse est désactivé, l'objet devient
    un NO-OP : l'appelant n'a aucun `if trace is not None` à écrire.

    Utilisation côté API :
        trace = PipelineTrace(question, session_id=conv_id, model=model_name)
        state = {..., "callbacks": trace.callbacks}
        with trace.span("agent2-recherche", search_query=q) as out:
            ...
            out["num_sources"] = n
        trace.finalize(answer=answer, num_sources=n)
    """

    def __init__(self, question: str, session_id: str, model: str) -> None:
        self._client = get_langfuse_client()
        self._trace = None
        self.callbacks: list = []
        if self._client is None:
            return
        try:
            self._trace = self._client.trace(
                name="rag-pipeline",
                session_id=session_id,
                input={"question": question},
                metadata={"model": model},
                tags=[model],
            )
            self.callbacks = [self._trace.get_langchain_handler(update_parent=False)]
        except Exception as exc:  # noqa: BLE001 — le tracing ne doit jamais casser une requête
            print(f"[langfuse] trace non créée : {exc}")
            self._trace = None

    @contextmanager
    def span(self, name: str, **inputs):
        """Mesure une étape. Remplir le dict `out` cédé pour enregistrer la sortie
        du span ; il est envoyé automatiquement à la fermeture du bloc `with`."""
        span = None
        if self._trace is not None:
            try:
                span = self._trace.span(name=name, input=inputs or None)
            except Exception:  # noqa: BLE001
                span = None
        out: dict = {}
        try:
            yield out
        finally:
            if span is not None:
                try:
                    span.end(output=out or None)
                except Exception:  # noqa: BLE001
                    pass

    def finalize(self, **output) -> None:
        """Renseigne la sortie de la trace et force l'envoi à Langfuse."""
        if self._trace is None:
            return
        try:
            self._trace.update(output=output)
            self._client.flush()
        except Exception:  # noqa: BLE001
            pass
