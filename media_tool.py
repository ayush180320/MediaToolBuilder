import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from psd_tools import PSDImage
import os
import threading
import time

# --- Configuration & Theme ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class ProMediaTool(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Media Workflow Studio Pro")
        self.geometry("900x650")
        self.resizable(True, True)

        # --- Layout: Split into Left (Controls) and Right (Preview/Log) ---
        self.grid_columnconfigure(0, weight=3) # Controls
        self.grid_columnconfigure(1, weight=2) # Preview
        self.grid_rowconfigure(0, weight=1)

        # LEFT SIDE: Controls (Tabs)
        self.left_frame = ctk.CTkFrame(self, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.tab_view = ctk.CTkTabview(self.left_frame)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_psd = self.tab_view.add("PSD Bulk Converter")
        self.tab_resize = self.tab_view.add("Smart Resizer")
        self.tab_banner = self.tab_view.add("Banner & Rename")

        # RIGHT SIDE: Preview & Logs
        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(0,10), pady=10)
        
        # Preview Area
        self.lbl_preview_title = ctk.CTkLabel(self.right_frame, text="Live Preview", font=("Roboto", 16, "bold"))
        self.lbl_preview_title.pack(pady=(20, 10))
        
        self.lbl_preview_img = ctk.CTkLabel(self.right_frame, text="[No Selection]", width=250, height=300, fg_color="#2b2b2b", corner_radius=10)
        self.lbl_preview_img.pack(pady=10, padx=20)

        # Log Area
        self.log_box = ctk.CTkTextbox(self.right_frame, height=150)
        self.log_box.pack(fill="x", padx=10, pady=10, side="bottom")
        self.log("Welcome to Pro Media Studio. Ready.")

        # Shared Variables
        self.file_list = [] 

        self._setup_psd_tab()
        self._setup_resize_tab()
        self._setup_banner_tab()

    # --- UTILS ---
    def log(self, message):
        self.log_box.insert("end", f"> {message}\n")
        self.log_box.see("end")

    def show_preview(self, filepath):
        """Generates a thumbnail for the preview window"""
        try:
            # Handle PSDs differently (slower)
            if filepath.lower().endswith(".psd"):
                self.lbl_preview_img.configure(text="Loading PSD...", image="")
                self.update() # Force UI update
                psd = PSDImage.open(filepath)
                img = psd.composite()
            else:
                img = Image.open(filepath)

            # Resize for preview (Thumbnail only)
            img.thumbnail((250, 300))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            
            self.lbl_preview_img.configure(image=ctk_img, text="")
        except Exception as e:
            self.lbl_preview_img.configure(text="Preview Unavailable", image="")
            print(e)

    def update_file_list_display(self, listbox, files):
        listbox.configure(state="normal")
        listbox.delete("0.0", "end")
        for f in files:
            listbox.insert("end", f"{os.path.basename(f)}\n")
        listbox.configure(state="disabled")
        
        # Preview the first file
        if files:
            self.show_preview(files[0])

    def save_image_pro(self, img_obj, output_path, original_dpi=(72, 72)):
        if img_obj.mode in ("RGBA", "P", "CMYK"):
            img_obj = img_obj.convert("RGB")
        img_obj.save(output_path, "JPEG", quality=100, subsampling=0, dpi=original_dpi)

    # ----------------------------------------------------------------
    # FEATURE 1: PSD BULK
    # ----------------------------------------------------------------
    def _setup_psd_tab(self):
        ctk.CTkLabel(self.tab_psd, text="Batch Convert PSD to JPG", font=("Arial", 14, "bold")).pack(pady=10)
        
        btn_select = ctk.CTkButton(self.tab_psd, text="Select Files (Bulk)", command=lambda: self.select_files(self.txt_psd_list, "psd"))
        btn_select.pack(pady=5)

        self.txt_psd_list = ctk.CTkTextbox(self.tab_psd, height=150, state="disabled")
        self.txt_psd_list.pack(pady=10, fill="x", padx=10)

        btn_run = ctk.CTkButton(self.tab_psd, text="Process Batch", fg_color="green", command=self.run_psd_batch)
        btn_run.pack(pady=20)

    def select_files(self, listbox_widget, mode):
        filetypes = [("Photoshop", "*.psd")] if mode == "psd" else [("Images", "*.jpg;*.png;*.jpeg")]
        files = filedialog.askopenfilenames(filetypes=filetypes)
        if files:
            self.file_list = files
            self.update_file_list_display(listbox_widget, files)
            self.log(f"Selected {len(files)} files.")

    def run_psd_batch(self):
        threading.Thread(target=self._process_psd_batch, daemon=True).start()

    def _process_psd_batch(self):
        total = len(self.file_list)
        for i, fpath in enumerate(self.file_list):
            try:
                self.log(f"Processing ({i+1}/{total}): {os.path.basename(fpath)}")
                psd = PSDImage.open(fpath)
                img = psd.composite()
                out = os.path.splitext(fpath)[0] + ".jpg"
                self.save_image_pro(img, out)
            except Exception as e:
                self.log(f"Error on {os.path.basename(fpath)}: {e}")
        self.log("Batch Complete!")
        messagebox.showinfo("Done", "PSD Batch Processing Complete")

    # ----------------------------------------------------------------
    # FEATURE 2: RESIZE BULK
    # ----------------------------------------------------------------
    def _setup_resize_tab(self):
        ctk.CTkLabel(self.tab_resize, text="Batch Resize 2:3 Artworks", font=("Arial", 14, "bold")).pack(pady=10)
        
        btn_select = ctk.CTkButton(self.tab_resize, text="Select Files (Bulk)", command=lambda: self.select_files(self.txt_res_list, "img"))
        btn_select.pack(pady=5)

        self.txt_res_list = ctk.CTkTextbox(self.tab_resize, height=100, state="disabled")
        self.txt_res_list.pack(pady=10, fill="x", padx=10)

        self.res_var = ctk.StringVar(value="286x410")
        sizes = ["286x410", "960x1440", "380x560", "630x945"]
        ctk.CTkOptionMenu(self.tab_resize, values=sizes, variable=self.res_var).pack(pady=10)

        btn_run = ctk.CTkButton(self.tab_resize, text="Resize All", fg_color="green", command=self.run_res_batch)
        btn_run.pack(pady=20)

    def run_res_batch(self):
        threading.Thread(target=self._process_res_batch, daemon=True).start()

    def _process_res_batch(self):
        target_str = self.res_var.get()
        w, h = map(int, target_str.split('x'))
        
        for fpath in self.file_list:
            try:
                img = Image.open(fpath)
                dpi = img.info.get('dpi', (72, 72))
                img_res = img.resize((w, h), Image.Resampling.LANCZOS)
                
                out = os.path.splitext(fpath)[0] + f"_{target_str}.jpg"
                self.save_image_pro(img_res, out, dpi)
                self.log(f"Resized: {os.path.basename(out)}")
            except Exception as e:
                self.log(f"Error: {e}")
        messagebox.showinfo("Done", "Resize Batch Complete")

    # ----------------------------------------------------------------
    # FEATURE 3: BANNER & RENAME
    # ----------------------------------------------------------------
    def _setup_banner_tab(self):
        ctk.CTkLabel(self.tab_banner, text="Banner Application", font=("Arial", 14, "bold")).pack(pady=10)
        
        btn_select = ctk.CTkButton(self.tab_banner, text="Select Files (Bulk)", command=lambda: self.select_files(self.txt_ban_list, "img"))
        btn_select.pack(pady=5)

        self.txt_ban_list = ctk.CTkTextbox(self.tab_banner, height=80, state="disabled")
        self.txt_ban_list.pack(pady=5, fill="x", padx=10)

        # Renaming Section
        frame_rename = ctk.CTkFrame(self.tab_banner, fg_color="#2b2b2b")
        frame_rename.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(frame_rename, text="Output Title Name:", font=("Arial", 11)).pack(anchor="w", padx=10, pady=(5,0))
        self.entry_title = ctk.CTkEntry(frame_rename, placeholder_text="e.g. SummerSale (Leave empty to keep filename)")
        self.entry_title.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(frame_rename, text="Format: [Title]_2DayBanner_286x410.jpg", text_color="gray", font=("Arial", 10)).pack(anchor="w", padx=10, pady=(0,5))

        # Banner Type
        self.ban_type = ctk.StringVar(value="2day")
        r_frame = ctk.CTkFrame(self.tab_banner, fg_color="transparent")
        r_frame.pack(pady=5)
        ctk.CTkRadioButton(r_frame, text="2-Day", variable=self.ban_type, value="2day").pack(side="left", padx=10)
        ctk.CTkRadioButton(r_frame, text="3-Day", variable=self.ban_type, value="3day").pack(side="left", padx=10)

        btn_run = ctk.CTkButton(self.tab_banner, text="Process Banners", fg_color="green", command=self.run_ban_batch)
        btn_run.pack(pady=15)

    def run_ban_batch(self):
        threading.Thread(target=self._process_ban_batch, daemon=True).start()

    def _process_ban_batch(self):
        art_w, art_h = 286, 371
        final_w, final_h = 286, 410
        tpl_name = "banner_2day.png" if self.ban_type.get() == "2day" else "banner_3day.png"
        
        if not os.path.exists(tpl_name):
            messagebox.showerror("Error", f"Missing {tpl_name}")
            return

        user_title = self.entry_title.get().strip() # Get the custom name

        for i, fpath in enumerate(self.file_list):
            try:
                img = Image.open(fpath)
                dpi = img.info.get('dpi', (72, 72))
                
                # Resize Art
                img_res = img.resize((art_w, art_h), Image.Resampling.LANCZOS)
                
                # Composite
                canvas = Image.new("RGB", (final_w, final_h), (255, 255, 255))
                canvas.paste(img_res, (0, 0))
                
                banner = Image.open(tpl_name).convert("RGBA")
                if banner.size != (final_w, final_h):
                    banner = banner.resize((final_w, final_h), Image.Resampling.LANCZOS)
                canvas.paste(banner, (0, 0), mask=banner)

                # --- RENAMING LOGIC ---
                suffix = "2DayBanner_286x410" if self.ban_type.get() == "2day" else "3DayBanner_286x410"
                
                if user_title:
                    # If processing multiple files with one title, append number: Title_01_2Day...
                    if len(self.file_list) > 1:
                        fname = f"{user_title}_{i+1:02d}_{suffix}.jpg"
                    else:
                        fname = f"{user_title}_{suffix}.jpg"
                else:
                    # Keep original name
                    fname = os.path.splitext(os.path.basename(fpath))[0] + f"_{suffix}.jpg"

                out_path = os.path.join(os.path.dirname(fpath), fname)
                
                self.save_image_pro(canvas, out_path, dpi)
                self.log(f"Created: {fname}")
                
            except Exception as e:
                self.log(f"Error: {e}")
        
        messagebox.showinfo("Success", "Banner Batch Completed")

if __name__ == "__main__":
    app = ProMediaTool()
    app.mainloop()
