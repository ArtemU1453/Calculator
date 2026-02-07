import customtkinter as ctk

class CuttingVisualization(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent)

        self.canvas = ctk.CTkCanvas(self, height=120)
        self.canvas.pack(fill="both", expand=True)

    def draw_scheme(self, result):

        self.canvas.delete("all")

        width = result["material_width"]
        scale = 600 / width
        x = 0

        def draw_block(size, color):
            nonlocal x
            w = size * scale
            self.canvas.create_rectangle(x,20,x+w,100,fill=color)
            x += w

        draw_block(result["waste_per_side"],"red")

        for _ in range(result["main_count"]):
            draw_block(result["main_width"],"blue")

        if result["additional_width"]:
            draw_block(result["additional_width"],"green")

        draw_block(result["waste_per_side"],"red")
