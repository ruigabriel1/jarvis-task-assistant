# Relatório de Garantia de Qualidade (QA Report)
## Jarvis Task Assistant

Este documento apresenta uma auditoria detalhada de qualidade do código, conformidade com boas práticas, avaliação de thread safety, modularidade, design de interface Tkinter (CustomTkinter), tolerância a falhas e sugestões práticas de refatoração para o projeto **Jarvis Task Assistant**.

---

### 1. Resumo Executivo
O **Jarvis Task Assistant** é um aplicativo de gerenciamento de tarefas controlado por voz com integração à inteligência artificial do Gemini. O aplicativo é composto por uma interface gráfica escrita em `customtkinter` (`app.pyw`), um motor de processamento de voz de segundo plano (`voice_handler.py`), um persistenciador de dados (`task_manager.py`) e uma suite de testes automatizados (`test_voice_handler.py`).

Após uma análise profunda do codebase, concluímos que o projeto está bem estruturado e o uso de threads de segundo plano para voz e chamadas de API está correto, gerando a responsividade da interface gráfica. Entretanto, foram encontrados **riscos de segurança de concorrência no sistema de logs**, **vulnerabilidades de corrupção de dados na gravação de arquivos**, **bugs de lógica na interpretação de comandos de voz** e **oportunidades críticas de refatoração para modularidade (DRY)**.

---

### 2. Avaliação por Componente

#### A. `app.pyw` (Interface Gráfica)
*   **Responsividade:** O uso de `self.after(0, ...)` para delegar atualizações da GUI a partir de threads secundárias está excelente e evita congelamentos ou colisões de concorrência com o loop do Tkinter.
*   **Edição Inline:** A funcionalidade de edição inline é muito elegante, eliminando a necessidade de pop-ups perturbadores. A suspensão temporária do refresh de voz enquanto o usuário digita (`editing_task_id is not None`) é uma ótima decisão de UX.
*   **Pontos de Melhoria de UI/UX:**
    1.  **Cursor do Canvas:** O indicador circular de ativação por voz é um widget `tk.Canvas` que não possui cursor interativo, fazendo com que o usuário não perceba que ele é clicável. Recomendado configurar `cursor="hand2"`.
    2.  **Foco Inicial:** Quando o app é aberto, o campo de entrada principal `entry_task` não ganha foco automaticamente.
    3.  **Truncamento de Texto:** Os cards de tarefas possuem altura fixa (`50px`) e impedem propagação de tamanho (`pack_propagate(False)`). Se um texto de tarefa for muito longo, ele será cortado horizontalmente, pois o label não tem quebra de linha ativada.
    4.  **Acessibilidade:** A indicação do modo de voz é baseada puramente em cores (azul ciano, cinza, amarelo, vermelho), o que afeta usuários com daltonismo. A barra de status de texto mitiga isso parcialmente, mas a indicação visual poderia ser melhorada com padrões ou textos adicionais.

#### B. `voice_handler.py` (Processamento de Voz & LLM)
*   **Processamento de Linguagem:** A tolerância a variações do nome "Jarvis" (ex: "Chaves", "Jarbas") melhora significativamente a experiência do usuário com falas em português. A lógica de conversão TTS via fila thread-safe em thread secundária está correta.
*   **Bug de Parsing de Prefixo:** Na extração de IDs para conclusão, edição ou remoção de tarefas, o algoritmo remove apenas o primeiro prefixo detectado e para:
    ```python
    clean_target = target.lower().strip()
    for id_pref in id_prefixes:
        if clean_target.startswith(id_pref):
            clean_target = clean_target[len(id_pref):].strip()
            break
    ```
    Se o usuário disser *"concluir a tarefa número 2"*, o loop remove *"a tarefa "* e faz um `break`. O termo resultante é *"número 2"*. Como contém a palavra "número", `clean_target.isdigit()` falhará e a conclusão por número não funcionará.
