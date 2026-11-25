export function normalize(value) {
  return value.normalize("NFKC").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}

export function matches(topic, query, aliases) {
  const groups = aliases.map(group => group.map(normalize));
  const fields = [topic.title, ...topic.categories, ...topic.keywords].map(normalize);
  const has = term => fields.some(field => field.includes(term));
  const words = query.trim().split(/[\s,]+/u).map(normalize).filter(Boolean);
  const reachable = new Set([0]);
  for (let start = 0; start < words.length; start++) {
    if (!reachable.has(start)) continue;
    for (let end = start + 1; end <= words.length; end++) {
      const term = words.slice(start, end).join("");
      if (has(term) || groups.some(group => group.includes(term) && group.some(has))) {
        reachable.add(end);
      }
    }
  }
  return reachable.has(words.length);
}
