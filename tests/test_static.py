from pathlib import Path
import json,re,unittest
ROOT=Path(__file__).resolve().parents[1]
class StaticTests(unittest.TestCase):
 def test_required_tree(self):
  for p in [".github/workflows","assets","data","docs","scripts","tests","index.html","portfolio.html","tw-market.html","news.html","institutional.html","asset.html","coverage.html","service-worker.js"]:self.assertTrue((ROOT/p).exists(),p)
 def test_version(self):
  self.assertEqual(json.loads((ROOT/"VERSION.json").read_text(encoding="utf-8"))["baseline_version"],"11.3.0")
 def test_ascii_filenames(self):
  for p in ROOT.rglob("*"):self.assertTrue(all(ord(c)<128 for c in p.name),f"non ASCII filename: {p}")
 def test_home_replaces_crypto(self):
  html=(ROOT/"index.html").read_text(encoding="utf-8")
  self.assertIn("今日市場重點",html);self.assertNotIn("虛擬貨幣即時排行",html);self.assertNotIn("工作",html)
 def test_calendar_is_grouped(self):
  js=(ROOT/"assets/home.js").read_text(encoding="utf-8")
  for text in ("重大事件","公司資訊","除權息共","localKey"):self.assertIn(text,js)
 def test_news_is_clean_and_classified(self):
  script=(ROOT/"scripts/update_news.py").read_text(encoding="utf-8")
  for text in ("article_url","clean_text","ai_category","market_direction","affected_markets"):self.assertIn(text,script)
 def test_market_rankings(self):
  html=(ROOT/"tw-market.html").read_text(encoding="utf-8")
  for text in ("今日個股漲幅前 15 名","今日個股跌幅前 15 名","今日 ETF 漲幅前 15 名","今日 ETF 跌幅前 15 名"):self.assertIn(text,html)
 def test_institutional_search_and_hot_lists(self):
  html=(ROOT/"institutional.html").read_text(encoding="utf-8")
  for text in ("輸入代碼或名稱才顯示籌碼資料","熱門個股前 10 名","熱門 ETF 前 10 名","當沖","融資","融券"):self.assertIn(text,html)
if __name__=="__main__":unittest.main()
