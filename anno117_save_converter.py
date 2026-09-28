"""
====================================================================
           Anno 117 Save Converter pour Goldberg Emulator
====================================================================
Auteur: Assistant IA Antigravity
Description:
Outil tout-en-un de gestion et de conversion de sauvegardes pour
Anno 117: Pax Romana fonctionnant sous émulateur Goldberg (upc_r2).
Permet l'import, l'export et la conversion automatique des fichiers
.a8s <--> .save avec détection automatique des dossiers du jeu.
====================================================================
"""

import os
import sys
import zlib
import shutil
import datetime
import argparse
import webbrowser
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Amélioration du rendu haute résolution (Hi-DPI) sous Windows
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# Constantes techniques
UPC_HEADER = b"\x24\x00\x00\x00" + (b"\x00" * 36)  # 40 octets (0x24 = 36 octets de padding nul)
ACCOUNT_TAG = "<!ACCOUNT>"
ACCOUNT_CRC32 = zlib.crc32(ACCOUNT_TAG.encode("ascii")) & 0xffffffff  # 1578458188


def get_crc32(s: str) -> int:
    """Calcule le CRC32 normalisé 32-bit d'une chaîne UTF-8."""
    return zlib.crc32(s.encode("utf-8")) & 0xffffffff


def a8s_to_save(a8s_bytes: bytes) -> bytes:
    """Ajoute l'en-tête conteneur attendu par l'émulateur Uplay de Goldberg."""
    return UPC_HEADER + a8s_bytes


def save_to_a8s(save_bytes: bytes) -> bytes:
    """Supprime l'en-tête de 40 octets pour restaurer le fichier .a8s d'origine."""
    if len(save_bytes) > 40 and save_bytes[:4] == b"\x24\x00\x00\x00":
        return save_bytes[40:]
    return save_bytes


def convert_single_file(input_path: str, output_path: str, direction: str = "auto") -> bool:
    """Convertit un fichier individuel entre .a8s et .save."""
    with open(input_path, "rb") as f:
        data = f.read()

    is_save = len(data) > 40 and data[:4] == b"\x24\x00\x00\x00"

    if direction == "auto":
        direction = "to_a8s" if is_save else "to_save"

    if direction == "to_save":
        res = a8s_to_save(data)
    else:
        res = save_to_a8s(data)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(res)
    return True


