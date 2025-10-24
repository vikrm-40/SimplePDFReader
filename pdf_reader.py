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

        # Control Frame (moved to top)
        try:
            self.control_frame = tk.Frame(self.root, bg="lightgray")
            self.control_frame.pack(fill=tk.X, side=tk.TOP, pady=5)
        except Exception as e:
            logging.critical(f"Failed to create control frame: {str(e)}")
            messagebox.showerror("Error", f"Failed to create control frame: {str(e)}")
            sys.exit(1)

        # Buttons
        try:
            tk.Button(self.control_frame, text="Open PDF", command=self.open_pdf).pack(side=tk.LEFT, padx=5)
            tk.Button(self.control_frame, text="Page Up", command=self.prev_page).pack(side=tk.LEFT, padx=5)
            tk.Button(self.control_frame, text="Page Down", command=self.next_page).pack(side=tk.LEFT, padx=5)
            tk.Button(self.control_frame, text="Previous", command=self.prev_page).pack(side=tk.LEFT, padx=5)
            tk.Button(self.control_frame, text="Next", command=self.next_page).pack(side=tk.LEFT, padx=5)
            tk.Button(self.control_frame, text="Zoom In", command=self.zoom_in).pack(side=tk.LEFT, padx=5)
            tk.Button(self.control_frame, text="Zoom Out", command=self.zoom_out).pack(side=tk.LEFT, padx=5)
        except Exception as e:
            logging.critical(f"Failed to create buttons: {str(e)}")
            messagebox.showerror("Error", f"Failed to create buttons: {str(e)}")
            sys.exit(1)

        # Page Label
        self.page_label = tk.Label(self.control_frame, text="Page: 0/0")
        self.page_label.pack(side=tk.LEFT, padx=5)

        # Search Bar
        self.search_var = tk.StringVar()
        tk.Entry(self.control_frame, textvariable=self.search_var, width=20).pack(side=tk.LEFT, padx=5)
        tk.Button(self.control_frame, text="Search", command=self.search_text).pack(side=tk.LEFT, padx=5)
        tk.Button(self.control_frame, text="Next Match", command=self.next_search).pack(side=tk.LEFT, padx=5)

        # Main frame (canvas and scrollbars)
        try:
            self.main_frame = tk.Frame(self.root)
            self.main_frame.pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            logging.critical(f"Failed to create main frame: {str(e)}")
            messagebox.showerror("Error", f"Failed to create main frame: {str(e)}")
            sys.exit(1)

        # Canvas with horizontal scrollbar
        try:
            self.canvas = tk.Canvas(self.main_frame, width=600, height=400, bg="white")
            self.h_scrollbar = tk.Scrollbar(self.main_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
            self.canvas.configure(xscrollcommand=self.h_scrollbar.set)
            self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            self.canvas.create_text(300, 200, text="No PDF loaded. Click 'Open PDF' to start.", font=("Arial", 12))
        except Exception as e:
            logging.critical(f"Failed to create canvas or horizontal scrollbar: {str(e)}")
            messagebox.showerror("Error", f"Failed to initialize canvas: {str(e)}")
            sys.exit(1)

        # Status Label
        self.status_label = tk.Label(self.root, text="No PDF loaded", anchor=tk.W, bg="lightgray")
        self.status_label.pack(fill=tk.X, side=tk.BOTTOM, padx=5)

        # Bind mouse wheel for page navigation
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.image_tk = None
        logging.info("GUI initialized successfully")

    def _on_mousewheel(self, event):
        if self.pdf_doc:
            if event.delta > 0:  # Scroll up
                self.prev_page()
            elif event.delta < 0:  # Scroll down
                self.next_page()
            logging.debug("Mouse wheel used for page navigation")

    def open_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if file_path:
            try:
                self.pdf_doc = fitz.open(file_path)
                if self.pdf_doc.is_encrypted:
                    raise ValueError("PDF is encrypted and cannot be opened without a password.")
                if self.pdf_doc.page_count == 0:
                    raise ValueError("PDF has no pages or is corrupted.")
                self.current_page = 0
                self.zoom_factor = 1.0
                self.search_results = []
                self.current_search_index = -1
                self.update_page()
                self.page_label.config(text=f"Page: {self.current_page + 1}/{self.pdf_doc.page_count}")
                self.status_label.config(text=f"Loaded: {os.path.basename(file_path)}")
                logging.info(f"Successfully opened PDF: {file_path}")
            except Exception as e:
                logging.error(f"Failed to open PDF {file_path}: {str(e)}")
                messagebox.showerror("Error", f"Failed to open PDF: {str(e)}")
                self.pdf_doc = None
                self.status_label.config(text="Failed to load PDF")
                self.canvas.delete("all")
                self.canvas.create_text(300, 200, text="Failed to load PDF.", font=("Arial", 12))

    def update_page(self):
        if not self.pdf_doc:
            self.status_label.config(text="No PDF loaded")
            self.canvas.delete("all")
            self.canvas.create_text(300, 200, text="No PDF loaded. Click 'Open PDF' to start.", font=("Arial", 12))
            return
        try:
            page = self.pdf_doc[self.current_page]
            zoom = 2.0 * self.zoom_factor
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            # Use pil_image() if available (PyMuPDF >= 1.22.0), else tobytes
            if PYMUPDF_VERSION >= (1, 22, 0) and hasattr(pix, 'pil_image'):
                img = pix.pil_image()
            else:
                img_data = pix.tobytes("RGB")
                img = Image.frombytes("RGB", (pix.width, pix.height), img_data)
            self.image_tk = ImageTk.PhotoImage(img)
            self.canvas.delete("all")

            # Center the image with equal borders
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            x_offset = max(0, (canvas_width - pix.width) // 2)
            y_offset = max(0, (canvas_height - pix.height) // 2)
            self.canvas.create_image(x_offset, y_offset, anchor=tk.NW, image=self.image_tk)
            self.canvas.config(scrollregion=(0, 0, pix.width + 2 * x_offset, pix.height + 2 * y_offset))

            # Add vertical scrollbar if page height exceeds canvas height
            if self.vertical_scrollbar:
                self.vertical_scrollbar.pack_forget()
                self.vertical_scrollbar = None
            if pix.height > canvas_height and self.zoom_factor > 1.0:
                self.vertical_scrollbar = tk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
                self.canvas.configure(yscrollcommand=self.vertical_scrollbar.set)
                self.vertical_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                logging.debug("Vertical scrollbar added due to zoom")

            self.status_label.config(text=f"Page {self.current_page + 1} displayed")
            logging.debug(f"Displayed page {self.current_page + 1} with zoom factor {self.zoom_factor}")
        except Exception as e:
            logging.error(f"Failed to update page {self.current_page + 1}: {str(e)}")
            messagebox.showerror("Error", f"Failed to display page: {str(e)}")
            self.status_label.config(text="Error displaying page")
            self.canvas.delete("all")
            self.canvas.create_text(300, 200, text="Error displaying page.", font=("Arial", 12))

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
        logging.debug(f"Zoomed in to factor: {self.zoom_factor}")

    def zoom_out(self):
        self.zoom_factor /= 1.2
        if self.zoom_factor < 0.1:
            self.zoom_factor = 0.1
        self.update_page()
        logging.debug(f"Zoomed out to factor: {self.zoom_factor}")

    def search_text(self):
        if not self.pdf_doc:
            self.status_label.config(text="No PDF loaded")
            return
        query = self.search_var.get().lower()
        self.search_results = []
        try:
            # Search all pages
            for page_num in range(self.pdf_doc.page_count):
                page = self.pdf_doc[page_num]
                text_instances = page.search_for(query)
                for rect in text_instances:
                    self.search_results.append((page_num, rect))
            if self.search_results:
                self.current_search_index = 0
                self.highlight_search()
                self.status_label.config(text=f"Found {len(self.search_results)} matches across document")
                logging.info(f"Found {len(self.search_results)} matches for '{query}' across document")
            else:
                messagebox.showinfo("Search", "No matches found.")
                self.canvas.delete("highlight")
                self.status_label.config(text="No matches found")
                logging.info(f"No matches found for '{query}' across document")
        except Exception as e:
            logging.error(f"Search failed: {str(e)}")
            messagebox.showerror("Error", f"Search failed: {str(e)}")
            self.status_label.config(text="Search error")

    def next_search(self):
        if self.search_results:
            self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
            self.highlight_search()
            self.status_label.config(text=f"Match {self.current_search_index + 1}/{len(self.search_results)} on page {self.search_results[self.current_search_index][0] + 1}")
            logging.debug(f"Moved to search result {self.current_search_index + 1}/{len(self.search_results)} on page {self.search_results[self.current_search_index][0] + 1}")

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
                # Adjust for centered image
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
        root.mainloop()
    except Exception as e:
        logging.critical(f"Application failed to start: {str(e)}")
        messagebox.showerror("Error", f"Application failed to start: {str(e)}")
        sys.exit(1)