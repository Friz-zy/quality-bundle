import json,sys
import pytest
from quality_bundle import main

def run_cli(monkeypatch,cwd,*argv):
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(sys,"argv",["quality",*argv])
    with pytest.raises(SystemExit) as exc:
        main.main()
    return exc.value.code

def make_suite(tmp_path,name,filename="test_x.py"):
    d=tmp_path/"tests/e2e"/name;d.mkdir(parents=True)
    (d/filename).write_text("def test_x(): pass")

def test_list_one_suite_per_line(tmp_path,monkeypatch,capsys):
    make_suite(tmp_path,"cli")
    code=run_cli(monkeypatch,tmp_path,"list")
    out=capsys.readouterr().out
    assert code==0
    assert out=="cli\n"
    assert "\\n" not in out

def test_list_multiple_suites_separate_lines(tmp_path,monkeypatch,capsys):
    make_suite(tmp_path,"cli")
    make_suite(tmp_path,"contract")
    code=run_cli(monkeypatch,tmp_path,"list")
    out=capsys.readouterr().out
    assert code==0
    assert out.splitlines()==["cli","contract"]

def test_run_unknown_suite_exits_2(tmp_path,monkeypatch,capsys):
    code=run_cli(monkeypatch,tmp_path,"run","bogus")
    err=capsys.readouterr().err
    assert code==2
    assert "error: Unknown suites: bogus" in err
    assert not (tmp_path/"artifacts/quality/summary.json").exists()

def test_plan_unknown_suite_exits_2(tmp_path,monkeypatch,capsys):
    code=run_cli(monkeypatch,tmp_path,"plan","nope")
    err=capsys.readouterr().err
    assert code==2
    assert "error: Unknown suites: nope" in err

def test_empty_run_writes_summary(tmp_path,monkeypatch,capsys):
    code=run_cli(monkeypatch,tmp_path,"run")
    out=capsys.readouterr().out
    assert code==0
    assert "No suites discovered." in out
    data=json.loads((tmp_path/"artifacts/quality/summary.json").read_text())
    assert data["status"]=="passed"
    assert data["suites"]==[]
    assert data["totals"]=={"suites":0,"passed":0,"failed":0,"duration_seconds":0.0}

def test_empty_run_no_summary_when_disabled(tmp_path,monkeypatch,capsys):
    (tmp_path/"quality.toml").write_text("[quality]\njson_summary = false\n")
    code=run_cli(monkeypatch,tmp_path,"run")
    assert code==0
    assert "No suites discovered." in capsys.readouterr().out
    assert not (tmp_path/"artifacts/quality/summary.json").exists()

def test_plan_contract_suite(tmp_path,monkeypatch,capsys):
    make_suite(tmp_path,"contract")
    code=run_cli(monkeypatch,tmp_path,"plan","contract")
    out=capsys.readouterr().out
    assert code==0
    assert "-m contract" in out

def test_plan_container_suite(tmp_path,monkeypatch,capsys):
    make_suite(tmp_path,"containers")
    code=run_cli(monkeypatch,tmp_path,"plan","container")
    out=capsys.readouterr().out
    assert code==0
    assert "-m container" in out

def capture_execute(monkeypatch):
    captured={}
    def fake_execute(argv,env=None):
        captured["argv"]=list(map(str,argv))
        return 0,0.1
    monkeypatch.setattr(main,"execute",fake_execute)
    return captured

def test_passthrough_leading_option_test_cmd(tmp_path,monkeypatch):
    captured=capture_execute(monkeypatch)
    code=run_cli(monkeypatch,tmp_path,"test","-k","health")
    assert code==0
    assert captured["argv"][-2:]==["-k","health"]
    assert "--e2e-config" not in captured["argv"]

def test_passthrough_leading_option_suite_cmd(tmp_path,monkeypatch):
    captured=capture_execute(monkeypatch)
    code=run_cli(monkeypatch,tmp_path,"cli","-k","health","tests/e2e/cli/test_x.py::test_other")
    assert code==0
    assert "-m cli" in " ".join(captured["argv"])
    assert captured["argv"][-3:]==["-k","health","tests/e2e/cli/test_x.py::test_other"]

def test_passthrough_config_in_front(tmp_path,monkeypatch):
    (tmp_path/"c.toml").write_text('[app]\nbase_url = "http://x"\n')
    captured=capture_execute(monkeypatch)
    code=run_cli(monkeypatch,tmp_path,"--config","c.toml","test","-k","y")
    assert code==0
    assert captured["argv"][-2:]==["-k","y"]
    assert "--e2e-config" in captured["argv"] and "c.toml" in captured["argv"]

def test_passthrough_config_equals_form(tmp_path,monkeypatch):
    (tmp_path/"c.toml").write_text('[app]\nbase_url = "http://x"\n')
    captured=capture_execute(monkeypatch)
    code=run_cli(monkeypatch,tmp_path,"--config=c.toml","test","-k","y")
    assert code==0
    assert captured["argv"][-2:]==["-k","y"]
    assert "c.toml" in captured["argv"]

def test_unknown_bare_subcommand_clean_error(tmp_path,monkeypatch,capsys):
    code=run_cli(monkeypatch,tmp_path,"bogus")
    err=capsys.readouterr().err
    assert code==2
    assert "error: Unknown suites: bogus" in err

def test_built_in_subcommands_after_config_form(tmp_path,monkeypatch,capsys):
    make_suite(tmp_path,"cli")
    code=run_cli(monkeypatch,tmp_path,"--config=c.toml","list")
    assert code==0

def test_schema_command_uses_console_script(monkeypatch,tmp_path,capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("E2E_OPENAPI","openapi.yaml")
    monkeypatch.setenv("E2E_BASE_URL","http://127.0.0.1:9")
    monkeypatch.setattr(main.shutil,"which",lambda name: "/fake/bin/schemathesis" if name=="schemathesis" else None)
    cfg=main.load_config(None)
    argv=main.external_command("schema",cfg)
    assert argv[0]=="/fake/bin/schemathesis"
    assert argv[1:3]==["run","openapi.yaml"]
    assert "--report" in argv and "--report-junit-path" in argv
    assert argv[-2:]==["--url","http://127.0.0.1:9"]

def test_schema_command_clean_error_when_absent(monkeypatch,tmp_path,capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("E2E_OPENAPI","openapi.yaml")
    monkeypatch.setattr(main.shutil,"which",lambda name: None)
    cfg=main.load_config(None)
    with pytest.raises(RuntimeError,match="Schemathesis is not installed"):
        main.external_command("schema",cfg)
