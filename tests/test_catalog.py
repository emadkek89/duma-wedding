import argparse
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import catalog


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.rules = catalog.load("rules")

    def analyze(self, platform, **details):
        raw = {"id": "example", "title": "", **details}
        return catalog.analyze(platform, raw, self.rules, set())[1]

    def test_relevance_and_content_based_title(self):
        item = self.analyze("youtube", title="이거 모르고 가면 진짜 후회해요!",
                            description="드레스투어 오프숄더 드레스 부유방 커버", tags=["Shorts"])
        self.assertEqual(item["title"], "드레스투어 전 알아야 할 주의사항")
        self.assertEqual(item["status"], "published")
        self.assertIn("겨드랑이", item["keywords"])
        self.assertEqual(item["platform"], "shorts")
        unrelated = self.analyze("youtube", title="회사 생활 브이로그")
        self.assertEqual(unrelated["status"], "review")
        generic = self.analyze("youtube", title="결혼식 전날 이거 절대 하지 마세요")
        self.assertEqual(generic["title"], generic["originalTitle"])

    def test_seed_deduplication_and_overrides(self):
        seed_key = "yt:yhgTtVzNlPs"
        collected = self.analyze("youtube", title="헤어변형 소개", date="2025-02-01")
        state = {"sources": {seed_key: collected}}
        topics, _ = catalog.inventory(state)
        self.assertEqual(len(topics), 5)
        self.assertEqual(topics[0]["title"], "헤어변형 꼭 필요할까?")
        real_load = catalog.load

        def load(name):
            if name == "overrides":
                return {"items": {seed_key: {"title": "수동 제목", "platform": "shorts",
                                             "categories": ["웨딩홀"]}}, "topics": {}}
            return real_load(name)

        with patch.object(catalog, "load", side_effect=load):
            topics, _ = catalog.inventory(state)
        self.assertEqual(topics[0]["title"], "수동 제목")
        self.assertEqual(topics[0]["categories"], ["웨딩홀"])
        self.assertIn("/shorts/", topics[0]["sources"][0]["url"])

    def test_group_cross_platform_only_with_matching_evidence(self):
        title = "웨딩촬영 헤어변형 준비할 때 알아야 할 점"
        yt = self.analyze("youtube", title=title)
        ig = self.analyze("instagram", description=title + "\n게시물 본문",
                          permalink="https://www.instagram.com/p/example/")
        matching = {"yt:example": yt, "ig:example": ig}
        topics, _ = catalog.inventory({"sources": matching})
        self.assertEqual(len(topics), 6)
        self.assertEqual(sum(len(topic["sources"]) == 2 for topic in topics), 1)
        ig["categories"] = ["신혼여행"]
        topics, _ = catalog.inventory({"sources": matching})
        self.assertEqual(len(topics), 7)

    def test_partial_failure_preserves_old_data_and_date(self):
        old = self.analyze("youtube", title="웨딩촬영 헤어변형", date="2025-01-01")
        state = {"sources": {"yt:old": old}, "status": {}, "lastUpdated": "2025-01-01"}

        def load(name):
            return copy.deepcopy(state) if name == "state" else self.rules

        def fail(_):
            yield {"id": "new", "title": "웨딩홀 비용"}
            raise OSError("credential-bearing output")

        with tempfile.TemporaryDirectory() as directory:
            with (patch.dict(os.environ, {"YOUTUBE_API_KEY": "fake", "INSTAGRAM_ACCESS_TOKEN": "fake"}, clear=True),
                  patch.object(catalog, "CATALOG", Path(directory)),
                  patch.object(catalog, "load", side_effect=load),
                  patch.object(catalog, "youtube_items", fail),
                  patch.object(catalog, "instagram_items", return_value=iter([
                      {"id": "new", "title": "", "description": "하객 축의금 꿀팁",
                       "permalink": "https://www.instagram.com/p/new/"}
                  ]))):
                result = catalog.refresh(argparse.Namespace(backfill=True, summary=None))
            saved = json.loads((Path(directory) / "state.json").read_text())
        self.assertTrue(result)
        self.assertEqual(saved["lastUpdated"], state["lastUpdated"])
        self.assertEqual(saved["sources"]["yt:old"], old)
        self.assertNotIn("yt:new", saved["sources"])
        self.assertIn("ig:new", saved["sources"])

    def test_official_youtube_pagination_and_metadata(self):
        def api(url, params):
            endpoint = url.rsplit("/", 1)[1]
            if endpoint == "channels":
                self.assertEqual(params["forHandle"], "@듬아")
                return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "upload-list"}}}]}
            if endpoint == "playlistItems":
                second = params.get("pageToken") == "next"
                return {
                    "items": [{"contentDetails": {"videoId": "second" if second else "first"}}],
                    **({} if second else {"nextPageToken": "next"}),
                }
            return {"items": [{"id": params["id"], "status": {"privacyStatus": "public"},
                               "snippet": {"title": "웨딩홀", "description": "본문"},
                               "contentDetails": {"duration": "PT2M"}}]}

        with (patch.dict(os.environ, {"YOUTUBE_API_KEY": "fake"}, clear=True),
              patch.object(catalog, "api", side_effect=api)):
            self.assertEqual([raw["id"] for raw in catalog.youtube_items(True)], ["first", "second"])

    def test_build_excludes_originals_and_reviews(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog.build(Path(directory))
            payload = json.loads((Path(directory) / "data.json").read_text())
            self.assertEqual(len(payload["topics"]), 5)
            self.assertEqual(len(payload["categories"]), 17)
            self.assertNotIn("originalTitle", json.dumps(payload))
            self.assertEqual({p.name for p in Path(directory).iterdir()},
                             {"index.html", "style.css", "app.js", "search.mjs", "data.json"})


if __name__ == "__main__":
    unittest.main()
