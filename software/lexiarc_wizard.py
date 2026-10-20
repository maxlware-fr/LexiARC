# -*- coding: utf-8 -*-
"""
lexiarc_wizard.py -- assistant "Creer une nouvelle emulation" en 4 etapes.

  1. Carte SD       : copier la carte originale (dossier / lecteur)  OU  importer une .img deja faite
  2. SD virtuelle   : creation de l'image FAT32 (ignoree si .img importee)
  3. Profil         : titre, processeur, RAM
  4. Dependances    : verification / telechargement d'emu293 + DLL, puis generation du .larc
"""
import os
import queue
import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import lexiarc_core as core

TITRES = [
    "Carte SD d'origine",
    "Création de la carte SD virtuelle",
    "Profil de l'émulation",
    "Dépendances et fichier .larc",
]

CPU_CHOICES = ["Sunplus S+core (Score7)"]
RAM_CHOICES = ["8MB", "16MB", "32MB", "64MB"]


def _fmt_size(n):
    return f"{n / 1024 ** 3:.2f} Go" if n >= 1024 ** 3 else f"{n / 1024 ** 2:.1f} Mo"


class EmulationWizard:
    def __init__(self, parent, icon_path=None, on_finished=None, defaults=None):
        """on_finished(larc_path: Path, lancer: bool) est appele a la fin."""
        self.parent = parent
        self.on_finished = on_finished
        defaults = defaults or {}

        self.win = tk.Toplevel(parent)
        self.win.title("Créer une nouvelle émulation")
        self.win.geometry("640x470")
        self.win.resizable(False, False)
        self.win.transient(parent)
        if icon_path and os.path.exists(icon_path):
            try:
                self.win.iconbitmap(icon_path)
            except Exception:
                pass
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self._annuler)

        # --- etat ---
        self.step = 0
        self.mode = tk.StringVar(value="copie")          # "copie" | "import"
        self.var_src = tk.StringVar()                    # dossier / lecteur de la carte originale
        self.var_img_import = tk.StringVar()             # .img existante
        self.var_img_dest = tk.StringVar(value=str(core.EMULATIONS_DIR / "sd_card.img"))
        self.var_size = tk.StringVar(value="4")
        self.var_nom = tk.StringVar(value=defaults.get("nom", "Lexibook JG7420AV"))
        self.var_auteur = tk.StringVar(value=defaults.get("auteur", ""))
        self.var_cpu = tk.StringVar(value=CPU_CHOICES[0])
        self.var_ram = tk.StringVar(value="32MB")

        self.src_info = None          # resultat de scan_source
        self.src_lead = None          # Path de windows/Lead.sys dans la source
        self.sd_ready = False         # une carte SD exploitable existe
        self.sd_key = None            # (mode, source) pour lequel sd_ready est vrai
        self.sd_img = None            # Path de l'image finale
        self.lead_path = None         # Path de Lead.sys a referencer dans le .larc
        self.busy = False
        self.cancel_event = threading.Event()
        self.q = queue.Queue()

        # --- squelette ---
        self.lbl_etape = ttk.Label(self.win, font=("Helvetica", 12, "bold"))
        self.lbl_etape.pack(anchor="w", padx=15, pady=(12, 2))
        self.barre_etapes = ttk.Progressbar(self.win, maximum=4, length=610)
        self.barre_etapes.pack(padx=15, pady=(0, 8))

        self.zone = ttk.Frame(self.win)
        self.zone.pack(fill="both", expand=True, padx=15)

        bas = ttk.Frame(self.win)
        bas.pack(fill="x", padx=15, pady=12)
        self.btn_annuler = ttk.Button(bas, text="Annuler", command=self._annuler)
        self.btn_annuler.pack(side="left")
        self.btn_suivant = ttk.Button(bas, text="Suivant ▶", command=self._suivant)
        self.btn_suivant.pack(side="right")
        self.btn_prec = ttk.Button(bas, text="◀ Précédent", command=self._precedent)
        self.btn_prec.pack(side="right", padx=6)

        self._afficher()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _vider(self):
        for w in self.zone.winfo_children():
            w.destroy()

    def _afficher(self):
        self._vider()
        self.lbl_etape.config(text=f"Étape {self.step + 1} sur 4 — {TITRES[self.step]}")
        self.barre_etapes["value"] = self.step + 1
        self.btn_prec.config(state="normal" if self.step > 0 and not self.busy else "disabled")
        self.btn_suivant.config(text="Terminer ✔" if self.step == 3 else "Suivant ▶", state="normal")
        [self._page1, self._page2, self._page3, self._page4][self.step]()

    def _precedent(self):
        if self.busy or self.step == 0:
            return
        self.step -= 1
        self._afficher()

    def _suivant(self):
        if self.busy:
            return
        valider = [self._valider1, self._valider2, self._valider3, self._terminer][self.step]
        if valider() and self.step < 3:
            self.step += 1
            self._afficher()

    def _annuler(self):
        if self.busy:
            if not messagebox.askyesno("Opération en cours", "Une opération est en cours. L'annuler et fermer ?",
                                       parent=self.win):
                return
            self.cancel_event.set()
        self.win.destroy()

    # ------------------------------------------------------------------
    # Etape 1 : carte SD
    # ------------------------------------------------------------------
    def _page1(self):
        f = self.zone
        ttk.Radiobutton(f, text="Copier la carte SD originale de la console (recommandé)",
                        variable=self.mode, value="copie", command=self._maj_page1).pack(anchor="w", pady=(10, 2))
        ttk.Label(f, text="Dossier ou lecteur contenant windows\\Lead.sys  (ex. E:\\ ou le dossier core\\) :",
                  foreground="gray").pack(anchor="w", padx=24)
        r1 = ttk.Frame(f)
        r1.pack(anchor="w", padx=24, pady=4)
        self.ent_src = ttk.Entry(r1, textvariable=self.var_src, width=58)
        self.ent_src.pack(side="left")
        self.btn_src = ttk.Button(r1, text="Parcourir…", command=self._choisir_src)
        self.btn_src.pack(side="left", padx=5)

        ttk.Radiobutton(f, text="Importer une carte SD virtuelle déjà faite (.img)",
                        variable=self.mode, value="import", command=self._maj_page1).pack(anchor="w", pady=(18, 2))
        r2 = ttk.Frame(f)
        r2.pack(anchor="w", padx=24, pady=4)
        self.ent_img = ttk.Entry(r2, textvariable=self.var_img_import, width=58)
        self.ent_img.pack(side="left")
        self.btn_img = ttk.Button(r2, text="Parcourir…", command=self._choisir_img)
        self.btn_img.pack(side="left", padx=5)

        self.lbl_info1 = ttk.Label(f, text="", wraplength=590, justify="left")
        self.lbl_info1.pack(anchor="w", pady=14)
        ttk.Label(f, text="Aucun fichier de la carte d'origine n'est modifié : elle est seulement lue.",
                  foreground="gray").pack(side="bottom", anchor="w")
        self._maj_page1()

    def _maj_page1(self):
        copie = self.mode.get() == "copie"
        for w in (self.ent_src, self.btn_src):
            w.config(state="normal" if copie else "disabled")
        for w in (self.ent_img, self.btn_img):
            w.config(state="disabled" if copie else "normal")

    def _choisir_src(self):
        d = filedialog.askdirectory(parent=self.win, title="Carte SD d'origine (dossier ou lecteur)")
        if d:
            self.var_src.set(d)
            self._analyser_src()

    def _choisir_img(self):
        f = filedialog.askopenfilename(parent=self.win, title="Carte SD virtuelle",
                                       filetypes=[("Image disque", "*.img"), ("Tous les fichiers", "*.*")])
        if f:
            self.var_img_import.set(f)

    def _analyser_src(self):
        ok, msg, lead, info = core.validate_source_folder(self.var_src.get())
        if not ok:
            self.lbl_info1.config(text="✘ " + msg, foreground="red")
            return False
        self.src_info, self.src_lead = info, lead
        txt = (f"✔ Carte d'origine reconnue : {info['files']} fichiers, {info['dirs']} dossiers, "
               f"{_fmt_size(info['bytes'])}.")
        if info["non_ascii"]:
            txt += (f"\n⚠ {info['non_ascii']} noms contiennent des caractères non-ASCII (ex. chinois) : "
                    "ils seront vérifiés après la copie.")
        self.lbl_info1.config(text=txt, foreground="darkgreen")
        self.var_size.set(str(core.suggest_size_gb(info["bytes"])))
        return True

    def _valider1(self):
        if not core.ensure_mtools():
            messagebox.showerror("mtools manquant",
                                 f"mtools est introuvable dans :\n{core.MTOOLS_DIR}\n\n"
                                 "Place mtools.exe dans bin\\mtools\\.", parent=self.win)
            return False
        if self.mode.get() == "copie":
            if not self.var_src.get():
                messagebox.showerror("Carte SD", "Choisis le dossier ou le lecteur de la carte d'origine.",
                                     parent=self.win)
                return False
            if not self._analyser_src():
                return False
            key = ("copie", self.var_src.get())
        else:
            p = self.var_img_import.get()
            if not p:
                messagebox.showerror("Carte SD", "Choisis le fichier .img à importer.", parent=self.win)
                return False
            ok, msg = core.validate_sd_image(p)
            if not ok:
                self.lbl_info1.config(text="✘ " + msg, foreground="red")
                return False
            key = ("import", p)
        if self.sd_key != key:      # la source a change : il faut refaire la carte
            self.sd_ready = False
            self.sd_key = None
        return True

    # ------------------------------------------------------------------
    # Etape 2 : creation de la carte SD virtuelle
    # ------------------------------------------------------------------
    def _page2(self):
        f = self.zone
        if self.mode.get() == "import":
            self.sd_img = Path(self.var_img_import.get())
            self.sd_ready = True
            self.sd_key = ("import", self.var_img_import.get())
            ttk.Label(f, text="✔ Tu as importé une carte SD déjà prête.\n\n"
                              f"{self.sd_img}\n\nIl n'y a rien à créer : passe à l'étape suivante.",
                      justify="left", foreground="darkgreen").pack(anchor="w", pady=30)
            return

        ttk.Label(f, text="La carte d'origine va être copiée dans une image disque FAT32 (.img),\n"
                          "que l'émulateur utilisera comme carte SD.", justify="left").pack(anchor="w", pady=(8, 10))
        g = ttk.Frame(f)
        g.pack(anchor="w")
        ttk.Label(g, text="Fichier image :").grid(row=0, column=0, sticky="w", pady=4)
        self.ent_dest = ttk.Entry(g, textvariable=self.var_img_dest, width=50)
        self.ent_dest.grid(row=0, column=1, padx=6)
        self.btn_dest = ttk.Button(g, text="…", width=3, command=self._choisir_dest)
        self.btn_dest.grid(row=0, column=2)
        ttk.Label(g, text="Taille (Go) :").grid(row=1, column=0, sticky="w", pady=4)
        self.box_size = ttk.Combobox(g, textvariable=self.var_size, width=8, state="readonly",
                                     values=[str(s) for s in core.SIZES_GB])
        self.box_size.grid(row=1, column=1, sticky="w", padx=6)
        need = self.src_info["bytes"] if self.src_info else 0
        ttk.Label(f, text=f"Contenu à copier : {_fmt_size(need)}. Sous Windows, le fichier image occupera "
                          "toute la taille choisie sur le disque.", foreground="gray",
                  wraplength=590, justify="left").pack(anchor="w", pady=(6, 8))

        self.btn_creer = ttk.Button(f, text="Créer la carte SD virtuelle", command=self._lancer_creation)
        self.btn_creer.pack(anchor="w", pady=4)
        self.pb = ttk.Progressbar(f, mode="determinate", length=600)
        self.pb.pack(anchor="w", pady=(10, 2))
        self.lbl_prog = ttk.Label(f, text="", wraplength=600, justify="left")
        self.lbl_prog.pack(anchor="w")
        self.lst_err = tk.Listbox(f, height=4, font=("Courier", 9))
        self.btn_annul_copie = ttk.Button(f, text="Annuler la copie", command=self.cancel_event.set)

        if self.sd_ready and self.sd_key == ("copie", self.var_src.get()):
            self.pb["value"] = 100
            self.lbl_prog.config(text=f"✔ Carte SD déjà créée : {self.sd_img}", foreground="darkgreen")
            self.btn_creer.config(state="disabled")
        else:
            self.btn_suivant.config(state="disabled")

    def _choisir_dest(self):
        f = filedialog.asksaveasfilename(parent=self.win, defaultextension=".img", initialfile="sd_card.img",
                                         filetypes=[("Image disque", "*.img")])
        if f:
            self.var_img_dest.set(f)

    def _lancer_creation(self):
        dest = Path(self.var_img_dest.get())
        if dest.exists() and not messagebox.askyesno(
                "Fichier existant", f"{dest}\nexiste déjà et sera ÉCRASÉ. Continuer ?", parent=self.win):
            return
        self.cancel_event.clear()
        self.busy = True
        self.btn_creer.config(state="disabled")
        self.btn_prec.config(state="disabled")
        self.btn_suivant.config(state="disabled")
        self.btn_annul_copie.pack(anchor="w", pady=4)
        self.pb.config(value=0)
        self.lbl_prog.config(text="Formatage FAT32…", foreground="black")
        src, size = self.var_src.get(), int(self.var_size.get())
        lead_src = self.src_lead

        def travail():
            try:
                res = core.create_virtual_sd(
                    src, dest, size,
                    progress_cb=lambda d, t, s: self.q.put(("prog", d, t, s)),
                    cancel_event=self.cancel_event)
                if res["cancelled"]:
                    dest.unlink(missing_ok=True)
                    self.q.put(("cancel",))
                    return
                lead_dst = dest.parent / "Lead.sys"
                shutil.copy2(lead_src, lead_dst)
                res["bad_names"] = core.check_unicode_names(src, dest)
                self.q.put(("done", res, dest, lead_dst))
            except Exception as e:
                self.q.put(("err", str(e)))

        threading.Thread(target=travail, daemon=True).start()
        self.win.after(100, self._poll)

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "prog":
                    _, d, t, s = msg
                    self.pb.config(value=100 * d / max(t, 1))
                    self.lbl_prog.config(text=f"{d} / {t} fichiers — {s}")
                elif kind == "done":
                    self._fin_creation(*msg[1:])
                    return
                elif kind == "cancel":
                    self._fin_busy()
                    self.lbl_prog.config(text="Copie annulée, image supprimée.", foreground="red")
                    self.btn_creer.config(state="normal")
                    self.btn_annul_copie.pack_forget()
                    return
                elif kind == "err":
                    self._fin_busy()
                    self.lbl_prog.config(text="✘ " + msg[1], foreground="red")
                    self.btn_creer.config(state="normal")
                    self.btn_annul_copie.pack_forget()
                    return
        except queue.Empty:
            pass
        if self.busy and self.win.winfo_exists():
            self.win.after(100, self._poll)

    def _fin_busy(self):
        self.busy = False
        self.btn_prec.config(state="normal")

    def _fin_creation(self, res, dest, lead_dst):
        self._fin_busy()
        self.btn_annul_copie.pack_forget()
        self.sd_img, self.lead_path = dest, lead_dst
        self.sd_ready = True
        self.sd_key = ("copie", self.var_src.get())
        self.pb.config(value=100)
        txt = f"✔ Carte SD créée : {res['copied']} / {res['total']} fichiers copiés."
        couleur = "darkgreen"
        if res["errors"]:
            couleur = "darkorange"
            txt += f"\n⚠ {len(res['errors'])} erreur(s) (le reste est utilisable)."
            self.lst_err.pack(fill="x", pady=4)
            for chemin, m in res["errors"][:50]:
                self.lst_err.insert("end", f"{chemin} -> {m[:60]}")
        if res.get("bad_names"):
            couleur = "darkorange"
            txt += ("\n⚠ Noms non-ASCII altérés par mtools : " + ", ".join(res["bad_names"][:3]) +
                    "\n   Certaines applis de la console pourraient ne pas retrouver ces dossiers.")
        self.lbl_prog.config(text=txt, foreground=couleur)
        self.btn_suivant.config(state="normal")

    def _valider2(self):
        if not self.sd_ready:
            messagebox.showinfo("Carte SD", "Crée d'abord la carte SD virtuelle.", parent=self.win)
            return False
        return True

    # ------------------------------------------------------------------
    # Etape 3 : profil
    # ------------------------------------------------------------------
    def _page3(self):
        f = self.zone
        g = ttk.Frame(f)
        g.pack(anchor="w", pady=14)
        ttk.Label(g, text="Titre de l'émulation :").grid(row=0, column=0, sticky="w", pady=7)
        ttk.Entry(g, textvariable=self.var_nom, width=36).grid(row=0, column=1, padx=10)
        ttk.Label(g, text="Auteur du profil :").grid(row=1, column=0, sticky="w", pady=7)
        ttk.Entry(g, textvariable=self.var_auteur, width=36).grid(row=1, column=1, padx=10)
        ttk.Label(g, text="Processeur utilisé :").grid(row=2, column=0, sticky="w", pady=7)
        ttk.Combobox(g, textvariable=self.var_cpu, values=CPU_CHOICES, state="readonly", width=33).grid(
            row=2, column=1, padx=10)
        ttk.Label(g, text="RAM :").grid(row=3, column=0, sticky="w", pady=7)
        ttk.Combobox(g, textvariable=self.var_ram, values=RAM_CHOICES, state="readonly", width=33).grid(
            row=3, column=1, padx=10)
        ttk.Label(
            f, foreground="gray", wraplength=590, justify="left",
            text="ℹ Ces informations sont enregistrées dans le .larc, mais emu293 n'a pas d'option de "
                 "processeur ni de RAM : il émule uniquement le SPG293 (S+core 7) avec sa mémoire fixe. "
                 "Elles servent donc d'identification du profil, sans effet sur l'émulation.").pack(anchor="w", pady=10)

    def _valider3(self):
        if not self.var_nom.get().strip():
            messagebox.showerror("Titre", "Donne un titre à l'émulation.", parent=self.win)
            return False
        return True

    # ------------------------------------------------------------------
    # Etape 4 : dependances + .larc
    # ------------------------------------------------------------------
    def _page4(self):
        f = self.zone
        ttk.Label(f, text="Composants nécessaires au lancement :").pack(anchor="w", pady=(8, 4))
        self.cadre_deps = ttk.Frame(f)
        self.cadre_deps.pack(fill="x")
        self.pb_dl = ttk.Progressbar(f, mode="determinate", length=600)
        self.pb_dl.pack(anchor="w", pady=(10, 2))
        self.lbl_dl = ttk.Label(f, text="", wraplength=600, justify="left")
        self.lbl_dl.pack(anchor="w")
        ttk.Label(f, foreground="gray", wraplength=600, justify="left",
                  text="À la fin, un fichier .larc est créé : il suffit de l'ouvrir via Fichier ▸ Lancer une "
                       "émulation pour démarrer.").pack(side="bottom", anchor="w")
        self._rafraichir_deps()

    def _rafraichir_deps(self):
        for w in self.cadre_deps.winfo_children():
            w.destroy()
        self.deps = core.check_dependencies()
        for i, d in enumerate(self.deps):
            ok = d["ok"]
            ttk.Label(self.cadre_deps, text=("✔ " if ok else "✘ ") + d["nom"],
                      foreground="darkgreen" if ok else "red").grid(row=i * 2, column=0, sticky="w", pady=(6, 0))
            if not ok:
                ttk.Label(self.cadre_deps, text="Manquant : " + ", ".join(d["manquants"]), foreground="gray",
                          wraplength=420, justify="left").grid(row=i * 2 + 1, column=0, sticky="w", padx=18)
                if d["id"] == "emu293":
                    bf = ttk.Frame(self.cadre_deps)
                    bf.grid(row=i * 2, column=1, rowspan=2, padx=20)
                    self.btn_dl = ttk.Button(bf, text="Télécharger depuis GitHub",
                                             command=lambda: self._telecharger(d["id"]))
                    self.btn_dl.pack(fill="x")
                    ttk.Button(bf, text="Choisir manuellement…", command=self._import_manuel).pack(fill="x", pady=3)
        ttk.Button(self.cadre_deps, text="Revérifier", command=self._rafraichir_deps).grid(
            row=len(self.deps) * 2, column=0, sticky="w", pady=8)

    def _telecharger(self, dep_id):
        self.busy = True
        self.btn_dl.config(state="disabled")
        self.btn_suivant.config(state="disabled")
        self.btn_prec.config(state="disabled")
        self.lbl_dl.config(text="Téléchargement…", foreground="black")

        def travail():
            try:
                core.download_dependency(dep_id, lambda d, t: self.q.put(("dl", d, t)))
                self.q.put(("dl_ok",))
            except Exception as e:
                self.q.put(("dl_err", str(e)))

        threading.Thread(target=travail, daemon=True).start()
        self.win.after(100, self._poll_dl)

    def _poll_dl(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m[0] == "dl":
                    self.pb_dl.config(value=100 * m[1] / m[2] if m[2] else 0)
                    self.lbl_dl.config(text=f"Téléchargement… {_fmt_size(m[1])}")
                elif m[0] in ("dl_ok", "dl_err"):
                    self.busy = False
                    self.btn_suivant.config(state="normal")
                    self.btn_prec.config(state="normal")
                    self.pb_dl.config(value=0)
                    if m[0] == "dl_ok":
                        self.lbl_dl.config(text="✔ Téléchargement terminé.", foreground="darkgreen")
                    else:
                        self.lbl_dl.config(text="✘ " + m[1], foreground="red")
                    self._rafraichir_deps()
                    return
        except queue.Empty:
            pass
        if self.busy and self.win.winfo_exists():
            self.win.after(100, self._poll_dl)

    def _import_manuel(self):
        d = filedialog.askdirectory(parent=self.win, title="Dossier contenant emu293.exe et ses DLL")
        if not d:
            return
        try:
            copies = core.import_emu293_from_folder(d)
            self.lbl_dl.config(text=f"✔ {len(copies)} fichier(s) copié(s) dans bin\\.", foreground="darkgreen")
        except core.CoreError as e:
            self.lbl_dl.config(text="✘ " + str(e), foreground="red")
        self._rafraichir_deps()

    def _terminer(self):
        manquants = [d for d in core.check_dependencies() if not d["ok"]]
        if manquants and not messagebox.askyesno(
                "Dépendances manquantes",
                "Il manque encore : " + ", ".join(d["nom"] for d in manquants) +
                "\n\nTu pourras créer le .larc mais pas lancer l'émulation tant que ce n'est pas réglé.\n"
                "Créer le .larc quand même ?", parent=self.win):
            return False

        nom = self.var_nom.get().strip()
        slug = core.slugify(nom)
        # Lead.sys : celui copie a cote de l'image, sinon extrait de l'image importee
        if not self.lead_path or not Path(self.lead_path).exists():
            dest_dir = core.EMULATIONS_DIR / slug
            lead = core.extract_lead_sys(self.sd_img, dest_dir)
            if lead is None and core.BUNDLED_LEAD_SYS.exists():
                lead = core.BUNDLED_LEAD_SYS
            if lead is None:
                messagebox.showerror("Lead.sys", "Impossible de trouver Lead.sys dans la carte SD importée.",
                                     parent=self.win)
                return False
            self.lead_path = lead

        defaut_dir = Path(self.sd_img).parent if self.mode.get() == "copie" else core.EMULATIONS_DIR / slug
        defaut_dir.mkdir(parents=True, exist_ok=True)
        larc = filedialog.asksaveasfilename(
            parent=self.win, title="Enregistrer le fichier .larc", defaultextension=".larc",
            initialdir=str(defaut_dir), initialfile=f"{slug}.larc",
            filetypes=[("Configuration LexiARC", "*.larc")])
        if not larc:
            return False
        try:
            core.save_larc(larc, nom, self.var_cpu.get(), self.var_ram.get(), self.var_auteur.get(),
                           self.sd_img, self.lead_path,
                           "copiee" if self.mode.get() == "copie" else "importee")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'écrire le .larc :\n{e}", parent=self.win)
            return False

        lancer = messagebox.askyesno("Émulation créée", f"Fichier créé :\n{larc}\n\nLancer l'émulation maintenant ?",
                                     parent=self.win)
        self.win.destroy()
        if self.on_finished:
            self.on_finished(Path(larc), lancer)
        return True
