import tkinter as tk
root = tk.Tk()
root.geometry("400x300")
root.title("Test Tkinter Window")
tk.Label(root, text="Hello, Tkinter!").pack(pady=10)
tk.Button(root, text="Click Me", command=lambda: print("Button clicked")).pack(pady=10)
root.mainloop()