import tkinter as tk
from tkinter import filedialog, messagebox
import logging
import sys
import os
from PIL import Image, ImageTk
try:
    import fitz  # PyMuPDF
except ImportError:
    messagebox.showerror("Error", "PyMuPDF is not installed. Install it using 'pip install PyMuPDF'.")
    sys.exit(1)

# Helper function for PyInstaller resource paths
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Set up logging
log_file = resource_path("pdf_reader.log")
logging.basicConfig(filename=log_file, level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Check PyMuPDF version
PYMUPDF_VERSION = tuple(map(int, fitz.__version__.split('.')))
logging.info(f"PyMuPDF version: {fitz.__version__}")

class PDFReaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple PDF Reader (PyMuPDF)")
        self.root.geometry("800x600")
        self.pdf_doc = None
        self.current_page = 0
        self.zoom_factor = 1.0
        self.search_results = []
        self.current_search_index = -1
        self.vertical_scrollbar = None
        self.thumbnails_visible = False

        # Control Frame
        self.control_frame = tk.Frame(self.root, bg="lightgray")
        self.control_frame.pack(fill=tk.X, side=tk.TOP, pady=5)

        # Buttons
        button_width = 14
        col = 0
        tk.Button(self.control_frame, text="Open PDF", command=self.open_pdf, width=button_width, height=1).grid(row=0, column=col, padx=5, pady=5); col += 1
        tk.Button(self.control_frame, text="Page Up", command=self.prev_page, width=button_width, height=1).grid(row=0, column=col, padx=5, pady=5); col += 1
        tk.Button(self.control_frame, text="Page Down", command=self.next_page, width=button_width, height=1).grid(row=0, column=col, padx=5, pady=5); col += 1

        # Search
        self.search_var = tk.StringVar()
        tk.Entry(self.control_frame, textvariable=self.search_var, width=20).grid(row=0, column=col, padx=5, pady=5); col += 1
        tk.Button(self.control_frame, text="Search", command=self.search_text, width=button_width, height=1).grid(row=0, column=col, padx=5, pady=5); col += 1
        tk.Button(self.control_frame, text="Next Match", command=self.next_search, width=button_width, height=1).grid(row=0, column=col, padx=5, pady=5); col += 1

        # Zoom & View
        tk.Button(self.control_frame, text="Zoom In", command=self.zoom_in, width=button_width, height=1).grid(row=0, column=col, padx=5, pady=5); col += 1
        tk.Button(self.control_frame, text="Zoom Out", command=self.zoom_out, width=button_width, height=1).grid(row=0, column=col, padx=5, pady=5); col += 1
        tk.Button(self.control_frame, text="Fit to Window", command=self.fit_to_window, width=button_width, height=1).grid(row=0, column=col, padx=5, pady=5); col += 1
        tk.Button(self.control_frame, text="Show/Hide Thumbs", command=self.toggle_thumbnails, width=button_width, height=1).grid(row=0, column=col, padx=5, pady=5); col += 1

        # Page Label
        self.page_label = tk.Label(self.control_frame, text="Page: 0/0", width=10)
        self.page_label.grid(row=0, column=col, padx=5, pady=5); col += 1

        # About
        tk.Button(self.control_frame, text="About", command=self.show_about, width=button_width, height=1).grid(row=0, column=col, padx=5, pady=5)

        # Main Frame
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas Frame
        self.canvas_frame = tk.Frame(self.main_frame)
        self.canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(self.canvas_frame, bg="white")
        self.h_scrollbar = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.h_scrollbar.set)
        self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas.create_text(300, 200, text="No PDF loaded. Click 'Open PDF' to start.", font=("Arial", 12))

        # Thumbnail Sidebar
        self.thumbnail_frame = tk.Frame(self.main_frame, width=150, bg="lightgray")
        self.thumbnail_canvas = tk.Canvas(self.thumbnail_frame, width=150, bg="lightgray")
        self.thumbnail_scrollbar = tk.Scrollbar(self.thumbnail_frame, orient=tk.VERTICAL, command=self.thumbnail_canvas.yview)
        self.thumbnail_canvas.configure(yscrollcommand=self.thumbnail_scrollbar.set)
        self.thumbnail_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.thumbnail_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.thumbnail_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.thumbnail_frame.pack_forget()

        # Bottom Status
        self.bottom_frame = tk.Frame(self.root, bg="lightgray")
        self.bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = tk.Label(self.bottom_frame, text="No PDF loaded", anchor=tk.W, bg="lightgray")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.zoom_label = tk.Label(self.bottom_frame, text="Zoom: 100%", anchor=tk.E, bg="lightgray")
        self.zoom_label.pack(side=tk.RIGHT, padx=5)

        # Enhanced Bindings
        self.canvas.bind("<MouseWheel>", self._on_canvas_mousewheel)
        self.canvas.bind("<Button-4>", lambda e: self._scroll_page(-1))
        self.canvas.bind("<Button-5>", lambda e: self._scroll_page(1))
        self.canvas.bind("<Double-Button-1>", self._double_click_zoom)
        self.root.bind("<Configure>", lambda e: self._resize_update())

        self.image_tk = None
        self.thumbnail_images = []
        self.animation_id = None
        logging.info("GUI initialized (Light mode only)")

    def _double_click_zoom(self, event):
        if not self.pdf_doc:
            return
        x, y = event.x, event.y
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        pix = self.pdf_doc[self.current_page].get_pixmap(matrix=fitz.Matrix(2.0 * self.zoom_factor, 2.0 * self.zoom_factor))
        x_offset = max(0, (canvas_width - pix.width) // 2)
        y_offset = max(0, (canvas_height - pix.height) // 2)
        click_x = x - x_offset
        click_y = y - y_offset
        if 0 <= click_x <= pix.width and 0 <= click_y <= pix.height:
            if self.zoom_factor < 2.0:
                self.zoom_factor *= 1.5
            else:
                self.zoom_factor /= 1.5
            self.update_page()
            self.zoom_label.config(text=f"Zoom: {int(self.zoom_factor * 100)}%")
            self.canvas.yview_moveto((click_y / pix.height) - 0.3)
            logging.debug(f"Double-click zoom at ({click_x}, {click_y})")

    def _smooth_scroll(self, target_y):
        if self.animation_id:
            self.root.after_cancel(self.animation_id)
        current_y = self.canvas.yview()[0]
        steps = 10
        step = (target_y - current_y) / steps
        def animate(i=0):
            if i < steps:
                self.canvas.yview_moveto(current_y + step * (i + 1))
                self.animation_id = self.root.after(10, animate, i + 1)
            else:
                self.animation_id = None
        animate()

    def _on_canvas_mousewheel(self, event):
        if not self.pdf_doc:
            return
        scroll_pos = self.canvas.yview()
        at_top = scroll_pos[0] <= 0.0
        at_bottom = scroll_pos[1] >= 1.0
        delta = event.delta

        if delta > 0:  # Scroll up
            if at_top and self.current_page > 0:
                self.prev_page()
                self._smooth_scroll(1.0)
            else:
                self.canvas.yview_scroll(-1, "units")
        elif delta < 0:  # Scroll down
            if at_bottom and self.current_page < self.pdf_doc.page_count - 1:
                self.next_page()
                self._smooth_scroll(0.0)
            else:
                self.canvas.yview_scroll(1, "units")

    def _scroll_page(self, direction):
        if not self.pdf_doc:
            return
        scroll_pos = self.canvas.yview()
        at_top = scroll_pos[0] <= 0.0
        at_bottom = scroll_pos[1] >= 1.0

        if direction < 0:  # Scroll up
            if at_top and self.current_page > 0:
                self.prev_page()
                self._smooth_scroll(1.0)
            else:
                self.canvas.yview_scroll(-3, "units")
        else:  # Scroll down
            if at_bottom and self.current_page < self.pdf_doc.page_count - 1:
                self.next_page()
                self._smooth_scroll(0.0)
            else:
                self.canvas.yview_scroll(3, "units")

    def _resize_update(self):
        if self.pdf_doc:
            self.update_page()

    def show_about(self):
        about_message = (
            "Simple PDF Reader v2.0\n\n"
            "Project Owner / Contributor: H Vikram Kondapalli\n"
            "Code Generator: Grok, created by xAI\n\n"
            "Features:\n"
            "- Smooth animated scroll\n"
            "- Double-click to zoom\n"
            "- Search with highlighting\n"
            "- Thumbnail sidebar\n"
            "- Fit to window\n\n"
            "Built with Python, PyMuPDF, Pillow, and Tkinter."
        )
        messagebox.showinfo("About Simple PDF Reader", about_message)

    def open_pdf(self, file_path=None):
        if not file_path:
            file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if file_path:
            try:
                self.pdf_doc = fitz.open(file_path)
                if self.pdf_doc.is_encrypted:
                    raise ValueError("Encrypted PDF")
                if self.pdf_doc.page_count == 0:
                    raise ValueError("Empty PDF")
                self.current_page = 0
                self.zoom_factor = 0.85
                self.update_page()
                self.update_thumbnails()
                self.page_label.config(text=f"Page: {self.current_page + 1}/{self.pdf_doc.page_count}")
                self.status_label.config(text=f"Loaded: {os.path.basename(file_path)}")
                self.zoom_label.config(text=f"Zoom: {int(self.zoom_factor * 100)}%")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open PDF: {str(e)}")
                self.pdf_doc = None

    def update_page(self):
        if not self.pdf_doc:
            return
        try:
            page = self.pdf_doc[self.current_page]
            zoom = 2.0 * self.zoom_factor
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            img = pix.pil_image() if PYMUPDF_VERSION >= (1, 22, 0) and hasattr(pix, 'pil_image') else Image.frombytes("RGB", (pix.width, pix.height), pix.tobytes("RGB"))
            self.image_tk = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            x_offset = max(0, (canvas_width - pix.width) // 2)
            y_offset = max(0, (canvas_height - pix.height) // 2)
            self.canvas.create_image(x_offset, y_offset, anchor=tk.NW, image=self.image_tk)
            self.canvas.config(scrollregion=(0, 0, pix.width + 2 * x_offset, pix.height + 2 * y_offset))

            if self.vertical_scrollbar:
                self.vertical_scrollbar.pack_forget()
                self.vertical_scrollbar = None
            if pix.height > canvas_height:
                self.vertical_scrollbar = tk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
                self.canvas.configure(yscrollcommand=self.vertical_scrollbar.set)
                self.vertical_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            self.status_label.config(text=f"Page {self.current_page + 1} displayed")
            self.zoom_label.config(text=f"Zoom: {int(self.zoom_factor * 100)}%")
        except Exception as e:
            logging.error(f"Page update failed: {str(e)}")

    def update_thumbnails(self):
        self.thumbnail_canvas.delete("all")
        self.thumbnail_images = []
        if not self.pdf_doc or not self.thumbnails_visible:
            return
        try:
            y_pos = 10
            for page_num in range(self.pdf_doc.page_count):
                page = self.pdf_doc[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(0.2, 0.2))
                if pix.colorspace != fitz.csRGB:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                img = pix.pil_image() if PYMUPDF_VERSION >= (1, 22, 0) and hasattr(pix, 'pil_image') else Image.frombytes("RGB", (pix.width, pix.height), pix.tobytes("RGB"))
                img = img.resize((100, int(100 * pix.height / pix.width)), Image.Resampling.LANCZOS)
                img_tk = ImageTk.PhotoImage(img)
                self.thumbnail_images.append(img_tk)
                self.thumbnail_canvas.create_image(75, y_pos, anchor=tk.N, image=img_tk)
                self.thumbnail_canvas.create_text(75, y_pos + img.height // 2, text=f"Page {page_num + 1}", font=("Arial", 8))
                self.thumbnail_canvas.tag_bind(self.thumbnail_canvas.create_rectangle(25, y_pos - img.height // 2, 125, y_pos + img.height // 2, outline=""), "<Button-1>", lambda e, pn=page_num: self.goto_page(pn))
                y_pos += img.height + 20
            self.thumbnail_canvas.config(scrollregion=(0, 0, 150, y_pos))
        except Exception as e:
            logging.error(f"Thumbnails failed: {str(e)}")

    def goto_page(self, page_num):
        if 0 <= page_num < self.pdf_doc.page_count:
            self.current_page = page_num
            self.update_page()
            self.page_label.config(text=f"Page: {self.current_page + 1}/{self.pdf_doc.page_count}")
            self.reset_search()
            self._smooth_scroll(0.0)

    def toggle_thumbnails(self):
        self.thumbnails_visible = not self.thumbnails_visible
        if self.thumbnails_visible:
            self.thumbnail_frame.pack(side=tk.LEFT, fill=tk.Y)
            self.update_thumbnails()
            self.status_label.config(text="Thumbnails shown")
        else:
            self.thumbnail_frame.pack_forget()
            self.status_label.config(text="Thumbnails hidden")

    def fit_to_window(self):
        if not self.pdf_doc:
            return
        try:
            page = self.pdf_doc[self.current_page]
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            page_width, page_height = page.rect.width, page.rect.height
            width_ratio = canvas_width / page_width
            height_ratio = canvas_height / page_height
            self.zoom_factor = min(width_ratio, height_ratio) / 2.0
            self.update_page()
            self.status_label.config(text="Fitted to window")
            self.zoom_label.config(text=f"Zoom: {int(self.zoom_factor * 100)}%")
        except Exception as e:
            logging.error(f"Fit failed: {str(e)}")

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_page()
            self.page_label.config(text=f"Page: {self.current_page + 1}/{self.pdf_doc.page_count}")
            self.reset_search()
            self._smooth_scroll(1.0)

    def next_page(self):
        if self.pdf_doc and self.current_page < self.pdf_doc.page_count - 1:
            self.current_page += 1
            self.update_page()
            self.page_label.config(text=f"Page: {self.current_page + 1}/{self.pdf_doc.page_count}")
            self.reset_search()
            self._smooth_scroll(0.0)

    def zoom_in(self):
        self.zoom_factor *= 1.2
        self.update_page()
        self.zoom_label.config(text=f"Zoom: {int(self.zoom_factor * 100)}%")

    def zoom_out(self):
        self.zoom_factor /= 1.2
        if self.zoom_factor < 0.1:
            self.zoom_factor = 0.1
        self.update_page()
        self.zoom_label.config(text=f"Zoom: {int(self.zoom_factor * 100)}%")

    def search_text(self):
        if not self.pdf_doc:
            return
        query = self.search_var.get().strip().lower()
        if not query:
            messagebox.showinfo("Search", "Enter a search term.")
            return
        self.search_results = []
        for page_num in range(self.pdf_doc.page_count):
            page = self.pdf_doc[page_num]
            text_instances = page.search_for(query)
            for rect in text_instances:
                self.search_results.append((page_num, rect))
        if self.search_results:
            self.current_search_index = 0
            self.highlight_search()
            self.status_label.config(text=f"Found {len(self.search_results)} matches")
        else:
            messagebox.showinfo("Search", "No matches found.")
            self.canvas.delete("highlight")
            self.status_label.config(text="No matches")

    def next_search(self):
        if self.search_results:
            self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
            self.highlight_search()
            self.status_label.config(text=f"Match {self.current_search_index + 1}/{len(self.search_results)}")

    def highlight_search(self):
        self.canvas.delete("highlight")
        if self.search_results:
            page_num, rect = self.search_results[self.current_search_index]
            if page_num != self.current_page:
                self.current_page = page_num
                self.update_page()
                self.page_label.config(text=f"Page: {self.current_page + 1}/{self.pdf_doc.page_count}")
            zoom = 2.0 * self.zoom_factor
            x0, y0, x1, y1 = [coord * zoom for coord in rect]
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            pix = self.pdf_doc[self.current_page].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            x_offset = max(0, (canvas_width - pix.width) // 2)
            y_offset = max(0, (canvas_height - pix.height) // 2)
            self.canvas.create_rectangle(x0 + x_offset, y0 + y_offset, x1 + x_offset, y1 + y_offset, fill="yellow", stipple="gray50", tags="highlight")

    def reset_search(self):
        self.search_results = []
        self.current_search_index = -1
        self.canvas.delete("highlight")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = PDFReaderApp(root)
        if len(sys.argv) > 1:
            pdf_path = sys.argv[1]
            app.open_pdf(pdf_path)
        root.mainloop()
    except Exception as e:
        logging.critical(f"App failed: {str(e)}")
        messagebox.showerror("Error", f"Failed to start: {str(e)}")
        sys.exit(1)