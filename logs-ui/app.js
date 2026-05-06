function normalizeText(value) {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();
}

function updateChatCount(countNode, visibleCount, hasQuery) {
  if (!countNode) {
    return;
  }

  if (hasQuery) {
    countNode.textContent =
      visibleCount === 1 ? "1 resultado" : `${visibleCount} resultados`;
    return;
  }

  countNode.textContent =
    visibleCount === 1 ? "1 activa" : `${visibleCount} activas`;
}

document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("chat-search");
  const countNode = document.getElementById("chat-count");
  const emptyState = document.getElementById("chat-no-results");
  const chatLinks = Array.from(document.querySelectorAll(".chat-link"));

  if (!searchInput || !countNode || !emptyState || chatLinks.length === 0) {
    return;
  }

  const getCurrentHash = () => {
    if (window.location.hash) {
      return window.location.hash;
    }
    return chatLinks[0].getAttribute("href");
  };

  const applySearch = () => {
    const rawQuery = searchInput.value;
    const query = normalizeText(rawQuery);
    const hasQuery = query.length > 0;

    const visibleLinks = chatLinks.filter((link) => {
      const haystack = normalizeText(link.textContent || "");
      const matches = !hasQuery || haystack.includes(query);
      link.hidden = !matches;
      return matches;
    });

    emptyState.hidden = visibleLinks.length > 0;
    updateChatCount(countNode, visibleLinks.length, hasQuery);

    if (visibleLinks.length === 0) {
      return;
    }

    const currentHash = getCurrentHash();
    const currentStillVisible = visibleLinks.some(
      (link) => link.getAttribute("href") === currentHash
    );

    if (!currentStillVisible) {
      const firstVisible = visibleLinks[0].getAttribute("href");
      if (firstVisible) {
        window.location.hash = firstVisible;
      }
    }
  };

  searchInput.addEventListener("input", applySearch);
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      searchInput.value = "";
      applySearch();
    }
  });

  applySearch();
});