*   **Concorrência no Log:** O método `log(self, message)` abre e anexa texto ao arquivo `jarvis.log` diretamente. Como é invocado simultaneamente pela thread de voz, pela thread do speaker (TTS), pela thread do Gemini e pela thread principal da GUI, ocorrem condições de corrida (*race conditions*) que podem causar exceções de compartilhamento de arquivo no Windows (`PermissionError`) ou misturar logs.

#### C. `task_manager.py` (Gerenciamento de Arquivos JSON)
*   **Thread Safety:** O uso de `threading.RLock()` protege adequadamente o acesso ao arquivo `tasks.json` em operações isoladas. A introdução do método `update_tasks(modify_callback)` garante a atomicidade do ciclo de Leitura-Modificação-Escrita.
*   **Vulnerabilidade de Corrupção de Dados:** Ao abrir o arquivo no modo `'w'` diretamente:
    ```python
    with open(self.filepath, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    ```
    O arquivo é truncado (apagado) no início da gravação. Se o aplicativo falhar ou o sistema perder energia durante o `json.dump`, o arquivo de tarefas ficará permanentemente vazio ou corrompido, gerando perda total dos dados.
*   **Falta de Tratamento de Corrupção:** Se o arquivo `tasks.json` estiver corrompido, `read_tasks` retorna `[]` silenciando o erro. Se o usuário em seguida adicionar qualquer tarefa, o gerenciador escreverá a nova lista, apagando silenciosamente as tarefas anteriores que poderiam ser recuperadas.

#### D. `test_voice_handler.py` (Testes de Unidade)
*   **Qualidade:** Excelente suíte de testes contendo 14 casos que cobrem todas as regras de negócio de voz sem a necessidade de interações físicas de áudio ou chamadas de API reais.
*   **Estabilidade:** O isolamento dos testes está bom, limpando arquivos temporários adequadamente no `tearDown`. Todos os 14 testes passam sem falhas.

---

### 3. Análise Profunda & Recomendações de Código

#### A. Concorrência e Thread Safety (Logs)
**Problema:** Operações de arquivo concorrentes não sincronizadas no método `log()` de `VoiceHandler`.
**Recomendação:** Utilizar o módulo nativo de logging do Python (`logging`), que é thread-safe por padrão, ou adicionar uma trava (`threading.Lock`) dedicada aos logs de arquivo.

#### B. Modularity & Acoplamento (Violação do Princípio DRY)
**Problema 1 (Sorting):** A lógica de ordenação e ordenação de prioridade das tarefas está duplicada em **6 lugares diferentes** no código (`app.pyw` e `voice_handler.py`), incluindo métodos de callback de edição, exclusão e conclusão por voz.
**Problema 2 (Anemic Model):** As funções de adicionar, editar, remover e concluir tarefas manipulam a lista bruta de dicionários em callbacks espalhados na GUI e no Voice Handler.
**Recomendação:** Centralizar a lógica de dados na classe `TaskManager`. Implementar métodos específicos como `get_sorted_tasks()`, `add_task()`, `delete_task()`, `complete_task()` e `edit_task()` dentro de `task_manager.py`.

#### C. Exception Safety e Integridade de Dados
**Problema:** Gravação insegura direta no arquivo de tarefas principal.
**Recomendação:** Escrever as tarefas primeiro em um arquivo temporário no mesmo diretório (ex: `tasks.json.tmp`) e depois usar `os.replace` para substituir o arquivo original de forma atômica e segura.

---

### 4. Diffs de Refatoração Propostos

#### Refatoração 1: Modularização e Escrita Segura em `task_manager.py`
Esta mudança centraliza a ordenação das tarefas, adiciona métodos de conveniência para manipulação e implementa gravação atômica via arquivo temporário.

