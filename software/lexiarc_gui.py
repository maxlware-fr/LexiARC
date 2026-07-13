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

# --- CONFIGURATION & CONSTANTES ---
VERSION = "0.2.0-BETA"
AUTEUR = "Maxlware"
LICENCE = "Apache-2.0 License"
DOCS_URL = "https://github.com/maxlware-fr/LexiARC/blob/main/docs/HOME.md"

ICON_PATH = "logo.ico"      # Icône de la barre de titre
LOGO_PATH = "logo.png"      # Logo pour l'écran d'accueil & splash screen

# --- Arborescence attendue du package (tout est relatif à ce script) ---
#   LexiARC/
#     lexiarc_gui.py        <- ce fichier
#     lexianalyzer.py
#     core/windows/Lead.sys <- BIOS console (bundlé avec le package)
#     bin/
#       emu293.exe + DLLs   <- exécutable emu293 compilé (bundlé avec le package)
#       mtools/
#         mcopy.exe, mdir.exe, mformat.exe, mmd.exe
BASE_DIR = Path(__file__).resolve().parent
BIN_DIR = BASE_DIR / "bin"
EMU293_EXE = BIN_DIR / "emu293.exe"
LEAD_SYS_PATH = BASE_DIR / "core" / "windows" / "Lead.sys"
MTOOLS_DIR = BIN_DIR / "mtools"
MCOPY = MTOOLS_DIR / "mcopy.exe"
MDIR = MTOOLS_DIR / "mdir.exe"
MFORMAT = MTOOLS_DIR / "mformat.exe"
MMD = MTOOLS_DIR / "mmd.exe"

