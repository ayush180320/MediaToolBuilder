"""
APPLICATION SECURITY MANIFEST & AUDIT LOG
-----------------------------------------
App Name:       Media Workflow Studio Pro
Version:        3.0 (Drag & Drop + Live Preview)
Author:         Ayush Singhal
Company:        Deluxe Media
Created:        2025
Purpose:        Local image manipulation (Resizing, PSD Conversion, Formatting).

SECURITY SCOPE:
  1. NETWORK:   BLOCKED. No network libraries are used. Works 100% Offline.
  2. FILESYSTEM: RESTRICTED. Only reads/writes in user-selected directories.
  3. TELEMETRY: NONE. No data is collected or sent.

COPYRIGHT NOTICE:
The logic and architecture of this script were authored by Ayush Singhal for Deluxe Media.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from PIL import Image, ImageTk, ImageFilter
from psd_tools import PSDImage
import os
import threading
import sys
import re

# --- Configuration & Theme ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Inherit from CTk and the DnD wrapper to enable Drag and Drop
class ProMediaTool(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        
        # Initialize Drag & Drop capability
        self.TkdndVersion = TkinterDnD._require(self)

        self.title("Media Workflow Studio Pro")
        self.geometry("1000x700")

        # --- HIDDEN AUTHOR SIGNATURE (EASTER EGG) ---
        # Press Control + Alt + A to reveal authorship
        self.bind("<Control-Alt-a>", self._reveal_author)
        self._author_signature = "Code by Ayush Singhal | Deluxe Media"
        
        # --- Layout Grid Configuration ---
        self.grid_columnconfigure(0, weight=3) # Left Control Panel
        self.grid_columnconfigure(1, weight=2) # Right Preview Panel
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT PANEL: Controls ---
        self.left_frame = ctk.CTkFrame(self, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.tab_view = ctk.CTkTabview(self.left_frame)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_psd = self.tab_view.add("PSD Bulk Converter")
        self.tab_resize = self.tab_view.add("Smart Resizer")
        self.tab_banner = self.tab_view.add("HD Banner & Rename")

        # --- RIGHT PANEL: Preview & Info ---
        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(0,10), pady=10)
        
        self.lbl_preview_title = ctk.CTkLabel(self.right_frame, text="Live Preview", font=("Roboto", 16, "bold"))
        self.lbl_preview_title.pack(pady=(20, 10))
        
        # Preview Image Box
        self.lbl_preview_img = ctk.CTkLabel(self.right_frame, text="[Drag Files Here]", width=286, height=410, fg_color="#2b2b2b", corner_radius=10)
        self.lbl_preview_img.pack(pady=10, padx=20)

        # File Info Panel (Replaces Log Box)
        self.lbl_info_title = ctk.CTkLabel(self.right_frame, text="File Information", font=("Roboto", 12, "bold"), text_color="gray70")
        self.lbl_info_title.pack(pady=(20, 0), anchor="w", padx=10)
        
        self.info_box = ctk.CTkTextbox(self.right_frame, height=120, fg_color="#222222", text_color="#00E5FF")
        self.info_box.pack(fill="x", padx=10, pady=5, side="top")
        self.info_box.insert("0.0", "Waiting for selection...")
        self.info_box.configure(state="disabled")

        # Internal State
        self.file_list = []
        self.current_preview_path = None # Tracks valid path for live preview
        self.current_tab = "psd" # Track active tab

        # Initialize Tabs
        self._setup_psd_tab()
        self._setup_resize_tab()
        self._setup_banner_tab()
        
        # --- ENABLE DRAG & DROP ---
        # Bind the drop event to the whole window
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.drop_files_handler)

    # --- CORE UTILITY: Resource Path ---
    def resource_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    # --- DRAG & DROP HANDLER ---
    def drop_files_handler(self, event):
        raw_files = event.data
        # Windows Drag&Drop formats paths with {} if they contain spaces. Regex fixes this.
        if "{" in raw_files:
            files = re.findall(r'\{.*?\}|\S+', raw_files)
            files = [f.replace("{", "").replace("}", "") for f in files]
        else:
            files = raw_files.split()
        
        if files:
            self.file_list = files
            self.current_preview_path = files[0]
            
            # Update the text box of the currently active tab
            active_tab = self.tab_view.get()
            if active_tab == "PSD Bulk Converter":
                self.update_file_list_display(self.txt_psd, files)
            elif active_tab == "Smart Resizer":
                self.update_file_list_display(self.txt_res, files)
            elif active_tab == "HD Banner & Rename":
                self.update_file_list_display(self.txt_ban, files)

            # Trigger File Info & Preview
            self.update_file_info(files[0])
            self.refresh_preview()

    # --- FILE INFO PANEL ---
    def update_file_info(self, filepath):
        try:
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            
            if filepath.lower().endswith(".psd"):
                psd = PSDImage.open(filepath)
                w, h = psd.width, psd.height
                fmt = "PSD (Adobe)"
                mode = psd.color_mode
            else:
                img = Image.open(filepath)
                w, h = img.size
                fmt = img.format
                mode = img.mode
                
            info_text = (
                f"Filename: {os.path.basename(filepath)}\n"
                f"Dimensions: {w} x {h} px\n"
                f"Format: {fmt} | Mode: {mode}\n"
                f"Size: {size_mb:.2f} MB"
            )
        except Exception as e:
            info_text = f"Could not read file info.\nError: {str(e)}"

        self.info_box.configure(state="normal")
        self.info_box.delete("0.0", "end")
        self.info_box.insert("0.0", info_text)
        self.info_box.configure(state="disabled")

    # --- LIVE PREVIEW ENGINE ---
    def refresh_preview(self):
        """ 
        Smart Preview that changes based on Context (Tab + Selected Options) 
        """
        if not self.current_preview_path:
            return

        try:
            # 1. Load Base Image
            if self.current_preview_path.lower().endswith(".psd"):
                psd = PSDImage.open(self.current_preview_path)
                img = psd.composite()
            else:
                img = Image.open(self.current_preview_path)

            active_tab = self.tab_view.get()

            # 2. IF BANNER TAB: Apply Live Composition
            if active_tab == "HD Banner & Rename":
                
                # Configuration for Preview (Same as Production)
                art_w, art_h = 286, 371
                final_w, final_h = 286, 410
                
                # Resize Art
                img = img.resize((art_w, art_h), Image.Resampling.LANCZOS)
                
                # Create Canvas
                canvas = Image.new("RGB", (final_w, final_h), (255, 255, 255))
                canvas.paste(img, (0, 0))
                
                # Load Banner Template
                tpl_name = "banner_2day.png" if self.ban_type.get() == "2day" else "banner_3day.png"
                tpl_path = self.resource_path(tpl_name)
                
                if os.path.exists(tpl_path):
                    banner = Image.open(tpl_path).convert("RGBA")
                    if banner.size != (final_w, final_h):
                        banner = banner.resize((final_w, final_h), Image.Resampling.LANCZOS)
                    # Overlay Banner on Preview
                    canvas.paste(banner, (0, 0), mask=banner)
                    img = canvas # The preview is now the composited banner
                else:
                    print("Template not found for preview")

            # 3. Display Result
            # Scale down for UI fits
            img.thumbnail((286, 410)) 
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.lbl_preview_img.configure(image=ctk_img, text="")
            
        except Exception as e:
            self.lbl_preview_img.configure(text=f"Preview Error", image="")
            print(e)

    def save_image_pro(self, img_obj, output_path, original_dpi=(72, 72)):
        if img_obj.mode in ("RGBA", "P", "CMYK"):
            img_obj = img_obj.convert("RGB")
        img_obj.save(output_path, "JPEG", quality=100, subsampling=0, dpi=original_dpi)

    def select_files(self, listbox_widget, mode):
        filetypes = [("Photoshop", "*.psd")] if mode == "psd" else [("Images", "*.jpg;*.png;*.jpeg")]
        files = filedialog.askopenfilenames(filetypes=filetypes)
        if files:
            self.file_list = files
            self.current_preview_path = files[0]
            self.update_file_list_display(listbox_widget, files)
            self.update_file_info(files[0])
            self.refresh_preview()

    def update_file_list_display(self, listbox, files):
        listbox.configure(state="normal")
        listbox.delete("0.0", "end")
        for f in files:
            listbox.insert("end", f"{os.path.basename(f)}\n")
        listbox.configure(state="disabled")

    # --- FEATURE 1: PSD CONVERSION ---
    def _setup_psd_tab(self):
        ctk.CTkLabel(self.tab_psd, text="Drag PSD files here", font=("Arial", 14, "bold"), text_color="gray50").pack(pady=10)
        ctk.CTkButton(self.tab_psd, text="Select Files", command=lambda: self.select_files(self.txt_psd, "psd")).pack(pady=5)
        self.txt_psd = ctk.CTkTextbox(self.tab_psd, height=150, state="disabled")
        self.txt_psd.pack(pady=10, fill="x", padx=10)
        ctk.CTkButton(self.tab_psd, text="Process Batch", fg_color="green", command=lambda: threading.Thread(target=self._process_psd, daemon=True).start()).pack(pady=20)

    def _process_psd(self):
        for f in self.file_list:
            try:
                psd = PSDImage.open(f)
                img = psd.composite()
                out = os.path.splitext(f)[0] + ".jpg"
                self.save_image_pro(img, out)
            except Exception: pass
        messagebox.showinfo("Done", "Batch Complete")

    # --- FEATURE 2: SMART RESIZING ---
    def _setup_resize_tab(self):
        ctk.CTkLabel(self.tab_resize, text="Drag Images here", font=("Arial", 14, "bold"), text_color="gray50").pack(pady=10)
        ctk.CTkButton(self.tab_resize, text="Select Files", command=lambda: self.select_files(self.txt_res, "img")).pack(pady=5)
        self.txt_res = ctk.CTkTextbox(self.tab_resize, height=100, state="disabled")
        self.txt_res.pack(pady=10, fill="x", padx=10)
        self.res_var = ctk.StringVar(value="286x410")
        ctk.CTkOptionMenu(self.tab_resize, values=["286x410", "960x1440", "380x560", "630x945"], variable=self.res_var).pack(pady=10)
        ctk.CTkButton(self.tab_resize, text="Resize All", fg_color="green", command=lambda: threading.Thread(target=self._process_res, daemon=True).start()).pack(pady=20)

    def _process_res(self):
        w, h = map(int, self.res_var.get().split('x'))
        for f in self.file_list:
            try:
                img = Image.open(f)
                dpi = img.info.get('dpi', (72, 72))
                img = img.resize((w, h), Image.Resampling.LANCZOS) # No sharpening here
                out = os.path.splitext(f)[0] + f"_{self.res_var.get()}.jpg"
                self.save_image_pro(img, out, dpi)
            except Exception: pass
        messagebox.showinfo("Done", "Batch Complete")

    # --- FEATURE 3: HD BANNER ---
    def _setup_banner_tab(self):
        ctk.CTkLabel(self.tab_banner, text="Live Banner Preview", font=("Arial", 14, "bold")).pack(pady=10)
        ctk.CTkButton(self.tab_banner, text="Select Files", command=lambda: self.select_files(self.txt_ban, "img")).pack(pady=5)
        self.txt_ban = ctk.CTkTextbox(self.tab_banner, height=80, state="disabled")
        self.txt_ban.pack(pady=5, fill="x", padx=10)
        
        # Renaming
        fr = ctk.CTkFrame(self.tab_banner, fg_color="#2b2b2b")
        fr.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(fr, text="Output Title Name:").pack(anchor="w", padx=10)
        self.entry_title = ctk.CTkEntry(fr, placeholder_text="e.g. SummerSale")
        self.entry_title.pack(fill="x", padx=10, pady=5)
        
        # Banner Selection with LIVE PREVIEW TRIGGER
        self.ban_type = ctk.StringVar(value="2day")
        r_frame = ctk.CTkFrame(self.tab_banner, fg_color="transparent")
        r_frame.pack(pady=5)
        
        # Adding command=self.refresh_preview to update image instantly when clicked
        ctk.CTkRadioButton(r_frame, text="2-Day", variable=self.ban_type, value="2day", command=self.refresh_preview).pack(side="left", padx=10)
        ctk.CTkRadioButton(r_frame, text="3-Day", variable=self.ban_type, value="3day", command=self.refresh_preview).pack(side="left", padx=10)
        
        ctk.CTkButton(self.tab_banner, text="Process Banners", fg_color="green", command=lambda: threading.Thread(target=self._process_ban, daemon=True).start()).pack(pady=15)

    def _process_ban(self):
        art_w, art_h, final_w, final_h = 286, 371, 286, 410
        tpl_name = "banner_2day.png" if self.ban_type.get() == "2day" else "banner_3day.png"
        tpl_path = self.resource_path(tpl_name)
        user_title = self.entry_title.get().strip()

        if not os.path.exists(tpl_path):
            messagebox.showerror("Error", f"Missing {tpl_name}")
            return

        for i, fpath in enumerate(self.file_list):
            try:
                img = Image.open(fpath)
                dpi = img.info.get('dpi', (72, 72))
                img_res = img.resize((art_w, art_h), Image.Resampling.LANCZOS)
                img_res = img_res.filter(ImageFilter.UnsharpMask(radius=0.8, percent=110, threshold=3))
                
                canvas = Image.new("RGB", (final_w, final_h), (255, 255, 255))
                canvas.paste(img_res, (0, 0))
                banner = Image.open(tpl_path).convert("RGBA")
                if banner.size != (final_w, final_h):
                    banner = banner.resize((final_w, final_h), Image.Resampling.LANCZOS)
                canvas.paste(banner, (0, 0), mask=banner)

                suffix = "2DayBanner_286x410" if self.ban_type.get() == "2day" else "3DayBanner_286x410"
                fname = f"{user_title}_{i+1:02d}_{suffix}.jpg" if user_title and len(self.file_list) > 1 else (f"{user_title}_{suffix}.jpg" if user_title else os.path.splitext(os.path.basename(fpath))[0] + f"_{suffix}.jpg")
                
                self.save_image_pro(canvas, os.path.join(os.path.dirname(fpath), fname), dpi)
            except Exception: pass
        messagebox.showinfo("Success", "HD Banners Created")

    def _reveal_author(self, event=None):
        messagebox.showinfo("Developer Signature", "MEDIA WORKFLOW STUDIO PRO v3.0\nAyush Singhal | Deluxe Media")

if __name__ == "__main__":
    app = ProMediaTool()
    app.mainloop()