```diff
--- C:\Users\ruiga\OneDrive\Documents\jarvis-task-assistant\task_manager.py
+++ C:\Users\ruiga\OneDrive\Documents\jarvis-task-assistant\task_manager.py
@@ -1,37 +1,99 @@
 import os
 import json
 import threading
+import tempfile
 
 class TaskManager:
     def __init__(self, filepath):
         self.filepath = filepath
         self._lock = threading.RLock()
+        self.priority_order = {"Alta": 1, "Média": 2, "Baixa": 3}
 
     def read_tasks(self):
         """Thread-safe read from tasks.json."""
         with self._lock:
             if not os.path.exists(self.filepath):
                 return []
             try:
                 with open(self.filepath, 'r', encoding='utf-8') as f:
                     return json.load(f)
             except Exception as e:
                 print(f"[TaskManager] Error reading tasks: {e}")
                 return []
 
     def write_tasks(self, tasks):
-        """Thread-safe write to tasks.json."""
+        """Thread-safe and atomic write to tasks.json using a temp file."""
         with self._lock:
+            dir_name = os.path.dirname(os.path.abspath(self.filepath))
+            temp_fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix="tasks_", suffix=".tmp")
             try:
-                with open(self.filepath, 'w', encoding='utf-8') as f:
+                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                     json.dump(tasks, f, ensure_ascii=False, indent=2)
+                os.replace(temp_path, self.filepath)
                 return True
             except Exception as e:
                 print(f"[TaskManager] Error writing tasks: {e}")
+                if os.path.exists(temp_path):
+                    try:
+                        os.remove(temp_path)
+                    except Exception:
+                        pass
                 return False
 
     def update_tasks(self, modify_callback):
         """Thread-safe and atomic read-modify-write cycle."""
         with self._lock:
             tasks = self.read_tasks()
             modified_tasks = modify_callback(tasks)
             if modified_tasks is not None:
                 return self.write_tasks(modified_tasks)
             return False
+
+    def get_sorted_tasks(self):
+        """Returns tasks sorted by completed status, priority, and ID."""
+        with self._lock:
+            tasks = self.read_tasks()
+            tasks.sort(key=lambda t: (
+                t.get("completed", False),
+                self.priority_order.get(t.get("priority", "Média"), 2),
+                t.get("id", 0)
+            ))
+            return tasks
+
+    def add_task(self, text, priority="Média"):
+        """Add a new task with unique ID."""
+        def callback(tasks_list):
+            new_id = max([t.get("id", 0) for t in tasks_list] + [0]) + 1
+            new_task = {"id": new_id, "text": text, "completed": False, "priority": priority}
+            tasks_list.append(new_task)
+            return tasks_list
+        return self.update_tasks(callback)
+
+    def toggle_task(self, task_id):
+        """Toggle the completed state of a task by ID."""
+        def callback(tasks_list):
+            for t in tasks_list:
+                if t["id"] == task_id:
+                    t["completed"] = not t["completed"]
+                    break
+            return tasks_list
+        return self.update_tasks(callback)
+
+    def delete_task(self, task_id):
+        """Delete a task by ID."""
+        def callback(tasks_list):
+            return [t for t in tasks_list if t["id"] != task_id]
+        return self.update_tasks(callback)
+
+    def save_edited_task(self, task_id, new_text, new_priority):
+        """Save changes to an existing task."""
+        def callback(tasks_list):
+            for t in tasks_list:
+                if t["id"] == task_id:
+                    t["text"] = new_text
+                    t["priority"] = new_priority
+                    break
+            return tasks_list
+        return self.update_tasks(callback)
```

---

#### Refatoração 2: Correção do Parsing de Prefixos e Thread-Safe Log em `voice_handler.py`
Esta alteração implementa a escuta recursiva de múltiplos prefixos de identificação por voz, prevenindo falhas de interpretação de números, e adiciona um `threading.Lock` para evitar conflito na gravação concorrente de logs.