# Fichiers essentiels à vérifier au démarrage
FICHIERS_ESSENTIELS = [
    str(LEAD_SYS_PATH),
    str(EMU293_EXE),
    str(BASE_DIR / "lexianalyzer.py"),
]


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
        """Vérifie la présence des composants nécessaires au démarrage"""
        manquants = [f for f in FICHIERS_ESSENTIELS if not os.path.exists(f)]
        if manquants:
            fichiers_str = "\n".join(f"- {f}" for f in manquants)
            messagebox.showwarning(
                "Fichiers manquants",
                f"Attention, certains composants essentiels sont introuvables :\n{fichiers_str}\n\n"
                "L'émulation ne pourra pas se lancer tant que Lead.sys et emu293.exe "
                "ne sont pas placés dans l'arborescence attendue (voir en-tête du script)."
            )
        if not MTOOLS_DIR.exists():
            messagebox.showwarning(
                "mtools manquant",
                f"Le dossier mtools est introuvable :\n{MTOOLS_DIR}\n\n"
                "Les fonctions Formatage / Implémentation / Éditeur de la carte SD "
                "ne fonctionneront pas tant que mcopy/mdir/mformat n'y sont pas placés."
            )

    def creer_ecran_accueil(self):
        """Message par défaut affiché au lancement"""
        self.label_accueil = tk.Label(
            self.root,
            text="Cliquez sur File pour commencer l'émulation",
            font=("Helvetica", 14, "italic"),
            fg="gray"
        )
        self.label_accueil.pack(expand=True)

    # ----------------------------------------------------------------------
    # Barre de menus
    # ----------------------------------------------------------------------
    def creer_menu(self):
        menubar = tk.Menu(self.root)

        # --- Menu FILE ---
        menu_file = tk.Menu(menubar, tearoff=0)

        # Sous-menu Émulation
        menu_emu = tk.Menu(menu_file, tearoff=0)
        menu_emu.add_command(label="Créer une émulation", command=self.fenetre_creer_emulation)
        menu_emu.add_command(label="Importer une émulation", command=self.action_importer_emulation)
        menu_file.add_cascade(label="Émulation", menu=menu_emu)

        # Sous-menu Compilation
        menu_comp = tk.Menu(menu_file, tearoff=0)
        menu_comp.add_command(label="Compiler en .elf", command=lambda: self.fenetre_compilation("elf"))
        menu_comp.add_command(label="Compiler en .wxn", command=lambda: self.fenetre_compilation("wxn"))
        menu_file.add_cascade(label="Compilation", menu=menu_comp)

        menu_file.add_separator()
        menu_file.add_command(label="Quitter", command=self.root.quit)
        menubar.add_cascade(label="File", menu=menu_file)

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

    def action_importer_emulation(self):
        filename = filedialog.askopenfilename(filetypes=[("Configuration LexiARC", "*.larc")])
        if not filename:
            return
        try:
            with open(filename, "r", encoding="utf-8") as f:
                config = json.load(f)
            sd_path = config.get("image_sd_path", "")
            if not os.path.exists(sd_path):
                messagebox.showerror("Erreur Import", f"L'image SD spécifiée est introuvable :\n{sd_path}")
                return
            self.ouvrir_ecran_emulation(config)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de lire le fichier de configuration : {e}")

    # ----------------------------------------------------------------------
    # Fenêtre : créer une émulation
    # ----------------------------------------------------------------------
    def fenetre_creer_emulation(self):
        win = tk.Toplevel(self.root)
        win.title("Créer une configuration d'émulation")
        win.geometry("450x350")
        if os.path.exists(ICON_PATH):
            try:
                win.iconbitmap(ICON_PATH)
            except Exception:
                pass
        win.grab_set()

        var_nom = tk.StringVar(value="Lexibook JG7420AV")
        var_auteur = tk.StringVar(value=AUTEUR)
        var_cpu = tk.StringVar(value="Sunplus S+core (Score7)")
        var_ram = tk.StringVar(value="32MB")
        var_sd = tk.StringVar()

        ttk.Label(win, text="Nom de l'émulateur :").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ttk.Entry(win, textvariable=var_nom, width=30).grid(row=0, column=1, padx=10, pady=10)

        ttk.Label(win, text="Auteur du profil :").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        ttk.Entry(win, textvariable=var_auteur, width=30).grid(row=1, column=1, padx=10, pady=10)

        ttk.Label(win, text="Type de processeur :").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        box_cpu = ttk.Combobox(win, textvariable=var_cpu, values=["Sunplus S+core (Score7)", "Sunplus unSP", "MIPS"], width=27)
        box_cpu.grid(row=2, column=1, padx=10, pady=10)
        box_cpu.current(0)

        ttk.Label(win, text="Taille de la RAM :").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        box_ram = ttk.Combobox(win, textvariable=var_ram, values=["8MB", "16MB", "32MB", "64MB"], width=27)
        box_ram.grid(row=3, column=1, padx=10, pady=10)
        box_ram.current(2)

        ttk.Label(win, text="Image carte SD (.img) :").grid(row=4, column=0, padx=10, pady=10, sticky="w")
        btn_frame = ttk.Frame(win)
        btn_frame.grid(row=4, column=1, padx=10, pady=10, sticky="w")
        ttk.Entry(btn_frame, textvariable=var_sd, width=20).pack(side="left")

        def parcourir_sd():
            filename = filedialog.askopenfilename(filetypes=[("Image Disque", "*.img"), ("Tous les fichiers", "*.*")])
            if filename:
                var_sd.set(filename)
        ttk.Button(btn_frame, text="...", width=3, command=parcourir_sd).pack(side="left", padx=5)

        def lancer_directement():
            if not var_nom.get() or not var_sd.get():
                messagebox.showerror("Erreur", "Veuillez renseigner un nom et l'emplacement de l'image SD.")
                return
            config_data = {
                "nom_emulateur": var_nom.get(),
                "auteur_profil": var_auteur.get(),
                "architecture_cpu": var_cpu.get(),
                "taille_ram": var_ram.get(),
                "image_sd_path": var_sd.get()
            }
            win.destroy()
            self.ouvrir_ecran_emulation(config_data)

        def sauvegarder_larc():
            if not var_nom.get() or not var_sd.get():
                messagebox.showerror("Erreur", "Veuillez renseigner un nom et l'emplacement de l'image SD.")
                return
            config_data = {
                "nom_emulateur": var_nom.get(),
                "auteur_profil": var_auteur.get(),
                "architecture_cpu": var_cpu.get(),
                "taille_ram": var_ram.get(),
                "image_sd_path": var_sd.get()
            }
            dest_file = filedialog.asksaveasfilename(
                defaultextension=".larc",
                filetypes=[("Configuration LexiARC", "*.larc")],
                initialfile=f"{var_nom.get().replace(' ', '_').lower()}.larc"
            )
            if dest_file:
                with open(dest_file, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, indent=4, ensure_ascii=False)
                messagebox.showinfo("Export réussi", f"Fichier de configuration exporté avec succès :\n{dest_file}")
                win.destroy()

        frame_boutons = ttk.Frame(win)
        frame_boutons.grid(row=5, column=0, columnspan=2, pady=20)
        ttk.Button(frame_boutons, text="Lancer l'émulation", command=lancer_directement).pack(side="left", padx=5)
        ttk.Button(frame_boutons, text="Exporter en .larc", command=sauvegarder_larc).pack(side="left", padx=5)

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
        """Lance réellement emu293.exe avec Lead.sys (bundlé) et l'image SD choisie."""
        sd_path = config.get("image_sd_path", "")

        if not EMU293_EXE.exists():
            messagebox.showerror(
                "emu293 introuvable",
                f"L'exécutable emu293 est introuvable :\n{EMU293_EXE}\n\n"
                "Place emu293.exe (+ les DLL mingw/SDL2/wx nécessaires) dans le dossier 'bin/' du package."
            )
            fenetre.destroy()
            return
        if not LEAD_SYS_PATH.exists():
            messagebox.showerror(
                "Lead.sys introuvable",
                f"Le BIOS Lead.sys est introuvable :\n{LEAD_SYS_PATH}\n\n"
                "Place-le dans 'core/windows/Lead.sys' du package."
            )
            fenetre.destroy()
            return
        if not sd_path or not os.path.exists(sd_path):
            messagebox.showerror("Image SD introuvable", f"Image SD introuvable :\n{sd_path}")
            fenetre.destroy()
            return

        try:
            self.emu_process = subprocess.Popen(
                [str(EMU293_EXE), str(LEAD_SYS_PATH), str(sd_path)],
                cwd=str(EMU293_EXE.parent),
            )
        except Exception as e:
            messagebox.showerror("Erreur de lancement", f"Impossible de lancer emu293 :\n{e}")
            fenetre.destroy()
            return

        for w in fenetre.winfo_children():
            w.destroy()

        info_text = (
            f"Système : {config.get('nom_emulateur', 'Inconnu')}\n"
            f"CPU : {config.get('architecture_cpu', 'N/A')} | RAM : {config.get('taille_ram', 'N/A')}\n"
            f"SD : {os.path.basename(sd_path)}\n\n"
            f"emu293 lancé (PID {self.emu_process.pid}).\n"
            "La fenêtre de jeu s'ouvre séparément (SDL/wx).\n"
            "Ferme-la normalement, ou utilise le bouton ci-dessous."
        )
        tk.Label(fenetre, text=info_text, fg="lime", bg="black",
                 font=("Courier", 12), justify="left").pack(expand=True)

        def arreter():
            if self.emu_process and self.emu_process.poll() is None:
                self.emu_process.terminate()
            fenetre.destroy()

        ttk.Button(fenetre, text="Arrêter l'émulation", command=arreter).pack(pady=10)
        fenetre.protocol("WM_DELETE_WINDOW", arreter)

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
        win = tk.Toplevel(self.root)
        win.title("Créer une implémentation")
        win.geometry("450x250")
        win.resizable(False, False)
        if os.path.exists(ICON_PATH):
            try:
                win.iconbitmap(ICON_PATH)
            except Exception:
                pass
        win.grab_set()

        ttk.Label(win, text="Type de jeu :").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        var_type = tk.StringVar(value="wxn")
        frame_type = ttk.Frame(win)
        frame_type.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        ttk.Radiobutton(frame_type, text="ELF (.elf)", variable=var_type, value="elf").pack(side="left")
        ttk.Radiobutton(frame_type, text="WXN (.wxn)", variable=var_type, value="wxn").pack(side="left", padx=10)

        ttk.Label(win, text="Fichier du jeu :").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        var_fichier = tk.StringVar()
        frame_fichier = ttk.Frame(win)
        frame_fichier.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        ttk.Entry(frame_fichier, textvariable=var_fichier, width=25).pack(side="left")

        def parcourir_fichier():
            ft = [("Fichier ELF", "*.elf")] if var_type.get() == "elf" else [("Fichier WXN", "*.wxn")]
            f = filedialog.askopenfilename(filetypes=ft + [("Tous les fichiers", "*.*")])
            if f:
                var_fichier.set(f)
        ttk.Button(frame_fichier, text="...", width=3, command=parcourir_fichier).pack(side="left", padx=5)

        ttk.Label(win, text="Carte SD (.img) :").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        var_sd = tk.StringVar(value=self.chemin_carte_sd or "")
        frame_sd = ttk.Frame(win)
        frame_sd.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        ttk.Entry(frame_sd, textvariable=var_sd, width=25).pack(side="left")
        ttk.Button(frame_sd, text="...", width=3,
                   command=lambda: var_sd.set(filedialog.askopenfilename(filetypes=[("Image SD", "*.img")]) or var_sd.get())
                   ).pack(side="left", padx=5)

        def commencer_implementation():
            if not var_fichier.get() or not var_sd.get():
                messagebox.showerror("Erreur", "Veuillez sélectionner le fichier du jeu et la carte SD.")
                return
            win.destroy()
            self._implementer_jeu_reel(var_sd.get(), var_fichier.get())

        ttk.Button(win, text="Commencer", command=commencer_implementation).grid(row=3, column=0, columnspan=2, pady=20)

    def _implementer_jeu_reel(self, sd_path, fichier):
        if not MCOPY.exists():
            messagebox.showerror("mtools introuvable", f"mcopy.exe introuvable :\n{MCOPY}")
            return

        dest_rel = simpledialog.askstring(
            "Destination sur la carte",
            "Chemin de destination dans l'image (ex: ::/Fun/Game Player/monjeu.wxn) :",
            initialvalue=f"::/Fun/Game Player/{os.path.basename(fichier)}"
        )
        if not dest_rel:
            return

        progress_win = tk.Toplevel(self.root)
        progress_win.title("Implémentation en cours...")
        progress_win.geometry("400x100")
        progress_win.resizable(False, False)
        progress_win.grab_set()
        ttk.Label(progress_win, text=f"Copie de {os.path.basename(fichier)} sur la carte SD...").pack(pady=10)
        barre = ttk.Progressbar(progress_win, mode="indeterminate", length=350)
        barre.pack(pady=10)
        barre.start(10)

        def faire_copie():
            try:
                result = subprocess.run(
                    [str(MCOPY), "-i", sd_path, fichier, dest_rel],
                    capture_output=True, text=True, timeout=60
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
                    messagebox.showinfo("Implémentation terminée",
                                         f"{os.path.basename(fichier)} copié avec succès sur la carte SD.")
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
                    [str(MFORMAT), "-i", self.chemin_carte_sd, "::"],
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
