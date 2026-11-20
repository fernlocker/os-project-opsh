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
# [BOX B1 START] owner: Adam FTOUKI | the tables ALIASES and BUILTINS | replace this whole box (down to its END line) with the real code
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
    # [BOX B6 START] owner: Adam FTOUKI | on_sigchld | replace this whole box (down to its END line) with the real code
    def on_sigchld(self, signum, frame):
        pass
    # [BOX B6 END]

    # ================================================================
    # EXPANSION  ($VAR, ${VAR}, $?, $!, $$, $((...)), $(...), `...`)
    # ================================================================
    # [BOX C2 START] owner: Cherine DAKLI | get_var | replace this whole box (down to its END line) with the real code
    def get_var(self, name):
        return ""
    # [BOX C2 END]

    # [BOX C3 START] owner: Cherine DAKLI | expand | replace this whole box (down to its END line) with the real code
    def expand(self, line):
        return line
    # [BOX C3 END]

    # [BOX C4 START] owner: Cherine DAKLI | matching_paren | replace this whole box (down to its END line) with the real code
    @staticmethod
    def matching_paren(s, start):
        return s.index(")", start)
    # [BOX C4 END]

    # [BOX C5 START] owner: Cherine DAKLI | arith | replace this whole box (down to its END line) with the real code
    @staticmethod
    def arith(expr):
        return expr
    # [BOX C5 END]

    # [BOX C6 START] owner: Cherine DAKLI | capture | replace this whole box (down to its END line) with the real code
    def capture(self, cmdline):
        return ""
    # [BOX C6 END]

    # ================================================================
    # PARSING
    # ================================================================
    # [BOX C1 START] owner: Cherine DAKLI | split_pipes | replace this whole box (down to its END line) with the real code
    @staticmethod
    def split_pipes(line):
        return [line]
    # [BOX C1 END]

    # [BOX B2 START] owner: Adam FTOUKI | parse_command | replace this whole box (down to its END line) with the real code
    @staticmethod
    def parse_command(text):
        return shlex.split(text), None, None, False, False
    # [BOX B2 END]

    # ================================================================
    # BUILTINS (run INSIDE the shell process)
    # ================================================================
    # [BOX B3 START] owner: Adam FTOUKI | builtin | replace this whole box (down to its END line) with the real code
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

    # [BOX B4 START] owner: Adam FTOUKI | apply_redirections | replace this whole box (down to its END line) with the real code
    @staticmethod
    def apply_redirections(infile, outfile, append):
        pass
    # [BOX B4 END]

    # [BOX B5 START] owner: Adam FTOUKI | run_builtin_redirected | replace this whole box (down to its END line) with the real code
    def run_builtin_redirected(self, cmd):
        return self.builtin(cmd[0])
    # [BOX B5 END]

    # ================================================================
    # SCRIPT MODE: if / for / while
    # ================================================================
    def parse_block(self, lines, i, ends):
        """Turn lines into a tree of nodes until one of `ends` is found.

        Returns (nodes, i): the list of nodes and the index of the line that ended
        the block. The nodes are tuples:
            ("cmd", line)
            ("if", condition, then_nodes, else_nodes)
            ("for", var, "word list", body_nodes)
            ("while", condition, body_nodes)
        It calls itself for the inside of a block (recursion), so loops can be nested.
        """
        nodes = []
        while i < len(lines):
            line = lines[i].strip()
            word = line.split()[0] if line else ""
            if word in ends:                       # end of the block we are reading
                return nodes, i
            if word == "if":                       # if CMD / then / else / fi
                cond = line[2:].strip()
                then_part, i = self.parse_block(lines, i + 2, ("else", "fi"))   # i+2: skip "then"
                else_part = []
                if lines[i].strip() == "else":
                    else_part, i = self.parse_block(lines, i + 1, ("fi",))
                nodes.append(("if", cond, then_part, else_part))
            elif word == "for":                    # for x in a b c / do / done
                parts = line.split()
                body, i = self.parse_block(lines, i + 2, ("done",))            # i+2: skip "do"
                nodes.append(("for", parts[1], " ".join(parts[3:]), body))
            elif word == "while":                  # while CMD / do / done
                body, i = self.parse_block(lines, i + 2, ("done",))
                nodes.append(("while", line[5:].strip(), body))
            elif line and not line.startswith("#"):  # an ordinary command
                nodes.append(("cmd", line))
            i += 1                                 # skip fi / done (or go to the next line)
        return nodes, i

    def run_nodes(self, nodes):
        # walk the tree made by parse_block and run it
        for node in nodes:
            kind = node[0]
            if kind == "cmd":
                self.run_line(node[1])
            elif kind == "if":                     # run the condition, look at $?
                self.run_line(node[1])
                self.run_nodes(node[2] if self.last_status == 0 else node[3])
            elif kind == "for":                    # one turn per word of the list
                for value in shlex.split(self.expand(node[2])):
                    self.vars[node[1]] = value
                    self.run_nodes(node[3])
            elif kind == "while":                  # repeat while the condition gives 0
                while True:
                    self.run_line(node[1])
                    if self.last_status != 0:
                        break
                    self.run_nodes(node[2])
            if self.last_status == 130:            # Ctrl-C killed a command (128 + SIGINT 2):
                raise KeyboardInterrupt            # stop the whole script, like bash

    def run_script(self, path):
        # script mode: python3 opsh.py file.opsh
        try:
            with open(path) as f:
                text = f.read()
        except OSError as e:                       # no such file, permission denied, directory...
            print(f"opsh: {path}: {e.strerror}", file=sys.stderr)
            return 127
        # allow "if cmd; then ...; fi" and "for x in a b; do ...; done" on one line
        text = re.sub(r";\s*(then|do|else|fi|done)\b", r"\n\1\n", text)
        lines = [l for l in text.splitlines()         # drop empty and comment lines
                 if l.strip() and not l.strip().startswith("#")]
        try:
            nodes, _ = self.parse_block(lines, 0, ())
        except IndexError:                         # parse_block ran past the end: no fi / done
            print(f"opsh: {path}: 'fi' or 'done' is missing", file=sys.stderr)
            return 2
        try:
            self.run_nodes(nodes)
        except KeyboardInterrupt:                  # Ctrl-C stops the script
            return 130
        return self.last_status

    # ================================================================
    # HISTORY, COMPLETION, .opshrc, REPL
    # ================================================================
    def setup_readline(self):
        # readline gives the arrow keys, the history (up/down) and the TAB key
        if not readline:                       # module missing on this system: skip
            return
        try:                                   # load the history of the previous sessions
            readline.read_history_file(HISTORY_FILE)
            self.history = [readline.get_history_item(i)
                            for i in range(1, readline.get_current_history_length() + 1)]
        except OSError:                        # first run: no ~/.opsh_history yet
            pass
        words = BUILTINS + list(ALIASES)       # the opsh words TAB can propose

        def complete(text, state):
            # readline calls this with state = 0, 1, 2 ... until we return None
            # first word -> commands, otherwise -> file names
            if readline.get_line_buffer().split()[:1] in ([], [text]):
                options = [w for w in words if w.startswith(text)]
            else:
                d, base = os.path.split(text)  # "code/op" -> ("code", "op")
                try:
                    options = [os.path.join(d, f) + ("/" if os.path.isdir(os.path.join(d or ".", f)) else "")
                               for f in os.listdir(d or ".") if f.startswith(base)]
                except OSError:                # folder does not exist / not readable
                    options = []
            return options[state] if state < len(options) else None
        readline.set_completer(complete)
        readline.set_completer_delims(" \t")   # a word ends at a space or a tab only
        # macOS uses libedit, Linux uses GNU readline: the TAB binding is written differently
        readline.parse_and_bind("bind ^I rl_complete" if "libedit" in (readline.__doc__ or "") else "tab: complete")

    def save_history(self):
        # write the history to ~/.opsh_history so the next opsh remembers it
        if readline:
            try:
                readline.write_history_file(HISTORY_FILE)
            except OSError:                    # read-only home, etc.: not worth a crash
                pass

    def load_rc(self):
        # ~/.opshrc = "run commands" file, executed once at start-up (like ~/.bashrc)
        if os.path.exists(RC_FILE):            # no file -> nothing to do, no error
            with open(RC_FILE) as f:
                for line in f:                 # every line goes through the normal path
                    self.run_line(line)        # same function as a line typed at the prompt

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
