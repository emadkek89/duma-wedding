import { matches } from "./search.mjs";

const platforms = { all: "전체", youtube: "유튜브", shorts: "쇼츠", instagram: "웨딩툰" };
const search = document.querySelector("#search");
const category = document.querySelector("#category");
const platformList = document.querySelector("#platforms");
const results = document.querySelector("#results");
const status = document.querySelector("#status");
const catalog = document.querySelector("#catalog");
let platform = "all";

function node(tag, value, className) {
  const element = document.createElement(tag);
  if (value) element.textContent = value;
  if (className) element.className = className;
  return element;
}

function card(topic) {
  const article = node("article", "", "card");
  if (topic.thumbnail) {
    const image = node("img");
    image.src = topic.thumbnail;
    image.alt = "";
    image.loading = "lazy";
    image.referrerPolicy = "no-referrer";
    image.addEventListener("error", () => image.remove(), { once: true });
    article.append(image);
  }
  const body = node("div", "", "card-body");
  const tags = node("div", "", "tags");
  for (const label of topic.categories) tags.append(node("span", label));
  const age = Date.now() - Date.parse(topic.date);
  if (age >= 0 && age < 7 * 86400000) tags.append(node("span", "신규", "new"));
  const links = node("div", "", "links");
  for (const source of topic.sources) {
    const link = node("a", `${platforms[source.platform]} 보기 ↗`);
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    links.append(link);
  }
  body.append(tags, node("h3", topic.title), links);
  article.append(body);
  return article;
}

async function init() {
  const response = await fetch("data.json");
  if (!response.ok) throw new Error("Catalog unavailable");
  const { topics, categories, aliases, lastUpdated } = await response.json();
  document.querySelector("#total").textContent = `전체 ${topics.length.toLocaleString("ko-KR")}개 주제 · 최신순`;
  document.querySelector("#updated").textContent = lastUpdated
    ? `마지막 정상 업데이트 ${new Intl.DateTimeFormat("ko-KR", { dateStyle: "medium", timeZone: "Asia/Seoul" }).format(new Date(lastUpdated))}`
    : "자동 업데이트 기록 대기 중";
  for (const name of categories) category.add(new Option(name, name));

  function render() {
    const filtered = topics.filter(topic =>
      (!category.value || topic.categories.includes(category.value))
      && (platform === "all" || topic.sources.some(source => source.platform === platform))
      && matches(topic, search.value, aliases)
    );
    status.textContent = filtered.length === topics.length ? "" : `검색 결과 ${filtered.length}개`;
    results.replaceChildren(...(filtered.length
      ? filtered.map(card)
      : [node("p", "관련 콘텐츠를 찾지 못했어요. 다른 검색어나 필터로 다시 찾아보세요.", "empty")]));
  }

  for (const [key, label] of Object.entries(platforms)) {
    const button = node("button", label);
    button.type = "button";
    button.setAttribute("aria-pressed", String(key === platform));
    button.addEventListener("click", () => {
      platform = key;
      for (const choice of platformList.children) {
        choice.setAttribute("aria-pressed", String(choice === button));
      }
      render();
    });
    platformList.append(button);
  }
  search.addEventListener("input", render);
  category.addEventListener("change", render);
  document.querySelector("#search-form").addEventListener("submit", event => {
    event.preventDefault();
    render();
    catalog.scrollIntoView();
  });
  render();
}

init().catch(() => {
  status.textContent = "콘텐츠를 불러오지 못했어요. 잠시 후 새로고침해 주세요.";
});
