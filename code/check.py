#!/usr/bin/env python3
"""
check.py - automatic tests for opsh, box by box.

    python3 check.py            test every box that is already written
    python3 check.py A1         test only box A1
    python3 check.py A1 A2      test several boxes
    python3 check.py C          test all the boxes of one member (A = Mohammed BEN CHRIF, B = Adam FTOUKI, C = Cherine DAKLI, D = Mohamed EL BOUDAKHANI)
    python3 check.py all        the teacher's demo + the script mode (final test)

PASS = the box behaves like the finished opsh.
FAIL = something is different: read "expected" and "got".
WAIT = the test needs a box that a teammate has not written yet.

The tests never touch your real files: they run in a temporary folder
with a temporary HOME (so your own ~/.opshrc and history are safe).
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OPSH = os.path.join(HERE, "opsh.py")
OWNERS = {"A": "Mohammed BEN CHRIF", "B": "Adam FTOUKI", "C": "Cherine DAKLI", "D": "Mohamed EL BOUDAKHANI"}
ALL_BOXES = ["A1", "A2", "A3", "A4", "A5", "B1", "B2", "B3", "B4", "B5", "B6",
             "C1", "C2", "C3", "C4", "C5", "C6", "D1", "D2", "D3", "D4", "D5", "D6"]
ENGINE = ["A2", "A3", "A4", "A5"]          # the boxes needed to really run a command

PRELUDE = "import os, sys, signal, time, tempfile\nimport opsh\nsh = opsh.Opsh()\n"


def written(box):
    """A box is written when its [BOX xx START] marker is gone from opsh.py."""
    return f"[BOX {box} START]" not in open(OPSH, encoding="utf-8").read()


def sandbox():
    home = tempfile.mkdtemp(prefix="opsh_check_")
    work = os.path.join(home, "work", "sub")
    os.makedirs(work)
    with open(os.path.join(home, "work", "sub", "a.txt"), "w") as f:
        f.write("one\ntwo\n")
    env = dict(os.environ, HOME=home, PYTHONPATH=HERE, PYTHONDONTWRITEBYTECODE="1")
    return home, work, env


def run(argv, stdin_text=""):
    home, work, env = sandbox()
    try:
        p = subprocess.run(argv, input=stdin_text, capture_output=True, text=True,
                           cwd=work, env=env, timeout=20)
        return p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return "", "FROZEN: no answer after 20 seconds (a pipe end left open? a missing waitpid?)"
    finally:
        shutil.rmtree(home, ignore_errors=True)


def unit(code):
    """Run a few Python lines that call the functions of opsh.py directly."""
    out, err = run([sys.executable, "-c", PRELUDE + code])
    return out.strip(), err.strip()


def session(lines, args=()):
    """Type lines into a real opsh (like a user) and return what appears."""
    out, err = run([sys.executable, OPSH, *args], "\n".join(lines) + "\n")
    return out.replace("opsh> ", "").strip(), err.strip()


# ---------------------------------------------------------------- the tests
# (box, title, boxes needed, kind, input, expected)
#   kind "unit": expected = the exact text printed
#   kind "has" : expected = list of texts that must ALL appear on the screen
T = []


def t(box, title, needs, kind, src, expected):
    T.append((box, title, [box] + needs, kind, src, expected))


# ---- Mohammed BEN CHRIF (boxes A) -----------------------------------------
t("A1", "the prompt opsh> appears and Ctrl-D leaves", [], "raw",
  [], "opsh> ")
t("A2", "run_line cuts the line and calls run_pipeline", [], "unit",
  "sh.run_pipeline = lambda c, t: print('RUN', [x[0] for x in c]) or 0\n"
  "sh.run_line('   ls -l   ')\nsh.run_line('')\nsh.run_line('# a comment')",
  "RUN [['ls', '-l']]")
t("A2", "run_line stores an assignment X=5 in self.vars", [], "unit",
  "sh.run_line('X=5')\nsh.run_line('NAME=\"hello world\"')\nprint(sh.vars, sh.last_status)",
  "{'X': '5', 'NAME': 'hello world'} 0")
t("A2", "run_line reports a syntax error with status 2", [], "unit",
  "sh.run_line(\"say 'oops\")\nprint(sh.last_status)", "2")
t("A3", "run_pipeline calls fork_pipeline and gives Ctrl-C back", [], "unit",
  "sh.fork_pipeline = lambda c, t, b: 7\n"
  "print(sh.run_pipeline([(['ls'], None, None, False, False)], 'ls'))\n"
  "print(signal.getsignal(signal.SIGINT) is signal.default_int_handler)",
  "7\nTrue")
t("A5", "wait_for returns the exit code of the child", [], "unit",
  "pid = os.fork()\nif pid == 0:\n    os._exit(4)\nprint(sh.wait_for([pid]), sh.wait_for([]))",
  "4 0")
t("A5", "wait_for gives 128+N when the child is killed by signal N", [], "unit",
  "pid = os.fork()\nif pid == 0:\n    signal.signal(signal.SIGINT, signal.SIG_DFL)\n"
  "    os.kill(os.getpid(), signal.SIGINT)\n    time.sleep(5)\n    os._exit(0)\n"
  "print(sh.wait_for([pid]))",
  "130")
t("A4", "a real program runs (fork + execvp + wait)", ["A2", "A3", "A5"], "has",
  ["echo hello from a child"], ["hello from a child"])
t("A4", "the exit status of the last command is kept", ["A2", "A3", "A5"], "unit",
  "sh.run_line(\"sh -c 'exit 3'\")\nprint(sh.last_status)\nsh.run_line('true')\nprint(sh.last_status)",
  "3\n0")
t("A4", "unknown command: message + status 127", ["A2", "A3", "A5"], "unit",
  "sh.run_line('nosuchcmd_xyz')\nprint(sh.last_status)", "127")
t("A4", "a pipe of two commands is wired correctly", ["A3", "A5"], "unit",
  "print(sh.run_pipeline([(['echo', 'a b c'], None, None, False, False),\n"
  "                       (['wc', '-w'], None, None, False, False)], 'x'))",
  "3\n0")
t("A4", "a background command does not block the shell", ["A3", "A5"], "unit",
  "t0 = time.time()\n"
  "r = sh.run_pipeline([(['sleep', '2'], None, None, False, True)], 'sleep 2 &')\n"
  "print(r, time.time() - t0 < 1, list(sh.jobs) == [1], sh.last_bg_pid == sh.jobs[1][0])",
  None)   # checked by a function below (the PID changes every time)

# ---- Adam FTOUKI (boxes B) ------------------------------------------------
t("B1", "the 7 aliases and the 10 builtins are in the tables", [], "unit",
  "print(opsh.ALIASES['list'], opsh.ALIASES['show'], opsh.ALIASES['newfile'], len(opsh.ALIASES))\n"
  "print('osinfo' in opsh.BUILTINS, 'go' in opsh.BUILTINS, len(opsh.BUILTINS))",
  "ls cat touch 7\nTrue True 10")
t("B2", "parse_command finds > and the file name", [], "unit",
  "print(opsh.Opsh.parse_command('say hi > f.txt'))",
  "(['say', 'hi'], None, 'f.txt', False, False)")
t("B2", "parse_command finds < and >>", [], "unit",
  "print(opsh.Opsh.parse_command('wc -l < in.txt >> out.txt'))",
  "(['wc', '-l'], 'in.txt', 'out.txt', True, False)")
t("B2", "parse_command finds & and keeps quotes together", [], "unit",
  "print(opsh.Opsh.parse_command('sleep 10 &'))\n"
  "print(opsh.Opsh.parse_command('say \"a > b\"'))",
  "(['sleep', '10'], None, None, False, True)\n(['say', 'a > b'], None, None, False, False)")
t("B2", "parse_command replaces an alias by the real program", ["B1"], "unit",
  "print(opsh.Opsh.parse_command('list -l')[0], opsh.Opsh.parse_command('show f')[0])",
  "['ls', '-l'] ['cat', 'f']")
t("B3", "say, osinfo and path", ["B1"], "unit",
  "print(sh.builtin(['say', 'a', 'b']))\nsh.builtin(['osinfo'])\n"
  "sh.builtin(['path'])\nprint(os.getcwd())",
  None)
t("B3", "go changes the folder of the shell itself; a wrong folder gives 1", ["B1"], "unit",
  "d = os.path.realpath(tempfile.mkdtemp())\nprint(sh.builtin(['go', d]), os.getcwd() == d)\n"
  "print(sh.builtin(['go', '/no/such/folder_xyz']))\n"
  "sh.builtin(['go'])\nprint(os.getcwd() == os.path.realpath(os.environ['HOME']))",
  "0 True\n1\nTrue")
t("B3", "export, past, info and quit", ["B1"], "unit",
  "sh.builtin(['export', 'ZZ=5'])\nprint(os.environ['ZZ'])\n"
  "sh.vars['YY'] = 'abc'\nsh.builtin(['export', 'YY'])\nprint(os.environ['YY'])\n"
  "sh.history = ['first', 'second']\nsh.builtin(['past'])\n"
  "sh.builtin(['info'])\n"
  "try:\n    sh.builtin(['quit', '3'])\nexcept SystemExit as e:\n    print('exit code', e.code)",
  None)
t("B3", "jobs lists the background jobs; fg with no job gives 1", ["B1"], "unit",
  "sh.jobs[1] = (4242, 'sleep 99')\nsh.builtin(['jobs'])\nsh.jobs.clear()\nprint(sh.builtin(['fg']))",
  "[1]  4242  Running   sleep 99\n1")
t("B4", "> sends fd 1 into a file, >> adds at the end, < reads", [], "unit",
  "f = os.path.join(tempfile.mkdtemp(), 'o.txt')\n"
  "for text, app in ((b'one\\n', False), (b'two\\n', False), (b'three\\n', True)):\n"
  "    pid = os.fork()\n"
  "    if pid == 0:\n"
  "        opsh.Opsh.apply_redirections(None, f, app)\n"
  "        os.write(1, text)\n"
  "        os._exit(0)\n"
  "    os.waitpid(pid, 0)\n"
  "print(open(f).read().split(), flush=True)\n"
  "pid = os.fork()\n"
  "if pid == 0:\n"
  "    opsh.Opsh.apply_redirections(f, None, False)\n"
  "    os.write(1, os.read(0, 100))\n"
  "    os._exit(0)\n"
  "os.waitpid(pid, 0)",
  "['two', 'three']\ntwo\nthree")
t("B5", "a builtin with > writes in the file, then the screen comes back", ["B1", "B3", "B4"], "unit",
  "f = os.path.join(tempfile.mkdtemp(), 'o.txt')\n"
  "print(sh.run_builtin_redirected((['say', 'hi'], None, f, False, False)))\n"
  "print('screen is back')\nprint(open(f).read().strip())",
  "0\nscreen is back\nhi")
t("B5", "a builtin with an impossible file gives an error and status 1", ["B1", "B3", "B4"], "unit",
  "print(sh.run_builtin_redirected((['say', 'hi'], None, '/no/such/dir/o.txt', False, False)))\n"
  "print('still alive')",
  "1\nstill alive")
t("B6", "a finished background job is collected (no zombie) and announced", [], "unit",
  "pid = os.fork()\nif pid == 0:\n    os._exit(0)\n"
  "sh.jobs[1] = (pid, 'demo job')\n"
  "for _ in range(30):\n    time.sleep(0.1)\n    if not sh.jobs:\n        break\n"
  "print(sh.jobs)",
  "[1]+ Done    demo job\n{}")

# ---- Cherine DAKLI (boxes C) ----------------------------------------------
t("C1", "split_pipes cuts on -> and removes the spaces", [], "unit",
  "print(opsh.Opsh.split_pipes('show f.txt -> sort -> wc -l'))\nprint(opsh.Opsh.split_pipes('list'))",
  "['show f.txt', 'sort', 'wc -l']\n['list']")
t("C1", "split_pipes does not cut inside quotes", [], "unit",
  "print(opsh.Opsh.split_pipes('say \"a -> b\" -> wc -c'))",
  "['say \"a -> b\"', 'wc -c']")
t("C2", "get_var knows $?, $!, $$, shell variables and the environment", [], "unit",
  "sh.vars['N'] = 'v'\nsh.last_status = 7\nsh.last_bg_pid = 99\n"
  "print(sh.get_var('N'), sh.get_var('?'), sh.get_var('!'), sh.get_var('$') == str(os.getpid()))\n"
  "print(sh.get_var('HOME') == os.environ['HOME'], repr(sh.get_var('NO_SUCH_VAR_XYZ')))",
  "v 7 99 True\nTrue ''")
t("C3", "expand replaces $VAR, ${VAR} and $?", ["C2"], "unit",
  "sh.vars['N'] = 'world'\nsh.last_status = 7\n"
  "print(sh.expand('hi $N ${N}! status=$?'))\nprint(sh.expand('price: 5$ and a $ alone'))",
  "hi world world! status=7\nprice: 5$ and a $ alone")
t("C3", "expand: nothing changes inside '...', but it does inside \"...\"", ["C2"], "unit",
  "sh.vars['N'] = 'world'\nprint(sh.expand(\"say '$N' and \\\"$N\\\"\"))",
  "say '$N' and \"world\"")
t("C4", "matching_paren finds the ) that closes the first (", [], "unit",
  "print(opsh.Opsh.matching_paren('$(a (b) c) d', 1))\n"
  "try:\n    opsh.Opsh.matching_paren('$(a (b c', 1)\nexcept SyntaxError as e:\n    print('error:', e)",
  "9\nerror: missing )")
t("C5", "arith computes + - * / % on whole numbers only", [], "unit",
  "print(opsh.Opsh.arith('1+2*3'), opsh.Opsh.arith('7/2'), opsh.Opsh.arith('(1+2)*3'), opsh.Opsh.arith('7%4'))\n"
  "try:\n    opsh.Opsh.arith('__import__(\"os\")')\nexcept SyntaxError:\n    print('refused')",
  "7 3 9 3\nrefused")
t("C5", "expand computes $((...)) and knows variables inside", ["C2", "C3"], "unit",
  "sh.vars['i'] = '4'\nprint(sh.expand('$((2+3)) $((i+1)) $(($i*2))'))",
  "5 5 8")
t("C6", "capture returns what a command prints", ENGINE, "unit",
  "print(repr(sh.capture('echo hi there')))", "'hi there'")
t("C6", "expand pastes the output of $(...) and `...`", ENGINE + ["C2", "C3", "C4"], "unit",
  "print(sh.expand('a $(echo b c) d `echo e` f'))\nprint(sh.expand('$(echo $(echo deep))'))",
  "a b c d e f\ndeep")

# ---- Mohamed EL BOUDAKHANI (boxes D) --------------------------------------
t("D1", "load_rc runs every line of ~/.opshrc (and no file = no error)", ["A2"], "unit",
  "sh.load_rc()\nprint(sh.vars)\nopen(opsh.RC_FILE, 'w').write('ZED=42\\n# comment\\nTWO=2\\n')\n"
  "sh.load_rc()\nprint(sh.vars)",
  "{}\n{'ZED': '42', 'TWO': '2'}")
t("D2", "setup_readline loads the old history and installs TAB completion", ["B1"], "unit",
  "import readline\nreadline.add_history('one')\nreadline.add_history('two')\n"
  "readline.write_history_file(opsh.HISTORY_FILE)\nreadline.clear_history()\n"
  "sh.setup_readline()\nprint(sh.history)\nc = readline.get_completer()\n"
  "print(c('osi', 0), c('osi', 1), c('new', 0), c('new', 1))",
  "['one', 'two']\nosinfo None newdir newfile")
t("D2", "setup_readline works the very first time (no history file yet)", [], "unit",
  "sh.setup_readline()\nprint(sh.history)", "[]")
t("D3", "save_history writes the history file", [], "unit",
  "import readline\nreadline.add_history('zzz_my_line')\nsh.save_history()\n"
  "print('zzz_my_line' in open(opsh.HISTORY_FILE).read())",
  "True")
t("D4", "parse_block builds the tree of an if / else", [], "unit",
  "print(sh.parse_block(['say a', 'if true', 'then', 'say b', 'else', 'say c', 'fi'], 0, ()))",
  "([('cmd', 'say a'), ('if', 'true', [('cmd', 'say b')], [('cmd', 'say c')])], 7)")
t("D4", "parse_block builds for, while and a loop inside a loop", [], "unit",
  "n, i = sh.parse_block(['for x in a b', 'do', 'while true', 'do', 'say $x', 'done', 'done', '# end'], 0, ())\n"
  "print(n)",
  "[('for', 'x', 'a b', [('while', 'true', [('cmd', 'say $x')])])]")
t("D5", "run_nodes repeats a for body once per word", [], "unit",
  "log = []\nsh.run_line = log.append\nsh.expand = lambda s: s\n"
  "sh.run_nodes([('for', 'x', 'a b', [('cmd', 'say $x')])])\nprint(log, sh.vars['x'])",
  "['say $x', 'say $x'] b")
t("D5", "run_nodes chooses then when the status is 0, else otherwise", [], "unit",
  "log = []\nsh.run_line = log.append\n"
  "tree = [('if', 'test', [('cmd', 'YES')], [('cmd', 'NO')])]\n"
  "sh.last_status = 0\nsh.run_nodes(tree)\nsh.last_status = 1\nsh.run_nodes(tree)\nprint(log)",
  "['test', 'YES', 'test', 'NO']")
t("D6", "run_script reads a file and runs it", ["D4", "D5", "A2"], "unit",
  "p = os.path.join(tempfile.mkdtemp(), 's.opsh')\nopen(p, 'w').write('# demo\\nX=1\\nY=2\\n')\n"
  "print(sh.run_script(p), sh.vars)",
  "0 {'X': '1', 'Y': '2'}")
t("D6", "script mode: if / for / while really run", ["D4", "D5"] + ENGINE + ["B1", "B2", "B3", "B5", "C2", "C3", "C5"],
  "script",
  "i=1\nwhile [ $i -le 3 ]; do\n  say loop $i\n  i=$((i+1))\ndone\n"
  "for f in x y\ndo\n  say item $f\ndone\n"
  "if [ -d /tmp ]; then\n  say yes\nelse\n  say no\nfi\n"
  "if [ -d /no/such ]; then\n  say yes2\nelse\n  say no2\nfi\n",
  "loop 1\nloop 2\nloop 3\nitem x\nitem y\nyes\nno2")


def special(box, title, out):
    """Tests whose answer contains something that changes (a PID, a folder)."""
    if title.startswith("a background command"):
        return out.splitlines()[-1:] == ["0 True True True"] and out.startswith("[1] ")
    if title.startswith("say, osinfo"):
        lines = out.splitlines()
        return (lines[:3] == ["a b", "0", "Systèmes d'Exploitation -- UIR/ESIN"]
                and len(lines) == 5 and lines[3] == lines[4])
    if title.startswith("export, past"):
        lines = out.splitlines()
        return (lines[:4] == ["5", "abc", "   1  first", "   2  second"]
                and lines[4].startswith("builtins : go, quit, path, say")
                and lines[-1] == "exit code 3")
    return False


def run_test(test):
    box, title, needs, kind, src, expected = test
    missing = [b for b in needs if not written(b)]
    if missing:
        who = ", ".join(f"{b} ({OWNERS[b[0]]})" for b in missing)
        return "WAIT", f"needs box {who}"
    if kind == "unit":
        out, err = unit(src)
        ok = special(box, title, out) if expected is None else out == expected
    elif kind == "raw":
        out, err = run([sys.executable, OPSH], "")
        ok = out.startswith(expected)
    elif kind == "has":
        out, err = session(src)
        ok = all(e in out for e in expected)
        expected = " ... ".join(expected)
    else:                                   # a script file
        home = tempfile.mkdtemp(prefix="opsh_script_")
        path = os.path.join(home, "t.opsh")
        with open(path, "w") as f:
            f.write(src)
        out, err = run([sys.executable, OPSH, path])
        out = out.strip()
        shutil.rmtree(home, ignore_errors=True)
        ok = out == expected
    if ok:
        return "PASS", ""
    msg = ""
    if expected is not None:
        msg += "      expected: " + str(expected).replace("\n", "\n                ") + "\n"
    msg += "      got     : " + (out.replace("\n", "\n                ") or "(nothing)")
    if err:
        msg += "\n      error   : " + err.replace("\n", "\n                ")
    return "FAIL", msg


# ---------------------------------------------------------------- final test
DEMO = [
    ("list", ["a.txt"]),
    ("go ..", []),
    ("path", ["/work"]),
    ("say hello > f.txt", []),
    ("show f.txt", ["hello"]),
    ("show f.txt -> wc -l", ["1"]),
    ("sleep 1 &", ["[1] "]),
    ("ps", ["sleep"]),
    ("osinfo", ["Systèmes d'Exploitation -- UIR/ESIN"]),
    ("NAME=team", []),
    ("say hi $NAME ${NAME}! $((6*7)) $(say sub)", ["hi team team! 42 sub"]),
    ("false", []),
    ("say status=$?", ["status=1"]),
    ("sleep 2", ["Done"]),
]


def final_test():
    missing = [b for b in ALL_BOXES if not written(b)]
    if missing:
        print("WAIT  the final test needs every box. Not written yet:")
        for b in missing:
            print(f"        {b}  ({OWNERS[b[0]]})")
        return 1
    fails = 0
    out, err = session([c for c, _ in DEMO])
    print("---- the teacher's demo (and a few extras) ----")
    for cmd, wants in DEMO:
        ok = all(w in out for w in wants)
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  opsh> {cmd}" + ("" if ok else f"      (missing on screen: {wants})"))
    if fails:
        print("\nwhat opsh printed:\n" + out + ("\n" + err if err else ""))
    ex = os.path.join(HERE, "example.opsh")
    print("---- script mode ----")
    if not os.path.exists(ex):
        print("WAIT  code/example.opsh does not exist yet (Mohamed EL BOUDAKHANI)")
        fails += 1
    else:
        out, err = run([sys.executable, OPSH, ex])
        wants = ["Systèmes d'Exploitation -- UIR/ESIN", "loop number 1", "loop number 3",
                 "item: gamma", "/tmp exists", "files here:"]
        ok = all(w in out for w in wants)
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  python3 opsh.py example.opsh")
        if not ok:
            print(out, err)
    print()
    print("ALL GOOD: opsh is ready for the demo." if not fails else f"{fails} problem(s) to fix.")
    return 1 if fails else 0


def main():
    args = [a for a in sys.argv[1:]]
    if args and args[0].lower() == "all":
        sys.exit(final_test())
    boxes = []
    for a in args:
        a = a.upper()
        if a in OWNERS:
            boxes += [b for b in ALL_BOXES if b[0] == a]
        elif a in ALL_BOXES:
            boxes.append(a)
        else:
            sys.exit(f"unknown box '{a}'. Boxes are: {' '.join(ALL_BOXES)}")
    explicit = bool(boxes)
    boxes = boxes or ALL_BOXES
    counts = {"PASS": 0, "FAIL": 0, "WAIT": 0}
    for box in boxes:
        if not written(box):
            if explicit:
                print(f"\n[{box}] {OWNERS[box[0]]}: not written yet (the marker [BOX {box} START] is still in opsh.py)")
            continue
        print(f"\n[{box}] {OWNERS[box[0]]}")
        for test in [x for x in T if x[0] == box]:
            state, msg = run_test(test)
            counts[state] += 1
            print(f"  {state}  {test[1]}" + (f"  -> {msg}" if state == "WAIT" else ""))
            if state == "FAIL":
                print(msg)
    todo = [b for b in ALL_BOXES if not written(b)]
    print(f"\n{counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['WAIT']} WAIT"
          f"   |   boxes written: {len(ALL_BOXES) - len(todo)}/{len(ALL_BOXES)}")
    if not explicit and todo:
        print("still to write: " + " ".join(todo))
    sys.exit(1 if counts["FAIL"] else 0)


if __name__ == "__main__":
    main()
