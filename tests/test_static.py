from pathlib import Path
import json,re,unittest
ROOT=Path(__file__).resolve().parents[1]
class StaticTests(unittest.TestCase):
 def test_required_tree(self):
  for p in [".github/workflows","assets","data","docs","scripts","tests","index.html","portfolio.html","tw-market.html","news.html","institutional.html","asset.html","coverage.html","service-worker.js"]:self.assertTrue((ROOT/p).exists(),p)
 def test_version(self):
  self.assertEqual(json.loads((ROOT/"VERSION.json").read_text(encoding="utf-8"))["baseline_version"],"11.3.0")
 def test_no_patch_folder_or_chinese_filename(self):
  for p in ROOT.rglob("*"):
   self.assertTrue(all(ord(c)<128 for c in p.name),f"non ASCII filename: {p}")
 def test_no_work_section(self):
  self.assertNotIn("工作",(ROOT/"index.html").read_text(encoding="utf-8"))
 def test_institutional_features(self):
  t=(ROOT/"institutional.html").read_text(encoding="utf-8");self.assertIn("當沖",t);self.assertIn("融資",t);self.assertIn("融券",t)
if __name__=="__main__":unittest.main()
