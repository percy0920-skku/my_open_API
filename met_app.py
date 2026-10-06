"""Met Museum Art Search - a Streamlit app.

Run with:
    pip install streamlit requests
    streamlit run met_art_search.py
"""

from concurrent.futures import ThreadPoolExecutor

import requests
import streamlit as st

SEARCH_URL = "https://collectionapi.metmuseum.org/public/collection/v1.1/search"
OBJECT_URL = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"
TIMEOUT = 10          # seconds, applied to every request
CANDIDATE_POOL = 60   # IDs requested from the search; some will lack images
ONE_HOUR = 3600


class ServiceUnavailable(Exception):
    """Raised when the Met API cannot be reached or returns errors."""


@st.cache_data(ttl=ONE_HOUR, show_spinner=False)
def search_object_ids(query: str) -> list[int]:
    """Search the collection and return a list of matching object IDs."""
    try:
        response = requests.get(
            SEARCH_URL,
            params={"q": query, "hasImages": "true", "limit": CANDIDATE_POOL},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ServiceUnavailable(str(exc)) from exc

    # objectIDs is null (None) when nothing is found
    return (data.get("objectIDs") or [])[:CANDIDATE_POOL]


@st.cache_data(ttl=ONE_HOUR, show_spinner=False)
def fetch_object(object_id: int) -> dict | None:
    """Fetch details for one artwork. Returns None if it doesn't exist.

    Network errors raise, so failures are not cached for an hour.
    """
    response = requests.get(OBJECT_URL.format(object_id), timeout=TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    return {
        "title": data.get("title") or "Untitled",
        "artist": data.get("artistDisplayName") or "Unknown artist",
        "date": data.get("objectDate") or "Date unknown",
        "image": data.get("primaryImageSmall") or "",
        "url": data.get("objectURL") or "",
    }


def _safe_fetch(object_id: int):
    """Return (artwork_or_None, had_error) so one bad ID doesn't stop the rest."""
    try:
        return fetch_object(object_id), False
    except (requests.RequestException, ValueError):
        return None, True


def get_artworks(query: str, wanted: int) -> list[dict]:
    """Collect up to `wanted` artworks that have an image."""
    object_ids = search_object_ids(query)
    artworks: list[dict] = []
    attempts = errors = 0

    with ThreadPoolExecutor(max_workers=6) as pool:
        # Fetch in small batches so we stop as soon as we have enough
        for start in range(0, len(object_ids), wanted):
            batch = object_ids[start : start + wanted]
            for artwork, had_error in pool.map(_safe_fetch, batch):
                attempts += 1
                errors += had_error
                if artwork and artwork["image"]:  # skip artworks with no image
                    artworks.append(artwork)
            if len(artworks) >= wanted:
                break

    if attempts and errors == attempts:
        raise ServiceUnavailable("Every artwork request failed.")

    return artworks[:wanted]


def show_grid(artworks: list[dict], columns: int = 3) -> None:
    """Render artworks in a grid with `columns` columns."""
    for row_start in range(0, len(artworks), columns):
        cols = st.columns(columns)
        for col, art in zip(cols, artworks[row_start : row_start + columns]):
            with col:
                st.image(art["image"], use_container_width=True)
                st.markdown(f"**{art['title']}**")
                st.caption(f"{art['artist']} · {art['date']}")
                if art["url"]:
                    st.markdown(f"[View on the Met website]({art['url']})")


def main() -> None:
    st.set_page_config(page_title="Met Museum Art Search", page_icon="🖼️", layout="wide")
    st.title("🖼️ Met Museum Art Search")

    query = st.text_input("Search for Artworks", value="flower").strip()
    count = st.slider("Number of artworks to show", min_value=3, max_value=12, value=6)

    if query:
        try:
            with st.spinner("Searching the Met collection..."):
                artworks = get_artworks(query, count)
        except ServiceUnavailable:
            st.error(
                "Sorry, we couldn't reach the Met Museum service right now. "
                "Please check your connection and try again in a moment."
            )
        else:
            if artworks:
                show_grid(artworks)
            else:
                st.info(
                    f"No artworks with images were found for “{query}”. "
                    "Try a different search word."
                )
    else:
        st.info("Enter a search word to explore the collection.")

    st.divider()
    st.caption(
        "Artwork data and images from The Metropolitan Museum of Art "
        "[Open Access](https://www.metmuseum.org/about-the-met/policies-and-documents/open-access) "
        "program, via the Met Collection API."
    )


if __name__ == "__main__":
    main()
