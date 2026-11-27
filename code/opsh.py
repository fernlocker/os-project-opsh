#!/usr/bin/env python3
# opsh - notre mini-shell en Python
# Projet semestriel Systèmes d'Exploitation, UIR/ESIN
#
#   python3 opsh.py              -> mode interactif (invite "opsh>")
#   python3 opsh.py script.opsh  -> exécute un fichier (if / for / while)
#
# Le chemin d'une ligne, en gros :
#   lecture -> historique -> on remplace $X, $?, $((...)), $(...)
#   -> on coupe sur "->" (c'est notre pipe) -> pour chaque morceau on trouve
#   les mots, > >> < et & -> builtin ? on le lance ici : sinon fork + execvp
#   -> on attend les fils (sauf avec &) et on garde le code de retour dans $?

import os
import re
import shlex
import signal
import sys

try:
    import readline  # flèches, historique et TAB
except ImportError:
    readline = None  # pas dispo partout, le shell marche quand même sans

# nos noms à nous pour des vrais programmes Linux
# (ce ne sont pas des builtins : ils passent par fork + exec comme les autres)
ALIASES = {
    "list": "ls", "show": "cat", "copy": "cp", "move": "mv",
    "del": "rm", "newdir": "mkdir", "newfile": "touch",
}
BUILTINS = ["go", "quit", "path", "say", "info", "past", "osinfo",
            "export", "jobs", "fg"]
HISTORY_FILE = os.path.expanduser("~/.opsh_history")
RC_FILE = os.path.expanduser("~/.opshrc")


