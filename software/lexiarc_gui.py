import os
import sys
import json
import secrets
import subprocess
import threading
import webbrowser
import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog, ttk

# Nécessite Pillow : pip install Pillow
from PIL import Image, ImageTk

import lexiarc_core as core
from lexiarc_wizard import EmulationWizard

# --- CONFIGURATION & CONSTANTES ---
VERSION = "0.2.0-BETA"
AUTEUR = "Maxlware"
LICENCE = "Apache-2.0 License"
DOCS_URL = "https://github.com/maxlware-fr/LexiARC/blob/main/docs/HOME.md"

ICON_PATH = str(core.RES_DIR / "logo.ico")      # Icône de la barre de titre
LOGO_PATH = str(core.RES_DIR / "logo.png")      # Logo pour l'écran d'accueil & splash screen

# Arborescence (voir lexiarc_core.py) : bin/emu293.exe + DLL, bin/mtools/mtools.exe,
# emulations/ (images SD + .larc créés par l'assistant), logs/.
# Lead.sys n'est plus "bundlé" : il est pris sur la carte SD de l'utilisateur.
BASE_DIR = core.APP_DIR
BIN_DIR = core.BIN_DIR
EMU293_EXE = core.EMU293_EXE
MTOOLS_DIR = core.MTOOLS_DIR
core.ensure_mtools()
MCOPY = MTOOLS_DIR / "mcopy.exe"
MDIR = MTOOLS_DIR / "mdir.exe"
MFORMAT = MTOOLS_DIR / "mformat.exe"
MMD = MTOOLS_DIR / "mmd.exe"


class LexiARCApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"LexiARC Emulator - {VERSION}")
        self.root.geometry("750x400")
        self.carte_sd_importee = False
        self.chemin_carte_sd = None      # Stocke le chemin de l'image SD importée
        self.definir_logo_fenetre()
        self.verifier_fichiers_essentiels()
        self.creer_menu()
        self.creer_ecran_accueil()

    # ----------------------------------------------------------------------
    # Utilitaires généraux
    # ----------------------------------------------------------------------
    def definir_logo_fenetre(self):
        """Applique l'icône .ico à la fenêtre principale (Windows)"""
        if os.path.exists(ICON_PATH):
            try:
                self.root.iconbitmap(ICON_PATH)
            except Exception as e:
                print(f"[*] Impossible d'appliquer l'icône : {e}")

    def verifier_fichiers_essentiels(self):
        """Statut des dépendances (non bloquant : l'assistant permet de les installer)."""
        self.statut_deps = ""
        for d in core.check_dependencies():
            if not d["ok"]:
                self.statut_deps += f"⚠ {d['nom']} : manquant ({', '.join(d['manquants'][:3])}" + \
                                    (", …" if len(d["manquants"]) > 3 else "") + ")\n"

    def creer_ecran_accueil(self):
        """Message par défaut affiché au lancement"""
        self.label_accueil = tk.Label(
            self.root,
            text="Menu Fichier ▸ Créer une émulation, ou ▸ Lancer une émulation"
                 + (("\n\n" + self.statut_deps.strip()) if self.statut_deps else ""),
            font=("Helvetica", 14, "italic"),
            fg="gray"
        )
        self.label_accueil.pack(expand=True)

    # ----------------------------------------------------------------------
    # Barre de menus
    # ----------------------------------------------------------------------
    def creer_menu(self):
        menubar = tk.Menu(self.root)

        # --- Menu FICHIER ---
        menu_file = tk.Menu(menubar, tearoff=0)

        # Sous-menu Créer une émulation
        menu_creer = tk.Menu(menu_file, tearoff=0)
        menu_creer.add_command(label="Créer une nouvelle émulation", command=self.fenetre_creer_emulation)
        menu_file.add_cascade(label="Créer une émulation", menu=menu_creer)
        menu_file.add_command(label="Lancer une émulation", command=self.action_lancer_emulation)

        # Sous-menu Compilation
        menu_comp = tk.Menu(menu_file, tearoff=0)
        menu_comp.add_command(label="Compiler en .elf", command=lambda: self.fenetre_compilation("elf"))
        menu_comp.add_command(label="Compiler en .wxn", command=lambda: self.fenetre_compilation("wxn"))
        menu_file.add_cascade(label="Compilation", menu=menu_comp)

        menu_file.add_separator()
        menu_file.add_command(label="Quitter", command=self.root.quit)
        menubar.add_cascade(label="Fichier", menu=menu_file)

        # --- Menu IMPLÉMENTATION ---
        menu_implementation = tk.Menu(menubar, tearoff=0)
        menu_implementation.add_command(label="Créer une implémentation", command=self.fenetre_creer_implementation)
        menu_implementation.add_command(label="Supprimer une implémentation", command=self.action_supprimer_implementation)
        menubar.add_cascade(label="Implémentation", menu=menu_implementation)

        # --- Menu CODE ---
        menu_code = tk.Menu(menubar, tearoff=0)
        menu_code.add_command(label="Importer sa carte SD", command=self.action_importer_carte_sd)
        menu_code.add_command(label="Éditeur (navigateur SD)", state="disabled", command=self.action_editeur)
        menu_code.add_command(label="Formatage", state="disabled", command=self.action_formatage)
        menu_code.add_command(label="Propriété", state="disabled", command=self.action_propriete)
        menubar.add_cascade(label="Code", menu=menu_code)
        self.menu_code = menu_code

        # --- Menu AIDE ---
        menu_aide = tk.Menu(menubar, tearoff=0)
        menu_aide.add_command(label="Documentation", command=self.ouvrir_documentation)
        menu_aide.add_command(label="A propos", command=self.fenetre_a_propos)
        menubar.add_cascade(label="Aide", menu=menu_aide)

        self.root.config(menu=menubar)

    # ----------------------------------------------------------------------
    # Actions du menu
    # ----------------------------------------------------------------------
    def ouvrir_documentation(self):
        webbrowser.open(DOCS_URL)

    def action_lancer_emulation(self):
        """Fichier ▸ Lancer une émulation : choisir un .larc puis lancer."""
        filename = filedialog.askopenfilename(
            title="Choisir le fichier d'émulation",
            initialdir=str(core.EMULATIONS_DIR) if core.EMULATIONS_DIR.exists() else None,
            filetypes=[("Configuration LexiARC", "*.larc")])
        if filename:
            self.lancer_larc(filename)

    def lancer_larc(self, chemin):
        try:
            config = core.load_larc(chemin)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de lire le fichier .larc :\n{e}")
            return
        problemes = core.pre_launch_check(config)
        if problemes:
            messagebox.showerror("Lancement impossible", "\n\n".join("• " + p for p in problemes) +
                                 "\n\nFichier ▸ Créer une émulation ▸ étape 4 permet d'installer les dépendances.")
            return
        self.ouvrir_ecran_emulation(config)

    # ----------------------------------------------------------------------
    # Fenêtre : créer une émulation
    # ----------------------------------------------------------------------
    def fenetre_creer_emulation(self):
        """Ouvre l'assistant en 4 étapes."""
        def fini(larc, lancer):
            self.verifier_fichiers_essentiels()
            if lancer:
                self.lancer_larc(larc)
        EmulationWizard(self.root, icon_path=ICON_PATH, on_finished=fini, defaults={"auteur": AUTEUR})

    # ----------------------------------------------------------------------
    # Splash Screen (fade-in/out) puis lancement RÉEL d'emu293
    # ----------------------------------------------------------------------
    def ouvrir_ecran_emulation(self, config):
        """
        Ouvre une fenêtre avec un fondu du logo (Pillow) sur fond blanc,
        puis lance réellement emu293.exe avec Lead.sys + l'image SD choisie.
        """
        emu_win = tk.Toplevel(self.root)
        emu_win.title(f"Écran d'émulation : {config.get('nom_emulateur', 'LexiARC')}")
        emu_win.geometry("640x480")
        emu_win.configure(bg="white")
        emu_win.resizable(False, False)
        if os.path.exists(ICON_PATH):
            try:
                emu_win.iconbitmap(ICON_PATH)
            except Exception:
                pass

        lbl_splash = tk.Label(emu_win, bg="white")
        lbl_splash.place(relx=0.5, rely=0.5, anchor="center")

        if not os.path.exists(LOGO_PATH):
            lbl_splash.destroy()
            emu_win.configure(bg="black")
            self._lancer_emu293(emu_win, config)
            return

        try:
            pil_logo = Image.open(LOGO_PATH).convert("RGBA")
        except Exception as e:
            print(f"Erreur chargement logo : {e}")
            lbl_splash.destroy()
            emu_win.configure(bg="black")
            self._lancer_emu293(emu_win, config)
            return

        logo_w, logo_h = pil_logo.size
        fond_blanc = Image.new("RGBA", (logo_w, logo_h), (255, 255, 255, 255))
        logo_sur_blanc = Image.alpha_composite(fond_blanc, pil_logo).convert("RGB")
        blanc_pur = Image.new("RGB", (logo_w, logo_h), (255, 255, 255))

        FADE_STEPS = 40
        STEP_MS = 25
        HOLD_MS = 1000

        state = {"step": 0, "phase": "fade_in", "after_id": None}

        def update_image(opacity):
            blended = Image.blend(blanc_pur, logo_sur_blanc, opacity)
            tk_img = ImageTk.PhotoImage(blended)
            lbl_splash.configure(image=tk_img)
            lbl_splash.image = tk_img

        def animer():
            if state["phase"] == "fade_in":
                progress = state["step"] / FADE_STEPS
                update_image(progress)
                state["step"] += 1
                if state["step"] > FADE_STEPS:
                    state["phase"] = "hold"
                    state["after_id"] = emu_win.after(HOLD_MS, animer)
                else:
                    state["after_id"] = emu_win.after(STEP_MS, animer)

            elif state["phase"] == "hold":
                state["phase"] = "fade_out"
                state["step"] = 0
                state["after_id"] = emu_win.after(STEP_MS, animer)

            elif state["phase"] == "fade_out":
                progress = 1.0 - (state["step"] / FADE_STEPS)
                update_image(progress)
                state["step"] += 1
                if state["step"] > FADE_STEPS:
                    state["phase"] = "done"
                    lbl_splash.destroy()
                    emu_win.configure(bg="black")
                    self._lancer_emu293(emu_win, config)
                else:
                    state["after_id"] = emu_win.after(STEP_MS, animer)

        def on_close():
            if state["after_id"] is not None:
                emu_win.after_cancel(state["after_id"])
            emu_win.destroy()
        emu_win.protocol("WM_DELETE_WINDOW", on_close)

        animer()

    def _lancer_emu293(self, fenetre, config):
        """Fenêtre d'émulation = console en direct : sortie d'emu293 (stdout+stderr) en temps réel,
        statut, code de sortie expliqué, boutons Arrêter / Relancer / Copier / Dossier des logs."""
        problemes = core.pre_launch_check(config)
        if problemes:
            messagebox.showerror("Lancement impossible", "\n\n".join("• " + p for p in problemes))
            fenetre.destroy()
            return

        for w in fenetre.winfo_children():
            w.destroy()
        fenetre.configure(bg="#1e1e1e")
        fenetre.geometry("820x540")
        fenetre.resizable(True, True)
        fenetre.minsize(560, 360)

        entete = (f"{config.get('nom_emulateur', 'Inconnu')}   |   "
                  f"{config.get('architecture_cpu', 'N/A')}   |   RAM {config.get('taille_ram', 'N/A')}   |   "
                  f"SD : {os.path.basename(str(config['_sd']))}")
        tk.Label(fenetre, text=entete, fg="#9cdcfe", bg="#1e1e1e", font=("Courier", 10), anchor="w").pack(
            fill="x", padx=8, pady=(8, 2))

        # --- zone de log ---
        cadre = tk.Frame(fenetre, bg="#1e1e1e")
        cadre.pack(fill="both", expand=True, padx=8, pady=4)
        txt = tk.Text(cadre, bg="#0c0c0c", fg="#d4d4d4", insertbackground="white", font=("Courier", 10),
                      wrap="word", state="disabled", relief="flat")
        sb = ttk.Scrollbar(cadre, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        txt.tag_configure("erreur", foreground="#f48771")
        txt.tag_configure("lexiarc", foreground="#6a9955")
        txt.tag_configure("info", foreground="#dcdcaa")

        statut = tk.Label(fenetre, text="", fg="lime", bg="#1e1e1e", font=("Courier", 10, "bold"), anchor="w")
        statut.pack(fill="x", padx=8)

        etat = {"session": None, "auto": tk.BooleanVar(value=True), "fini": False}

        def ecrire(texte, tag=None):
            txt.configure(state="normal")
            for ligne in texte.splitlines(keepends=True):
                t = tag
                if t is None:
                    bas = ligne.lower()
                    if ligne.startswith("# LexiARC"):
                        t = "lexiarc"
                    elif any(m in bas for m in ("fail", "error", "erreur", "terminate", "cannot", "unable")):
                        t = "erreur"
                txt.insert("end", ligne, t) if t else txt.insert("end", ligne)
            txt.configure(state="disabled")
            if etat["auto"].get():
                txt.see("end")

        def demarrer():
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            txt.configure(state="disabled")
            etat["fini"] = False
            try:
                etat["session"] = core.launch_emulation(config)
            except Exception as e:
                ecrire(f"Impossible de lancer emu293 : {e}\n", "erreur")
                statut.config(text="■ Non lancé", fg="#f48771")
                return
            self.emu_process = etat["session"].proc
            statut.config(text=f"● En cours (PID {self.emu_process.pid})", fg="lime")
            btn_stop.config(state="normal")
            btn_relance.config(state="disabled")
            fenetre.after(100, lire)

        def lire():
            sess = etat["session"]
            if sess is None or not fenetre.winfo_exists():
                return
            try:
                while True:
                    m = sess.q.get_nowait()
                    if isinstance(m, tuple):          # ("exit", code)
                        code = m[1]
                        etat["fini"] = True
                        sess.close()
                        indice = core.explain_exit(code)
                        ok = (code & 0xFFFFFFFF) == 0
                        statut.config(text=f"■ Arrêté — code {code & 0xFFFFFFFF} (0x{code & 0xFFFFFFFF:08X})",
                                      fg="lime" if ok else "#f48771")
                        ecrire(f"\n[emu293 terminé, code {code & 0xFFFFFFFF}]\n", "info")
                        if indice:
                            ecrire(f"→ {indice}\n", "info")
                        btn_stop.config(state="disabled")
                        btn_relance.config(state="normal")
                        return
                    ecrire(m)
            except Exception:
                pass
            fenetre.after(100, lire)

        def arreter():
            if etat["session"]:
                etat["session"].stop()

        def copier():
            fenetre.clipboard_clear()
            fenetre.clipboard_append(txt.get("1.0", "end"))
            statut.config(text=statut.cget("text") + "   (journal copié)")

        def ouvrir_logs():
            core.LOGS_DIR.mkdir(exist_ok=True)
            try:
                os.startfile(str(core.LOGS_DIR))
            except AttributeError:
                webbrowser.open(core.LOGS_DIR.as_uri())

        def fermer():
            arreter()
            if etat["session"]:
                etat["session"].close()
            fenetre.destroy()

        barre = tk.Frame(fenetre, bg="#1e1e1e")
        barre.pack(fill="x", padx=8, pady=8)
        btn_stop = ttk.Button(barre, text="Arrêter", command=arreter)
        btn_stop.pack(side="left")
        btn_relance = ttk.Button(barre, text="Relancer", command=demarrer, state="disabled")
        btn_relance.pack(side="left", padx=6)
        ttk.Button(barre, text="Copier le journal", command=copier).pack(side="left")
        ttk.Button(barre, text="Dossier des logs", command=ouvrir_logs).pack(side="left", padx=6)
        ttk.Checkbutton(barre, text="Défilement auto", variable=etat["auto"]).pack(side="right")
        fenetre.protocol("WM_DELETE_WINDOW", fermer)

        demarrer()

    # ----------------------------------------------------------------------
    # Compilation : NON DISPONIBLE (voir en-tête du fichier / rapport chat)
    # ----------------------------------------------------------------------
    def fenetre_compilation(self, format_output="elf"):
        details = (
            "Ce toolchain n'existe pas encore : GCC ciblant 'score-elf' n'est plus maintenu "
            "dans les binutils/gcc modernes (support retiré ~2015)."
        )
        if format_output == "wxn":
            details += (
                "\n\nDe plus, le chiffrement .wxn semble géré par le contrôleur DMA matériel "
                "de la console (registres MMIO), pas par un algorithme logiciel simple — "
                "il n'a pas encore été reproduit."
            )
        messagebox.showinfo(
            f"Compilation .{format_output} non disponible",
            f"Cette fonctionnalité n'est PAS encore implémentée.\n\n{details}\n\n"
            "En attendant, utilise lexianalyzer.py / score_disasm.py pour l'analyse manuelle."
        )

    # ----------------------------------------------------------------------
    # Implémentation : copie RÉELLE d'un jeu sur l'image SD via mcopy
    # ----------------------------------------------------------------------
    def fenetre_creer_implementation(self):
        """Implémentation : copier un fichier (ELF, WXN ou AUTRE) sur la carte SD, à l'endroit choisi."""
        win = tk.Toplevel(self.root)
        win.title("Créer une implémentation")
        win.geometry("520x270")
        win.resizable(False, False)
        if os.path.exists(ICON_PATH):
            try:
                win.iconbitmap(ICON_PATH)
            except Exception:
                pass
        win.grab_set()

        ttk.Label(win, text="Type de fichier :").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        var_type = tk.StringVar(value="wxn")
        frame_type = ttk.Frame(win)
        frame_type.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        ttk.Radiobutton(frame_type, text="ELF (.elf)", variable=var_type, value="elf").pack(side="left")
        ttk.Radiobutton(frame_type, text="WXN (.wxn)", variable=var_type, value="wxn").pack(side="left", padx=10)
        ttk.Radiobutton(frame_type, text="Autre", variable=var_type, value="autre").pack(side="left")

        ttk.Label(win, text="Fichier :").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        var_fichier = tk.StringVar()
        frame_fichier = ttk.Frame(win)
        frame_fichier.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        ttk.Entry(frame_fichier, textvariable=var_fichier, width=34).pack(side="left")

        def parcourir_fichier():
            t = var_type.get()
            ft = {"elf": [("Fichier ELF", "*.elf")], "wxn": [("Fichier WXN", "*.wxn")]}.get(t, [])
            f = filedialog.askopenfilename(parent=win, filetypes=ft + [("Tous les fichiers", "*.*")])
            if f:
                var_fichier.set(f)
        ttk.Button(frame_fichier, text="...", width=3, command=parcourir_fichier).pack(side="left", padx=5)

        ttk.Label(win, text="Carte SD (.img) :").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        var_sd = tk.StringVar(value=self.chemin_carte_sd or "")
        frame_sd = ttk.Frame(win)
        frame_sd.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        ttk.Entry(frame_sd, textvariable=var_sd, width=34).pack(side="left")
        ttk.Button(frame_sd, text="...", width=3,
                   command=lambda: var_sd.set(filedialog.askopenfilename(
                       parent=win, filetypes=[("Image SD", "*.img"), ("Tous les fichiers", "*.*")]) or var_sd.get())
                   ).pack(side="left", padx=5)

        ttk.Label(win, text="Étape suivante : tu choisis le dossier de la carte où déposer le fichier.",
                  foreground="gray").grid(row=3, column=0, columnspan=2, padx=10, sticky="w")

        def commencer_implementation():
            if not var_fichier.get() or not var_sd.get():
                messagebox.showerror("Erreur", "Veuillez sélectionner le fichier et la carte SD.", parent=win)
                return
            if not os.path.isfile(var_fichier.get()):
                messagebox.showerror("Erreur", "Le fichier sélectionné est introuvable.", parent=win)
                return
            if not os.path.isfile(var_sd.get()):
                messagebox.showerror("Erreur", "L'image de la carte SD est introuvable.", parent=win)
                return
            sd, fichier, type_ = var_sd.get(), var_fichier.get(), var_type.get()
            win.destroy()
            self._implementer_jeu_reel(sd, fichier, type_)

        ttk.Button(win, text="Choisir la destination…", command=commencer_implementation).grid(
            row=4, column=0, columnspan=2, pady=18)

    def _choisir_destination_sd(self, sd_path, nom_fichier, type_):
        """Sélecteur de dossier DANS l'image SD (via mdir). Retourne (dossier, nom) ou None."""
        if core.list_sd_dir(sd_path, "::/") is None:
            messagebox.showerror("Carte SD illisible",
                                 "Impossible de lire cette image (FAT). Est-ce bien une carte SD formatée ?")
            return None

        win = tk.Toplevel(self.root)
        win.title("Où déposer le fichier sur la carte SD ?")
        win.geometry("560x470")
        if os.path.exists(ICON_PATH):
            try:
                win.iconbitmap(ICON_PATH)
            except Exception:
                pass
        win.transient(self.root)
        win.grab_set()

        # dossier de départ : Game Player pour elf/wxn s'il existe, sinon la racine
        depart = "::/"
        if type_ in ("elf", "wxn") and core.list_sd_dir(sd_path, "::/Fun/Game Player") is not None:
            depart = "::/Fun/Game Player"

        courant = tk.StringVar(value=depart)
        var_nom = tk.StringVar(value=nom_fichier)
        resultat = {"val": None}
        contenu = {"dirs": [], "files": []}

        ttk.Label(win, text="Dossier de destination :").pack(anchor="w", padx=10, pady=(10, 0))
        ttk.Label(win, textvariable=courant, font=("Courier", 10, "bold")).pack(anchor="w", padx=10)

        cadre = ttk.Frame(win)
        cadre.pack(fill="both", expand=True, padx=10, pady=6)
        liste = tk.Listbox(cadre, font=("Courier", 10), activestyle="none")
        sb = ttk.Scrollbar(cadre, command=liste.yview)
        liste.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        liste.pack(side="left", fill="both", expand=True)

        def rafraichir():
            res = core.list_sd_dir(sd_path, courant.get())
            liste.delete(0, "end")
            if res is None:
                contenu["dirs"], contenu["files"] = [], []
                liste.insert("end", "[Dossier illisible]")
                return
            contenu["dirs"], contenu["files"] = res
            for d in res[0]:
                liste.insert("end", "[DIR] " + d)
            for f in res[1]:
                liste.insert("end", "      " + f)
                liste.itemconfig("end", foreground="gray")
            if not res[0] and not res[1]:
                liste.insert("end", "(dossier vide)")
                liste.itemconfig("end", foreground="gray")

        def ouvrir(event=None):
            sel = liste.curselection()
            if not sel or sel[0] >= len(contenu["dirs"]):
                return
            courant.set(core.sd_join(courant.get(), contenu["dirs"][sel[0]]))
            rafraichir()

        def remonter():
            courant.set(core.sd_parent(courant.get()))
            rafraichir()

        def nouveau_dossier():
            nom = simpledialog.askstring("Nouveau dossier", "Nom du dossier à créer ici :", parent=win)
            if not nom or not nom.strip():
                return
            ok, err = core.make_sd_dir(sd_path, core.sd_join(courant.get(), nom.strip()))
            if not ok:
                messagebox.showerror("Création impossible", err, parent=win)
            rafraichir()

        liste.bind("<Double-Button-1>", ouvrir)

        barre = ttk.Frame(win)
        barre.pack(fill="x", padx=10)
        ttk.Button(barre, text="⬆ Remonter", command=remonter).pack(side="left")
        ttk.Button(barre, text="Ouvrir", command=ouvrir).pack(side="left", padx=6)
        ttk.Button(barre, text="Nouveau dossier…", command=nouveau_dossier).pack(side="left")

        ligne = ttk.Frame(win)
        ligne.pack(fill="x", padx=10, pady=10)
        ttk.Label(ligne, text="Nom sur la carte :").pack(side="left")
        ttk.Entry(ligne, textvariable=var_nom, width=36).pack(side="left", padx=8)

        def valider():
            nom = var_nom.get().strip()
            if not nom or any(c in nom for c in '/\\:*?"<>|'):
                messagebox.showerror("Nom invalide", "Le nom du fichier est vide ou contient un caractère interdit.",
                                     parent=win)
                return
            if nom.lower() in (f.lower() for f in contenu["files"]):
                if not messagebox.askyesno("Fichier existant",
                                           f"« {nom} » existe déjà dans ce dossier.\nLe remplacer ?", parent=win):
                    return
            resultat["val"] = (courant.get(), nom)
            win.destroy()

        bas = ttk.Frame(win)
        bas.pack(fill="x", padx=10, pady=(0, 12))
        ttk.Button(bas, text="Annuler", command=win.destroy).pack(side="left")
        ttk.Button(bas, text="Copier ici ▶", command=valider).pack(side="right")

        rafraichir()
        self.root.wait_window(win)
        return resultat["val"]

    def _implementer_jeu_reel(self, sd_path, fichier, type_="autre"):
        if not core.ensure_mtools():
            messagebox.showerror("mtools introuvable", f"mtools introuvable :\n{core.MTOOLS_DIR}")
            return

        choix = self._choisir_destination_sd(sd_path, os.path.basename(fichier), type_)
        if not choix:
            return
        dest_dir, nom = choix

        progress_win = tk.Toplevel(self.root)
        progress_win.title("Implémentation en cours...")
        progress_win.geometry("420x100")
        progress_win.resizable(False, False)
        progress_win.grab_set()
        ttk.Label(progress_win, text=f"Copie de {os.path.basename(fichier)} vers {dest_dir.rstrip('/')}/{nom}…").pack(pady=10)
        barre = ttk.Progressbar(progress_win, mode="indeterminate", length=370)
        barre.pack(pady=10)
        barre.start(10)

        def faire_copie():
            try:
                ok, err = core.copy_file_to_sd(sd_path, fichier, dest_dir, nom)
            except Exception as e:
                ok, err = False, str(e)

            def finir():
                barre.stop()
                progress_win.destroy()
                if ok:
                    messagebox.showinfo("Implémentation terminée",
                                        f"{nom} copié avec succès dans {dest_dir.rstrip('/')}/ sur la carte SD.")
                else:
                    messagebox.showerror("Échec de la copie (mcopy)", err or "Erreur inconnue")
            self.root.after(0, finir)

        threading.Thread(target=faire_copie, daemon=True).start()

    def action_supprimer_implementation(self):
        messagebox.showerror("Erreur", "Fonctionnalité de suppression indisponible pour le moment.")

    # ----------------------------------------------------------------------
    # Code : Importer sa carte SD et activation des sous-menus
    # ----------------------------------------------------------------------
    def action_importer_carte_sd(self):
        filename = filedialog.askopenfilename(filetypes=[("Image Disque", "*.img")])
        if filename:
            self.chemin_carte_sd = filename
            self.carte_sd_importee = True
            messagebox.showinfo("Carte SD importée",
                                f"La carte SD {os.path.basename(filename)} a été chargée avec succès.")
            self.menu_code.entryconfigure("Éditeur (navigateur SD)", state="normal")
            self.menu_code.entryconfigure("Formatage", state="normal")
            self.menu_code.entryconfigure("Propriété", state="normal")

    def _mdir(self, chemin_image_relatif):
        """Appelle mdir sur l'image SD courante et retourne stdout brut, ou None si erreur."""
        if not MDIR.exists():
            return None
        try:
            result = subprocess.run(
                [str(MDIR), "-i", self.chemin_carte_sd, chemin_image_relatif],
                capture_output=True, text=True, timeout=15
            )
            return result.stdout
        except Exception:
            return None

    def action_editeur(self):
        """Navigateur RÉEL (lecture seule) de l'arborescence de la carte SD via mtools."""
        if not self.chemin_carte_sd or not os.path.exists(self.chemin_carte_sd):
            messagebox.showerror("Erreur", "Aucune carte SD importée.")
            return
        if not MDIR.exists():
            messagebox.showerror("mtools introuvable", f"mdir.exe introuvable :\n{MDIR}")
            return

        edit_win = tk.Toplevel(self.root)
        edit_win.title("Navigateur de la carte SD (lecture seule)")
        edit_win.geometry("700x500")
        if os.path.exists(ICON_PATH):
            try:
                edit_win.iconbitmap(ICON_PATH)
            except Exception:
                pass

        chemin_courant = tk.StringVar(value="::/")
        entries = []  # liste de (nom_affiche, est_dossier)

        frame_haut = ttk.Frame(edit_win)
        frame_haut.pack(fill="x", padx=5, pady=5)
        ttk.Label(frame_haut, textvariable=chemin_courant, font=("Courier", 10, "bold")).pack(side="left")

        listbox = tk.Listbox(edit_win, font=("Courier", 10))
        listbox.pack(fill="both", expand=True, padx=5, pady=5)

        def parser_ligne(line):
            # lignes mdir : "NOM     <DIR>     date  heure  [nom_long]"
            # ou "NOM     EXT    taille  date  heure  [nom_long]"
            parts = line.split()
            if not parts:
                return None
            est_dir = "<DIR>" in line
            nom_long = None
            if len(parts) >= 5 and not parts[-1].isdigit():
                # dernier champ = nom long si présent (contient souvent des minuscules/espaces)
                idx_date = None
                for i, p in enumerate(parts):
                    if "-" in p or "/" in p:
                        idx_date = i
                        break
                if idx_date is not None and idx_date + 2 < len(parts):
                    nom_long = " ".join(parts[idx_date + 2:])
            nom_court = parts[0] if not est_dir else parts[0]
            nom_affiche = nom_long if nom_long else nom_court
            if nom_affiche in (".", ".."):
                return None
            return nom_affiche, est_dir

        def lister(chemin):
            stdout = self._mdir(chemin)
            listbox.delete(0, "end")
            entries.clear()
            if stdout is None:
                listbox.insert("end", "[Erreur mtools -- voir console]")
                return
            for line in stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("Volume") or line.startswith("Directory") or "bytes free" in line or "files" in line.split(",")[0] if "," in line else False:
                    continue
                parsed = parser_ligne(line)
                if parsed:
                    nom, est_dir = parsed
                    entries.append((nom, est_dir))
                    listbox.insert("end", ("[DIR] " if est_dir else "      ") + nom)
            chemin_courant.set(chemin)

        def remonter():
            c = chemin_courant.get()
            if c in ("::/", "::"):
                return
            c = c.rstrip("/")
            parent = "/".join(c.split("/")[:-1])
            if not parent or parent == "::":
                parent = "::/"
            lister(parent)

        def ouvrir_selection(event=None):
            sel = listbox.curselection()
            if not sel:
                return
            nom, est_dir = entries[sel[0]]
            if not est_dir:
                messagebox.showinfo(
                    "Fichier",
                    f"{nom}\n\nNavigateur en lecture seule : l'édition de fichiers binaires "
                    "de jeu n'a pas de sens ici. Utilise lexianalyzer.py pour l'analyse."
                )
                return
            base = chemin_courant.get().rstrip("/")
            lister(f"{base}/{nom}")

        listbox.bind("<Double-Button-1>", ouvrir_selection)

        frame_boutons = ttk.Frame(edit_win)
        frame_boutons.pack(side="bottom", fill="x", padx=5, pady=5)
        ttk.Button(frame_boutons, text="⬆ Remonter", command=remonter).pack(side="left", padx=5)
        ttk.Button(frame_boutons, text="Rafraîchir", command=lambda: lister(chemin_courant.get())).pack(side="left", padx=5)
        ttk.Button(frame_boutons, text="Fermer", command=edit_win.destroy).pack(side="right", padx=5)

        lister("::/")

    def action_formatage(self):
        """Formatage RÉEL de la carte SD via mformat (mtools)."""
        if not self.chemin_carte_sd or not os.path.exists(self.chemin_carte_sd):
            messagebox.showerror("Erreur", "Aucune carte SD importée.")
            return
        if not MFORMAT.exists():
            messagebox.showerror("mtools introuvable", f"mformat.exe introuvable :\n{MFORMAT}")
            return

        reponse = messagebox.askyesno(
            "Formatage",
            "Êtes-vous sûr de vouloir formater la carte SD ?\nToutes les données seront perdues.",
            icon="warning"
        )
        if not reponse:
            return

        progress_win = tk.Toplevel(self.root)
        progress_win.title("Formatage en cours...")
        progress_win.geometry("400x100")
        progress_win.resizable(False, False)
        progress_win.grab_set()
        ttk.Label(progress_win, text="Formatage de la carte SD en cours (mformat)...").pack(pady=10)
        barre = ttk.Progressbar(progress_win, mode="indeterminate", length=350)
        barre.pack(pady=10)
        barre.start(10)

        def faire_format():
            try:
                result = subprocess.run(
                    [str(MFORMAT), "-i", self.chemin_carte_sd, "-F", "-T", str(os.path.getsize(self.chemin_carte_sd) // 512), "::"],
                    capture_output=True, text=True, timeout=120
                )
                ok = result.returncode == 0
                err = (result.stderr or result.stdout or "").strip()
            except Exception as e:
                ok = False
                err = str(e)

            def finir():
                barre.stop()
                progress_win.destroy()
                if ok:
                    messagebox.showinfo("Formatage terminé", "La carte SD a été formatée avec succès.")
                else:
                    messagebox.showerror("Échec du formatage (mformat)", err or "Erreur inconnue")
            self.root.after(0, finir)

        threading.Thread(target=faire_format, daemon=True).start()

    def action_propriete(self):
        """Propriétés RÉELLES de la carte SD (taille fichier + espace libre via mdir)."""
        if not self.chemin_carte_sd or not os.path.exists(self.chemin_carte_sd):
            messagebox.showerror("Erreur", "Aucune carte SD importée.")
            return

        nom_fichier = os.path.basename(self.chemin_carte_sd)
        taille = os.path.getsize(self.chemin_carte_sd)
        taille_mo = taille / (1024 * 1024)
        date_modif = os.path.getmtime(self.chemin_carte_sd)
        date_str = datetime.datetime.fromtimestamp(date_modif).strftime("%d/%m/%Y %H:%M:%S")

        espace_libre = "Inconnu (mtools introuvable ou erreur)"
        stdout = self._mdir("::/")
        if stdout:
            for line in stdout.splitlines():
                if "bytes free" in line:
                    espace_libre = line.strip()
                    break

        console_info = {
            "Modèle": "Lexibook JG7420AV",
            "CPU": "Sunplus S+core (Score7)",
            "Fichier image": nom_fichier,
            "Taille du fichier": f"{taille_mo:.2f} Mo",
            "Espace libre (réel)": espace_libre,
            "Dernière modification": date_str,
        }

        prop_win = tk.Toplevel(self.root)
        prop_win.title("Propriétés de la console")
        prop_win.geometry("450x300")
        prop_win.resizable(False, False)
        if os.path.exists(ICON_PATH):
            try:
                prop_win.iconbitmap(ICON_PATH)
            except Exception:
                pass

        ttk.Label(prop_win, text="Propriétés de la carte SD", font=("Helvetica", 12, "bold")).pack(pady=10)

        cadre = ttk.Frame(prop_win)
        cadre.pack(fill="both", expand=True, padx=20, pady=10)

        row = 0
        for cle, valeur in console_info.items():
            ttk.Label(cadre, text=cle + " :", font=("Helvetica", 10, "bold")).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Label(cadre, text=valeur, font=("Helvetica", 10)).grid(row=row, column=1, sticky="w", padx=10)
            row += 1

        ttk.Button(prop_win, text="Fermer", command=prop_win.destroy).pack(pady=10)

    # ----------------------------------------------------------------------
    # Fenêtre À propos
    # ----------------------------------------------------------------------
    def fenetre_a_propos(self):
        win = tk.Toplevel(self.root)
        win.title("A propos de LexiARC")
        win.geometry("480x440")
        if os.path.exists(ICON_PATH):
            try:
                win.iconbitmap(ICON_PATH)
            except Exception:
                pass
        win.grab_set()

        if os.path.exists(LOGO_PATH):
            try:
                self.logo_image = tk.PhotoImage(file=LOGO_PATH)
                lbl_img = tk.Label(win, image=self.logo_image)
                lbl_img.pack(pady=15)
            except Exception:
                tk.Label(win, text="[ Logo Introuvable ]", font=("Helvetica", 14, "bold"), fg="red").pack(pady=15)
        else:
            tk.Label(win, text="[ Fichier logo.png Manquant ]", font=("Helvetica", 14, "bold"), fg="red").pack(pady=15)

        tk.Label(win, text="Nom du logiciel : LexiARC", font=("Helvetica", 12, "bold")).pack(pady=2)
        tk.Label(win, text=f"Version : {VERSION}", font=("Helvetica", 10)).pack(pady=2)
        tk.Label(win, text=f"Auteur : {AUTEUR}", font=("Helvetica", 10)).pack(pady=2)
        tk.Label(win, text=f"Licence : {LICENCE}", font=("Helvetica", 10, "italic")).pack(pady=2)

        declaration_int = (
            "\nDéclaration importante :\n"
            "AUCUN fichier original de la console n'a été modifié ni altéré.\n"
            "Ce logiciel interagit uniquement avec des images mémoire fournies par "
            "l'utilisateur, à des fins de préservation.\n\n"
            "emu293 (moteur d'émulation) est un projet tiers, distribué avec ce package "
            "sous sa propre licence — voir bin/emu293/LICENSE."
        )
        tk.Label(win, text=declaration_int, font=("Helvetica", 9), fg="darkred", justify="center", wraplength=420).pack(pady=15)

        ttk.Button(win, text="Fermer", command=win.destroy).pack(pady=10)


# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("Loading LexiARC GUI...")
    root = tk.Tk()
    app = LexiARCApp(root)
    print("LexiARC GUI loaded. Entering main loop.")
    root.mainloop()
    print("LexiARC GUI closed.")