def detect_goldberg_paths() -> list:
    """Scanne le système (registre Steam, bibliothèques Steam, AppData) pour trouver les dossiers Goldberg."""
    candidates = []

    # 1. Scanner les bibliothèques Steam
    steam_roots = []
    try:
        import winreg
        for reg_path in [r"SOFTWARE\WOW6432Node\Valve\Steam", r"SOFTWARE\Valve\Steam"]:
            for root_key in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                try:
                    with winreg.OpenKey(root_key, reg_path) as k:
                        val, _ = winreg.QueryValueEx(k, "InstallPath")
                        if os.path.exists(val) and val not in steam_roots:
                            steam_roots.append(val)
                except Exception:
                    pass
    except Exception:
        pass

    default_steam = r"C:\Program Files (x86)\Steam"
    if default_steam not in steam_roots and os.path.exists(default_steam):
        steam_roots.append(default_steam)

    lib_paths = list(steam_roots)
    import re
    for sr in steam_roots:
        vdf = os.path.join(sr, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf):
            try:
                with open(vdf, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                for m in re.finditer(r'"path"\s+"([^"]+)"', content):
                    p = m.group(1).replace("\\\\", "\\")
                    if os.path.exists(p) and p not in lib_paths:
                        lib_paths.append(p)
            except Exception:
                pass

    for lp in lib_paths:
        p922 = os.path.join(lp, "steamapps", "common", "Anno 117 - Pax Romana", "Bin", "Win64", "saves", "922")
        if os.path.exists(p922):
            candidates.append(p922)
        psaves = os.path.join(lp, "steamapps", "common", "Anno 117 - Pax Romana", "Bin", "Win64", "saves")
        if os.path.exists(psaves) and psaves not in candidates and p922 not in candidates:
            candidates.append(psaves)

    # 2. Scanner AppData Roaming
    appdata = os.environ.get("APPDATA")
    if appdata:
        g_appdata = os.path.join(appdata, "Goldberg UplayEmu Saves")
        if os.path.exists(g_appdata):
            for sub in os.listdir(g_appdata):
                p = os.path.join(g_appdata, sub)
                if os.path.isdir(p) and p not in candidates:
                    candidates.append(p)

    return candidates


def detect_anno_accounts() -> list:
    """Détecte les comptes Anno 117 existants dans Documents et OneDrive Documents."""
    accounts = []
    user_p = os.environ.get("USERPROFILE", "")
    candidates = [
        os.path.join(user_p, "Documents", "Anno 117 - Pax Romana", "accounts"),
        os.path.join(user_p, "OneDrive", "Documents", "Anno 117 - Pax Romana", "accounts")
    ]
    for c in candidates:
        if os.path.exists(c):
            for sub in os.listdir(c):
                full_sub = os.path.join(c, sub)
                if os.path.isdir(full_sub) and not sub.endswith("- Copie") and full_sub not in accounts:
                    accounts.append(full_sub)
    return accounts


def format_size(bytes_size: int) -> str:
    """Formate une taille en octets de manière lisible."""
    if bytes_size < 1024:
        return f"{bytes_size} O"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} Ko"
    else:
        return f"{bytes_size / (1024 * 1024):.2f} Mo"


class ModernConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Anno 117 : Pax Romana - Convertisseur de Sauvegardes Goldberg")
        self.geometry("860x700")
        self.minsize(780, 600)

        # Palette moderne Dark
        self.c_bg = "#18181f"
        self.c_card = "#22222c"
        self.c_input = "#141419"
        self.c_border = "#343444"
        self.c_text = "#f3f4f6"
        self.c_muted = "#9ca3af"
        self.c_accent = "#3b82f6"
        self.c_accent_hover = "#2563eb"
        self.c_success = "#10b981"
        self.c_success_hover = "#059669"
        self.c_warning = "#f59e0b"

        self.configure(bg=self.c_bg)
        self._init_styles()

        # Variables dynamiques
        self.source_dir_var = tk.StringVar()
        self.target_goldberg_var = tk.StringVar()
        self.profile_name_var = tk.StringVar(value="Marcus")
        self.backup_var = tk.BooleanVar(value=True)

        self.single_in_var = tk.StringVar()
        self.single_out_var = tk.StringVar()

        self._auto_detect_initial_paths()
        self._build_ui()
        self._refresh_profiles_and_saves()

    def _init_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=self.c_bg, foreground=self.c_text, font=("Segoe UI", 10))
        style.configure("TFrame", background=self.c_bg)
        style.configure("Card.TFrame", background=self.c_card, relief="flat")
        style.configure("TLabel", background=self.c_bg, foreground=self.c_text)
        style.configure("Card.TLabel", background=self.c_card, foreground=self.c_text)
        style.configure("Muted.TLabel", background=self.c_card, foreground=self.c_muted, font=("Segoe UI", 9))
        style.configure("Badge.TLabel", background="#064e3b", foreground="#a7f3d0", font=("Segoe UI", 9, "bold"), padding=[6, 2])

        # Notebook (Onglets)
        style.configure("TNotebook", background=self.c_bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=self.c_card, foreground=self.c_muted, padding=[18, 10], font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", self.c_accent)], foreground=[("selected", "#ffffff")])

        # Boutons
        style.configure("TButton", background=self.c_accent, foreground="#ffffff", borderwidth=0, padding=[14, 7], font=("Segoe UI", 10, "bold"))
        style.map("TButton", background=[("active", self.c_accent_hover)])

        style.configure("Secondary.TButton", background=self.c_border, foreground=self.c_text, borderwidth=0, padding=[10, 6], font=("Segoe UI", 9))
        style.map("Secondary.TButton", background=[("active", "#4a4a5e")])

        style.configure("TCheckbutton", background=self.c_card, foreground=self.c_text)
        style.map("TCheckbutton", background=[("active", self.c_card)])

        style.configure("TCombobox", fieldbackground=self.c_input, background=self.c_card, foreground=self.c_text)

    def _auto_detect_initial_paths(self):
        """Recherche automatiquement les chemins pertinents sans forcer de chemin fixe."""
        # 1. Détection dossier Goldberg
        goldberg_candidates = detect_goldberg_paths()
        if goldberg_candidates:
            self.target_goldberg_var.set(goldberg_candidates[0])
            self.detected_goldberg = True
        else:
            self.target_goldberg_var.set("")
            self.detected_goldberg = False

        # 2. Détection dossier Source
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_folders = [f for f in os.listdir(script_dir) if os.path.isdir(os.path.join(script_dir, f)) and not f.startswith(".")]

        chosen_source = ""
        for lf in local_folders:
            p = os.path.join(script_dir, lf)
            for _, _, files in os.walk(p):
                if any(f.endswith(".a8s") for f in files):
                    chosen_source = p
                    break
            if chosen_source:
                break

        if not chosen_source:
            accounts = detect_anno_accounts()
            if accounts:
                chosen_source = accounts[0]

        self.source_dir_var.set(chosen_source or "")

    def _build_ui(self):
        # Header banner
        header = tk.Frame(self, bg=self.c_card, height=65)
        header.pack(fill="x", side="top")

        title_lbl = tk.Label(header, text="🏛️ Anno 117: Pax Romana — Save Manager", font=("Segoe UI", 14, "bold"), bg=self.c_card, fg="#ffffff")
        title_lbl.pack(side="left", padx=20, pady=16)

        sub_lbl = tk.Label(header, text="Convertisseur .a8s <—> .save pour Goldberg Emulator", font=("Segoe UI", 9), bg=self.c_card, fg=self.c_muted)
        sub_lbl.pack(side="right", padx=20, pady=20)

        # Onglets
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=16, pady=14)

        tab_import = ttk.Frame(notebook)
        tab_export = ttk.Frame(notebook)
        tab_single = ttk.Frame(notebook)

        notebook.add(tab_import, text="  📥 Importer vers Goldberg (.a8s ➔ .save)  ")
        notebook.add(tab_export, text="  📤 Exporter depuis Goldberg (.save ➔ .a8s)  ")
        notebook.add(tab_single, text="  🔄 Convertisseur Manuel Fichier  ")

        self._build_tab_import(tab_import)
        self._build_tab_export(tab_export)
        self._build_tab_single(tab_single)

    def _build_tab_import(self, parent):
        container = ttk.Frame(parent, padding=14)
        container.pack(fill="both", expand=True)

        # Card 1: Dossier Source
        card1 = ttk.Frame(container, style="Card.TFrame", padding=12)
        card1.pack(fill="x", pady=(0, 10))

        c1_top = ttk.Frame(card1, style="Card.TFrame")
        c1_top.pack(fill="x")
        ttk.Label(c1_top, text="1. Dossier source de vos sauvegardes (.a8s)", font=("Segoe UI", 10, "bold"), style="Card.TLabel").pack(side="left")
        ttk.Label(c1_top, text="Dossier contenant accountdata.a8s et vos profils", style="Muted.TLabel").pack(side="right")

        f_src = ttk.Frame(card1, style="Card.TFrame")
        f_src.pack(fill="x", pady=(8, 0))
        e_src = tk.Entry(f_src, textvariable=self.source_dir_var, bg=self.c_input, fg=self.c_text, insertbackground="white", font=("Segoe UI", 9), relief="flat")
        e_src.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))
        e_src.bind("<KeyRelease>", lambda e: self._refresh_profiles_and_saves())

        ttk.Button(f_src, text="Parcourir...", style="Secondary.TButton", command=self._browse_source).pack(side="left")

        # Card 2: Dossier Destination Goldberg
        card2 = ttk.Frame(container, style="Card.TFrame", padding=12)
        card2.pack(fill="x", pady=(0, 10))

        c2_top = ttk.Frame(card2, style="Card.TFrame")
        c2_top.pack(fill="x")
        ttk.Label(c2_top, text="2. Emplacement du dossier Goldberg (saves\\922)", font=("Segoe UI", 10, "bold"), style="Card.TLabel").pack(side="left")

        if self.detected_goldberg:
            ttk.Label(c2_top, text="✔ Détecté automatiquement", style="Badge.TLabel").pack(side="right")

        f_dst = ttk.Frame(card2, style="Card.TFrame")
        f_dst.pack(fill="x", pady=(8, 0))
        e_dst = tk.Entry(f_dst, textvariable=self.target_goldberg_var, bg=self.c_input, fg=self.c_text, insertbackground="white", font=("Segoe UI", 9), relief="flat")
        e_dst.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        ttk.Button(f_dst, text="Parcourir...", style="Secondary.TButton", command=self._browse_goldberg).pack(side="left", padx=(0, 6))
        ttk.Button(f_dst, text="📁 Ouvrir", style="Secondary.TButton", command=lambda: self._open_folder(self.target_goldberg_var.get())).pack(side="left")

        # Card 3: Profil & Sélection de la sauvegarde
        card3 = ttk.Frame(container, style="Card.TFrame", padding=12)
        card3.pack(fill="x", pady=(0, 10))

        f_pick = ttk.Frame(card3, style="Card.TFrame")
        f_pick.pack(fill="x")

        ttk.Label(f_pick, text="Profil :", style="Card.TLabel").pack(side="left")
        self.combo_profiles = ttk.Combobox(f_pick, textvariable=self.profile_name_var, width=14)
        self.combo_profiles.pack(side="left", padx=(6, 18))
        self.combo_profiles.bind("<<ComboboxSelected>>", lambda e: self._filter_saves_for_profile())
        self.combo_profiles.bind("<KeyRelease>", lambda e: self._filter_saves_for_profile())

        ttk.Label(f_pick, text="Sauvegarde à charger dans le jeu :", font=("Segoe UI", 10, "bold"), style="Card.TLabel").pack(side="left")
        self.combo_saves = ttk.Combobox(f_pick, state="readonly", width=38)
        self.combo_saves.pack(side="left", padx=(6, 0))

        ttk.Checkbutton(card3, text="Créer une sauvegarde (backup horodaté) des anciens fichiers .save", variable=self.backup_var).pack(anchor="w", pady=(10, 0))

        # Grand bouton d'action
        btn_run = tk.Button(container, text="⚡ Convertir & Appliquer pour Goldberg", bg=self.c_success, fg="#ffffff",
                            activebackground=self.c_success_hover, activeforeground="#ffffff", font=("Segoe UI", 11, "bold"),
                            relief="flat", cursor="hand2", pady=8, command=self._action_import_to_goldberg)
        btn_run.pack(fill="x", pady=(4, 10))

        # Console / Logs
        card_log = ttk.Frame(container, style="Card.TFrame", padding=8)
        card_log.pack(fill="both", expand=True)
        ttk.Label(card_log, text="Statut de l'opération :", font=("Segoe UI", 9, "bold"), style="Card.TLabel").pack(anchor="w")

        self.txt_log = tk.Text(card_log, bg=self.c_input, fg="#a7f3d0", insertbackground="white", height=7, font=("Consolas", 9), relief="flat")
        self.txt_log.pack(fill="both", expand=True, pady=(4, 0))

    def _build_tab_export(self, parent):
        container = ttk.Frame(parent, padding=16)
        container.pack(fill="both", expand=True)

        card = ttk.Frame(container, style="Card.TFrame", padding=14)
        card.pack(fill="x", pady=(0, 14))

        ttk.Label(card, text="Exporter vos sauvegardes Goldberg vers le format .a8s", font=("Segoe UI", 11, "bold"), style="Card.TLabel").pack(anchor="w")
        ttk.Label(card, text="Utile si vous souhaitez récupérer vos parties jouées avec Goldberg pour les utiliser sur le jeu officiel.", style="Muted.TLabel").pack(anchor="w", pady=(2, 12))

        ttk.Label(card, text="Dossier Goldberg source :", style="Card.TLabel").pack(anchor="w")
        f_exp_src = ttk.Frame(card, style="Card.TFrame")
        f_exp_src.pack(fill="x", pady=(4, 12))
        tk.Entry(f_exp_src, textvariable=self.target_goldberg_var, bg=self.c_input, fg=self.c_text, insertbackground="white", relief="flat").pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))
        ttk.Button(f_exp_src, text="Parcourir...", style="Secondary.TButton", command=self._browse_goldberg).pack(side="left")

        self.export_dst_var = tk.StringVar(value=os.path.join(os.environ.get("USERPROFILE", ""), "Desktop", "Anno117_Exports"))
        ttk.Label(card, text="Dossier de destination pour les fichiers .a8s extraits :", style="Card.TLabel").pack(anchor="w")
        f_exp_dst = ttk.Frame(card, style="Card.TFrame")
        f_exp_dst.pack(fill="x", pady=(4, 16))
        tk.Entry(f_exp_dst, textvariable=self.export_dst_var, bg=self.c_input, fg=self.c_text, insertbackground="white", relief="flat").pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))
        ttk.Button(f_exp_dst, text="Parcourir...", style="Secondary.TButton", command=self._browse_export_dst).pack(side="left")

        btn_export = tk.Button(container, text="📤 Exporter tous les .save en .a8s", bg=self.c_accent, fg="#ffffff",
                               activebackground=self.c_accent_hover, activeforeground="#ffffff", font=("Segoe UI", 10, "bold"),
                               relief="flat", cursor="hand2", pady=8, command=self._action_export_from_goldberg)
        btn_export.pack(fill="x")

        # Explications
        info_card = ttk.Frame(container, style="Card.TFrame", padding=12)
        info_card.pack(fill="x", pady=14)
        info_text = (
            "💡 Comment fonctionne l'exportation ?\n"
            "• Le fichier 1578458188.save sera automatiquement restauré en 'accountdata.a8s'.\n"
            "• Les sauvegardes de partie (comme 3065337527.save) seront restaurées en fichier .a8s complet sans l'en-tête de 40 octets.\n"
            "• Vous pourrez ensuite les copier dans vos documents Anno 117."
        )
        ttk.Label(info_card, text=info_text, style="Muted.TLabel", justify="left").pack(anchor="w")

    def _build_tab_single(self, parent):
        container = ttk.Frame(parent, padding=16)
        container.pack(fill="both", expand=True)

        card = ttk.Frame(container, style="Card.TFrame", padding=14)
        card.pack(fill="x", pady=(0, 14))

        ttk.Label(card, text="Conversion directe d'un fichier", font=("Segoe UI", 11, "bold"), style="Card.TLabel").pack(anchor="w")
        ttk.Label(card, text="Convertissez n'importe quel fichier .a8s en .save ou inversement.", style="Muted.TLabel").pack(anchor="w", pady=(2, 12))

        ttk.Label(card, text="Fichier d'entrée (.a8s ou .save) :", style="Card.TLabel").pack(anchor="w")
        f_in = ttk.Frame(card, style="Card.TFrame")
        f_in.pack(fill="x", pady=(4, 12))
        tk.Entry(f_in, textvariable=self.single_in_var, bg=self.c_input, fg=self.c_text, insertbackground="white", relief="flat").pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))
        ttk.Button(f_in, text="Parcourir...", style="Secondary.TButton", command=self._browse_single_in).pack(side="left")

        ttk.Label(card, text="Fichier de sortie :", style="Card.TLabel").pack(anchor="w")
        f_out = ttk.Frame(card, style="Card.TFrame")
        f_out.pack(fill="x", pady=(4, 16))
        tk.Entry(f_out, textvariable=self.single_out_var, bg=self.c_input, fg=self.c_text, insertbackground="white", relief="flat").pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))
        ttk.Button(f_out, text="Parcourir...", style="Secondary.TButton", command=self._browse_single_out).pack(side="left")

        btn_conv = tk.Button(container, text="🔄 Lancer la conversion du fichier", bg=self.c_accent, fg="#ffffff",
                             activebackground=self.c_accent_hover, activeforeground="#ffffff", font=("Segoe UI", 10, "bold"),
                             relief="flat", cursor="hand2", pady=8, command=self._action_convert_single)
        btn_conv.pack(fill="x")

    def _browse_source(self):
        d = filedialog.askdirectory(initialdir=self.source_dir_var.get() or os.getcwd(), title="Sélectionnez le dossier de vos sauvegardes Anno 117 (.a8s)")
        if d:
            self.source_dir_var.set(d)
            self._refresh_profiles_and_saves()

    def _browse_goldberg(self):
        d = filedialog.askdirectory(initialdir=self.target_goldberg_var.get() or os.getcwd(), title="Sélectionnez le dossier des sauvegardes Goldberg (saves\\922)")
        if d:
            self.target_goldberg_var.set(d)

    def _browse_export_dst(self):
        d = filedialog.askdirectory(initialdir=self.export_dst_var.get(), title="Dossier de destination pour l'exportation")
        if d:
            self.export_dst_var.set(d)

    def _browse_single_in(self):
        f = filedialog.askopenfilename(title="Sélectionner le fichier à convertir", filetypes=[("Sauvegardes Anno/Goldberg", "*.a8s;*.save"), ("Tous les fichiers", "*.*")])
        if f:
            self.single_in_var.set(f)
            if f.endswith(".a8s"):
                self.single_out_var.set(f[:-4] + ".save")
            elif f.endswith(".save"):
                self.single_out_var.set(f[:-5] + ".a8s")

    def _browse_single_out(self):
        f = filedialog.asksaveasfilename(title="Enregistrer le fichier converti sous", filetypes=[("Sauvegardes", "*.save;*.a8s"), ("Tous les fichiers", "*.*")])
        if f:
            self.single_out_var.set(f)

    def _open_folder(self, path):
        if path and os.path.exists(path):
            os.startfile(path)
        else:
            messagebox.showwarning("Dossier introuvable", f"Le dossier suivant n'existe pas encore :\n{path}")

    def _refresh_profiles_and_saves(self):
        src = self.source_dir_var.get().strip()
        if not src or not os.path.exists(src):
            return

        # Détecter les sous-dossiers qui représentent des profils (ex: Marcus)
        subdirs = [d for d in os.listdir(src) if os.path.isdir(os.path.join(src, d)) and not d.startswith(".")]
        if subdirs:
            self.combo_profiles["values"] = subdirs
            curr = self.profile_name_var.get()
            if curr not in subdirs:
                self.combo_profiles.current(0)
        else:
            self.combo_profiles["values"] = ["Marcus"]

        self._filter_saves_for_profile()

    def _filter_saves_for_profile(self):
        src = self.source_dir_var.get().strip()
        profile = self.profile_name_var.get().strip()
        if not src or not os.path.exists(src):
            return

        saves = []
        target_search_dir = os.path.join(src, profile) if profile and os.path.exists(os.path.join(src, profile)) else src

        for root, _, files in os.walk(target_search_dir):
            for f in files:
                if f.endswith(".a8s") and f != "accountdata.a8s":
                    p = os.path.join(root, f)
                    mtime = os.path.getmtime(p)
                    size_str = format_size(os.path.getsize(p))
                    date_str = datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
                    saves.append((mtime, f, f"{f}  —  [{size_str} | {date_str}]"))

        # Trier par date la plus récente
        saves.sort(key=lambda x: x[0], reverse=True)
        display_list = [s[2] for s in saves]
        self.save_name_mapping = {s[2]: s[1] for s in saves}

        self.combo_saves["values"] = display_list
        if display_list:
            self.combo_saves.current(0)
        else:
            self.combo_saves.set("Aucune sauvegarde .a8s trouvée")

    def _log(self, msg: str):
        self.txt_log.insert("end", msg + "\n")
        self.txt_log.see("end")

    def _action_import_to_goldberg(self):
        src = self.source_dir_var.get().strip()
        dst = self.target_goldberg_var.get().strip()
        selected_display = self.combo_saves.get()

        if not src or not os.path.exists(src):
            messagebox.showerror("Erreur", "Le dossier source spécifié n'existe pas.")
            return

        if not dst:
            messagebox.showerror("Erreur", "Veuillez spécifier le dossier des sauvegardes Goldberg (saves\\922).")
            return

        if not selected_display or selected_display not in self.save_name_mapping:
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier de sauvegarde .a8s valide.")
            return

        chosen_file = self.save_name_mapping[selected_display]
        profile = self.profile_name_var.get().strip() or "Marcus"

        try:
            self.txt_log.delete("1.0", "end")
            self._log(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Démarrage de la conversion...")

            # 1. Backup
            if self.backup_var.get() and os.path.exists(dst):
                files_to_backup = [f for f in os.listdir(dst) if f.endswith(".save")]
                if files_to_backup:
                    backup_dir = os.path.join(dst, f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
                    os.makedirs(backup_dir, exist_ok=True)
                    for bf in files_to_backup:
                        shutil.copy2(os.path.join(dst, bf), os.path.join(backup_dir, bf))
                    self._log(f"✔ Sauvegarde des anciens fichiers effectuée dans :\n   ↳ {backup_dir}")

            # 2. Conversion accountdata.a8s
            acc_file = os.path.join(src, "accountdata.a8s")
            if os.path.exists(acc_file):
                acc_dst = os.path.join(dst, f"{ACCOUNT_CRC32}.save")
                convert_single_file(acc_file, acc_dst, direction="to_save")
                self._log(f"✔ Compte converti : accountdata.a8s ➔ {ACCOUNT_CRC32}.save ({format_size(os.path.getsize(acc_dst))})")
            else:
                self._log("ℹ 'accountdata.a8s' non trouvé à la racine de la source. Seule la partie sera appliquée.")

            # 3. Conversion de la partie
            profile_crc = get_crc32(profile)
            game_save_dst = os.path.join(dst, f"{profile_crc}.save")

            # Trouver le chemin complet du fichier sélectionné
            full_save_path = os.path.join(src, profile, chosen_file)
            if not os.path.exists(full_save_path):
                for root, _, files in os.walk(src):
                    if chosen_file in files:
                        full_save_path = os.path.join(root, chosen_file)
                        break

            convert_single_file(full_save_path, game_save_dst, direction="to_save")
            self._log(f"✔ Sauvegarde de partie appliquée : {chosen_file} ➔ {profile_crc}.save ({format_size(os.path.getsize(game_save_dst))})")

            self._log("🎉 Opération terminée avec succès ! Vous pouvez lancer Anno 117.")
            res = messagebox.askyesno("Succès !", "La sauvegarde a été convertie et installée avec succès pour Goldberg !\n\nSouhaitez-vous ouvrir le dossier des sauvegardes ?")
            if res:
                self._open_folder(dst)

        except Exception as e:
            self._log(f"❌ Erreur : {e}")
            messagebox.showerror("Erreur", f"Une erreur est survenue lors de l'opération :\n{e}")

    def _action_export_from_goldberg(self):
        src = self.target_goldberg_var.get().strip()
        dst = self.export_dst_var.get().strip()

        if not src or not os.path.exists(src):
            messagebox.showerror("Erreur", "Le dossier source Goldberg spécifié n'existe pas.")
            return

        save_files = [f for f in os.listdir(src) if f.endswith(".save")]
        if not save_files:
            messagebox.showwarning("Aucun fichier", "Aucun fichier .save trouvé dans le dossier Goldberg.")
            return

        os.makedirs(dst, exist_ok=True)
        count = 0
        for sf in save_files:
            in_p = os.path.join(src, sf)
            name_no_ext = sf[:-5]

            # Déduire le nom convivial
            if name_no_ext == str(ACCOUNT_CRC32):
                out_name = "accountdata.a8s"
            elif name_no_ext == str(get_crc32(self.profile_name_var.get())):
                out_name = f"{self.profile_name_var.get()}_Session.a8s"
            else:
                out_name = f"{name_no_ext}.a8s"

            out_p = os.path.join(dst, out_name)
            convert_single_file(in_p, out_p, direction="to_a8s")
            count += 1

        messagebox.showinfo("Exportation Réussie", f"{count} fichier(s) .save ont été convertis en .a8s dans :\n{dst}")
        self._open_folder(dst)

    def _action_convert_single(self):
        in_p = self.single_in_var.get().strip()
        out_p = self.single_out_var.get().strip()

        if not in_p or not os.path.exists(in_p):
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier source existant.")
            return
        if not out_p:
            messagebox.showerror("Erreur", "Veuillez spécifier le fichier de sortie.")
            return

        try:
            convert_single_file(in_p, out_p, direction="auto")
            messagebox.showinfo("Succès", f"Fichier converti avec succès vers :\n{out_p}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de la conversion :\n{e}")


def cli_main():
    parser = argparse.ArgumentParser(description="Convertisseur de sauvegardes Anno 117 pour Goldberg Emulator")
    parser.add_argument("--source", "-s", help="Dossier contenant les fichiers .a8s")
    parser.add_argument("--dest", "-d", help="Dossier saves/922 de Goldberg")
    parser.add_argument("--file", "-f", help="Nom du fichier de sauvegarde .a8s à convertir (ex: 'Autosave 57.a8s')")
    parser.add_argument("--profile", "-p", default="Marcus", help="Nom du profil (défaut: Marcus)")
    parser.add_argument("--single-in", help="Chemin d'entrée pour la conversion unique")
    parser.add_argument("--single-out", help="Chemin de sortie pour la conversion unique")

    args = parser.parse_args()

    if args.single_in and args.single_out:
        convert_single_file(args.single_in, args.single_out)
        print(f"✔ Converti : {args.single_in} -> {args.single_out}")
        return

    if args.source and args.dest and args.file:
        # CLI headless import
        save_path = os.path.join(args.source, args.profile, args.file)
        if not os.path.exists(save_path):
            save_path = os.path.join(args.source, args.file)
        profile_crc = get_crc32(args.profile)
        convert_single_file(save_path, os.path.join(args.dest, f"{profile_crc}.save"), direction="to_save")
        acc = os.path.join(args.source, "accountdata.a8s")
        if os.path.exists(acc):
            convert_single_file(acc, os.path.join(args.dest, f"{ACCOUNT_CRC32}.save"), direction="to_save")
        print(f"✔ Import terminé pour {args.file} (Profil: {args.profile}) vers {args.dest}")
        return

    # Lancement de l'interface graphique
    app = ModernConverterApp()
    app.mainloop()


if __name__ == "__main__":
    cli_main()
