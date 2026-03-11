import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiFetch, apiUrl } from "../api/client";

const POLL_INTERVAL_MS = 3000;

type CardGalleryItem = {
  id: string;
  position: number;
  name: string | null;
  meaning: string | null;
  description: string | null;
  status: string;
  image_url: string | null;
};

type DeckDetailOut = {
  id: string;
  session_id: string;
  style_bible_id: string;
  status: string;
  deck_size: number;
  created_at: string;
  approved_count: number;
  total_cards: number;
  cards: CardGalleryItem[] | null;
};

export default function DeckProgressPage() {
  const { deckId } = useParams<"deckId">();
  const navigate = useNavigate();
  const [deck, setDeck] = useState<DeckDetailOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchDeck = useCallback(async () => {
    if (!deckId) return;
    try {
      const data = await apiFetch<DeckDetailOut>(
        `/decks/${deckId}?include=cards`
      );
      setDeck(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load deck");
    }
  }, [deckId]);

  useEffect(() => {
    if (!deckId) {
      navigate("/", { replace: true });
      return;
    }
    fetchDeck();
  }, [deckId, navigate, fetchDeck]);

  useEffect(() => {
    if (!deckId || !deck) return;
    if (deck.status === "complete" || deck.status === "failed") return;
    const t = setInterval(fetchDeck, POLL_INTERVAL_MS);
    return () => clearInterval(t);
  }, [deckId, deck?.status, fetchDeck]);

  function handleDownload(type: "zip" | "pdf") {
    if (!deckId) return;
    window.open(apiUrl(`/decks/${deckId}/download?type=${type}`), "_blank", "noopener");
  }

  if (!deckId) {
    return null;
  }

  const isComplete = deck?.status === "complete";
  const isFailed = deck?.status === "failed";
  const isGenerating =
    !deck || deck.status === "pending" || deck.status === "generating";
  const cards = deck?.cards ?? [];

  return (
    <main style={{ maxWidth: 900, margin: "2rem auto", padding: "0 1rem" }}>
      <p style={{ marginBottom: "1rem" }}>
        <a href="/">← Start over</a>
      </p>
      <h1>Your deck</h1>

      {isGenerating && (
        <p>
          Generating cards… {deck?.approved_count ?? 0} / {deck?.total_cards ?? deck?.deck_size ?? "—"} approved
        </p>
      )}

      {isFailed && (
        <p style={{ color: "crimson" }}>
          Deck generation failed. You can try again from the start page.
        </p>
      )}

      {isComplete && (
        <>
          <p>
            Your deck is ready. Download the full set or browse the cards below.
          </p>
          <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
            <button type="button" onClick={() => handleDownload("zip")}>
              Download ZIP
            </button>
            <button type="button" onClick={() => handleDownload("pdf")}>
              Download PDF
            </button>
          </div>
          {cards.length > 0 && (
            <section
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
                gap: "1rem",
              }}
            >
              {cards
                .slice()
                .sort((a, b) => a.position - b.position)
                .map((card) => (
                  <figure
                    key={card.id}
                    style={{
                      margin: 0,
                      textAlign: "center",
                      breakInside: "avoid",
                    }}
                  >
                    {card.image_url ? (
                      <img
                        src={apiUrl(card.image_url)}
                        alt={card.name ?? `Card ${card.position}`}
                        loading="lazy"
                        style={{
                          width: "100%",
                          aspectRatio: "1",
                          objectFit: "cover",
                          borderRadius: 6,
                        }}
                      />
                    ) : (
                      <div
                        style={{
                          width: "100%",
                          aspectRatio: "1",
                          background: "#eee",
                          borderRadius: 6,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: "0.85rem",
                          color: "#666",
                        }}
                      >
                        No image
                      </div>
                    )}
                    <figcaption style={{ fontSize: "0.8rem", marginTop: 4 }}>
                      {card.name ?? `#${card.position}`}
                    </figcaption>
                  </figure>
                ))}
            </section>
          )}
        </>
      )}

      {error && (
        <p style={{ color: "crimson", marginTop: "1rem" }}>{error}</p>
      )}
    </main>
  );
}
