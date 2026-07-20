"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, FileText, RefreshCw, Database, Upload, Trash2 } from "lucide-react";
import { listDocuments, uploadDocument, deleteDocument, type DocumentOut } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setDocs(await listDocuments());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        await uploadDocument(file);
      }
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handleDelete(doc: DocumentOut) {
    if (!confirm(`Supprimer « ${doc.title || doc.filename} » de l'index ?`)) return;
    setDeletingId(doc.id);
    setError(null);
    try {
      await deleteDocument(doc.id);
      setDocs((prev) => prev.filter((d) => d.id !== doc.id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDeletingId(null);
    }
  }

  useEffect(() => {
    // Garde d'auth locale : n'appelle pas l'API sans jeton (le ChatProvider
    // gère la redirection, mais on évite un appel 401 dans la fenêtre de course).
    if (!getToken()) return;
    load();
  }, []);

  const totalChunks = docs.reduce((a, d) => a + d.n_chunks, 0);

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="icon" className="h-9 w-9">
            <Link href="/">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-xl font-semibold">Corpus documentaire</h1>
            <p className="text-sm text-muted-foreground">Documents scientifiques indexés dans la base vectorielle</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf"
            multiple
            className="hidden"
            onChange={(e) => handleUpload(e.target.files)}
          />
          <Button size="sm" onClick={() => fileRef.current?.click()} disabled={uploading}>
            <Upload className={`h-4 w-4 ${uploading ? "animate-pulse" : ""}`} />
            {uploading ? "Indexation…" : "Importer un PDF"}
          </Button>
          <Button variant="outline" size="sm" onClick={load} disabled={loading || uploading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Rafraîchir
          </Button>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <FileText className="h-8 w-8 text-primary" />
            <div>
              <div className="text-2xl font-semibold">{docs.length}</div>
              <div className="text-xs text-muted-foreground">documents</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <Database className="h-8 w-8 text-primary" />
            <div>
              <div className="text-2xl font-semibold">{totalChunks}</div>
              <div className="text-xs text-muted-foreground">chunks indexés</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {error && (
        <Card className="mb-4 border-destructive/40 bg-destructive/5">
          <CardContent className="p-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      )}

      <Card>
        <div className="grid grid-cols-12 gap-2 border-b px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <div className="col-span-5">Titre</div>
          <div className="col-span-2">Année</div>
          <div className="col-span-2">Chunks</div>
          <div className="col-span-2">Statut</div>
          <div className="col-span-1" />
        </div>
        {loading && <div className="p-6 text-center text-sm text-muted-foreground">Chargement…</div>}
        {!loading && docs.length === 0 && (
          <div className="p-8 text-center text-sm text-muted-foreground">
            Aucun document indexé. Lance le script d&apos;ingestion du corpus ou importe un PDF.
          </div>
        )}
        {!loading &&
          docs.map((d) => (
            <div
              key={d.id}
              className="group grid grid-cols-12 items-center gap-2 border-b px-4 py-3 text-sm last:border-0"
            >
              <div className="col-span-5 min-w-0">
                <div className="truncate font-medium" title={d.title || d.filename}>
                  {d.title || d.filename}
                </div>
                {d.title && (
                  <div className="truncate text-[11px] text-muted-foreground" title={d.filename}>
                    {d.filename}
                  </div>
                )}
              </div>
              <div className="col-span-2 text-muted-foreground">{d.year ?? "—"}</div>
              <div className="col-span-2 text-muted-foreground">{d.n_chunks}</div>
              <div className="col-span-2">
                <Badge variant={d.status === "indexed" ? "success" : "secondary"}>{d.status}</Badge>
              </div>
              <div className="col-span-1 flex justify-end">
                <button
                  onClick={() => handleDelete(d)}
                  disabled={deletingId === d.id}
                  className="opacity-0 transition-opacity group-hover:opacity-100 disabled:opacity-50"
                  title="Supprimer de l'index"
                >
                  <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                </button>
              </div>
            </div>
          ))}
      </Card>
    </div>
  );
}
