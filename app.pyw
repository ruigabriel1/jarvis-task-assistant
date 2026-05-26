import os
import json
import tkinter as tk
import customtkinter as ctk
from task_manager import TaskManager
from voice_handler import VoiceHandler

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class JarvisApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.project_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.project_dir, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.tasks_filepath = os.path.join(self.data_dir, "tasks.db")

        # Gerenciador de tarefas thread-safe
        self.task_manager = TaskManager(self.tasks_filepath)

        self.title("Jarvis - Tarefas Diárias")
        self.geometry("520x650")
        self.resizable(False, False)
        self.center_window()

        self.bg_color = "#121212"
        self.card_bg_color = "#1E1E1E"
        self.accent_color = "#00E5FF"
        
        self.configure(fg_color=self.bg_color)
        self.priority_order = {"Alta": 1, "Média": 2, "Baixa": 3}
        
        # ID da tarefa atualmente no modo de edição manual inline (None se nenhuma)
        self.editing_task_id = None

        self.create_widgets()
        self.voice_handler = VoiceHandler(self.task_manager, self.on_voice_event)
        self.update_status(self.voice_handler.active_mode)
        self.refresh_tasks()
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def center_window(self):
        self.update_idletasks()
        width = 520
        height = 650
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def create_widgets(self):
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=25, pady=(25, 10))

        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="JARVIS", 
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=self.accent_color
        )
        self.title_label.pack(anchor="w")

        self.status_label = ctk.CTkLabel(
            self.header_frame, 
            text="Modo: Inativo (Diga \"Ligar Jarvis\")", 
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#8E8E93"
        )
        self.status_label.pack(anchor="w", pady=(2, 0))

        self.indicator_canvas = tk.Canvas(
            self.header_frame, 
            width=16, 
            height=16, 
            bg=self.bg_color, 
            highlightthickness=0
        )
        self.indicator_canvas.place(relx=1.0, rely=0.3, anchor="ne")
        self.draw_indicator("#3A3A3C")
        self.indicator_canvas.bind("<Button-1>", self.toggle_voice_handler)

        self.tasks_container = ctk.CTkScrollableFrame(
            self, 
            fg_color=self.bg_color, 
            label_text="SUAS TAREFAS",
            label_font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            label_text_color="#8E8E93"
        )
        self.tasks_container._scrollbar.configure(width=6)
        self.tasks_container.pack(fill="both", expand=True, padx=20, pady=(10, 15))

        self.input_frame = ctk.CTkFrame(self, fg_color=self.card_bg_color, corner_radius=12)
        self.input_frame.pack(fill="x", padx=20, pady=(0, 25))

        self.entry_task = ctk.CTkEntry(
            self.input_frame, 
            placeholder_text="Escreva uma nova nota ou tarefa...", 
            fg_color="#121212",
            border_color="#2C2C2E",
            height=40,
            font=ctk.CTkFont(family="Segoe UI", size=13)
        )
        self.entry_task.grid(row=0, column=0, columnspan=2, sticky="ew", padx=15, pady=(15, 8))
        self.entry_task.bind("<Return>", lambda e: self.add_task())

        self.combo_priority = ctk.CTkOptionMenu(
            self.input_frame, 
            values=["Alta", "Média", "Baixa"],
            fg_color="#121212",
            button_color="#2C2C2E",
            button_hover_color="#3A3A3C",
            dropdown_fg_color="#1E1E1E",
            dropdown_hover_color="#2C2C2E",
            height=32,
            width=110,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.combo_priority.set("Média")
        self.combo_priority.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 15))

        self.btn_add = ctk.CTkButton(
            self.input_frame, 
            text="Adicionar", 
            fg_color=self.accent_color,
            text_color="#121212",
            hover_color="#00B8D4",
            height=32,
            width=110,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.add_task
        )
        self.btn_add.grid(row=1, column=1, sticky="e", padx=15, pady=(0, 15))

        self.input_frame.columnconfigure(0, weight=1)
        self.input_frame.columnconfigure(1, weight=1)

    def draw_indicator(self, color):
        self.indicator_canvas.delete("all")
        self.indicator_canvas.create_oval(2, 2, 14, 14, fill=color, outline="")

    def on_voice_event(self, event_type):
        if event_type == "refresh":
            if self.editing_task_id is None:
                self.after(0, self.refresh_tasks)
        elif event_type == "status_active":
            self.after(0, lambda: self.update_status(True))
        elif event_type == "status_inactive":
            self.after(0, lambda: self.update_status(False))
        elif event_type == "api_key_missing":
            self.after(0, self.show_api_key_error)
        elif event_type == "connection_error":
            self.after(0, self.show_connection_error)

    def update_status(self, is_active):
        hk_display = self.voice_handler.hotkey.title() if hasattr(self, 'voice_handler') else "Ctrl+Shift+J"
        if is_active:
            self.status_label.configure(
                text=f"Modo: Ativo (Ouvindo comandos. Pressione {hk_display} ou diga \"Desligar Jarvis\" para silenciar)",
                text_color=self.accent_color
            )
            self.draw_indicator(self.accent_color)
        else:
            self.status_label.configure(
                text=f"Modo: Inativo (Diga \"Ligar Jarvis\", clique no indicador ou pressione {hk_display} para ativar)",
                text_color="#8E8E93"
            )
            self.draw_indicator("#3A3A3C")

    def show_api_key_error(self):
        self.status_label.configure(
            text="Atenção: Configure GEMINI_API_KEY no config.json para tirar dúvidas.",
            text_color="#FF9F0A"
        )
        self.draw_indicator("#FF9F0A")

    def show_connection_error(self):
        self.status_label.configure(
            text="Erro de Voz: Não foi possível acessar o serviço do Google (Sem Internet?).",
            text_color="#FF453A"
        )
        self.draw_indicator("#FF453A")

    def toggle_voice_handler(self, event=None):
        if hasattr(self, 'voice_handler'):
            self.voice_handler.toggle_active()

    def add_task(self):
        text = self.entry_task.get().strip()
        if not text:
            return
        priority = self.combo_priority.get()
        
        def add_cb(tasks_list):
            new_id = max([t.get("id", 0) for t in tasks_list] + [0]) + 1
            new_task = {"id": new_id, "text": text, "completed": False, "priority": priority}
            tasks_list.append(new_task)
            return tasks_list
            
        if self.task_manager.update_tasks(add_cb):
            self.refresh_tasks()
        self.entry_task.delete(0, tk.END)

    def toggle_task(self, task_id):
        def toggle_cb(tasks_list):
            for t in tasks_list:
                if t["id"] == task_id:
                    t["completed"] = not t["completed"]
                    break
            return tasks_list
        if self.task_manager.update_tasks(toggle_cb):
            self.refresh_tasks()

    def delete_task(self, task_id):
        def delete_cb(tasks_list):
            return [t for t in tasks_list if t["id"] != task_id]
        if self.task_manager.update_tasks(delete_cb):
            self.refresh_tasks()

    def save_edited_task(self, task_id, new_text, new_priority):
        def save_cb(tasks_list):
            for t in tasks_list:
                if t["id"] == task_id:
                    t["text"] = new_text
                    t["priority"] = new_priority
                    break
            return tasks_list
        self.editing_task_id = None
        if self.task_manager.update_tasks(save_cb):
            self.refresh_tasks()

    def cancel_editing(self):
        self.editing_task_id = None
        self.refresh_tasks()

    def refresh_tasks(self):
        for widget in self.tasks_container.winfo_children():
            widget.destroy()

        tasks = self.task_manager.read_tasks()
        tasks.sort(key=lambda t: (
            t.get("completed", False), 
            self.priority_order.get(t.get("priority", "Média"), 2),
            t.get("id", 0)
        ))

        if not tasks:
            self.show_empty_state()
            return

        for idx, t in enumerate(tasks):
            self.create_task_card(t, idx + 1)

    def show_empty_state(self):
        empty_label = ctk.CTkLabel(
            self.tasks_container,
            text="Nenhuma tarefa pendente.\n\nDiga: \"Jarvis, adicionar comprar café com prioridade alta\"",
            font=ctk.CTkFont(family="Segoe UI", size=13, slant="italic"),
            text_color="#636366",
            pady=40
        )
        empty_label.pack(fill="x", padx=10)

    def create_task_card(self, task, display_num):
        card = ctk.CTkFrame(self.tasks_container, fg_color=self.card_bg_color, height=50, corner_radius=8)
        card.pack(fill="x", pady=5, padx=5)
        card.pack_propagate(False)

        if self.editing_task_id == task["id"]:
            self.edit_task_inline(card, task)
            return

        is_completed = task.get("completed", False)
        if is_completed:
            text_color = "#48484A"
            text_font = ctk.CTkFont(family="Segoe UI", size=13, overstrike=True)
            p_color = "#3A3A3C"
        else:
            text_color = "#FFFFFF"
            text_font = ctk.CTkFont(family="Segoe UI", size=13)
            priority_colors = {"Alta": "#FF453A", "Média": "#FF9F0A", "Baixa": "#8E8E93"}
            p_color = priority_colors.get(task.get("priority", "Média"), "#8E8E93")

        # Número da Tarefa
        num_label = ctk.CTkLabel(
            card, 
            text=f"{display_num}.", 
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#8E8E93",
            width=20
        )
        num_label.pack(side="left", padx=(10, 2))

        # Checkbox
        checkbox = ctk.CTkCheckBox(
            card,
            text="",
            width=24,
            height=24,
            corner_radius=12,
            fg_color=self.accent_color,
            hover_color="#00B8D4",
            border_color="#48484A",
            command=lambda: self.toggle_task(task["id"])
        )
        checkbox.pack(side="left", padx=(5, 8))
        if is_completed:
            checkbox.select()

        # Botão Deletar
        btn_del = ctk.CTkButton(
            card,
            text="✕",
            width=20,
            height=20,
            fg_color="transparent",
            text_color="#636366",
            hover_color="#3A3A3C",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=lambda: self.delete_task(task["id"])
        )
        btn_del.pack(side="right", padx=(5, 5))

        # Botão Editar
        btn_edit = ctk.CTkButton(
            card,
            text="✎",
            width=20,
            height=20,
            fg_color="transparent",
            text_color="#636366",
            hover_color="#3A3A3C",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=lambda: self.start_editing(task["id"])
        )
        btn_edit.pack(side="right", padx=(2, 2))

        # Badge Prioridade
        priority_label = ctk.CTkLabel(
            card,
            text=task.get("priority", "Média").upper(),
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=p_color,
            fg_color="transparent",
            width=50
        )
        priority_label.pack(side="right", padx=(5, 10))

        # Texto da Tarefa
        text_label = ctk.CTkLabel(card, text=task["text"], font=text_font, text_color=text_color, anchor="w")
        text_label.pack(side="left", fill="both", expand=True, padx=5)

    def start_editing(self, task_id):
        self.editing_task_id = task_id
        self.refresh_tasks()

    def edit_task_inline(self, card, task):
        # Elementos da direita empacotados primeiro
        btn_cancel = ctk.CTkButton(
            card, text="✕", width=24, height=24, fg_color="#FF453A", text_color="#FFFFFF",
            hover_color="#FF3B30", font=ctk.CTkFont(size=12, weight="bold"), command=self.cancel_editing
        )
        btn_cancel.pack(side="right", padx=(4, 10))

        btn_save = ctk.CTkButton(
            card, text="✓", width=24, height=24, fg_color="#34C759", text_color="#FFFFFF",
            hover_color="#30D158", font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self.save_edited_task(task["id"], entry_edit.get().strip(), combo_edit.get())
        )
        btn_save.pack(side="right", padx=(4, 4))

        combo_edit = ctk.CTkOptionMenu(
            card, values=["Alta", "Média", "Baixa"], width=85, height=26,
            fg_color="#121212", button_color="#2C2C2E", dropdown_fg_color="#1E1E1E"
        )
        combo_edit.set(task.get("priority", "Média"))
        combo_edit.pack(side="right", padx=(4, 4))

        entry_edit = ctk.CTkEntry(
            card, fg_color="#121212", border_color=self.accent_color, height=28,
            font=ctk.CTkFont(family="Segoe UI", size=13)
        )
        entry_edit.insert(0, task["text"])
        entry_edit.pack(side="left", fill="x", expand=True, padx=(15, 4))
        entry_edit.focus()

        # Bindings
        entry_edit.bind("<Return>", lambda e: self.save_edited_task(task["id"], entry_edit.get().strip(), combo_edit.get()))
        entry_edit.bind("<Escape>", lambda e: self.cancel_editing())

    def on_closing(self):
        if hasattr(self, 'voice_handler'):
            self.voice_handler.close()
        self.destroy()

if __name__ == "__main__":
    app = JarvisApp()
    app.mainloop()