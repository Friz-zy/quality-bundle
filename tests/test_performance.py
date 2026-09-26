from types import SimpleNamespace
from quality_bundle.performance import PerformanceResult, evaluate

def test_performance_thresholds_pass():
    result=PerformanceResult(1000,0,0.0,100,50,150,300,75)
    cfg=SimpleNamespace(p50_ms=100,p95_ms=200,p99_ms=400,failure_rate=.01,min_rps=50)
    assert evaluate(result,cfg)==[]

def test_performance_thresholds_fail():
    result=PerformanceResult(100,2,.02,10,50,600,1200,100)
    cfg=SimpleNamespace(p50_ms=None,p95_ms=500,p99_ms=1000,failure_rate=.01,min_rps=20)
    failures=evaluate(result,cfg)
    assert len(failures)==4
