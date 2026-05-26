import os
import json
import unittest
from unittest.mock import MagicMock
from voice_handler import VoiceHandler
from task_manager import TaskManager

class TestVoiceHandler(unittest.TestCase):
    def setUp(self):
        self.test_tasks_file = "test_tasks.json"
        if os.path.exists(self.test_tasks_file):
            try:
                os.remove(self.test_tasks_file)
            except Exception:
                pass
            
        self.initial_tasks = [
            {"id": 1, "text": "Configurar o Jarvis Task Assistant", "completed": False, "priority": "Alta"},
            {"id": 2, "text": "Comprar café", "completed": False, "priority": "Média"},
            {"id": 3, "text": "Limpar a mesa", "completed": True, "priority": "Baixa"}
        ]
        
        self.task_manager = TaskManager(self.test_tasks_file)
        self.task_manager.write_tasks(self.initial_tasks)
            
        self.gui_callback = MagicMock()
        
        # Initialize VoiceHandler offline without mic
        self.handler = VoiceHandler(self.task_manager, self.gui_callback, start_listening=False)
        self.handler.active_mode = True
        
        # Mock speak/TTS to collect spoken messages
        self.spoken_messages = []
        self.handler.speak = self.spoken_messages.append
        
        # Mock handle_question to prevent real Gemini call
        self.handler.handle_question = MagicMock()

    def tearDown(self):
        self.handler.close()
        if os.path.exists(self.test_tasks_file):
            try:
                os.remove(self.test_tasks_file)
            except Exception:
                pass

    def get_tasks(self):
        return self.task_manager.read_tasks()

    def test_add_task_simple(self):
        self.handler.process_phrase("adicionar comprar pão")
        tasks = self.get_tasks()
        self.assertEqual(len(tasks), 4)
        self.assertEqual(tasks[-1]["text"], "comprar pão")
        self.assertEqual(tasks[-1]["priority"], "Média")
        self.assertTrue(any("comprar pão" in msg for msg in self.spoken_messages))

    def test_add_task_with_priority_high(self):
        self.handler.process_phrase("crie a tarefa estudar Python com prioridade alta")
        tasks = self.get_tasks()
        self.assertEqual(len(tasks), 4)
        self.assertEqual(tasks[-1]["text"], "estudar Python")
        self.assertEqual(tasks[-1]["priority"], "Alta")

    def test_add_task_with_priority_low(self):
        self.handler.process_phrase("adicionar caminhar no parque com prioridade baixa")
        tasks = self.get_tasks()
        self.assertEqual(tasks[-1]["text"], "caminhar no parque")
        self.assertEqual(tasks[-1]["priority"], "Baixa")

    def test_complete_task_by_number(self):
        # Tasks sorted order: 
        # 1. Configurar o Jarvis... (id 1, Alta, False)
        # 2. Comprar café (id 2, Média, False)
        # 3. Limpar a mesa (id 3, Baixa, True)
        self.handler.process_phrase("concluir número 2")
        tasks = self.get_tasks()
        # id 2 should now be completed
        task2 = next(t for t in tasks if t["id"] == 2)
        self.assertTrue(task2["completed"])

    def test_complete_task_by_text(self):
        self.handler.process_phrase("concluir café")
        tasks = self.get_tasks()
        task2 = next(t for t in tasks if t["id"] == 2)
        self.assertTrue(task2["completed"])

    def test_delete_task_by_number(self):
        self.handler.process_phrase("deletar a 1")
        tasks = self.get_tasks()
        self.assertEqual(len(tasks), 2)
        self.assertFalse(any(t["id"] == 1 for t in tasks))

    def test_delete_task_by_text(self):
        self.handler.process_phrase("remover café")
        tasks = self.get_tasks()
        self.assertEqual(len(tasks), 2)
        self.assertFalse(any(t["id"] == 2 for t in tasks))

    def test_edit_task_by_number(self):
        self.handler.process_phrase("alterar a 2 para comprar leite")
        tasks = self.get_tasks()
        task2 = next(t for t in tasks if t["id"] == 2)
        self.assertEqual(task2["text"], "comprar leite")

    def test_edit_task_by_text(self):
        self.handler.process_phrase("mudar café para comprar café preto")
        tasks = self.get_tasks()
        task2 = next(t for t in tasks if t["id"] == 2)
        self.assertEqual(task2["text"], "comprar café preto")

    def test_edit_priority_direct(self):
        self.handler.process_phrase("café com prioridade alta")
        tasks = self.get_tasks()
        task2 = next(t for t in tasks if t["id"] == 2)
        self.assertEqual(task2["priority"], "Alta")

    def test_wake_word(self):
        self.handler.active_mode = False
        self.handler.process_phrase("Ligar Jarvis")
        self.assertTrue(self.handler.active_mode)

    def test_sleep_word(self):
        self.handler.active_mode = True
        self.handler.process_phrase("Desligar Jarvis")
        self.assertFalse(self.handler.active_mode)

    def test_list_tasks(self):
        self.handler.process_phrase("quais são minhas tarefas")
        self.assertTrue(any("tarefas pendentes" in msg for msg in self.spoken_messages))

    def test_complete_task_with_multiple_prefixes(self):
        # Test stripping multiple prefixes sequentially: "concluir a número 2" -> target "a número 2" -> "2"
        self.handler.process_phrase("concluir a número 2")
        tasks = self.get_tasks()
        task2 = next(t for t in tasks if t["id"] == 2)
        self.assertTrue(task2["completed"])

    def test_delete_task_with_tarefa_prefix(self):
        # Test stripping "tarefa" prefix: "deletar tarefa 1" -> target "tarefa 1" -> "1"
        self.handler.process_phrase("deletar tarefa 1")
        tasks = self.get_tasks()
        self.assertEqual(len(tasks), 2)
        self.assertFalse(any(t["id"] == 1 for t in tasks))

    def test_complete_task_by_text_with_prefix(self):
        # Test completing by text with prefix: "concluir a tarefa comprar café" -> target "a tarefa comprar café" -> clean target "comprar café"
        self.handler.process_phrase("concluir a tarefa comprar café")
        tasks = self.get_tasks()
        task2 = next(t for t in tasks if t["id"] == 2)
        self.assertTrue(task2["completed"])

    def test_complete_task_with_multiple_prefixes(self):
        # Test stripping multiple prefixes sequentially: "concluir a número 2" -> target "a número 2" -> "2"
        self.handler.process_phrase("concluir a número 2")
        tasks = self.get_tasks()
        task2 = next(t for t in tasks if t["id"] == 2)
        self.assertTrue(task2["completed"])

    def test_delete_task_with_tarefa_prefix(self):
        # Test stripping "tarefa" prefix: "deletar tarefa 1" -> target "tarefa 1" -> "1"
        self.handler.process_phrase("deletar tarefa 1")
        tasks = self.get_tasks()
        self.assertEqual(len(tasks), 2)
        self.assertFalse(any(t["id"] == 1 for t in tasks))

    def test_complete_task_by_text_with_prefix(self):
        # Test completing by text with prefix: "concluir a tarefa comprar café" -> target "a tarefa comprar café" -> clean target "comprar café"
        self.handler.process_phrase("concluir a tarefa comprar café")
        tasks = self.get_tasks()
        task2 = next(t for t in tasks if t["id"] == 2)
        self.assertTrue(task2["completed"])

    def test_fallback_to_gemini(self):
        # Unrecognized phrase should trigger LLM fallback (handle_question)
        self.handler.process_phrase("Quem é o presidente do Brasil?")
        self.handler.handle_question.assert_called_once_with("Quem é o presidente do Brasil?")

if __name__ == "__main__":
    unittest.main()