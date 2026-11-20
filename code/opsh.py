#!/usr/bin/env python3
"""
opsh - a mini-shell written in Python   (Systèmes d'Exploitation - UIR/ESIN)
============================================================================
    python3 opsh.py               interactive mode   (prompt: opsh>)
    python3 opsh.py script.opsh   script mode        (if / for / while)

How one command line travels through opsh:

  read line -> save in history -> expand $VAR ${VAR} $? $! $((..)) $(..) `..`
            -> split on '->' (our pipe) -> for each piece: split words,
               find > >> < and & -> builtin? run it : fork() + execvp()
            -> wait for the children (or not, if '&') -> store $?
"""

import os
import re
import shlex
import signal
import sys

try:
    import readline          # arrow keys, history, TAB completion
except ImportError:          # (not available on every platform)
    readline = None

# ---------------------------------------------------------------- tables
# opsh name -> real Linux program (these are NOT builtins: we fork+exec them)
# [BOX B1 START] owner: Person B | the tables ALIASES and BUILTINS | replace this whole box (down to its END line) with the real code
ALIASES = {}
BUILTINS = []
# [BOX B1 END]
HISTORY_FILE = os.path.expanduser("~/.opsh_history")
RC_FILE = os.path.expanduser("~/.opshrc")


class Opsh:
    def __init__(self):
        self.vars = {}            # shell variables (not exported)
        self.last_status = 0      # $?
        self.last_bg_pid = ""     # $!
        self.history = []
        self.jobs = {}            # job number -> (pid, command text)
        self.next_job = 1
        # SIGCHLD: a child changed state -> reap finished BACKGROUND jobs
        signal.signal(signal.SIGCHLD, self.on_sigchld)

    # ================================================================
    # SIGNALS
    # ================================================================
    # [BOX B6 START] owner: Person B | on_sigchld | replace this whole box (down to its END line) with the real code
    def on_sigchld(self, signum, frame):
        pass
    # [BOX B6 END]

    # ================================================================
    # EXPANSION  ($VAR, ${VAR}, $?, $!, $$, $((...)), $(...), `...`)
    # ================================================================
    # [BOX C2 START] owner: Person C | get_var | replace this whole box (down to its END line) with the real code
    def get_var(self, name):
        return ""
    # [BOX C2 END]

    # [BOX C3 START] owner: Person C | expand | replace this whole box (down to its END line) with the real code
    def expand(self, line):
        return line
    # [BOX C3 END]

    # [BOX C4 START] owner: Person C | matching_paren | replace this whole box (down to its END line) with the real code
    @staticmethod
    def matching_paren(s, start):
        return s.index(")", start)
    # [BOX C4 END]

    # [BOX C5 START] owner: Person C | arith | replace this whole box (down to its END line) with the real code
    @staticmethod
    def arith(expr):
        return expr
    # [BOX C5 END]

    # [BOX C6 START] owner: Person C | capture | replace this whole box (down to its END line) with the real code
    def capture(self, cmdline):
        return ""
    # [BOX C6 END]

    # ================================================================
    # PARSING
    # ================================================================
    # [BOX C1 START] owner: Person C | split_pipes | replace this whole box (down to its END line) with the real code
    @staticmethod
    def split_pipes(line):
        return [line]
    # [BOX C1 END]

    # [BOX B2 START] owner: Person B | parse_command | replace this whole box (down to its END line) with the real code
    @staticmethod
    def parse_command(text):
        return shlex.split(text), None, None, False, False
    # [BOX B2 END]

    # ================================================================
    # BUILTINS (run INSIDE the shell process)
    # ================================================================
    # [BOX B3 START] owner: Person B | builtin | replace this whole box (down to its END line) with the real code
    def builtin(self, argv):
        print("opsh: box B3 (builtin) is not written yet")
        return 0
    # [BOX B3 END]

    # ================================================================
    # EXECUTION
    # ================================================================
    def run_line(self, line):
        line = line.strip()
        if not line or line.startswith("#"):
            return
        try:
            line = self.expand(line)
            # VAR=value  (assignment, no spaces around '=')
            m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
            if m:
                self.vars[m.group(1)] = shlex.split(m.group(2))[0] if m.group(2) else ""
                if m.group(1) in os.environ:
                    os.environ[m.group(1)] = self.vars[m.group(1)]
                self.last_status = 0
                return
            commands = [self.parse_command(p) for p in self.split_pipes(line)]
        except (SyntaxError, ValueError, IndexError, ZeroDivisionError) as e:
            print(f"opsh: syntax error: {e}", file=sys.stderr)
            self.last_status = 2
            return
        if any(not c[0] for c in commands):
            print("opsh: syntax error near '->'", file=sys.stderr)
            self.last_status = 2
            return
        self.last_status = self.run_pipeline(commands, line)

    # [BOX A3 START] owner: Person A | run_pipeline | replace this whole box (down to its END line) with the real code
    def run_pipeline(self, commands, text):
        print("opsh: box A3 (run_pipeline) is not written yet. I would run:",
              [c[0] for c in commands])
        return 0
    # [BOX A3 END]

    # [BOX A4 START] owner: Person A | fork_pipeline | replace this whole box (down to its END line) with the real code
    def fork_pipeline(self, commands, text, background):
        print("opsh: box A4 (fork_pipeline) is not written yet. I would start:",
              [c[0] for c in commands])
        return 0
    # [BOX A4 END]

    # [BOX A5 START] owner: Person A | wait_for | replace this whole box (down to its END line) with the real code
    def wait_for(self, pids):
        return 0
    # [BOX A5 END]

    # [BOX B4 START] owner: Person B | apply_redirections | replace this whole box (down to its END line) with the real code
    @staticmethod
    def apply_redirections(infile, outfile, append):
        pass
    # [BOX B4 END]

    # [BOX B5 START] owner: Person B | run_builtin_redirected | replace this whole box (down to its END line) with the real code
    def run_builtin_redirected(self, cmd):
        return self.builtin(cmd[0])
    # [BOX B5 END]

    # ================================================================
    # SCRIPT MODE: if / for / while
    # ================================================================
    # [BOX D4 START] owner: Person D | parse_block | replace this whole box (down to its END line) with the real code
    def parse_block(self, lines, i, ends):
        return [], len(lines)
    # [BOX D4 END]

    # [BOX D5 START] owner: Person D | run_nodes | replace this whole box (down to its END line) with the real code
    def run_nodes(self, nodes):
        pass
    # [BOX D5 END]

    # [BOX D6 START] owner: Person D | run_script | replace this whole box (down to its END line) with the real code
    def run_script(self, path):
        print("opsh: box D6 (run_script) is not written yet")
        return 0
    # [BOX D6 END]

    # ================================================================
    # HISTORY, COMPLETION, .opshrc, REPL
    # ================================================================
    # [BOX D2 START] owner: Person D | setup_readline | replace this whole box (down to its END line) with the real code
    def setup_readline(self):
        pass
    # [BOX D2 END]

    # [BOX D3 START] owner: Person D | save_history | replace this whole box (down to its END line) with the real code
    def save_history(self):
        pass
    # [BOX D3 END]

    # [BOX D1 START] owner: Person D | load_rc | replace this whole box (down to its END line) with the real code
    def load_rc(self):
        pass
    # [BOX D1 END]

    def repl(self):
        self.setup_readline()
        self.load_rc()
        while True:
            try:
                line = input("opsh> ")
            except KeyboardInterrupt:          # Ctrl-C at the prompt: new line
                print()
                continue
            except EOFError:                   # Ctrl-D: leave like 'quit'
                print()
                break
            if line.strip():
                self.history.append(line)
            self.run_line(line)
        self.save_history()


def main():
    shell = Opsh()
    if len(sys.argv) > 1:                       # script mode
        sys.exit(shell.run_script(sys.argv[1]))
    shell.repl()


if __name__ == "__main__":
    main()
