import { matches } from "./search.mjs";

const platforms = { all: "전체", youtube: "유튜브", shorts: "쇼츠", instagram: "웨딩툰" };
const svgNamespace = "http://www.w3.org/2000/svg";
const search = document.querySelector("#search");
const categoryList = document.querySelector("#categories");
const platform = document.querySelector("#platform");
const results = document.querySelector("#results");
const status = document.querySelector("#status");
const catalog = document.querySelector("#catalog");
let category = "";

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
    const label = `${platforms[source.platform]} 보기`;
    const link = node("a");
    link.setAttribute("aria-label", label);
    link.title = label;
    const icon = document.createElementNS(svgNamespace, "svg");
    icon.setAttribute("aria-hidden", "true");
    const symbol = document.createElementNS(svgNamespace, "use");
    symbol.setAttribute("href", `#source-${source.platform}`);
    icon.append(symbol);
    link.append(icon);
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
  for (const [key, label] of Object.entries(platforms)) {
    platform.add(new Option(key === "all" ? "모든 플랫폼" : label, key));
  }

  function render() {
    const filtered = topics.filter(topic =>
      (!category || topic.categories.includes(category))
      && (platform.value === "all" || topic.sources.some(source => source.platform === platform.value))
      && matches(topic, search.value, aliases)
    );
    status.textContent = filtered.length === topics.length ? "" : `검색 결과 ${filtered.length}개`;
    results.replaceChildren(...(filtered.length
      ? filtered.map(card)
      : [node("p", "관련 콘텐츠를 찾지 못했어요. 다른 검색어나 필터로 다시 찾아보세요.", "empty")]));
  }

  for (const name of ["", ...categories]) {
    const button = node("button", name || "전체 카테고리");
    button.type = "button";
    button.setAttribute("aria-pressed", String(name === category));
    button.addEventListener("click", () => {
      category = name;
      for (const choice of categoryList.children) {
        choice.setAttribute("aria-pressed", String(choice === button));
      }
      render();
    });
    categoryList.append(button);
  }
  search.addEventListener("input", render);
  platform.addEventListener("change", render);
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
