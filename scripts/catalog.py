"""Collect official metadata, classify locally, and export the Pages payload."""
import argparse
import datetime as dt
import html
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unicodedata
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"
LABELS = {"youtube": "유튜브", "instagram": "인스타그램"}
YT_API = "https://www.googleapis.com/youtube/v3/"
RSS_NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
          "media": "http://search.yahoo.com/mrss/"}
UTC = dt.timezone.utc


def load(name):
    return json.loads((CATALOG / f"{name}.json").read_text(encoding="utf-8"))


def write(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def norm(value):
    return "".join(c for c in unicodedata.normalize("NFKC", value).casefold() if c.isalnum())


def now():
    return dt.datetime.now(UTC).isoformat(timespec="seconds")


def date_value(value):
    if value:
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC).isoformat()
        except ValueError:
            pass
    return None


def request(url, parameters=None, token=None, limit=16_000_000):
    if urlparse(url).scheme != "https":
        raise ValueError("HTTPS required")
    if parameters:
        url += "?" + urlencode(parameters)
    headers = {"User-Agent": "DumaWeddingDictionary/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request(url, headers=headers), timeout=20) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Response too large")
    return data


def api(url, parameters=None, token=None):
    return json.loads(request(url, parameters, token))


def ocr(urls, notes):
    if os.getenv("ENABLE_OCR") != "1":
        return ""
    if not shutil.which("tesseract"):
        notes.add("OCR 실행 도구 없음")
        return ""
    texts = []
    for url in list(dict.fromkeys(filter(None, urls)))[:10]:
        try:
            safe = thumbnail(url)
            if not safe:
                continue
            with tempfile.TemporaryDirectory() as directory:
                image = Path(directory) / "image"
                image.write_bytes(request(safe))
                result = subprocess.run(
                    ["tesseract", str(image), "stdout", "-l", "kor+eng"],
                    capture_output=True, check=True, timeout=12, text=True,
                )
                texts.append(result.stdout)
        except (OSError, ValueError, subprocess.SubprocessError):
            notes.add("일부 이미지 OCR 처리 실패")
    return "\n".join(texts)


def caption(video_id, notes):
    token = os.getenv("YOUTUBE_CAPTIONS_ACCESS_TOKEN")
    if not token:
        return ""
    try:
        tracks = api(YT_API + "captions", {"part": "snippet", "videoId": video_id}, token)["items"]
        tracks = sorted(tracks, key=lambda track: not track["snippet"]["language"].startswith("ko"))
        track = next((track for track in tracks if track["snippet"]["status"] == "serving"), None)
        if track:
            raw = request(YT_API + "captions/" + quote(track["id"], safe=""), {"tfmt": "vtt"}, token)
            return re.sub(r"<[^>]*>|^.*-->.*$|^WEBVTT.*$", " ", raw.decode("utf-8"), flags=re.M)
    except (OSError, ValueError, KeyError):
        notes.add("일부 자막을 공식 API에서 읽을 수 없음")
    return ""


def thumbnail(url):
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.hostname or ""
    allowed = ("ytimg.com", "ggpht.com", "cdninstagram.com", "fbcdn.net", "instagram.com")
    if parsed.scheme == "https" and any(host == domain or host.endswith("." + domain) for domain in allowed):
        return url
    return None


