import os
import sys
import json
import secrets
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog, ttk

# Nécessite Pillow : pip install Pillow
from PIL import Image, ImageTk

# --- CONFIGURATION & CONSTANTES ---
VERSION = "0.1.0-BETA"
AUTEUR = "Maxlware"
LICENCE = "Apache-2.0 License"
DOCS_URL = "https://github.com/maxlware-fr/LexiARC/blob/main/docs/HOME.md"

ICON_PATH = "logo.ico"      # Icône de la barre de titre
LOGO_PATH = "logo.png"      # Logo pour l'écran d'accueil & splash screen

# Fichiers essentiels à vérifier au démarrage
FICHIERS_ESSENTIELS = [
    "core/windows/Lead.sys",
    "lexianalyzer.py"
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
                f"Attention, certains fichiers essentiels sont introuvables :\n{fichiers_str}\n\n"
                "Certaines fonctionnalités risquent de ne pas fonctionner."
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
        menu_code.add_command(label="Éditeur", state="disabled", command=self.action_editeur)
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
            except:
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

        ttk.Button(win, text="Exporter en .larc", command=sauvegarder_larc).grid(row=5, column=0, columnspan=2, pady=20)

    # ----------------------------------------------------------------------
    # Splash Screen : animation du logo sur fond blanc (Fade-in/out)
    # ----------------------------------------------------------------------
    def ouvrir_ecran_emulation(self, config):
        """
        Ouvre une fenêtre 640x480 avec un fondu du logo (Pillow) sur fond blanc,
        puis bascule vers l'écran noir de l'émulateur.
        """
        emu_win = tk.Toplevel(self.root)
        emu_win.title(f"Écran d'émulation : {config.get('nom_emulateur', 'LexiARC')}")
        emu_win.geometry("640x480")
        emu_win.configure(bg="white")
        emu_win.resizable(False, False)
        if os.path.exists(ICON_PATH):
            try:
                emu_win.iconbitmap(ICON_PATH)
            except:
                pass

        lbl_splash = tk.Label(emu_win, bg="white")
        lbl_splash.place(relx=0.5, rely=0.5, anchor="center")

        if not os.path.exists(LOGO_PATH):
            lbl_splash.destroy()
            emu_win.configure(bg="black")
            self._afficher_interface_emulation(emu_win, config)
            return

        try:
            pil_logo = Image.open(LOGO_PATH).convert("RGBA")
        except Exception as e:
            print(f"Erreur chargement logo : {e}")
            lbl_splash.destroy()
            emu_win.configure(bg="black")
            self._afficher_interface_emulation(emu_win, config)
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
                    self._afficher_interface_emulation(emu_win, config)
                else:
                    state["after_id"] = emu_win.after(STEP_MS, animer)

        def on_close():
            if state["after_id"] is not None:
                emu_win.after_cancel(state["after_id"])
            emu_win.destroy()
        emu_win.protocol("WM_DELETE_WINDOW", on_close)

        animer()

    def _afficher_interface_emulation(self, fenetre, config):
        """Affiche l'écran d'émulation final (texte de débogage)."""
        info_text = (
            f"Système : {config.get('nom_emulateur', 'Inconnu')}\n"
            f"CPU : {config.get('architecture_cpu', 'N/A')} | RAM : {config.get('taille_ram', 'N/A')}\n"
            f"SD : {os.path.basename(config.get('image_sd_path', ''))}\n\n"
            "[Prêt pour l'injection du cœur d'exécution]"
        )
        lbl_runtime = tk.Label(
            fenetre, text=info_text, fg="green", bg="black",
            font=("Courier", 12), justify="left"
        )
        lbl_runtime.pack(expand=True)

    # ----------------------------------------------------------------------
    # Fenêtre de compilation avec barre de progression et faux fichier
    # ----------------------------------------------------------------------
    def fenetre_compilation(self, format_output="elf"):
        win = tk.Toplevel(self.root)
        win.title(f"Compilation d'un jeu (.{format_output})")
        win.geometry("500x380")
        win.resizable(False, False)
        if os.path.exists(ICON_PATH):
            try:
                win.iconbitmap(ICON_PATH)
            except:
                pass
        win.grab_set()

        var_zip = tk.StringVar()
        var_nom_jeu = tk.StringVar()
        var_id_jeu = tk.StringVar()
        var_auteur = tk.StringVar()
        var_cle_mode = tk.StringVar(value="auto")
        var_cle_manuelle = tk.StringVar()

        ttk.Label(win, text="Archive du code source (.zip) :").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        frame_zip = ttk.Frame(win)
        frame_zip.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        ttk.Entry(frame_zip, textvariable=var_zip, width=30).pack(side="left")
        ttk.Button(frame_zip, text="...", width=3, command=lambda: self._parcourir_zip(var_zip)).pack(side="left", padx=5)

        ttk.Label(win, text="Nom du jeu :").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        ttk.Entry(win, textvariable=var_nom_jeu, width=30).grid(row=1, column=1, padx=10, pady=10)

        ttk.Label(win, text="ID du jeu (minuscules/tirets) :").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        id_entry = ttk.Entry(win, textvariable=var_id_jeu, width=30)
        id_entry.grid(row=2, column=1, padx=10, pady=10)

        def valider_id(action, value_if_allowed):
            if action == "0":
                return True
            return all(c.islower() or c == '-' for c in value_if_allowed)
        vcmd = (win.register(valider_id), '%d', '%P')
        id_entry.configure(validate="key", validatecommand=vcmd)

        ttk.Label(win, text="Auteur :").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        ttk.Entry(win, textvariable=var_auteur, width=30).grid(row=3, column=1, padx=10, pady=10)

        ttk.Label(win, text="Clé de chiffrement :").grid(row=4, column=0, padx=10, pady=10, sticky="w")
        frame_cle = ttk.Frame(win)
        frame_cle.grid(row=4, column=1, padx=10, pady=10, sticky="w")
        ttk.Radiobutton(frame_cle, text="Automatique", variable=var_cle_mode, value="auto").pack(anchor="w")
        ttk.Radiobutton(frame_cle, text="Manuelle", variable=var_cle_mode, value="manuel").pack(anchor="w")
        entry_cle = ttk.Entry(frame_cle, textvariable=var_cle_manuelle, width=25, state="disabled")
        entry_cle.pack(pady=(5, 0))

        def basculer_cle(*args):
            if var_cle_mode.get() == "manuel":
                entry_cle.config(state="normal")
            else:
                entry_cle.config(state="disabled")
                var_cle_manuelle.set("")
        var_cle_mode.trace_add("write", basculer_cle)

        def generer_cle_aleatoire():
            return secrets.token_hex(16)

        def lancer_compilation():
            if not var_zip.get():
                messagebox.showerror("Erreur", "Veuillez sélectionner une archive .zip.")
                return
            if not var_nom_jeu.get().strip():
                messagebox.showerror("Erreur", "Le nom du jeu est obligatoire.")
                return
            if not var_id_jeu.get().strip():
                messagebox.showerror("Erreur", "L'ID du jeu est obligatoire.")
                return

            cle = generer_cle_aleatoire() if var_cle_mode.get() == "auto" else var_cle_manuelle.get().strip()
            if var_cle_mode.get() == "manuel" and not cle:
                messagebox.showerror("Erreur", "Veuillez entrer une clé de chiffrement manuelle.")
                return

            win.destroy()
            self._simuler_compilation_avec_progression(format_output, var_nom_jeu.get(), var_id_jeu.get())

        ttk.Button(win, text="Compiler", command=lancer_compilation).grid(row=5, column=0, columnspan=2, pady=20)

    def _simuler_compilation_avec_progression(self, format_output, nom_jeu, id_jeu):
        progress_win = tk.Toplevel(self.root)
        progress_win.title("Compilation en cours...")
        progress_win.geometry("400x120")
        progress_win.resizable(False, False)
        if os.path.exists(ICON_PATH):
            try: progress_win.iconbitmap(ICON_PATH)
            except: pass
        progress_win.grab_set()

        ttk.Label(progress_win, text=f"Compilation du jeu {nom_jeu} en .{format_output}").pack(pady=10)
        barre = ttk.Progressbar(progress_win, mode="determinate", length=350)
        barre.pack(pady=10)

        max_steps = 100
        barre["maximum"] = max_steps
        barre["value"] = 0

        def incrementer(step=0):
            if step <= max_steps:
                barre["value"] = step
                progress_win.after(30, lambda: incrementer(step+1))
            else:
                progress_win.destroy()
                ext = "zip" if format_output == "elf" else "wxn"
                filename = filedialog.asksaveasfilename(
                    defaultextension=f".{ext}",
                    filetypes=[(f"Fichier {ext.upper()}", f"*.{ext}")],
                    initialfile=f"{id_jeu}.{ext}"
                )
                if filename:
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(f"Faux contenu compilé pour {nom_jeu} (format {format_output})\n")
                    messagebox.showinfo("Compilation terminée", f"Fichier enregistré : {os.path.basename(filename)}")
        incrementer()

    def _parcourir_zip(self, variable):
        filename = filedialog.askopenfilename(filetypes=[("Archive ZIP", "*.zip")])
        if filename:
            variable.set(filename)

    # ----------------------------------------------------------------------
    # Implémentation : Créer une implémentation
    # ----------------------------------------------------------------------
    def fenetre_creer_implementation(self):
        win = tk.Toplevel(self.root)
        win.title("Créer une implémentation")
        win.geometry("450x250")
        win.resizable(False, False)
        if os.path.exists(ICON_PATH):
            try: win.iconbitmap(ICON_PATH)
            except: pass
        win.grab_set()

        ttk.Label(win, text="Type de jeu :").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        var_type = tk.StringVar(value="elf")
        frame_type = ttk.Frame(win)
        frame_type.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        ttk.Radiobutton(frame_type, text="ELF (.zip)", variable=var_type, value="elf").pack(side="left")
        ttk.Radiobutton(frame_type, text="WXN (.wxn)", variable=var_type, value="wxn").pack(side="left", padx=10)

        ttk.Label(win, text="Fichier du jeu :").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        var_fichier = tk.StringVar()
        frame_fichier = ttk.Frame(win)
        frame_fichier.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        ttk.Entry(frame_fichier, textvariable=var_fichier, width=25).pack(side="left")
        def parcourir_fichier():
            ext = "*.zip" if var_type.get() == "elf" else "*.wxn"
            ft = [("Fichier ZIP", "*.zip")] if var_type.get() == "elf" else [("Fichier WXN", "*.wxn")]
            f = filedialog.askopenfilename(filetypes=ft)
            if f: var_fichier.set(f)
        ttk.Button(frame_fichier, text="...", width=3, command=parcourir_fichier).pack(side="left", padx=5)

        ttk.Label(win, text="Carte SD (.img) :").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        var_sd = tk.StringVar()
        frame_sd = ttk.Frame(win)
        frame_sd.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        ttk.Entry(frame_sd, textvariable=var_sd, width=25).pack(side="left")
        ttk.Button(frame_sd, text="...", width=3, command=lambda: var_sd.set(filedialog.askopenfilename(filetypes=[("Image SD", "*.img")]) or var_sd.get())).pack(side="left", padx=5)

        def commencer_implementation():
            if not var_fichier.get() or not var_sd.get():
                messagebox.showerror("Erreur", "Veuillez sélectionner le fichier du jeu et la carte SD.")
                return
            win.destroy()
            self._simuler_implementation_avec_progression(var_type.get(), var_fichier.get())

        ttk.Button(win, text="Commencer", command=commencer_implementation).grid(row=3, column=0, columnspan=2, pady=20)

    def _simuler_implementation_avec_progression(self, type_jeu, fichier):
        progress_win = tk.Toplevel(self.root)
        progress_win.title("Implémentation en cours...")
        progress_win.geometry("400x120")
        progress_win.resizable(False, False)
        if os.path.exists(ICON_PATH):
            try: progress_win.iconbitmap(ICON_PATH)
            except: pass
        progress_win.grab_set()

        ttk.Label(progress_win, text=f"Implémentation du jeu ({type_jeu.upper()})").pack(pady=10)
        barre = ttk.Progressbar(progress_win, mode="determinate", length=350)
        barre.pack(pady=10)

        max_steps = 80
        barre["maximum"] = max_steps
        barre["value"] = 0

        def incrementer(step=0):
            if step <= max_steps:
                barre["value"] = step
                progress_win.after(40, lambda: incrementer(step+1))
            else:
                progress_win.destroy()
                messagebox.showinfo("Implémentation terminée", "Le jeu a été implémenté avec succès.")
        incrementer()

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
            self.menu_code.entryconfigure("Éditeur", state="normal")
            self.menu_code.entryconfigure("Formatage", state="normal")
            self.menu_code.entryconfigure("Propriété", state="normal")

    def action_editeur(self):
        """Éditeur des fichiers système de la console contenue dans la carte SD."""
        if not self.chemin_carte_sd or not os.path.exists(self.chemin_carte_sd):
            messagebox.showerror("Erreur", "Aucune carte SD importée.")
            return

        # Fenêtre d'édition
        edit_win = tk.Toplevel(self.root)
        edit_win.title("Éditeur des fichiers système")
        edit_win.geometry("700x500")
        if os.path.exists(ICON_PATH):
            try: edit_win.iconbitmap(ICON_PATH)
            except: pass

        # Cadre de gauche : liste des fichiers système (simulée)
        frame_gauche = ttk.Frame(edit_win, width=200)
        frame_gauche.pack(side="left", fill="y", padx=5, pady=5)

        ttk.Label(frame_gauche, text="Fichiers système :").pack(anchor="w", pady=5)
        listbox_fichiers = tk.Listbox(frame_gauche, width=30)
        listbox_fichiers.pack(fill="both", expand=True)

        # Contenu simulé des fichiers système (vous pouvez les lire depuis l'image si vous avez un parser)
        fichiers_systeme = {
            "boot.cfg": "boot=main.elf\ninit=/bin/init\nconsole=tty0",
            "system.ini": "[System]\nversion=1.0\nlanguage=fr",
            "settings.xml": "<settings>\n  <display brightness=\"80\" />\n</settings>"
        }
        for nom in fichiers_systeme:
            listbox_fichiers.insert("end", nom)

        # Cadre de droite : zone d'édition
        frame_droit = ttk.Frame(edit_win)
        frame_droit.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        ttk.Label(frame_droit, text="Contenu du fichier :").pack(anchor="w", pady=5)
        text_editor = tk.Text(frame_droit, wrap="word", undo=True)
        text_editor.pack(fill="both", expand=True)

        def charger_fichier(event=None):
            selection = listbox_fichiers.curselection()
            if not selection:
                return
            nom = listbox_fichiers.get(selection[0])
            contenu = fichiers_systeme.get(nom, "")
            text_editor.delete("1.0", "end")
            text_editor.insert("1.0", contenu)

        listbox_fichiers.bind("<<ListboxSelect>>", charger_fichier)

        # Boutons sauvegarder / annuler
        frame_boutons = ttk.Frame(edit_win)
        frame_boutons.pack(side="bottom", fill="x", padx=5, pady=5)

        def sauvegarder_modifications():
            selection = listbox_fichiers.curselection()
            if not selection:
                messagebox.showwarning("Aucun fichier", "Sélectionnez un fichier à sauvegarder.")
                return
            nom = listbox_fichiers.get(selection[0])
            contenu = text_editor.get("1.0", "end-1c")
            fichiers_systeme[nom] = contenu
            messagebox.showinfo("Sauvegarde", f"Le fichier {nom} a été sauvegardé (simulation).")

        ttk.Button(frame_boutons, text="Sauvegarder", command=sauvegarder_modifications).pack(side="right", padx=5)
        ttk.Button(frame_boutons, text="Fermer", command=edit_win.destroy).pack(side="right", padx=5)

        # Pré-sélectionner le premier fichier
        if fichiers_systeme:
            listbox_fichiers.select_set(0)
            charger_fichier()

    def action_formatage(self):
        """Formater le disque (simulation avec confirmation et progression)."""
        if not self.chemin_carte_sd or not os.path.exists(self.chemin_carte_sd):
            messagebox.showerror("Erreur", "Aucune carte SD importée.")
            return

        reponse = messagebox.askyesno(
            "Formatage",
            "Êtes-vous sûr de vouloir formater la carte SD ?\nToutes les données seront perdues.",
            icon="warning"
        )
        if not reponse:
            return

        # Fenêtre de progression
        progress_win = tk.Toplevel(self.root)
        progress_win.title("Formatage en cours...")
        progress_win.geometry("400x120")
        progress_win.resizable(False, False)
        if os.path.exists(ICON_PATH):
            try: progress_win.iconbitmap(ICON_PATH)
            except: pass
        progress_win.grab_set()

        ttk.Label(progress_win, text="Formatage de la carte SD...").pack(pady=10)
        barre = ttk.Progressbar(progress_win, mode="determinate", length=350)
        barre.pack(pady=10)

        max_steps = 60
        barre["maximum"] = max_steps
        barre["value"] = 0

        def incrementer(step=0):
            if step <= max_steps:
                barre["value"] = step
                progress_win.after(50, lambda: incrementer(step+1))
            else:
                progress_win.destroy()
                messagebox.showinfo("Formatage terminé", "La carte SD a été formatée avec succès.")

        incrementer()

    def action_propriete(self):
        """Propriétés de la console (basées sur la carte SD importée)."""
        if not self.chemin_carte_sd or not os.path.exists(self.chemin_carte_sd):
            messagebox.showerror("Erreur", "Aucune carte SD importée.")
            return

        # Récupération d'infos sur le fichier .img
        nom_fichier = os.path.basename(self.chemin_carte_sd)
        taille = os.path.getsize(self.chemin_carte_sd)
        taille_mo = taille / (1024*1024)
        date_modif = os.path.getmtime(self.chemin_carte_sd)
        import datetime
        date_str = datetime.datetime.fromtimestamp(date_modif).strftime("%d/%m/%Y %H:%M:%S")

        # Infos simulées sur la console
        console_info = {
            "Modèle": "Lexibook JG7420AV",
            "CPU": "Sunplus S+core (Score7)",
            "RAM": "32 MB",
            "Système de fichiers": "FAT32 (simulé)",
            "Capacité totale": f"{taille_mo:.2f} Mo",
            "Espace libre": f"{taille_mo * 0.7:.2f} Mo (simulé)",
            "Dernière modification": date_str
        }

        prop_win = tk.Toplevel(self.root)
        prop_win.title("Propriétés de la console")
        prop_win.geometry("400x300")
        prop_win.resizable(False, False)
        if os.path.exists(ICON_PATH):
            try: prop_win.iconbitmap(ICON_PATH)
            except: pass

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
            except:
                pass
        win.grab_set()

        if os.path.exists(LOGO_PATH):
            try:
                self.logo_image = tk.PhotoImage(file=LOGO_PATH)
                lbl_img = tk.Label(win, image=self.logo_image)
                lbl_img.pack(pady=15)
            except Exception as e:
                tk.Label(win, text="[ Logo Introuvable ]", font=("Helvetica", 14, "bold"), fg="red").pack(pady=15)
        else:
            tk.Label(win, text="[ Fichier logo.png Manquant ]", font=("Helvetica", 14, "bold"), fg="red").pack(pady=15)

        tk.Label(win, text=f"Nom du logiciel : LexiARC", font=("Helvetica", 12, "bold")).pack(pady=2)
        tk.Label(win, text=f"Version : {VERSION}", font=("Helvetica", 10)).pack(pady=2)
        tk.Label(win, text=f"Auteur : {AUTEUR}", font=("Helvetica", 10)).pack(pady=2)
        tk.Label(win, text=f"Licence : {LICENCE}", font=("Helvetica", 10, "italic")).pack(pady=2)

        declaration_int = (
            "\nDéclaration importante :\n"
            "AUCUN fichier original de la console n'a été modifié ni altéré.\n"
            "Ce logiciel interagit uniquement avec les structures en lecture seule\n"
            "ou via des images mémoires conformes à des fins de préservation."
        )
        tk.Label(win, text=declaration_int, font=("Helvetica", 9), fg="darkred", justify="center", wraplength=420).pack(pady=15)

        ttk.Button(win, text="Fermer", command=win.destroy).pack(pady=10)


# ----------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = LexiARCApp(root)
    root.mainloop()
