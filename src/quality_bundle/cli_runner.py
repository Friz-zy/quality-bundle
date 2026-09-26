from __future__ import annotations
import os,shlex,subprocess
from dataclasses import dataclass
@dataclass(frozen=True)
class CLIResult:
    argv:tuple[str,...]; returncode:int; stdout:str; stderr:str
    def assert_ok(self):
        assert self.returncode==0,f"Command failed ({self.returncode}): {shlex.join(self.argv)}\nstdout:\n{self.stdout}\nstderr:\n{self.stderr}"
        return self
@dataclass(frozen=True)
class CLI:
    executable:str
    def run(self,*args,cwd=None,env=None,stdin=None,timeout=30):
        e=os.environ.copy()
        if env:e.update(env)
        argv=(self.executable,*args)
        r=subprocess.run(argv,cwd=cwd,env=e,input=stdin,capture_output=True,text=True,timeout=timeout,check=False)
        return CLIResult(argv,r.returncode,r.stdout,r.stderr)
