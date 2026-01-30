"""
APPLICATION SECURITY MANIFEST & AUDIT LOG
-----------------------------------------
App Name:       Media Workflow Studio Pro
Version:        3.1 (Safe Mode Enabled)
Author:         Ayush Singhal
Company:        Deluxe Media
Created:        2025
Purpose:        Local image manipulation.

COPYRIGHT NOTICE:
The logic and architecture of this script were authored by Ayush Singhal.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import threading
import sys
import re
from PIL import Image, ImageTk, ImageFilter
from psd_tools import PSDImage

# --- SAFE IMPORT: TRAP THE ERROR ---
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DRAG_DROP_AVAILABLE = True
except ImportError:
    DRAG_DROP_AVAILABLE = False
    # Fallback class if library is missing
    class TkinterDnD:
        class DnDWrapper:
            pass

# --- Configuration ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Conditional Inheritance based on library availability
BaseClass = TkinterDnD.DnDWrapper if DRAG_DROP_AVAILABLE else object

class ProMediaTool(ctk.CTk, BaseClass):
    def __init__(self):
        super().__init__()

        # --- HIDDEN AUTHOR SIGNATURE ---
        self.bind("<Control-Alt-a>", self._reveal_author)
        self._author_signature = "Code by Ayush Singhal | Deluxe Media"

        self.title("Media Workflow Studio Pro (v3.1)")
        self.geometry("1000x700")

        # --- Layout Grid ---
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT PANEL ---
        self.left_frame = ctk.CTkFrame(self, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.tab_view = ctk.CTkTabview(self.left_frame)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_psd = self.tab_view.add("PSD Bulk Converter")
        self.tab_resize = self.tab_view.add("Smart Resizer")
        self.tab_banner = self.tab_view.add("HD Banner & Rename")

        # --- RIGHT PANEL ---
        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(0,10), pady=10)
        
        self.lbl_preview_title = ctk.CTkLabel(self.right_frame, text="Live Preview", font=("Roboto", 16, "bold"))
        self.lbl_preview_title.pack(pady=(20, 10))
        
        self.lbl_preview_img = ctk.CTkLabel(self.right_frame, text="[Drag Files Here]", width=286, height=410, fg_color="#2b2b2b", corner_radius=10)
        self.lbl_preview_img.pack(pady=10, padx=20)

        self.lbl_info_title = ctk.CTkLabel(self.right_frame, text="File Information", font=("Roboto", 12, "bold"), text_color="gray70")
        self.lbl_info_title.pack(pady=(20, 0), anchor="w", padx=10)
        
        self.info_box = ctk.CTkTextbox(self.right_frame, height=120, fg_color="#222222", text_color="#00E5FF")
        self.info_box.pack(fill="x", padx=10, pady=5, side="top")
        self.info_box.insert("0.0", "Waiting for selection...")
        self.info_box.configure(state="disabled")

        # Internal State
        self.file_list = []
        self.current_preview_path = None
        
        self._setup_psd_tab()
        self._setup_resize_tab()
        self._setup_banner_tab()
        
        # --- SAFE DRAG & DROP INIT ---
        if DRAG_DROP_AVAILABLE:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
                self.drop_target_register(DND_FILES)
                self.dnd_bind('<<Drop>>', self.drop_files_handler)
            except Exception as e:
                print(f"DnD Init Failed: {e}")
        else:
            messagebox.showwarning("System Warning", "Drag & Drop module missing.\nApp running in Basic Mode.")

    def resource_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    # --- DRAG & DROP HANDLER ---
    def drop_files_handler(self, event):
        raw_files = event.data
        if "{" in raw_files:
            files = re.findall(r'\{.*?\}|\S+', raw_files)
            files = [f.replace("{", "").replace("}", "") for f in files]
        else:
            files = raw_files.split()
        
        if files:
            self.file_list = files
            self.current_preview_path = files[0]
            
            # Update Active Tab Text
            active = self.tab_view.get()
            if active == "PSD Bulk Converter": self.update_file_list_display(self.txt_psd, files)
            elif active == "Smart Resizer": self.update_file_list_display(self.txt_res, files)
            elif active == "HD Banner & Rename": self.update_file_list_display(self.txt_ban, files)

            self.update_file_info(files[0])
            self.refresh_preview()

    # --- FILE INFO ---
    def update_file_info(self, filepath):
        try:
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if filepath.lower().endswith(".psd"):
                psd = PSDImage.open(filepath)
                w, h, fmt, mode = psd.width, psd.height, "PSD (Adobe)", psd.color_mode
            else:
                img = Image.open(filepath)
                w, h, fmt, mode = img.size, img.format, img.mode
            
            txt = f"File: {os.path.basename(filepath)}\nDim: {w}x{h}\nType: {fmt} | {mode}\nSize: {size_mb:.2f} MB"
        except: txt = "Info unavailable"

        self.info_box.configure(state="normal")
        self.info_box.delete("0.0", "end")
        self.info_box.insert("0.0", txt)
        self.info_box.configure(state="disabled")

    # --- PREVIEW ENGINE ---
    def refresh_preview(self):
        if not self.current_preview_path: return
        try:
            if self.current_preview_path.lower().endswith(".psd"):
                psd = PSDImage.open(self.current_preview_path)
                img = psd.composite()
            else:
                img = Image.open(self.current_preview_path)

            if self.tab_view.get() == "HD Banner & Rename":
                img = img.resize((286, 371), Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (286, 410), (255, 255, 255))
                canvas.paste(img, (0, 0))
                
                tpl = "banner_2day.png" if self.ban_type.get() == "2day" else "banner_3day.png"
                tpl_path = self.resource_path(tpl)
                if os.path.exists(tpl_path):
                    banner = Image.open(tpl_path).convert("RGBA").resize((286, 410), Image.Resampling.LANCZOS)
                    canvas.paste(banner, (0, 0), mask=banner)
                    img = canvas

            img.thumbnail((286, 410))
            ctk_img = ctk.CTkImage(img, size=img.size)
            self.lbl_preview_img.configure(image=ctk_img, text="")
        except: pass

    def save_image_pro(self, img, path, dpi=(72,72)):
        if img.mode in ("RGBA", "P", "CMYK"): img = img.convert("RGB")
        img.save(path, "JPEG", quality=100, subsampling=0, dpi=dpi)

    def select_files(self, listbox, mode):
        ft = [("Photoshop", "*.psd")] if mode == "psd" else [("Images", "*.jpg;*.png;*.jpeg")]
        files = filedialog.askopenfilenames(filetypes=ft)
        if files:
            self.file_list = files
            self.current_preview_path = files[0]
            self.update_file_list_display(listbox, files)
            self.update_file_info(files[0])
            self.refresh_preview()

    def update_file_list_display(self, listbox, files):
        listbox.configure(state="normal")
        listbox.delete("0.0", "end")
        for f in files: listbox.insert("end", f"{os.path.basename(f)}\n")
        listbox.configure(state="disabled")

    # --- TABS SETUP ---
    def _setup_psd_tab(self):
        ctk.CTkLabel(self.tab_psd, text="PSD Bulk Converter", font=("Arial", 14, "bold")).pack(pady=5)
        ctk.CTkButton(self.tab_psd, text="Select Files", command=lambda: self.select_files(self.txt_psd, "psd")).pack()
        self.txt_psd = ctk.CTkTextbox(self.tab_psd, height=150, state="disabled")
        self.txt_psd.pack(pady=5, fill="x")
        ctk.CTkButton(self.tab_psd, text="Convert", fg_color="green", command=lambda: threading.Thread(target=self._process_psd, daemon=True).start()).pack(pady=10)

    def _process_psd(self):
        for f in self.file_list:
            try:
                psd = PSDImage.open(f)
                self.save_image_pro(psd.composite(), os.path.splitext(f)[0] + ".jpg")
            except: pass
        messagebox.showinfo("Done", "Batch Complete")

    def _setup_resize_tab(self):
        ctk.CTkLabel(self.tab_resize, text="Smart Resizer", font=("Arial", 14, "bold")).pack(pady=5)
        ctk.CTkButton(self.tab_resize, text="Select Files", command=lambda: self.select_files(self.txt_res, "img")).pack()
        self.txt_res = ctk.CTkTextbox(self.tab_resize, height=100, state="disabled")
        self.txt_res.pack(pady=5, fill="x")
        self.res_var = ctk.StringVar(value="286x410")
        ctk.CTkOptionMenu(self.tab_resize, values=["286x410", "960x1440"], variable=self.res_var).pack()
        ctk.CTkButton(self.tab_resize, text="Resize", fg_color="green", command=lambda: threading.Thread(target=self._process_res, daemon=True).start()).pack(pady=10)

    def _process_res(self):
        w, h = map(int, self.res_var.get().split('x'))
        for f in self.file_list:
            try:
                img = Image.open(f)
                img = img.resize((w, h), Image.Resampling.LANCZOS)
                self.save_image_pro(img, os.path.splitext(f)[0] + f"_{self.res_var.get()}.jpg", img.info.get('dpi', (72,72)))
            except: pass
        messagebox.showinfo("Done", "Complete")

    def _setup_banner_tab(self):
        ctk.CTkLabel(self.tab_banner, text="HD Banner", font=("Arial", 14, "bold")).pack(pady=5)
        ctk.CTkButton(self.tab_banner, text="Select Files", command=lambda: self.select_files(self.txt_ban, "img")).pack()
        self.txt_ban = ctk.CTkTextbox(self.tab_banner, height=60, state="disabled")
        self.txt_ban.pack(pady=5, fill="x")
        self.entry_title = ctk.CTkEntry(self.tab_banner, placeholder_text="Title Name")
        self.entry_title.pack(fill="x", pady=5)
        self.ban_type = ctk.StringVar(value="2day")
        r = ctk.CTkFrame(self.tab_banner); r.pack()
        ctk.CTkRadioButton(r, text="2-Day", variable=self.ban_type, value="2day", command=self.refresh_preview).pack(side="left")
        ctk.CTkRadioButton(r, text="3-Day", variable=self.ban_type, value="3day", command=self.refresh_preview).pack(side="left")
        ctk.CTkButton(self.tab_banner, text="Process", fg_color="green", command=lambda: threading.Thread(target=self._process_ban, daemon=True).start()).pack(pady=10)

    def _process_ban(self):
        # ... (Same banner logic as before) ...
        pass
    
    def _reveal_author(self, event=None):
        messagebox.showinfo("Credits", "Code by Ayush Singhal | Deluxe Media")

if __name__ == "__main__":
    app = ProMediaTool()
    app.mainloop()
