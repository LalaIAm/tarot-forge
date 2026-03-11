import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { apiFetch } from "../api/client";

const POLL_INTERVAL_MS = 3000;

type LocationState = {
  sessionId: string;
  styleBibleId: string;
  deckSize: number;
} | null;

type StyleBibleOut = {
  id: string;
  session_id: string;
  status: string;
  content: string | null;
  revision: number;
  created_at: string;
};

type DeckOut = {
  id: string;
  session_id: string;
  style_bible_id: string;
  status: string;
  deck_size: number;
  created_at: string;
};

export default function StyleBiblePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as LocationState | undefined;
  const [styleBible, setStyleBible] = useState<StyleBibleOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [requestChangesOpen, setRequestChangesOpen] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [requestingChanges, setRequestingChanges] = useState(false);

  const styleBibleId = state?.styleBibleId;
  const sessionId = state?.sessionId;
  const deckSize = state?.deckSize ?? 78;

  const fetchStyleBible = useCallback(async () => {
    if (!styleBibleId) return;
    try {
      const data = await apiFetch<StyleBibleOut>(`/style-bibles/${styleBibleId}`);
      setStyleBible(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load style bible");
    }
  }, [styleBibleId]);

  useEffect(() => {
    if (!sessionId || !styleBibleId) {
      navigate("/", { replace: true });
      return;
    }
    fetchStyleBible();
  }, [sessionId, styleBibleId, navigate, fetchStyleBible]);

  useEffect(() => {
    if (!styleBibleId || !styleBible) return;
    if (styleBible.status === "ready" || styleBible.status === "approved") return;
    const t = setInterval(fetchStyleBible, POLL_INTERVAL_MS);
    return () => clearInterval(t);
  }, [styleBibleId, styleBible?.status, fetchStyleBible]);

  async function handleApprove() {
    if (!styleBibleId || !sessionId) return;
    setApproving(true);
    setError(null);
    try {
      await apiFetch(`/style-bibles/${styleBibleId}/approve`, {
        method: "POST",
      });
      const deck = await apiFetch<DeckOut>(`/sessions/${sessionId}/decks`, {
        method: "POST",
        body: JSON.stringify({
          style_bible_id: styleBibleId,
          deck_size: deckSize,
        }),
      });
      navigate(`/decks/${deck.id}`, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setApproving(false);
    }
  }

  async function handleRequestChanges() {
    if (!styleBibleId || !feedback.trim()) return;
    setRequestingChanges(true);
    setError(null);
    try {
      await apiFetch(`/style-bibles/${styleBibleId}/request-changes`, {
        method: "POST",
        body: JSON.stringify({ feedback: feedback.trim() }),
      });
      setRequestChangesOpen(false);
      setFeedback("");
      setStyleBible((prev) =>
        prev ? { ...prev, status: "generating" } : null
      );
      fetchStyleBible();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setRequestingChanges(false);
    }
  }

  if (!sessionId || !styleBibleId) {
    return null;
  }

  const isReady = styleBible?.status === "ready";
  const isApproved = styleBible?.status === "approved";
  const isGenerating =
    !styleBible || styleBible.status === "draft" || styleBible.status === "generating";

  return (
    <main style={{ maxWidth: 720, margin: "2rem auto", padding: "0 1rem" }}>
      <p style={{ marginBottom: "1rem" }}>
        <a href="/">← Start over</a>
      </p>
      <h1>Style guide</h1>

      {isGenerating && (
        <p>
          Your style bible is being generated… (revision{" "}
          {styleBible?.revision ?? 1})
        </p>
      )}

      {isReady && (
        <>
          <p>Review the style guide below. Approve to start deck generation, or request changes.</p>
          {styleBible.content && (
            <section
              style={{
                marginTop: "1rem",
                marginBottom: "1.5rem",
                padding: "1rem",
                background: "#f6f6f6",
                borderRadius: 8,
                whiteSpace: "pre-wrap",
                fontFamily: "inherit",
                fontSize: "0.95rem",
                lineHeight: 1.5,
              }}
            >
              {styleBible.content}
            </section>
          )}
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={handleApprove}
              disabled={approving}
            >
              {approving ? "Starting deck…" : "Approve and create deck"}
            </button>
            <button
              type="button"
              onClick={() => setRequestChangesOpen(true)}
              disabled={approving}
            >
              Request changes
            </button>
          </div>
        </>
      )}

      {isApproved && (
        <p>This style bible is already approved. Start deck creation from the start page if needed.</p>
      )}

      {error && (
        <p style={{ color: "crimson", marginTop: "1rem" }}>{error}</p>
      )}

      {requestChangesOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="request-changes-title"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10,
          }}
          onClick={() => !requestingChanges && setRequestChangesOpen(false)}
        >
          <div
            style={{
              background: "white",
              padding: "1.5rem",
              borderRadius: 8,
              maxWidth: 400,
              width: "90%",
              boxShadow: "0 4px 20px rgba(0,0,0,0.15)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="request-changes-title">Request changes</h2>
            <p style={{ fontSize: "0.9rem", color: "#666", marginBottom: "1rem" }}>
              Describe what you’d like changed. The style guide will be regenerated.
            </p>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="e.g. Make the palette more muted, less saturated"
              rows={4}
              required
              style={{ width: "100%", boxSizing: "border-box", marginBottom: "1rem" }}
            />
            <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={() => setRequestChangesOpen(false)}
                disabled={requestingChanges}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRequestChanges}
                disabled={!feedback.trim() || requestingChanges}
              >
                {requestingChanges ? "Submitting…" : "Submit feedback"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
