import json
from quality_bundle.reporting import SuiteResult,write_summary
def test_summary(tmp_path):
    p=tmp_path/"summary.json"
    write_summary(p,[SuiteResult("cli",["pytest"],0,1.2,"passed")])
    data=json.loads(p.read_text())
    assert data["status"]=="passed"
    assert data["totals"]["passed"]==1
