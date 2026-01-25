import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from psd_tools import PSDImage
import os
import threading
import sys  # Added sys for internal path handling

# --- Configuration & Theme ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class ProMediaTool(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Media Workflow Studio Pro (Standalone)")
        self.geometry("950x650")
        
        # --- Layout ---
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # LEFT SIDE: Controls
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
        
        self.lbl_preview_title = ctk.CTkLabel(self.right_frame, text="Live Preview", font=("Roboto", 16, "bold"))
        self.lbl_preview_title.pack(pady=(20, 10))
        
        self.lbl_preview_img = ctk.CTkLabel(self.right_frame, text="[No Selection]", width=250, height=300, fg_color="#2b2b2b", corner_radius=10)
        self.lbl_preview_img.pack(pady=10, padx=20)

        self.log_box = ctk.CTkTextbox(self.right_frame, height=150)
        self.log_box.pack(fill="x", padx=10, pady=10, side="bottom")
        self.log("System Ready. Templates Embedded.")

        self.file_list = [] 

        self._setup_psd_tab()
        self._setup_resize_tab()
        self._setup_banner_tab()

    # --- CRITICAL: Resource Path Helper ---
    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    # --- UTILS ---
    def log(self, message):
        self.log_box.insert("end", f"> {message}\n")
        self.log_box.see("end")

    def show_preview(self, filepath):
        try:
            if filepath.lower().endswith(".psd"):
                self.lbl_preview_img.configure(text="Loading PSD...", image="")
                self.update()
                psd = PSDImage.open(filepath)
                img = psd.composite()
            else:
                img = Image.open(filepath)

            img.thumbnail((250, 300))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.lbl_preview_img.configure(image=ctk_img, text="")
        except Exception:
            self.lbl_preview_img.configure(text="Preview Unavailable", image="")

    def update_file_list_display(self, listbox, files):
        listbox.configure(state="normal")
        listbox.delete("0.0", "end")
        for f in files:
            listbox.insert("end", f"{os.path.basename(f)}\n")
        listbox.configure(state="disabled")
        if files: self.show_preview(files[0])

    def save_image_pro(self, img_obj, output_path, original_dpi=(72, 72)):
        if img_obj.mode in ("RGBA", "P", "CMYK"):
            img_obj = img_obj.convert("RGB")
        img_obj.save(output_path, "JPEG", quality=100, subsampling=0, dpi=original_dpi)

    def select_files(self, listbox_widget, mode):
        filetypes = [("Photoshop", "*.psd")] if mode == "psd" else [("Images", "*.jpg;*.png;*.jpeg")]
        files = filedialog.askopenfilenames(filetypes=filetypes)
        if files:
            self.file_list = files
            self.update_file_list_display(listbox_widget, files)
            self.log(f"Selected {len(files)} files.")

    # --- FEATURES ---
    def _setup_psd_tab(self):
        ctk.CTkLabel(self.tab_psd, text="Batch Convert PSD to JPG", font=("Arial", 14, "bold")).pack(pady=10)
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
                self.log(f"Converted: {os.path.basename(out)}")
            except Exception as e: self.log(f"Error: {e}")
        messagebox.showinfo("Done", "Batch Complete")

    def _setup_resize_tab(self):
        ctk.CTkLabel(self.tab_resize, text="Batch Resize 2:3 Artworks", font=("Arial", 14, "bold")).pack(pady=10)
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
                img = img.resize((w, h), Image.Resampling.LANCZOS)
                out = os.path.splitext(f)[0] + f"_{self.res_var.get()}.jpg"
                self.save_image_pro(img, out, dpi)
                self.log(f"Resized: {os.path.basename(out)}")
            except Exception as e: self.log(f"Error: {e}")
        messagebox.showinfo("Done", "Batch Complete")

    def _setup_banner_tab(self):
        ctk.CTkLabel(self.tab_banner, text="Banner Application (Embedded)", font=("Arial", 14, "bold")).pack(pady=10)
        ctk.CTkButton(self.tab_banner, text="Select Files", command=lambda: self.select_files(self.txt_ban, "img")).pack(pady=5)
        self.txt_ban = ctk.CTkTextbox(self.tab_banner, height=80, state="disabled")
        self.txt_ban.pack(pady=5, fill="x", padx=10)
        
        fr = ctk.CTkFrame(self.tab_banner, fg_color="#2b2b2b")
        fr.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(fr, text="Output Title Name:").pack(anchor="w", padx=10)
        self.entry_title = ctk.CTkEntry(fr, placeholder_text="e.g. SummerSale")
        self.entry_title.pack(fill="x", padx=10, pady=5)
        
        self.ban_type = ctk.StringVar(value="2day")
        r_frame = ctk.CTkFrame(self.tab_banner, fg_color="transparent")
        r_frame.pack(pady=5)
        ctk.CTkRadioButton(r_frame, text="2-Day", variable=self.ban_type, value="2day").pack(side="left", padx=10)
        ctk.CTkRadioButton(r_frame, text="3-Day", variable=self.ban_type, value="3day").pack(side="left", padx=10)
        
        ctk.CTkButton(self.tab_banner, text="Process Banners", fg_color="green", command=lambda: threading.Thread(target=self._process_ban, daemon=True).start()).pack(pady=15)

    def _process_ban(self):
        art_w, art_h, final_w, final_h = 286, 371, 286, 410
        # CRITICAL: Use resource_path to find the internal image
        tpl_name = "banner_2day.png" if self.ban_type.get() == "2day" else "banner_3day.png"
        tpl_path = self.resource_path(tpl_name)

        if not os.path.exists(tpl_path):
            messagebox.showerror("Error", f"Internal Error: Cannot find {tpl_name}")
            return

        user_title = self.entry_title.get().strip()

        for i, fpath in enumerate(self.file_list):
            try:
                img = Image.open(fpath)
                dpi = img.info.get('dpi', (72, 72))
                img_res = img.resize((art_w, art_h), Image.Resampling.LANCZOS)
                
                canvas = Image.new("RGB", (final_w, final_h), (255, 255, 255))
                canvas.paste(img_res, (0, 0))
                
                banner = Image.open(tpl_path).convert("RGBA")
                if banner.size != (final_w, final_h):
                    banner = banner.resize((final_w, final_h), Image.Resampling.LANCZOS)
                canvas.paste(banner, (0, 0), mask=banner)

                suffix = "2DayBanner_286x410" if self.ban_type.get() == "2day" else "3DayBanner_286x410"
                if user_title:
                    fname = f"{user_title}_{i+1:02d}_{suffix}.jpg" if len(self.file_list) > 1 else f"{user_title}_{suffix}.jpg"
                else:
                    fname = os.path.splitext(os.path.basename(fpath))[0] + f"_{suffix}.jpg"

                self.save_image_pro(canvas, os.path.join(os.path.dirname(fpath), fname), dpi)
                self.log(f"Created: {fname}")
            except Exception as e: self.log(f"Error: {e}")
        messagebox.showinfo("Success", "Banner Batch Completed")

if __name__ == "__main__":
    app = ProMediaTool()
    app.mainloop()