def youtube_items(backfill):
    key = os.getenv("YOUTUBE_API_KEY")
    channel_id = os.getenv("YOUTUBE_CHANNEL_ID")
    if channel_id and not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", channel_id):
        raise ValueError("Invalid YouTube channel ID")
    if key:
        pages = api(YT_API + "channels", {
            "part": "contentDetails", **({"id": channel_id} if channel_id else {"forHandle": "@듬아"}),
            "key": key,
        })["items"]
        if len(pages) != 1:
            raise ValueError("YouTube channel not found")
        playlist = pages[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        following = None
        while True:
            params = {"part": "contentDetails", "playlistId": playlist, "maxResults": 50, "key": key}
            if following:
                params["pageToken"] = following
            page = api(YT_API + "playlistItems", params)
            ids = [item["contentDetails"]["videoId"] for item in page["items"]]
            if ids:
                details = api(YT_API + "videos", {
                    "part": "snippet,status", "id": ",".join(ids), "key": key,
                })["items"]
                for item in details:
                    if item["status"]["privacyStatus"] != "public":
                        continue
                    snippet = item["snippet"]
                    images = snippet.get("thumbnails", {})
                    cover = next((images[k]["url"] for k in ("maxres", "standard", "high", "medium", "default")
                                  if k in images), None)
                    yield dict(id=item["id"], title=snippet["title"], date=snippet.get("publishedAt"),
                               description=snippet.get("description", ""), tags=snippet.get("tags", []),
                               thumbnail=cover)
            following = page.get("nextPageToken")
            if not following or not backfill:
                break
    elif channel_id:
        raw = request("https://www.youtube.com/feeds/videos.xml", {"channel_id": channel_id})
        feed = ET.fromstring(raw)
        feed_channel = feed.findtext("yt:channelId", namespaces=RSS_NS)
        if feed_channel not in (channel_id, channel_id.removeprefix("UC")):
            raise ValueError("Unexpected YouTube RSS channel")
        for entry in feed.findall("a:entry", RSS_NS):
            cover = entry.find("media:group/media:thumbnail", RSS_NS)
            link = entry.find("a:link", RSS_NS)
            yield dict(id=entry.findtext("yt:videoId", namespaces=RSS_NS),
                       title=entry.findtext("a:title", "", RSS_NS),
                       date=entry.findtext("a:published", namespaces=RSS_NS),
                       description=entry.findtext("media:group/media:description", "", RSS_NS),
                       thumbnail=cover.get("url") if cover is not None else None,
                       permalink=link.get("href") if link is not None else None)
    else:
        return


def instagram_items(backfill):
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    if not token:
        return
    version = os.getenv("META_GRAPH_VERSION", "v25.0")
    if not re.fullmatch(r"v\d+\.\d+", version):
        raise ValueError("Invalid Meta Graph API version")
    instagram = "https://graph.instagram.com/" + version + "/"
    account = api(instagram + "me", {"fields": "user_id,username"}, token)
    if account["username"].casefold() != "duma.toon":
        raise ValueError("Unexpected Instagram account")
    account_id = str(account["user_id"])
    if not account_id.isdigit():
        raise ValueError("Invalid Instagram account ID")
    after = None
    while True:
        params = {
            "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,children{media_type,media_url,thumbnail_url}",
            "limit": 50,
        }
        if after:
            params["after"] = after
        page = api(instagram + account_id + "/media", params, token)
        for item in page["data"]:
            permalink = item["permalink"]
            path = urlparse(permalink)
            match = re.fullmatch(r"/(?:p|reel|tv)/([\w-]+)/?", path.path, re.ASCII)
            if path.hostname not in ("www.instagram.com", "instagram.com") or not match:
                continue
            first = item.get("thumbnail_url") if item["media_type"] == "VIDEO" else item.get("media_url")
            slides = [child.get("thumbnail_url") if child["media_type"] == "VIDEO" else child.get("media_url")
                      for child in item.get("children", {}).get("data", [])]
            yield dict(id=match[1], title="", description=item.get("caption", ""), date=item.get("timestamp"),
                       thumbnail=first or next(filter(None, slides), None), slides=slides, permalink=permalink)
        paging = page.get("paging", {})
        after = paging.get("cursors", {}).get("after")
        if not backfill or not paging.get("next") or not after:
            break


def analyze(platform, raw, rules, notes):
    identifier = raw["id"]
    if not re.fullmatch(r"[\w-]+", identifier, re.ASCII):
        raise ValueError("Invalid media ID")
    title = html.unescape(raw["title"]).strip()
    description = html.unescape(raw.get("description", ""))
    cover = thumbnail(raw.get("thumbnail"))
    image_text = ocr([cover, *raw.get("slides", [])], notes)
    transcript = caption(identifier, notes) if platform == "youtube" else ""
    supporting = " ".join([description, *raw.get("tags", []), image_text, transcript])
    evidence = [norm(title), norm(supporting)]
    has = lambda phrase: any(norm(phrase) in field for field in evidence)
    keywords = set()
    categories = []
    for category, terms in rules["categories"].items():
        found = {term for term in terms if has(term)}
        if found:
            categories.append(category)
            keywords.update(found)
    for entry in rules["related"]:
        if any(map(has, entry["when"])) and (not entry.get("requires") or any(map(has, entry["requires"]))):
            keywords.update(entry["also"])
    # Strong evidence gates publishing. Generic supporting keywords alone can be incidental.
    wedding = any(has(word) for word in ("웨딩", "결혼 준비", "예비신부", "본식", "결혼식", "신혼",
                                         "허니문", "스드메", "청첩장", "혼주", "축의금", "드레스투어",
                                         "헤어변형", "해외여행 초심자", "해외여행 초보", "첫 해외여행"))
    display = title
    for entry in rules["titles"]:
        if any(map(has, entry["when"])) and any(map(has, entry["requires"])):
            display = entry["title"]
            break
    if not display:
        # IG captions are descriptions. Derive a compact label from evidenced topics.
        display = " · ".join(sorted(keywords, key=lambda word: (-len(norm(word)), word))[:2])
    status = "published" if (platform == "instagram" or wedding) and display else "review"
    original_link = raw.get("permalink") or ""
    if platform == "youtube":
        is_short = (urlparse(original_link).path == "/shorts/" + identifier
                    or any(norm(tag) in ("shorts", "youtubeshorts", "쇼츠") for tag in raw.get("tags", []))
                    or bool(re.search(r"(?:^|\s)#(?:shorts|쇼츠)\b", title + " " + description, re.I)))
        kind = "shorts" if is_short else "youtube"
        url = f"https://www.youtube.com/shorts/{identifier}" if is_short else f"https://youtu.be/{identifier}"
        item_id = "yt:" + identifier
    else:
        kind, url, item_id = "instagram", original_link, "ig:" + identifier
    heading = title
    if platform == "instagram" and description:
        first_line = description.splitlines()[0].strip()
        if 12 <= len(norm(first_line)) <= 60:
            heading = first_line
    return item_id, {
        "fingerprint": fingerprint(heading),
        "title": display, "originalTitle": title or None, "categories": categories or ["기타 웨딩꿀팁"],
        "keywords": sorted(keywords), "platform": kind, "url": url, "date": date_value(raw.get("date")),
        "thumbnail": cover, "status": status,
        "reason": ("표시 제목을 만들 수 있는 주제 단서 부족" if not display else "웨딩 관련성 불확실")
        if status == "review" else None,
    }


def refresh(args):
    rules, state = load("rules"), load("state")
    backfill = args.backfill
    results, successes, failures = {}, [], []
    collectors = {"youtube": youtube_items, "instagram": instagram_items}
    configured = {"youtube": bool(os.getenv("YOUTUBE_API_KEY") or os.getenv("YOUTUBE_CHANNEL_ID")),
                  "instagram": bool(os.getenv("INSTAGRAM_ACCESS_TOKEN"))}
    for source, collect in collectors.items():
        if not configured[source]:
            results[source] = {"state": "미연결", "at": now()}
            continue
        notes = set()
        try:
            items = dict(analyze(source, raw, rules, notes) for raw in collect(backfill))
        except (OSError, ValueError, KeyError, ET.ParseError) as error:
            # Exceptions from HTTP clients can contain credential-bearing URLs.
            failure = f"HTTP {error.code}" if hasattr(error, "code") else type(error).__name__
            results[source] = {"state": "실패", "detail": failure, "at": now()}
            failures.append(source)
        else:
            state["sources"].update(items)
            results[source] = {"state": "정상", "count": len(items), "at": now(), "notes": sorted(notes)}
            successes.append(source)
    if successes and not failures:
        state["lastUpdated"] = now()
    state["status"] = results
    write(CATALOG / "state.json", state)
    if args.summary:
        summary(args.summary, state)
    for source, result in results.items():
        print(f"{LABELS[source]} {result['state']} {result.get('detail', result.get('count', ''))}")
    return bool(failures)


def fingerprint(title):
    title = re.sub(r"(?:^|\s)#(?:shorts|쇼츠)\b", "", title, flags=re.I)
    normalized = norm(title)
    if len(normalized) < 12:
        return None
    return hashlib.sha256(normalized.encode()).hexdigest()


def topic_key(item_id, item):
    signature = item.get("fingerprint")
    return "same:" + signature if signature else item_id


def current_categories(labels, evidence, rules):
    renamed = {
        "웨딩드레스": "드레스",
        "스튜디오·웨딩촬영": "스튜디오",
        "신랑·예복": "신랑정장",
        "웨딩네일": "웨딩뷰티",
        "청첩장": "하객",
        "본식 준비·진행": "본식",
    }
    categories = {renamed.get(label, label) for label in labels if label != "하객·축의금"}
    if "하객·축의금" in labels:
        fields = [norm(field) for field in evidence]
        matched = {
            label for label in ("하객", "축의금")
            if any(norm(term) in field for term in rules["categories"][label] for field in fields)
        }
        categories.update(matched or {"하객"})
    return [label for label in rules["categories"] if label in categories]


def inventory(state):
    rules = load("rules")
    items = {key: value.copy() for key, value in state["sources"].items()}
    manual = load("overrides")
    for seed in load("seed"):
        key = seed["id"]
        deltas = {k: v for k, v in seed.items() if k != "id"}
        item = items.setdefault(key, {"platform": "instagram" if key.startswith("ig:") else "youtube"})
        item.update(deltas, status="published")
        if item["platform"] == "shorts":
            item["url"] = f"https://www.youtube.com/shorts/{key.split(':', 1)[1]}"
    for key, edits in manual["items"].items():
        if key in items:
            items[key].update(edits)
            if edits.get("platform") == "shorts" and "url" not in edits and key.startswith("yt:"):
                items[key]["url"] = f"https://www.youtube.com/shorts/{key.split(':', 1)[1]}"
    groups = {}
    for key, item in items.items():
        if item["status"] != "published":
            continue
        evidence = [item["title"], item.get("originalTitle") or "", *item["keywords"]]
        item["categories"] = current_categories(item["categories"], evidence, rules)
        name = item.get("topic") or topic_key(key, item)
        groups.setdefault(name, []).append((key, item))

    topics = []
    for name, members in groups.items():
        members.sort(key=lambda pair: (pair[1].get("date") or "", pair[0]), reverse=True)
        items_in_topic = [item for _, item in members]
        edits = manual["topics"].get(name, {})
        if edits.get("hidden"):
            continue
        if len(items_in_topic) > 1 and name.startswith("same:"):
            # Duplicate display formats remain independent unless explicitly grouped.
            formats = {item["platform"] for item in items_in_topic}
            shared = set.intersection(*(set(item["categories"]) for item in items_in_topic))
            shared.discard("기타 웨딩꿀팁")
            if len(formats) != len(items_in_topic) or not shared:
                for key, item in members:
                    topics.append(public_topic([item], manual["topics"].get(key, {}), rules))
                continue
        topics.append(public_topic(items_in_topic, edits, rules))
    topics = [topic for topic in topics if topic]
    topics.sort(key=lambda topic: topic["date"] or "", reverse=True)
    return topics, items


def public_topic(items, edits, rules):
    if edits.get("hidden"):
        return None
    categories = {label for item in items for label in item["categories"]}
    title = edits.get("title", items[0]["title"])
    keywords = edits.get("keywords", sorted({term for item in items for term in item["keywords"]}))
    return {
        "title": title,
        "categories": current_categories(edits.get("categories", categories), [title, *keywords], rules),
        "keywords": keywords,
        "date": max((item.get("date") or "" for item in items), default="") or None,
        "thumbnail": next((item["thumbnail"] for item in items if item.get("thumbnail")), None),
        "sources": [{"platform": item["platform"], "url": item["url"]} for item in items],
    }


def safe_line(value):
    return html.escape(str(value)).replace("|", "&#124;").replace("\n", " ")


def summary(path, state):
    topics, items = inventory(state)
    lines = ["## 수집 상태", ""]
    for source, detail in state["status"].items():
        lines.append(f"- {LABELS[source]} · {detail['state']} · {detail.get('detail', detail.get('count', '—'))}")
        for note in detail.get("notes", []):
            lines.append(f"  - {note}")
    lines.extend(["", "## 검토 대기", ""])
    for key, item in items.items():
        if item["status"] == "review":
            lines.append(f"- {safe_line(key)} · {safe_line(item['title'] or item.get('originalTitle') or '제목 없음')} · {safe_line(item.get('reason') or '')}")
    lines.extend(["", "## 병합 검토 후보", ""])
    candidates = {}
    for key, item in items.items():
        if item["status"] == "published" and item["title"]:
            candidates.setdefault(norm(item["title"]), []).append((key, item))
    for entries in candidates.values():
        if len({item.get("topic") or topic_key(key, item) for key, item in entries}) > 1:
            lines.append("- " + safe_line(entries[0][1]["title"]) + " · " + ", ".join(key for key, _ in entries))
    lines.extend(["", "## 최근 게시물", "", f"공개 주제 {len(topics)}개", ""])
    for key, item in sorted(items.items(), key=lambda pair: pair[1].get("date") or "", reverse=True)[:20]:
        lines.append(f"- {safe_line(key)} · {safe_line(item.get('date') or '날짜 없음')} · {safe_line(item['title'])}")
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write("\n" + "\n".join(lines) + "\n")


def build(destination):
    rules, state = load("rules"), load("state")
    topics, _ = inventory(state)
    shutil.copytree(ROOT / "site", destination, dirs_exist_ok=True)
    write(destination / "data.json", {
        "topics": topics, "categories": list(rules["categories"]), "aliases": rules["aliases"],
        "lastUpdated": state.get("lastUpdated"),
    })


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    refresh_command = commands.add_parser("refresh")
    refresh_command.add_argument("--backfill", action="store_true")
    refresh_command.add_argument("--summary")
    build_command = commands.add_parser("build")
    build_command.add_argument("--out", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    if args.command == "refresh":
        return refresh(args)
    build(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
