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

        # Control Frame (at top with grid layout)
        try:
            self.control_frame = tk.Frame(self.root, bg="lightgray")
            self.control_frame.pack(fill=tk.X, side=tk.TOP, pady=5)
        except Exception as e:
            logging.critical(f"Failed to create control frame: {str(e)}")
            messagebox.showerror("Error", f"Failed to create control frame: {str(e)}")
            sys.exit(1)

        # Buttons and widgets with fixed dimensions in grid layout
        try:
            button_width = 14
            button_height = 1

            # Row 0: Main controls
            col = 0
            tk.Button(self.control_frame, text="Open PDF", command=self.open_pdf, width=button_width, height=button_height).grid(row=0, column=col, padx=5, pady=5); col += 1
            tk.Button(self.control_frame, text="Page Up", command=self.prev_page, width=button_width, height=button_height).grid(row=0, column=col, padx=5, pady=5); col += 1
            tk.Button(self.control_frame, text="Page Down", command=self.next_page, width=button_width, height=button_height).grid(row=0, column=col, padx=5, pady=5); col += 1

            # Search Entry, Search, Next Match — grouped together
            self.search_var = tk.StringVar()
            tk.Entry(self.control_frame, textvariable=self.search_var, width=20).grid(row=0, column=col, padx=5, pady=5); col += 1
            tk.Button(self.control_frame, text="Search", command=self.search_text, width=button_width, height=button_height).grid(row=0, column=col, padx=5, pady=5); col += 1
            tk.Button(self.control_frame, text="Next Match", command=self.next_search, width=button_width, height=button_height).grid(row=0, column=col, padx=5, pady=5); col += 1

            # Zoom controls
            tk.Button(self.control_frame, text="Zoom In", command=self.zoom_in, width=button_width, height=button_height).grid(row=0, column=col, padx=5, pady=5); col += 1
            tk.Button(self.control_frame, text="Zoom Out", command=self.zoom_out, width=button_width, height=button_height).grid(row=0, column=col, padx=5, pady=5); col += 1
            tk.Button(self.control_frame, text="Fit to Window", command=self.fit_to_window, width=button_width, height=button_height).grid(row=0, column=col, padx=5, pady=5); col += 1
            tk.Button(self.control_frame, text="Show/Hide Thumbs", command=self.toggle_thumbnails, width=button_width, height=button_height).grid(row=0, column=col, padx=5, pady=5); col += 1

            # Page label
            self.page_label = tk.Label(self.control_frame, text="Page: 0/0", width=10)
            self.page_label.grid(row=0, column=col, padx=5, pady=5); col += 1

            # About button at the end
            tk.Button(self.control_frame, text="About", command=self.show_about, width=button_width, height=button_height).grid(row=0, column=col, padx=5, pady=5)

        except Exception as e:
            logging.critical(f"Failed to create control frame widgets: {str(e)}")
            messagebox.showerror("Error", f"Failed to create control frame widgets: {str(e)}")
            sys.exit(1)

        # Main Frame (contains canvas and thumbnail sidebar)
        try:
            self.main_frame = tk.Frame(self.root)
            self.main_frame.pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            logging.critical(f"Failed to create main frame: {str(e)}")
            messagebox.showerror("Error", f"Failed to create main frame: {str(e)}")
            sys.exit(1)

        # Canvas frame (canvas and horizontal scrollbar)
        try:
            self.canvas_frame = tk.Frame(self.main_frame)
            self.canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
            self.canvas = tk.Canvas(self.canvas_frame, width=600, height=400, bg="white")
            self.h_scrollbar = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
            self.canvas.configure(xscrollcommand=self.h_scrollbar.set)
            self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            self.canvas.create_text(300, 200, text="No PDF loaded. Click 'Open PDF' to start.", font=("Arial", 12))
        except Exception as e:
            logging.critical(f"Failed to create canvas or horizontal scrollbar: {str(e)}")
            messagebox.showerror("Error", f"Failed to initialize canvas: {str(e)}")
            sys.exit(1)

        # Thumbnail Sidebar (to the left of canvas, aligned with canvas height)
        try:
            self.thumbnail_frame = tk.Frame(self.main_frame, width=150)
            self.thumbnail_canvas = tk.Canvas(self.thumbnail_frame, width=150, height=400, bg="lightgray")
            self.thumbnail_scrollbar = tk.Scrollbar(self.thumbnail_frame, orient=tk.VERTICAL, command=self.thumbnail_canvas.yview)
            self.thumbnail_canvas.configure(yscrollcommand=self.thumbnail_scrollbar.set)
            self.thumbnail_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.thumbnail_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.thumbnail_frame.pack(side=tk.LEFT, fill=tk.Y)
            self.thumbnail_frame.pack_forget()  # Hidden by default
        except Exception as e:
            logging.critical(f"Failed to create thumbnail sidebar: {str(e)}")
            messagebox.showerror("Error", f"Failed to create thumbnail sidebar: {str(e)}")
            sys.exit(1)

        # Bottom frame for status and zoom labels
        try:
            self.bottom_frame = tk.Frame(self.root, bg="lightgray")
            self.bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)
            self.status_label = tk.Label(self.bottom_frame, text="No PDF loaded", anchor=tk.W, bg="lightgray")
            self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            self.zoom_label = tk.Label(self.bottom_frame, text="Zoom: 100%", anchor=tk.E, bg="lightgray")
            self.zoom_label.pack(side=tk.RIGHT, padx=5)
        except Exception as e:
            logging.critical(f"Failed to create bottom frame or labels: {str(e)}")
            messagebox.showerror("Error", f"Failed to create status/zoom labels: {str(e)}")
            sys.exit(1)

        # Bind mouse wheel for page navigation
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.image_tk = None
        self.thumbnail_images = []
        logging.info("GUI initialized successfully")

    def show_about(self):
        """Display an About message box with application details."""
        about_message = (
            "Simple PDF Reader v1.0\n\n"
            "Project Owner / Contributor: H Vikram Kondapalli\n"
            "Code Generator: Grok, created by xAI\n\n"
            "Built using:\n"
            "- Python\n"
            "- PyMuPDF (for PDF rendering)\n"
            "- Pillow (for image processing)\n"
            "- Tkinter (for the graphical user interface)\n\n"
            "A lightweight PDF reader with navigation, zoom, search, and thumbnail features."
        )
        messagebox.showinfo("About Simple PDF Reader", about_message)
        logging.debug("Displayed About message")

    def _on_mousewheel(self, event):
        if self.pdf_doc:
            if event.delta > 0:  # Scroll up
                self.prev_page()
            elif event.delta < 0:  # Scroll down
                self.next_page()
            logging.debug("Mouse wheel used for page navigation")

    def open_pdf(self, file_path=None):
        """Open a PDF file, either from file_path (command-line) or file dialog."""
        if not file_path:
            file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if file_path:
            try:
                if not os.path.isfile(file_path) or not file_path.lower().endswith('.pdf'):
                    raise ValueError("Invalid or non-existent PDF file")
                self.pdf_doc = fitz.open(file_path)
                if self.pdf_doc.is_encrypted:
                    raise ValueError("PDF is encrypted and cannot be opened without a password.")
                if self.pdf_doc.page_count == 0:
                    raise ValueError("PDF has no pages or is corrupted.")
                self.current_page = 0
                self.zoom_factor = 0.85
                self.update_page()
                self.update_thumbnails()
                self.page_label.config(text=f"Page: {self.current_page + 1}/{self.pdf_doc.page_count}")
                self.status_label.config(text=f"Loaded: {os.path.basename(file_path)}")
                self.zoom_label.config(text=f"Zoom: {int(self.zoom_factor * 100)}%")
                logging.info(f"Successfully opened PDF: {file_path} at 85% zoom")
            except Exception as e:
                logging.error(f"Failed to open PDF {file_path}: {str(e)}")
                messagebox.showerror("Error", f"Failed to open PDF: {str(e)}")
                self.pdf_doc = None
                self.status_label.config(text="Failed to load PDF")
                self.zoom_label.config(text="Zoom: 100%")
                self.canvas.delete("all")
                self.canvas.create_text(300, 200, text="Failed to load PDF.", font=("Arial", 12))

    def update_page(self):
        if not self.pdf_doc:
            self.status_label.config(text="No PDF loaded")
            self.zoom_label.config(text="Zoom: 100%")
            self.canvas.delete("all")
            self.canvas.create_text(300, 200, text="No PDF loaded. Click 'Open PDF' to start.", font=("Arial", 12))
            return
        try:
            page = self.pdf_doc[self.current_page]
            zoom = 2.0 * self.zoom_factor
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            if PYMUPDF_VERSION >= (1, 22, 0) and hasattr(pix, 'pil_image'):
                img = pix.pil_image()
            else:
                img_data = pix.tobytes("RGB")
                img = Image.frombytes("RGB", (pix.width, pix.height), img_data)
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
            if pix.height > canvas_height and self.zoom_factor > 1.0:
                self.vertical_scrollbar = tk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
                self.canvas.configure(yscrollcommand=self.vertical_scrollbar.set)
                self.vertical_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                logging.debug("Vertical scrollbar added due to zoom")

            self.status_label.config(text=f"Page {self.current_page + 1} displayed")
            self.zoom_label.config(text=f"Zoom: {int(self.zoom_factor * 100)}%")
            logging.debug(f"Displayed page {self.current_page + 1} with zoom factor {self.zoom_factor}")
        except Exception as e:
            logging.error(f"Failed to update page {self.current_page + 1}: {str(e)}")
            messagebox.showerror("Error", f"Failed to display page: {str(e)}")
            self.status_label.config(text="Error displaying page")
            self.zoom_label.config(text="Zoom: 100%")
            self.canvas.delete("all")
            self.canvas.create_text(300, 200, text="Error displaying page.", font=("Arial", 12))

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
                if PYMUPDF_VERSION >= (1, 22, 0) and hasattr(pix, 'pil_image'):
                    img = pix.pil_image()
                else:
                    img_data = pix.tobytes("RGB")
                    img = Image.frombytes("RGB", (pix.width, pix.height), img_data)
                img = img.resize((100, int(100 * pix.height / pix.width)), Image.Resampling.LANCZOS)
                img_tk = ImageTk.PhotoImage(img)
                self.thumbnail_images.append(img_tk)
                self.thumbnail_canvas.create_image(75, y_pos, anchor=tk.N, image=img_tk)
                self.thumbnail_canvas.create_text(75, y_pos + img.height // 2, text=f"Page {page_num + 1}", font=("Arial", 12))
                self.thumbnail_canvas.tag_bind(self.thumbnail_canvas.create_rectangle(25, y_pos - img.height // 2, 125, y_pos + img.height // 2, outline=""), "<Button-1>", lambda e, pn=page_num: self.goto_page(pn))
                y_pos += img.height + 20
            self.thumbnail_canvas.config(scrollregion=(0, 0, 150, y_pos))
            logging.debug("Thumbnails updated")
        except Exception as e:
            logging.error(f"Failed to update thumbnails: {str(e)}")
            messagebox.showerror("Error", f"Failed to update thumbnails: {str(e)}")
            self.status_label.config(text="Thumbnail update failed")

    def goto_page(self, page_num):
        if 0 <= page_num < self.pdf_doc.page_count:
            self.current_page = page_num
            self.update_page()
            self.page_label.config(text=f"Page: {self.current_page + 1}/{self.pdf_doc.page_count}")
            self.reset_search()
            logging.debug(f"Navigated to page {self.current_page + 1} via thumbnail")

    def toggle_thumbnails(self):
        self.thumbnails_visible = not self.thumbnails_visible
        if self.thumbnails_visible:
            self.thumbnail_frame.pack(side=tk.LEFT, fill=tk.Y)
            self.update_thumbnails()
            self.status_label.config(text="Thumbnail sidebar shown")
        else:
            self.thumbnail_frame.pack_forget()
            self.status_label.config(text="Thumbnail sidebar hidden")
        logging.debug(f"Thumbnails visible: {self.thumbnails_visible}")

    def fit_to_window(self):
        if not self.pdf_doc:
            self.status_label.config(text="No PDF loaded")
            self.zoom_label.config(text="Zoom: 100%")
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
            self.status_label.config(text="Page fitted to window")
            self.zoom_label.config(text=f"Zoom: {int(self.zoom_factor * 100)}%")
            logging.debug(f"Fitted to window with zoom factor: {self.zoom_factor}")
        except Exception as e:
            logging.error(f"Failed to fit to window: {str(e)}")
            messagebox.showerror("Error", f"Failed to fit to window: {str(e)}")

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_page()
            self.page_label.config(text=f"Page: {self.current_page + 1}/{self.pdf_doc.page_count}")
            self.reset_search()
            logging.debug(f"Navigated to previous page: {self.current_page + 1}")

    def next_page(self):
        if self.pdf_doc and self.current_page < self.pdf_doc.page_count - 1:
            self.current_page += 1
            self.update_page()
            self.page_label.config(text=f"Page: {self.current_page + 1}/{self.pdf_doc.page_count}")
            self.reset_search()
            logging.debug(f"Navigated to next page: {self.current_page + 1}")

    def zoom_in(self):
        self.zoom_factor *= 1.2
        self.update_page()
        self.zoom_label.config(text=f"Zoom: {int(self.zoom_factor * 100)}%")
        logging.debug(f"Zoomed in to factor: {self.zoom_factor}")

    def zoom_out(self):
        self.zoom_factor /= 1.2
        if self.zoom_factor < 0.1:
            self.zoom_factor = 0.1
        self.update_page()
        self.zoom_label.config(text=f"Zoom: {int(self.zoom_factor * 100)}%")
        logging.debug(f"Zoomed out to factor: {self.zoom_factor}")

    def search_text(self):
        if not self.pdf_doc:
            self.status_label.config(text="No PDF loaded")
            self.zoom_label.config(text="Zoom: 100%")
            return
        query = self.search_var.get().strip().lower()
        if not query:
            messagebox.showinfo("Search", "Please enter a search term.")
            return
        self.search_results = []
        try:
            for page_num in range(self.pdf_doc.page_count):
                page = self.pdf_doc[page_num]
                text_instances = page.search_for(query)
                for rect in text_instances:
                    self.search_results.append((page_num, rect))
            if self.search_results:
                self.current_search_index = 0
                self.highlight_search()
                self.status_label.config(text=f"Found {len(self.search_results)} matches across document")
                logging.info(f"Found {len(self.search_results)} matches for '{query}'")
            else:
                messagebox.showinfo("Search", "No matches found.")
                self.canvas.delete("highlight")
                self.status_label.config(text="No matches found")
                logging.info(f"No matches found for '{query}'")
        except Exception as e:
            logging.error(f"Search failed: {str(e)}")
            messagebox.showerror("Error", f"Search failed: {str(e)}")
            self.status_label.config(text="Search error")

    def next_search(self):
        if self.search_results:
            self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
            self.highlight_search()
            self.status_label.config(text=f"Match {self.current_search_index + 1}/{len(self.search_results)} on page {self.search_results[self.current_search_index][0] + 1}")
            logging.debug(f"Moved to search result {self.current_search_index + 1}/{len(self.search_results)}")

    def highlight_search(self):
        self.canvas.delete("highlight")
        if self.search_results:
            try:
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
                logging.debug(f"Highlighted search result at index {self.current_search_index} on page {page_num + 1}")
            except Exception as e:
                logging.error(f"Failed to highlight search: {str(e)}")
                messagebox.showerror("Error", f"Failed to highlight search result: {str(e)}")
                self.status_label.config(text="Highlight error")

    def reset_search(self):
        self.search_results = []
        self.current_search_index = -1
        self.canvas.delete("highlight")
        self.status_label.config(text="Search reset")
        logging.debug("Reset search results")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = PDFReaderApp(root)
        if len(sys.argv) > 1:
            pdf_path = sys.argv[1]
            app.open_pdf(pdf_path)
        root.mainloop()
    except Exception as e:
        logging.critical(f"Application failed to start: {str(e)}")
        messagebox.showerror("Error", f"Application failed to start: {str(e)}")
        sys.exit(1)