class Opsh:
    def __init__(self):
        self.vars = {}          # variables du shell (pas exportées)
        self.last_status = 0    # c'est $?
        self.last_bg_pid = ""   # c'est $!
        self.history = []
        self.jobs = {}          # numéro de job -> (pid, texte de la commande)
        self.next_job = 1
        self.bg_extra = []      # avec "a -> b &", les pids de a (on garde b dans jobs)
        # dès qu'un fils se termine, le noyau nous envoie SIGCHLD
        signal.signal(signal.SIGCHLD, self.on_sigchld)

    # ---------- signaux ----------

    def on_sigchld(self, signum, frame):
        # On ne ramasse ici que les jobs en arrière-plan, sinon ils restent
        # zombies. Les commandes normales sont attendues par wait_for.
        for num, (pid, cmd) in list(self.jobs.items()):
            try:
                done, status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                done = pid
            # pop et pas del : le handler peut être appelé deux fois d'affilée
            if done == pid and self.jobs.pop(num, None):
                print(f"\n[{num}]+ Done    {cmd}")
        for pid in list(self.bg_extra):
            try:
                done, status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                done = pid
            if done == pid and pid in self.bg_extra:
                self.bg_extra.remove(pid)

    # ---------- les variables et le reste des $ ----------

    def get_var(self, name):
        if name == "?":
            return str(self.last_status)
        if name == "!":
            return str(self.last_bg_pid)
        if name == "$":
            return str(os.getpid())
        return self.vars.get(name, os.environ.get(name, ""))

    def expand(self, line):
        # On lit la ligne caractère par caractère. Entre '...' on ne touche à
        # rien, entre "..." on remplace quand même les variables (comme bash).
        out, i, quote = "", 0, None
        while i < len(line):
            c = line[i]
            if c == "'" and quote != '"':
                quote = None if quote == "'" else "'"
                out += c
                i += 1
            elif c == '"' and quote != "'":
                quote = None if quote == '"' else '"'
                out += c
                i += 1
            elif quote == "'":
                out += c
                i += 1
            elif line.startswith("$((", i):
                # calcul : $((6*7)), et les noms de variables valent leur valeur
                end = line.find("))", i)
                if end < 0:
                    raise SyntaxError("missing ))")
                expr = self.expand(line[i + 3:end])
                expr = re.sub(
                    r"[A-Za-z_][A-Za-z0-9_]*",
                    lambda v: self.get_var(v.group()) or "0",
                    expr,
                )
                out += self.arith(expr)
                i = end + 2
            elif line.startswith("$(", i):
                # $(commande) : on la lance et on colle ce qu'elle affiche
                end = self.matching_paren(line, i + 1)
                out += self.capture(line[i + 2:end])
                i = end + 1
            elif c == "`":
                end = line.find("`", i + 1)
                if end < 0:
                    raise SyntaxError("missing `")
                out += self.capture(line[i + 1:end])
                i = end + 1
            elif line.startswith("${", i):
                end = line.find("}", i)
                if end < 0:
                    raise SyntaxError("missing }")
                out += self.get_var(line[i + 2:end])
                i = end + 1
            elif c == "$" and i + 1 < len(line):
                m = re.match(r"[A-Za-z_][A-Za-z0-9_]*|[?!$]", line[i + 1:])
                if m:
                    out += self.get_var(m.group())
                    i += 1 + len(m.group())
                else:
                    out += c  # un $ tout seul reste un $
                    i += 1
            else:
                out += c
                i += 1
        return out

    @staticmethod
    def matching_paren(s, start):
        # trouve la ) qui ferme la ( de départ, même avec $(say $(date)) dedans
        depth = 0
        for j in range(start, len(s)):
            depth += {"(": 1, ")": -1}.get(s[j], 0)
            if depth == 0:
                return j
        raise SyntaxError("missing )")

    @staticmethod
    def arith(expr):
        # on vérifie qu'il n'y a que des chiffres et des opérateurs avant le eval,
        # et / devient // parce qu'on ne fait que des entiers
        if not re.fullmatch(r"[\d\s+\-*/%()]*", expr):
            raise SyntaxError(f"bad arithmetic: {expr}")
        try:
            return str(int(eval(expr.replace("/", "//"))))
        except SyntaxError:
            raise SyntaxError(f"bad arithmetic: {expr}") from None

    def capture(self, cmdline):
        # Pour $(...) : un fils exécute la commande avec sa sortie branchée sur
        # un pipe, et le père lit tout ce qui sort du pipe.
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r)
            os.dup2(w, 1)
            os.close(w)
            self.run_line(cmdline)
            sys.stdout.flush()
            os._exit(self.last_status)
        os.close(w)
        with os.fdopen(r) as f:
            data = f.read()
        os.waitpid(pid, 0)
        return data.rstrip("\n")

    # ---------- découpage de la ligne ----------

    @staticmethod
    def split_pipes(line):
        # coupe sur "->", sauf si c'est entre guillemets
        parts, cur, quote, i = [], "", None, 0
        while i < len(line):
            c = line[i]
            if c in "'\"":
                quote = None if quote == c else (c if quote is None else quote)
            if quote is None and line.startswith("->", i):
                parts.append(cur)
                cur, i = "", i + 2
                continue
            cur += c
            i += 1
        parts.append(cur)  # le dernier morceau
        return [p.strip() for p in parts]

    @staticmethod
    def parse_command(text):
        # "say hi > f.txt" donne (['say', 'hi'], None, 'f.txt', False, False)
        # c'est-à-dire : argv, fichier d'entrée, fichier de sortie, >> ?, & ?
        lex = shlex.shlex(text, posix=True, punctuation_chars="<>&")
        lex.whitespace_split = True
        tokens = list(lex)
        argv, infile, outfile, append, bg = [], None, None, False, False
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t in (">", ">>", "<") and i + 1 >= len(tokens):
                raise SyntaxError(f"missing file name after {t}")
            if t in (">", ">>"):
                outfile, append = tokens[i + 1], t == ">>"
                i += 2
            elif t == "<":
                infile = tokens[i + 1]
                i += 2
            elif t == "&":
                bg = True
                i += 1
            else:
                argv.append(t)
                i += 1
        if argv and argv[0] in ALIASES:
            argv[0] = ALIASES[argv[0]]
        return argv, infile, outfile, append, bg

    # ---------- les builtins ----------

    def builtin(self, argv):
        # Ces commandes tournent dans le shell lui-même, sans fork.
        # Pour go c'est obligatoire : un fils qui fait chdir ne change pas
        # le dossier du père.
        cmd, args = argv[0], argv[1:]
        if cmd == "go":
            target = args[0] if args else os.path.expanduser("~")
            try:
                os.chdir(os.path.expanduser(target))
            except OSError as e:
                print(f"go: {target}: {e.strerror}", file=sys.stderr)
                return 1
        elif cmd == "quit":
            self.save_history()
            if args and not args[0].lstrip("-").isdigit():
                print(f"quit: {args[0]}: not a number", file=sys.stderr)
                return 1
            sys.exit(int(args[0]) if args else 0)
        elif cmd == "path":
            print(os.getcwd())
        elif cmd == "say":
            print(" ".join(args))
        elif cmd == "osinfo":
            print("Systèmes d'Exploitation -- UIR/ESIN")
        elif cmd == "info":
            print("builtins : " + ", ".join(BUILTINS))
            print("aliases  : " + ", ".join(f"{k}={v}" for k, v in ALIASES.items()))
            print("pipe     : cmd1 -> cmd2   redirections: > >> <   background: &")
        elif cmd == "past":
            for n, h in enumerate(self.history, 1):
                print(f"{n:>4}  {h}")
        elif cmd == "export":
            # export NOM=valeur, ou export NOM pour une variable déjà définie
            for a in args:
                name, _, value = a.partition("=")
                os.environ[name] = value if "=" in a else self.vars.get(name, "")
        elif cmd == "jobs":
            for num, (pid, c) in self.jobs.items():
                print(f"[{num}]  {pid}  Running   {c}")
        elif cmd == "fg":
            # version simple : on attend le job comme une commande normale
            if args and not args[0].lstrip("%").isdigit():
                print(f"fg: {args[0]}: not a job number", file=sys.stderr)
                return 1
            num = int(args[0].lstrip("%")) if args else max(self.jobs, default=None)
            if num not in self.jobs:
                print("fg: no such job", file=sys.stderr)
                return 1
            pid, c = self.jobs.pop(num)
            print(c)
            # pendant l'attente, un Ctrl-C est renvoyé au job
            signal.signal(signal.SIGINT, lambda s, f: os.kill(pid, s))
            try:
                return self.wait_for([pid])
            finally:
                signal.signal(signal.SIGINT, signal.default_int_handler)
        return 0

    # ---------- exécution ----------

    def run_line(self, line):
        line = line.strip()
        if not line or line.startswith("#"):
            return
        try:
            line = self.expand(line)
            # X=valeur (sans espace autour du =) : c'est une affectation
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
        # un builtin tout seul se lance dans le shell (go, quit, export en ont besoin)
        if len(commands) == 1 and commands[0][0][0] in BUILTINS and not background:
            return self.run_builtin_redirected(commands[0])

        # Pendant que les fils tournent, le shell ignore Ctrl-C (comme bash).
        # Les fils remettent SIGINT par défaut, donc Ctrl-C n'arrête qu'eux.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            return self.fork_pipeline(commands, text, background)
        finally:
            signal.signal(signal.SIGINT, signal.default_int_handler)

    def fork_pipeline(self, commands, text, background):
        # Un fork par commande. Entre deux commandes il y a un pipe :
        # la sortie de l'une devient l'entrée de la suivante.
        pids, prev_read = [], None
        for idx, (argv, infile, outfile, append, _) in enumerate(commands):
            last = idx == len(commands) - 1
            if not last:
                r, w = os.pipe()  # r = côté lecture, w = côté écriture
            pid = os.fork()
            if pid == 0:
                # on est dans le fils
                signal.signal(signal.SIGINT, signal.SIG_DFL)
                signal.signal(signal.SIGCHLD, signal.SIG_DFL)
                if background:
                    os.setpgid(0, 0)  # son propre groupe, Ctrl-C ne le touche pas
                if prev_read is not None:
                    os.dup2(prev_read, 0)  # lit la sortie de la commande d'avant
                    os.close(prev_read)
                if not last:
                    os.close(r)
                    os.dup2(w, 1)  # écrit dans le pipe au lieu de l'écran
                    os.close(w)
                try:
                    self.apply_redirections(infile, outfile, append)
                    if argv[0] in BUILTINS:  # ex : say hi -> wc -c
                        status = self.builtin(argv)
                        sys.stdout.flush()
                        os._exit(status)
                    os.execvp(argv[0], argv)  # le fils devient le programme
                except FileNotFoundError as e:
                    # soit le programme n'existe pas, soit le fichier après < >
                    print(f"opsh: {e.filename + ': no such file' if e.filename else 'command not found: ' + argv[0]}", file=sys.stderr)
                    os._exit(127)
                except OSError as e:
                    # pas le droit, c'est un dossier, etc.
                    print(f"opsh: {e.filename or argv[0]}: {e.strerror}", file=sys.stderr)
                    os._exit(126)
            # on est dans le père
            pids.append(pid)
            if prev_read is not None:
                os.close(prev_read)
            if not last:
                # Important : le père ferme son côté écriture. Sinon la commande
                # suivante ne voit jamais la fin du pipe et le shell reste bloqué.
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
        # attend tous les fils et renvoie le code du dernier (c'est lui qui donne $?)
        status = 0
        for pid in pids:
            try:
                _, st = os.waitpid(pid, 0)
            except ChildProcessError:
                continue
            status = os.waitstatus_to_exitcode(st)
            if status < 0:
                # tué par le signal N : on renvoie 128 + N comme bash (Ctrl-C donne 130)
                print()
                status = 128 - status
        return status

    @staticmethod
    def apply_redirections(infile, outfile, append):
        if infile:
            fd = os.open(infile, os.O_RDONLY)
            os.dup2(fd, 0)  # le fichier remplace le clavier (fd 0)
            os.close(fd)
        if outfile:
            flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC)
            fd = os.open(outfile, flags, 0o644)
            os.dup2(fd, 1)  # le fichier remplace l'écran (fd 1)
            os.close(fd)

    def run_builtin_redirected(self, cmd):
        # Un builtin avec > ou < tourne dans le shell, donc on garde une copie
        # de l'écran et du clavier, on redirige, puis on remet tout en place.
        argv, infile, outfile, append, _ = cmd
        saved = os.dup(0), os.dup(1)
        try:
            sys.stdout.flush()
            self.apply_redirections(infile, outfile, append)
            status = self.builtin(argv)
            sys.stdout.flush()
        except (OSError, ValueError) as e:
            print(f"opsh: {e.filename}: {e.strerror}" if getattr(e, "filename", None) else f"opsh: {e}", file=sys.stderr)
            status = 1
        finally:
            os.dup2(saved[0], 0)
            os.dup2(saved[1], 1)
            os.close(saved[0])
            os.close(saved[1])
        return status

    # ---------- mode script : if / for / while ----------

    def parse_block(self, lines, i, ends):
        # Transforme les lignes en arbre jusqu'à tomber sur un des mots de `ends`.
        # Renvoie (noeuds, i). Les noeuds ressemblent à :
        #   ("cmd", ligne)
        #   ("if", condition, partie_then, partie_else)
        #   ("for", var, "liste de mots", corps)
        #   ("while", condition, corps)
        # La fonction s'appelle elle-même pour l'intérieur d'un bloc,
        # c'est ce qui permet d'avoir des boucles dans des boucles.
        nodes = []
        while i < len(lines):
            line = lines[i].strip()
            word = line.split()[0] if line else ""
            if word in ends:
                return nodes, i
            if word == "if":
                cond = line[2:].strip()
                then_part, i = self.parse_block(lines, i + 2, ("else", "fi"))  # i+2 : on saute "then"
                else_part = []
                if lines[i].strip() == "else":
                    else_part, i = self.parse_block(lines, i + 1, ("fi",))
                nodes.append(("if", cond, then_part, else_part))
            elif word == "for":
                parts = line.split()
                body, i = self.parse_block(lines, i + 2, ("done",))  # i+2 : on saute "do"
                nodes.append(("for", parts[1], " ".join(parts[3:]), body))
            elif word == "while":
                body, i = self.parse_block(lines, i + 2, ("done",))
                nodes.append(("while", line[5:].strip(), body))
            elif line and not line.startswith("#"):
                nodes.append(("cmd", line))
            i += 1  # on passe le fi / done, ou on va juste à la ligne suivante
        return nodes, i

    def run_nodes(self, nodes):
        for node in nodes:
            kind = node[0]
            if kind == "cmd":
                self.run_line(node[1])
            elif kind == "if":
                # on lance la condition et on regarde $?
                self.run_line(node[1])
                self.run_nodes(node[2] if self.last_status == 0 else node[3])
            elif kind == "for":
                for value in shlex.split(self.expand(node[2])):
                    self.vars[node[1]] = value
                    self.run_nodes(node[3])
            elif kind == "while":
                while True:
                    self.run_line(node[1])
                    if self.last_status != 0:
                        break
                    self.run_nodes(node[2])
            if self.last_status == 130:
                # Ctrl-C a tué une commande (128 + 2) : on arrête tout le script
                raise KeyboardInterrupt

    def run_script(self, path):
        try:
            with open(path) as f:
                text = f.read()
        except OSError as e:
            print(f"opsh: {path}: {e.strerror}", file=sys.stderr)
            return 127
        # pour accepter aussi "for x in a b; do say $x; done" sur une seule ligne
        text = re.sub(r";\s*(then|do|else|fi|done)\b", r"\n\1\n", text)
        lines = [l for l in text.splitlines()
                 if l.strip() and not l.strip().startswith("#")]
        try:
            nodes, _ = self.parse_block(lines, 0, ())
        except IndexError:
            # parse_block est sorti du fichier : il manque un fi ou un done
            print(f"opsh: {path}: 'fi' or 'done' is missing", file=sys.stderr)
            return 2
        try:
            self.run_nodes(nodes)
        except KeyboardInterrupt:
            return 130
        return self.last_status

    # ---------- historique, TAB, .opshrc et la boucle principale ----------

    def setup_readline(self):
        if not readline:
            return
        try:
            # on recharge l'historique des sessions d'avant
            readline.read_history_file(HISTORY_FILE)
            self.history = [readline.get_history_item(i)
                            for i in range(1, readline.get_current_history_length() + 1)]
        except OSError:
            pass  # premier lancement, pas encore de ~/.opsh_history
        words = BUILTINS + list(ALIASES)

        def complete(text, state):
            # readline nous appelle avec state = 0, 1, 2... jusqu'à ce qu'on renvoie None.
            # Premier mot -> on propose nos commandes, sinon -> des noms de fichiers.
            if readline.get_line_buffer().split()[:1] in ([], [text]):
                options = [w for w in words if w.startswith(text)]
            else:
                d, base = os.path.split(text)  # "code/op" -> ("code", "op")
                try:
                    options = [os.path.join(d, f) + ("/" if os.path.isdir(os.path.join(d or ".", f)) else "")
                               for f in os.listdir(d or ".") if f.startswith(base)]
                except OSError:
                    options = []
            return options[state] if state < len(options) else None
        readline.set_completer(complete)
        readline.set_completer_delims(" \t")
        # macOS a libedit au lieu de GNU readline, et TAB ne s'active pas pareil
        readline.parse_and_bind("bind ^I rl_complete" if "libedit" in (readline.__doc__ or "") else "tab: complete")

    def save_history(self):
        if readline:
            try:
                readline.write_history_file(HISTORY_FILE)
            except OSError:
                pass  # home en lecture seule par exemple, pas grave

    def load_rc(self):
        # ~/.opshrc est lu une fois au démarrage, comme ~/.bashrc
        # chaque ligne passe par run_line, exactement comme si on l'avait tapée
        if os.path.exists(RC_FILE):
            with open(RC_FILE) as f:
                for line in f:
                    self.run_line(line)

    def repl(self):
        self.setup_readline()
        self.load_rc()
        while True:
            try:
                line = input("opsh> ")
            except KeyboardInterrupt:
                print()  # Ctrl-C à l'invite : on passe juste à la ligne
                continue
            except EOFError:
                print()  # Ctrl-D : on sort, comme quit
                break
            if line.strip():
                self.history.append(line)
            self.run_line(line)
        self.save_history()


def main():
    shell = Opsh()
    if len(sys.argv) > 1:
        sys.exit(shell.run_script(sys.argv[1]))
    shell.repl()


if __name__ == "__main__":
    main()
