"""The Python planner must agree with the Photoshop (JS) planner in scripts/core.jsxinc."""
import json
import math
import shutil
import subprocess
import unittest
from pathlib import Path

from manga_ai.layout_plan import page_size_cap, plan_layout, rect_shape, wrap_scored

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')

RUNNER = r"""
const fs=require('fs'),vm=require('vm');
const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync('scripts/core.jsxinc','utf8'),ctx);
const cases=JSON.parse(fs.readFileSync(0,'utf8'));
const out=cases.map(c=>{
  const u=s=>s.length*.5;
  const p=ctx.MTA.planLayout(c.shape,c.paragraphs,u,c.ref,c.options);
  return p?{size:p.size,lines:Array.from(p.lines),axis:p.axis,baseline:p.baseline,fill:p.fill}:null;
});
console.log(JSON.stringify(out));
"""


def ellipse(cx, cy, rx, ry):
    rows = []
    for y in range(math.ceil(cy - ry) + 1, math.floor(cy + ry)):
        k = math.sqrt(1 - ((y - cy) / ry) ** 2)
        rows.append([y, round(cx - rx * k), round(cx + rx * k)])
    return {'box': [cx - rx, cy - ry, 2 * rx, 2 * ry], 'center': [cx, cy], 'rows': rows}


CASES = [
    {'shape': ellipse(150, 110, 95, 100), 'paragraphs': ['…và nói “Em yêu anh” đi.'],
     'ref': 1.26, 'options': {'min': 10, 'max': 60, 'leading': 1.05, 'accRatio': 1.0, 'capRatio': .7}},
    {'shape': ellipse(200, 150, 120, 90), 'paragraphs': ['Cậu đang nói cái gì vậy hả tớ chẳng hiểu gì cả'],
     'ref': 1.0, 'options': {'min': 10, 'max': 80, 'leading': 1.1}},
    {'shape': rect_shape([0, 0, 160, 260]), 'paragraphs': ['Thầy ơi!!'],
     'ref': 1.26, 'options': {'min': 10, 'max': 40, 'leading': 1.05, 'accRatio': 1.04, 'capRatio': .72, 'sparseFill': .18, 'sparseBoost': 1.12}},
    {'shape': ellipse(100, 120, 60, 110), 'paragraphs': ['Món yêu thích là đào.'],
     'ref': 1.2, 'options': {'min': 10, 'max': 50, 'leading': 1.05, 'accRatio': .95, 'capRatio': .68, 'fillWeight': 4, 'fillTarget': .4}},
    {'shape': ellipse(120, 90, 110, 80), 'paragraphs': ['Một hai ba', 'bốn năm sáu bảy tám chín mười'],
     'ref': 1.1, 'options': {'min': 12, 'max': 44, 'leading': 1.0}},
    {'shape': rect_shape([0, 0, 99, 315]), 'paragraphs': ['Aizawa-san!'],
     'ref': 1.2, 'options': {'min': 18, 'max': 48, 'leading': 1.05}},
    {'shape': rect_shape([0, 0, 121, 373]), 'paragraphs': ['Là giải thưởng lớn của cuộc thi nấu ăn Pháp tại Tokyo——'],
     'ref': 1.15, 'options': {'min': 30, 'max': 72, 'leading': 1.05}},
]


@unittest.skipUnless(NODE, 'node is required for the parity check')
class ParityTests(unittest.TestCase):
    def test_python_planner_matches_the_photoshop_planner(self):
        result = subprocess.run([NODE, '-e', RUNNER], input=json.dumps(CASES), capture_output=True, text=True, cwd=ROOT, check=True)
        js = json.loads(result.stdout)
        for case, expected in zip(CASES, js):
            py = plan_layout(case['shape'], case['paragraphs'], lambda s: len(s) * .5, case['ref'], dict(case['options']))
            self.assertIsNotNone(py)
            self.assertIsNotNone(expected)
            self.assertAlmostEqual(py['size'], expected['size'], places=6, msg=str(case['paragraphs']))
            self.assertEqual(py['lines'], expected['lines'])
            self.assertAlmostEqual(py['axis'], expected['axis'], places=6)
            self.assertAlmostEqual(py['baseline'], expected['baseline'], places=6)

    def test_wrap_prefers_readable_breaks_and_page_cap_uses_lower_median(self):
        scored = wrap_scored(['một hai ba bốn'], [9, 9], len)
        self.assertEqual(scored[1], ['một hai', 'ba bốn'])
        hyph = wrap_scored(['Aizawa-san!'], [7, 7], len)
        self.assertEqual(hyph[1], ['Aizawa-', 'san!'])
        whole = wrap_scored(['Aizawa-san!'], [15], len)
        self.assertEqual(whole[1], ['Aizawa-san!'])
        prolonged = wrap_scored(['Tokyo——'], [5, 5], len)
        self.assertEqual(prolonged[1], ['Tokyo', '——'])
        prolonged_whole = wrap_scored(['Tokyo——'], [10], len)
        self.assertEqual(prolonged_whole[1], ['Tokyo——'])
        self.assertEqual(page_size_cap([38, 62], 1.3, 10), 1.3 * 38)
        self.assertEqual(page_size_cap([], 1.3, 10), None)


if __name__ == '__main__':
    unittest.main()
