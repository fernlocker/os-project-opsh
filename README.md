# opsh — un mini-shell en Python

Projet semestriel · Systèmes d'Exploitation · UIR / ESIN · Automne 2026
Projet 2 (opsh) · Groupe TPD

**Membres :** Mohammed BEN CHRIF · Adam FTOUKI · Cherine DAKLI · Mohamed EL BOUDAKHANI

## Description

opsh est un interpréteur de commandes écrit en Python. Il lit une ligne,
remplace les variables, la découpe, puis lance les programmes avec
`os.fork()` / `os.execvp()` et les attend avec `os.waitpid()`.
Il gère les redirections (`>`, `>>`, `<`), les pipes (notés `->`),
l'arrière-plan (`&`), les signaux (Ctrl-C, SIGCHLD), les variables,
la substitution de commande, un fichier de démarrage, l'historique,
la complétion et un mode script (if / for / while).

## Prérequis

- Linux, macOS ou WSL2 (Ubuntu). **Ne fonctionne pas sous Windows natif**
  (`os.fork` n'existe pas).
- Python 3.9 ou plus récent. Aucune bibliothèque à installer.

## Lancer le projet

    git clone https://github.com/fernlocker/os-project-opsh.git
    cd os-project-opsh/code
    python3 opsh.py                 # mode interactif (invite : opsh>)
    python3 opsh.py example.opsh    # mode script
    python3 check.py all            # tests automatiques

Quitter : `quit` ou Ctrl-D.

Fichier de démarrage (facultatif) : opsh exécute `~/.opshrc` à chaque lancement.

    cp .opshrc.example ~/.opshrc

## Commandes

| Bash | opsh | Type |
|---|---|---|
| cd, exit, pwd, echo, help, history | go, quit, path, say, info, past | builtin |
| — | osinfo | builtin |
| ls, cat, cp, mv, rm, mkdir, touch | list, show, copy, move, del, newdir, newfile | alias |
| cmd1 \| cmd2 | cmd1 -> cmd2 | pipe |

Autres builtins : `export`, `jobs`, `fg`.

## Exemples

    opsh> list
    opsh> go ..
    opsh> path
    opsh> say hello > f.txt
    opsh> show f.txt -> wc -l
    opsh> sleep 10 &
    opsh> NAME=monde
    opsh> say bonjour $NAME, nous sommes $(date +%A)
    opsh> say $((6*7))

## Mode script

    python3 opsh.py example.opsh

Un script contient des commandes opsh, une par ligne, et des blocs :

    if [ -d /tmp ]
    then
      say "/tmp existe"
    else
      say "pas de /tmp"
    fi

    for f in alpha beta gamma
    do
      say item: $f
    done

    i=1
    while [ $i -le 3 ]
    do
      say "tour $i"
      i=$((i+1))
    done

Les blocs peuvent aussi s'écrire sur une ligne : `for x in a b; do say $x; done`.
Les lignes vides et les commentaires (`# ...`) sont ignorés.
Un fichier inexistant donne le statut 127, un `fi` / `done` manquant donne le statut 2,
et Ctrl-C arrête le script avec le statut 130.

## Structure du dépôt

    code/opsh.py              le shell (une classe Opsh)
    code/check.py             tests automatiques
    code/example.opsh         script de démonstration
    code/.opshrc.example      exemple de fichier de démarrage (à copier en ~/.opshrc)
    report.pdf                rapport (à ajouter)
    demo.mp4                  vidéo de démonstration (à ajouter)

## Jalons réalisés

| Jalon | État | Fonctions principales |
|---|---|---|
| 1. REPL, fork/exec | en cours (reste C1) | repl, run_line, fork_pipeline, wait_for |
| 2. Builtins, alias, redirections | à faire (B1–B5) | builtin, parse_command, apply_redirections |
| 3. Pipes, arrière-plan, signaux | en cours (reste C1, B6) | split_pipes, fork_pipeline, on_sigchld |
| 4. Variables et expansion | en cours (reste C2, C3) | get_var, expand |
| 5. Substitution, .opshrc, historique, complétion | en cours (reste C4–C6) | capture, load_rc, setup_readline |
| 6. Mode script (+ jobs, fg) | en cours (reste B3 pour jobs/fg) | parse_block, run_nodes, run_script |

## Qui a fait quoi

| Membre | Boîtes | Partie |
|---|---|---|
| Mohammed BEN CHRIF | A1–A5 | boucle REPL, exécution (fork/exec/wait), pipes ; dépôt Git |
| Adam FTOUKI | B1–B6 | alias, builtins, redirections, SIGCHLD ; vidéo |
| Cherine DAKLI | C1–C6 | découpage `->`, variables, arithmétique, substitution ; rapport |
| Mohamed EL BOUDAKHANI | D1–D6 | .opshrc, historique, complétion, mode script ; README et tests |

## Limites connues

- `bg` et Ctrl-Z ne sont pas implémentés ; `fg` est simplifié.
- Pas de redirection de la sortie d'erreur (`2>`), pas de jokers (`*.txt`).
- Pas de `elif` dans les scripts.
- Arithmétique entière uniquement.