```diff
--- C:\Users\ruiga\OneDrive\Documents\jarvis-task-assistant\voice_handler.py
+++ C:\Users\ruiga\OneDrive\Documents\jarvis-task-assistant\voice_handler.py
@@ -19,6 +19,7 @@
         self.running = True
         
         self.project_dir = os.path.dirname(os.path.abspath(__file__))
         self.log_filepath = os.path.join(self.project_dir, "jarvis.log")
+        self.log_lock = threading.Lock()
         
         try:
-            with open(self.log_filepath, 'w', encoding='utf-8') as f:
-                f.write(f"=== LOG DO JARVIS INICIADO EM {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
+            with self.log_lock:
+                with open(self.log_filepath, 'w', encoding='utf-8') as f:
+                    f.write(f"=== LOG DO JARVIS INICIADO EM {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
         except Exception:
             pass
@@ -57,11 +58,12 @@
     def log(self, message):
         timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
         try:
-            with open(self.log_filepath, 'a', encoding='utf-8') as f:
-                f.write(f"[{timestamp}] {message}\n")
+            with self.log_lock:
+                with open(self.log_filepath, 'a', encoding='utf-8') as f:
+                    f.write(f"[{timestamp}] {message}\n")
         except Exception:
             pass
 
     def _speech_worker(self):
@@ -231,10 +232,15 @@
             
             clean_target = target.lower().strip()
-            for id_pref in id_prefixes:
-                if clean_target.startswith(id_pref):
-                    clean_target = clean_target[len(id_pref):].strip()
-                    break
+            # Processamento em loop para remover múltiplos prefixos encadeados (ex: "a tarefa de número 2")
+            stripped = True
+            while stripped:
+                stripped = False
+                for id_pref in id_prefixes:
+                    if clean_target.startswith(id_pref):
+                        clean_target = clean_target[len(id_pref):].strip()
+                        stripped = True
+                        break
 
             completed_info = {"text": "", "found": False}
```

---

#### Refatoração 3: Interface Gráfica UX em `app.pyw`
Esta mudança melhora o comportamento visual da janela principal, forçando o foco inicial no campo de entrada de tarefas e adicionando o cursor do tipo mãozinha ao canvas do status de voz, o que indica visualmente que o elemento é clicável.

```diff
--- C:\Users\ruiga\OneDrive\Documents\jarvis-task-assistant\app.pyw
+++ C:\Users\ruiga\OneDrive\Documents\jarvis-task-assistant\app.pyw
@@ -37,6 +37,7 @@
         self.voice_handler = VoiceHandler(self.task_manager, self.on_voice_event)
         self.refresh_tasks()
         
+        self.entry_task.focus()
         self.protocol("WM_DELETE_WINDOW", self.on_closing)
 
     def center_window(self):
@@ -75,6 +76,7 @@
             highlightthickness=0
         )
         self.indicator_canvas.place(relx=1.0, rely=0.3, anchor="ne")
+        self.indicator_canvas.configure(cursor="hand2")
         self.draw_indicator("#3A3A3C")
         self.indicator_canvas.bind("<Button-1>", self.toggle_voice_handler)
```

---

### 5. Lista de Ações Recomendadas
Para elevar a robustez e maturidade do projeto, sugerimos as seguintes atividades:

1.  **Refatorar o Acesso a Dados:** Aplicar a Refatoração 1 no arquivo `task_manager.py`. Substituir a manipulação direta de dicionários no arquivo `app.pyw` por chamadas diretas como `self.task_manager.toggle_task()`, simplificando a interface gráfica.
2.  **Corrigir a Escuta e Log:** Aplicar a Refatoração 2 no arquivo `voice_handler.py` para garantir logs thread-safe e a eliminação do bug de identificação de números com múltiplos prefixos.
3.  **Melhorar Polimento Visual:** Aplicar a Refatoração 3 no arquivo `app.pyw` para melhor feedback visual ao usuário sobre o indicador clicável e ganho automático de foco.
4.  **Tolerância a Arquivo Corrompido:** Modificar `read_tasks` para gerar um backup do arquivo `tasks.json` caso o JSON de leitura seja inválido, prevenindo a perda total silenciosa das tarefas anteriores na próxima escrita.
5.  **Acessibilidade de Voz:** Adicionar uma dica de ferramenta (Tooltip) ou um rótulo textual legível perto do canvas informando o status atual de forma redundante e acessível.
