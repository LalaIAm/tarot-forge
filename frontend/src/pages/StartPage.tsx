import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../api/client";

type StyleBibleJobOut = {
  session_id: string;
  style_bible_id: string;
  status: string;
};

export default function StartPage() {
  const navigate = useNavigate();
  const [creativeDirection, setCreativeDirection] = useState("");
  const [medium, setMedium] = useState("");
  const [deckSize, setDeckSize] = useState<22 | 78>(78);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const out = await apiFetch<StyleBibleJobOut>("/style-bible", {
        method: "POST",
        body: JSON.stringify({
          creative_direction: creativeDirection.trim(),
          medium: medium.trim(),
          deck_size: deckSize,
        }),
      });
      navigate("/style-bible", {
        state: {
          sessionId: out.session_id,
          styleBibleId: out.style_bible_id,
          deckSize,
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main style={{ maxWidth: 480, margin: "2rem auto", padding: "0 1rem" }}>
      <h1>Vibe Tarot</h1>
      <p>
        Describe your vision and we’ll generate a style guide, then your deck.
      </p>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: "1rem" }}>
          <label
            htmlFor="direction"
            style={{ display: "block", marginBottom: 4 }}
          >
            Creative direction
          </label>
          <textarea
            id="direction"
            value={creativeDirection}
            onChange={(e) => setCreativeDirection(e.target.value)}
            placeholder="e.g. dark botanical, art nouveau"
            rows={3}
            required
            style={{ width: "100%", boxSizing: "border-box" }}
          />
        </div>
        <div style={{ marginBottom: "1rem" }}>
          <label htmlFor="medium" style={{ display: "block", marginBottom: 4 }}>
            Artistic medium
          </label>
          <input
            id="medium"
            type="text"
            value={medium}
            onChange={(e) => setMedium(e.target.value)}
            placeholder="e.g. watercolor, digital collage"
            required
            style={{ width: "100%", boxSizing: "border-box" }}
          />
        </div>
        <div style={{ marginBottom: "1rem" }}>
          <label style={{ display: "block", marginBottom: 4 }}>Deck size</label>
          <select
            aria-label="Deck size"
            value={deckSize}
            onChange={(e) => setDeckSize(Number(e.target.value) as 22 | 78)}
          >
            <option value={22}>22 (Major Arcana only)</option>
            <option value={78}>78 (full deck)</option>
          </select>
        </div>
        {error && (
          <p style={{ color: "crimson", marginBottom: "1rem" }}>{error}</p>
        )}
        <button type="submit" disabled={submitting}>
          {submitting ? "Starting…" : "Create style guide"}
        </button>
      </form>
    </main>
  );
}
