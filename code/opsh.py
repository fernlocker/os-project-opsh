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

    def run_pipeline(self, commands, text):
        background = commands[-1][4]
        # A single builtin runs in the shell itself (needed for go / quit / export)
        if len(commands) == 1 and commands[0][0][0] in BUILTINS and not background:
            return self.run_builtin_redirected(commands[0])

        # The shell IGNORES Ctrl-C while children run (like bash).
        # Children put SIGINT back to default, so Ctrl-C kills THEM only.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            return self.fork_pipeline(commands, text, background)
        finally:
            signal.signal(signal.SIGINT, signal.default_int_handler)

    def fork_pipeline(self, commands, text, background):
        pids, prev_read = [], None
        for idx, (argv, infile, outfile, append, _) in enumerate(commands):
            last = idx == len(commands) - 1
            if not last:
                r, w = os.pipe()               # pipe: w = write end, r = read end
            pid = os.fork()
            if pid == 0:                       # ---------------- CHILD
                signal.signal(signal.SIGINT, signal.SIG_DFL)
                signal.signal(signal.SIGCHLD, signal.SIG_DFL)
                if background:
                    os.setpgid(0, 0)           # own group: Ctrl-C won't kill it
                if prev_read is not None:      # read from previous command
                    os.dup2(prev_read, 0)
                    os.close(prev_read)
                if not last:                   # write into the pipe
                    os.close(r)
                    os.dup2(w, 1)
                    os.close(w)
                try:
                    self.apply_redirections(infile, outfile, append)
                    if argv[0] in BUILTINS:    # builtin inside a pipeline
                        status = self.builtin(argv)
                        sys.stdout.flush()
                        os._exit(status)
                    os.execvp(argv[0], argv)   # replaces the child's program
                except FileNotFoundError as e:     # the program, or a file after < >
                    print(f"opsh: {e.filename + ': no such file' if e.filename else 'command not found: ' + argv[0]}", file=sys.stderr)
                    os._exit(127)
                except OSError as e:               # no permission, is a directory...
                    print(f"opsh: {e.filename or argv[0]}: {e.strerror}", file=sys.stderr)
                    os._exit(126)
            # ------------------------------------------------- PARENT
            pids.append(pid)
            if prev_read is not None:
                os.close(prev_read)            # parent must close pipe ends!
            if not last:
                os.close(w)
                prev_read = r

        if background:
            num = self.next_job
            self.next_job += 1
            self.jobs[num] = (pids[-1], text.rstrip("& "))
            self.last_bg_pid = pids[-1]
            print(f"[{num}] {pids[-1]}")
            return 0
        return self.wait_for(pids)

    def wait_for(self, pids):
        """Wait for every foreground child; return the status of the LAST one."""
        status = 0
        for pid in pids:
            try:
                _, st = os.waitpid(pid, 0)     # sleeps until this child ends
            except ChildProcessError:
                continue
            status = os.waitstatus_to_exitcode(st)
            if status < 0:                     # killed by signal N -> 128+N like bash
                print()
                status = 128 - status
        return status

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
