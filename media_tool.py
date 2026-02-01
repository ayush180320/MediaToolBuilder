"""
APPLICATION SECURITY MANIFEST & AUDIT LOG
-----------------------------------------
App Name:       Media Workflow Studio Pro
Version:        5.0 (Manual Rename & Fixed Reset)
Author:         Ayush Singhal
Company:        Deluxe Media
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

# --- SAFE IMPORT: DRAG & DROP ---
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DRAG_DROP_AVAILABLE = True
except ImportError:
    DRAG_DROP_AVAILABLE = False
    class TkinterDnD:
        class DnDWrapper:
            pass

# --- Configuration ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

BaseClass = TkinterDnD.DnDWrapper if DRAG_DROP_AVAILABLE else object

class ProMediaTool(ctk.CTk, BaseClass):
    def __init__(self):
        super().__init__()

        self.title("Media Workflow Studio Pro v5.0")
        self.geometry("1100x700") # Increased height for rename controls
        self.minsize(1100, 700)
        
        self.bind("<Control-Alt-a>", self._reveal_author)
        
        # --- Layout ---
        self.grid_columnconfigure(0, weight=3) 
        self.grid_columnconfigure(1, weight=4) 
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT PANEL ---
        self.left_frame = ctk.CTkFrame(self, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.tab_view = ctk.CTkTabview(self.left_frame, command=self.on_tab_switch)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_psd = self.tab_view.add("PSD Bulk Converter")
        self.tab_resize = self.tab_view.add("Smart Resizer")
        self.tab_banner = self.tab_view.add("HD Banner & Rename")

        # --- RIGHT PANEL ---
        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(0,10), pady=10)
        
        # Preview Dropdown
        self.lbl_preview_title = ctk.CTkLabel(self.right_frame, text="Live Preview & Rename", font=("Roboto", 16, "bold"))
        self.lbl_preview_title.pack(pady=(20, 5))

        self.preview_selector = ctk.CTkOptionMenu(self.right_frame, dynamic_resizing=False, width=280, command=self.on_selector_change)
        self.preview_selector.set("No Files Selected")
        self.preview_selector.configure(state="disabled")
        self.preview_selector.pack(pady=5)
        
        # Preview Image
        self.lbl_preview_img = ctk.CTkLabel(self.right_frame, text="[Drag Files Here]", width=286, height=410, fg_color="#2b2b2b", corner_radius=10)
        self.lbl_preview_img.pack(pady=10, padx=20)

        # --- ONE-BY-ONE RENAME SECTION ---
        self.rename_container = ctk.CTkFrame(self.right_frame, fg_color="#222222")
        self.rename_container.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(self.rename_container, text="Edit Filename (For current selection):", font=("Arial", 11)).pack(anchor="w", padx=10, pady=(5,0))
        
        self.entry_manual_name = ctk.CTkEntry(self.rename_container, placeholder_text="Filename without extension")
        self.entry_manual_name.pack(fill="x", padx=10, pady=5)
        self.entry_manual_name.bind("<KeyRelease>", self.on_manual_rename_type) # Live update
        
        self.lbl_final_name = ctk.CTkLabel(self.rename_container, text="Output: ...", text_color="gray", font=("Courier", 11))
        self.lbl_final_name.pack(anchor="w", padx=10, pady=(0,5))
        # ----------------------------------

        self.lbl_info_title = ctk.CTkLabel(self.right_frame, text="File Information", font=("Roboto", 12, "bold"), text_color="gray70")
        self.lbl_info_title.pack(pady=(10, 0), anchor="w", padx=20)
        
        self.info_box = ctk.CTkTextbox(self.right_frame, height=60, fg_color="#222222", text_color="#00E5FF")
        self.info_box.pack(fill="x", padx=20, pady=5, side="top")
        self.info_box.insert("0.0", "Waiting for selection...")
        self.info_box.configure(state="disabled")

        # Internal State
        self.file_list = []
        self.file_names = []
        self.custom_names_map = {} # Stores {filepath: new_name}
        self.current_preview_path = None
        
        self._setup_psd_tab()
        self._setup_resize_tab()
        self._setup_banner_tab()
        
        if DRAG_DROP_AVAILABLE:
            self.TkdndVersion = TkinterDnD._require(self)
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self.drop_files_handler)

    def resource_path(self, relative_path):
        try: base_path = sys._MEIPASS
        except: base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    # --- RESET ENGINE (FIXED) ---
    def reset_ui(self):
        """Resets everything to pristine state"""
        self.file_list = []
        self.file_names = []
        self.custom_names_map = {}
        self.current_preview_path = None
        
        # 1. Reset Selector (Sequence is important to prevent getting stuck)
        self.preview_selector.configure(state="normal") 
        self.preview_selector.set("No Files Selected")
        self.preview_selector.configure(values=["No Files Selected"])
        self.preview_selector.configure(state="disabled")

        # 2. Reset Visuals
        self.lbl_preview_img.configure(image=None, text="[Drag Files Here]")
        self.entry_manual_name.delete(0, "end")
        self.lbl_final_name.configure(text="Output: ...")
        
        # 3. Reset Info Box
        self.info_box.configure(state="normal")
        self.info_box.delete("0.0", "end")
        self.info_box.insert("0.0", "Waiting for selection...")
        self.info_box.configure(state="disabled")
        
        # 4. Reset Tab Inputs
        for txt in [self.txt_psd, self.txt_res, self.txt_ban]:
            txt.configure(state="normal")
            txt.delete("0.0", "end")
            txt.configure(state="disabled")

    def on_tab_switch(self):
        self.reset_ui()

    # --- INPUT HANDLING ---
    def handle_files_input(self, files):
        if not files: return
        
        # 1. Store Data
        self.file_list = files
        self.file_names = [os.path.basename(f) for f in files]
        
        # 2. Initialize Custom Names Map (Default to original name)
        self.custom_names_map = {}
        for f in files:
            base = os.path.splitext(os.path.basename(f))[0]
            self.custom_names_map[f] = base

        # 3. Wake up Selector
        self.preview_selector.configure(state="normal")
        self.preview_selector.configure(values=self.file_names)
        self.preview_selector.set(self.file_names[0])
        
        # 4. Update Text Box
        active = self.tab_view.get()
        target_box = self.txt_psd if active == "PSD Bulk Converter" else (self.txt_res if active == "Smart Resizer" else self.txt_ban)
        
        target_box.configure(state="normal")
        target_box.delete("0.0", "end")
        for f in self.file_names: target_box.insert("end", f"{f}\n")
        target_box.configure(state="disabled")

        # 5. Load First Item
        self.current_preview_path = self.file_list[0]
        self.update_rename_fields() # Populate the rename box
        self.update_preview_logic()
        self.update_file_info(self.current_preview_path)

    def on_selector_change(self, selected_filename):
        if selected_filename == "No Files Selected" or not self.file_list: return
        try:
            index = self.file_names.index(selected_filename)
            self.current_preview_path = self.file_list[index]
            self.update_rename_fields() # Sync rename box to new selection
            self.update_preview_logic()
            self.update_file_info(self.current_preview_path)
        except ValueError: pass

    # --- RENAME LOGIC ---
    def update_rename_fields(self):
        """Populate the rename entry with stored value for this file"""
        if not self.current_preview_path: return
        
        stored_name = self.custom_names_map.get(self.current_preview_path, "")
        
        self.entry_manual_name.delete(0, "end")
        self.entry_manual_name.insert(0, stored_name)
        self._update_suffix_label(stored_name)

    def on_manual_rename_type(self, event):
        """Save text to memory as user types"""
        if not self.current_preview_path: return
        
        new_name = self.entry_manual_name.get()
        self.custom_names_map[self.current_preview_path] = new_name
        self._update_suffix_label(new_name)

    def _update_suffix_label(self, name):
        """Shows user what the final file will look like"""
        if self.tab_view.get() == "HD Banner & Rename":
            suffix = "2DayBanner_286x410" if self.ban_type.get() == "2day" else "3DayBanner_286x410"
            self.lbl_final_name.configure(text=f"Output: {name}_{suffix}.jpg")
        else:
            self.lbl_final_name.configure(text=f"Output: {name}.jpg")

    # --- DRAG & DROP ---
    def drop_files_handler(self, event):
        raw_files = event.data
        if "{" in raw_files:
            files = re.findall(r'\{.*?\}|\S+', raw_files)
            files = [f.replace("{", "").replace("}", "") for f in files]
        else:
            files = raw_files.split()
        self.handle_files_input(files)

    def select_files(self, mode):
        ft = [("Photoshop", "*.psd")] if mode == "psd" else [("Images", "*.jpg;*.png;*.jpeg")]
        files = filedialog.askopenfilenames(filetypes=ft)
        if files: self.handle_files_input(files)

    # --- FILE INFO ---
    def update_file_info(self, filepath):
        txt = "Reading..."
        try:
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if filepath.lower().endswith(".psd"):
                psd = PSDImage.open(filepath)
                w, h, fmt, mode = psd.width, psd.height, "PSD (Adobe)", psd.color_mode
            else:
                img = Image.open(filepath)
                w, h = img.size
                fmt = img.format if img.format else "Image"
                mode = img.mode
            txt = f"Dim: {w}x{h} | Type: {fmt}\nSize: {size_mb:.2f} MB"
        except Exception as e:
            txt = f"Error: {str(e)}"

        self.info_box.configure(state="normal")
        self.info_box.delete("0.0", "end")
        self.info_box.insert("0.0", txt)
        self.info_box.configure(state="disabled")

    # --- PREVIEW ENGINE ---
    def update_preview_logic(self):
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
                
                # Update label in case radio button changed
                stored = self.custom_names_map.get(self.current_preview_path, "")
                self._update_suffix_label(stored)

            img.thumbnail((286, 410), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(img, size=img.size)
            self.lbl_preview_img.configure(image=ctk_img, text="")
        except Exception as e:
            self.lbl_preview_img.configure(image="", text=f"Preview Failed\n{str(e)}")

    def refresh_preview(self):
        self.update_preview_logic()

    def save_image_pro(self, img, path, dpi=(72,72)):
        if img.mode in ("RGBA", "P", "CMYK"): img = img.convert("RGB")
        img.save(path, "JPEG", quality=100, subsampling=0, dpi=dpi)

    # --- TABS ---
    def _setup_psd_tab(self):
        ctk.CTkLabel(self.tab_psd, text="PSD Bulk Converter", font=("Arial", 14, "bold")).pack(pady=5)
        btn_frame = ctk.CTkFrame(self.tab_psd, fg_color="transparent")
        btn_frame.pack(pady=5)
        ctk.CTkButton(btn_frame, text="Select Files", command=lambda: self.select_files("psd")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Reset", fg_color="#C62828", hover_color="#B71C1C", width=80, command=self.reset_ui).pack(side="left", padx=5)
        self.txt_psd = ctk.CTkTextbox(self.tab_psd, height=150, state="disabled")
        self.txt_psd.pack(pady=5, fill="x")
        ctk.CTkButton(self.tab_psd, text="Convert All", fg_color="green", command=lambda: threading.Thread(target=self._process_psd, daemon=True).start()).pack(pady=10)

    def _process_psd(self):
        if not self.file_list: return messagebox.showwarning("Error", "No files selected")
        count = 0
        for f in self.file_list:
            try:
                out_dir = os.path.join(os.path.dirname(f), "Converted_PSD")
                os.makedirs(out_dir, exist_ok=True)
                psd = PSDImage.open(f)
                out_path = os.path.join(out_dir, os.path.basename(os.path.splitext(f)[0] + ".jpg"))
                self.save_image_pro(psd.composite(), out_path)
                count += 1
            except Exception as e: print(e)
        messagebox.showinfo("Report", f"Converted {count} files.")

    def _setup_resize_tab(self):
        ctk.CTkLabel(self.tab_resize, text="Smart Resizer", font=("Arial", 14, "bold")).pack(pady=5)
        btn_frame = ctk.CTkFrame(self.tab_resize, fg_color="transparent")
        btn_frame.pack(pady=5)
        ctk.CTkButton(btn_frame, text="Select Files", command=lambda: self.select_files("img")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Reset", fg_color="#C62828", hover_color="#B71C1C", width=80, command=self.reset_ui).pack(side="left", padx=5)
        self.txt_res = ctk.CTkTextbox(self.tab_resize, height=100, state="disabled")
        self.txt_res.pack(pady=5, fill="x")
        self.res_var = ctk.StringVar(value="286x410")
        ctk.CTkOptionMenu(self.tab_resize, values=["286x410", "960x1440", "380x560", "630x945"], variable=self.res_var).pack()
        ctk.CTkButton(self.tab_resize, text="Resize All", fg_color="green", command=lambda: threading.Thread(target=self._process_res, daemon=True).start()).pack(pady=10)

    def _process_res(self):
        if not self.file_list: return messagebox.showwarning("Error", "No files selected")
        w, h = map(int, self.res_var.get().split('x'))
        count = 0
        for f in self.file_list:
            try:
                out_dir = os.path.join(os.path.dirname(f), "Resized_Output")
                os.makedirs(out_dir, exist_ok=True)
                img = Image.open(f)
                img = img.resize((w, h), Image.Resampling.LANCZOS)
                out_path = os.path.join(out_dir, os.path.basename(os.path.splitext(f)[0] + f"_{self.res_var.get()}.jpg"))
                self.save_image_pro(img, out_path, img.info.get('dpi', (72,72)))
                count += 1
            except: pass
        messagebox.showinfo("Success", f"Resized {count} files.")

    def _setup_banner_tab(self):
        ctk.CTkLabel(self.tab_banner, text="HD Banner & Batch Rename", font=("Arial", 14, "bold")).pack(pady=5)
        
        btn_frame = ctk.CTkFrame(self.tab_banner, fg_color="transparent")
        btn_frame.pack(pady=5)
        ctk.CTkButton(btn_frame, text="Select Files", command=lambda: self.select_files("img")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Reset", fg_color="#C62828", hover_color="#B71C1C", width=80, command=self.reset_ui).pack(side="left", padx=5)
        
        self.txt_ban = ctk.CTkTextbox(self.tab_banner, height=60, state="disabled")
        self.txt_ban.pack(pady=5, fill="x")
        
        ctk.CTkLabel(self.tab_banner, text="Use the panel on the RIGHT to rename files individually.", text_color="gray").pack(pady=5)

        self.ban_type = ctk.StringVar(value="2day")
        r = ctk.CTkFrame(self.tab_banner); r.pack(pady=5)
        ctk.CTkRadioButton(r, text="2-Day Banner", variable=self.ban_type, value="2day", command=self.refresh_preview).pack(side="left", padx=10)
        ctk.CTkRadioButton(r, text="3-Day Banner", variable=self.ban_type, value="3day", command=self.refresh_preview).pack(side="left", padx=10)
        
        ctk.CTkButton(self.tab_banner, text="Process Batch", fg_color="green", command=lambda: threading.Thread(target=self._process_ban, daemon=True).start()).pack(pady=10)

    def _process_ban(self):
        if not self.file_list: return messagebox.showwarning("Error", "No files selected")
        tpl = "banner_2day.png" if self.ban_type.get() == "2day" else "banner_3day.png"
        tpl_path = self.resource_path(tpl)
        if not os.path.exists(tpl_path): return messagebox.showerror("Error", f"Missing {tpl}")
        
        count = 0
        for fpath in self.file_list:
            try:
                out_dir = os.path.join(os.path.dirname(fpath), "Banner_Output")
                os.makedirs(out_dir, exist_ok=True)
                
                # PROCESSING
                img = Image.open(fpath)
                dpi = img.info.get('dpi', (72, 72))
                img_res = img.resize((286, 371), Image.Resampling.LANCZOS)
                img_res = img_res.filter(ImageFilter.UnsharpMask(radius=0.8, percent=110, threshold=3))
                
                canvas = Image.new("RGB", (286, 410), (255, 255, 255))
                canvas.paste(img_res, (0, 0))
                banner = Image.open(tpl_path).convert("RGBA").resize((286, 410), Image.Resampling.LANCZOS)
                canvas.paste(banner, (0, 0), mask=banner)
                
                # RETRIEVE CUSTOM NAME (Or use default if map failed)
                base_name = self.custom_names_map.get(fpath, os.path.splitext(os.path.basename(fpath))[0])
                
                # Define Suffix
                suffix = "2DayBanner_286x410" if self.ban_type.get() == "2day" else "3DayBanner_286x410"
                fname = f"{base_name}_{suffix}.jpg"
                    
                self.save_image_pro(canvas, os.path.join(out_dir, fname), dpi)
                count += 1
            except Exception as e: print(e)
        messagebox.showinfo("Success", f"Processed {count} files.")

    def _reveal_author(self, event=None):
        messagebox.showinfo("Credits", "Code by Ayush Singhal | Deluxe Media")

if __name__ == "__main__":
    app = ProMediaTool()
    app.mainloop()
