import threading
import time
import json
import os
import queue
import urllib.request
import urllib.error
import speech_recognition as sr
import pyttsx3
import pythoncom
import re
import asyncio
import tempfile

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

try:
    import keyboard
except ImportError:
    keyboard = None

class VoiceHandler:
    def __init__(self, task_manager, gui_callback=None, start_listening=True):
        self.task_manager = task_manager
        self.gui_callback = gui_callback
        self.active_mode = False
        self.running = True
        self.edge_voice = "pt-BR-AntonioNeural"
        
        self.project_dir = os.path.dirname(os.path.abspath(__file__))
        self.log_dir = os.path.join(self.project_dir, "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_filepath = os.path.join(self.log_dir, "jarvis.log")
        
        try:
            with open(self.log_filepath, 'w', encoding='utf-8') as f:
                f.write(f"=== LOG DO JARVIS INICIADO EM {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        except Exception:
            pass

        self.log("Inicializando VoiceHandler...")
        self.speech_queue = queue.Queue()
        self.speaker_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.speaker_thread.start()

        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        
        self.mic_available = False
        self.stop_listening_fn = None

        # Configurações do motor de reconhecimento de voz e hotkey
        self.hotkey = "ctrl+shift+j"
        self.speech_engine = "google"
        self.whisper_model_name = "tiny"
        self.whisper_device = "auto"
        self.whisper_compute_type = "auto"
        self.whisper_model = None
        self.whisper_loading = False
        self.whisper_loaded = False

        # Carregar configurações do config.json
        config_path = os.path.join(self.project_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.hotkey = config.get("HOTKEY", "ctrl+shift+j")
                    self.speech_engine = config.get("speech_engine", "auto")
                    self.whisper_model_name = config.get("whisper_model", "tiny")
                    self.whisper_device = config.get("whisper_device", "auto")
                    self.whisper_compute_type = config.get("whisper_compute_type", "auto")
            except Exception as e:
                self.log(f"Erro ao ler config.json: {e}")

        if start_listening:
            # Inicializa Whisper em segundo plano se configurado
            if self.speech_engine in ["faster-whisper", "auto"]:
                self.whisper_loading = True
                threading.Thread(target=self._init_whisper_backend, daemon=True).start()

            try:
                self.microphone = sr.Microphone()
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
                self.mic_available = True
                self.log("Microfone padrão inicializado e calibrado.")
                self.stop_listening_fn = self.recognizer.listen_in_background(
                    self.microphone, 
                    self.audio_callback,
                    phrase_time_limit=6
                )
                self.log("Escuta contínua de fundo ativada.")
            except Exception as e:
                self.log(f"ERRO ao inicializar microfone: {e}")

        self.hotkey_hook = None
        if start_listening and keyboard:
            try:
                self.hotkey_hook = keyboard.add_hotkey(self.hotkey, self.toggle_active)
                self.log(f"Hotkey global '{self.hotkey}' registrada com sucesso.")
            except Exception as e:
                self.log(f"Erro ao registrar hotkey global '{self.hotkey}': {e}")

    def _resolve_whisper_params(self):
        device = self.whisper_device
        compute_type = self.whisper_compute_type

        if device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
                    self.log("GPU com suporte CUDA detectada para Whisper.")
                else:
                    device = "cpu"
                    self.log("GPU não detectada. Utilizando CPU para Whisper.")
            except ImportError:
                device = "cpu"
                self.log("PyTorch não importado. Utilizando CPU para Whisper.")

        if compute_type == "auto":
            if device == "cuda":
                compute_type = "float16"
            else:
                compute_type = "int8"

        return device, compute_type

    def _init_whisper_backend(self):
        self.log("Iniciando carregamento do motor faster-whisper em segundo plano...")
        try:
            from faster_whisper import WhisperModel
            import numpy as np # Garante que numpy está disponível
            
            device, compute_type = self._resolve_whisper_params()
            
            self.log(f"Carregando modelo '{self.whisper_model_name}' (device={device}, compute_type={compute_type})...")
            self.whisper_model = WhisperModel(
                self.whisper_model_name,
                device=device,
                compute_type=compute_type
            )
            self.whisper_loaded = True
            self.whisper_loading = False
            self.log(f"Motor faster-whisper carregado com sucesso. Modelo: {self.whisper_model_name}")
        except ImportError as e:
            self.whisper_loading = False
            self.log(f"faster-whisper ou dependência não instalada. Erro: {e}")
            if self.speech_engine == "faster-whisper":
                self.speak("Aviso: Motor de voz offline não está disponível. Usando modo online.")
        except Exception as e:
            self.whisper_loading = False
            self.log(f"Erro ao inicializar o modelo faster-whisper '{self.whisper_model_name}': {e}")
            if self.speech_engine == "faster-whisper":
                self.speak("Aviso: Falha ao carregar o modelo de voz offline. Usando modo online.")

    def _transcribe(self, audio):
        use_whisper = False
        if self.speech_engine == "faster-whisper":
            if self.whisper_loaded:
                use_whisper = True
            else:
                self.log("Whisper configurado mas ainda não carregado ou falhou. Tentando Google...")
        elif self.speech_engine == "auto":
            if self.whisper_loaded:
                use_whisper = True

        if use_whisper:
            try:
                self.log("Transcrevendo com motor offline (faster-whisper)...")
                import numpy as np
                raw_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
                audio_np = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Executa transcrição no idioma português
                segments, info = self.whisper_model.transcribe(
                    audio_np,
                    beam_size=5,
                    language="pt"
                )
                
                text = "".join(segment.text for segment in segments).strip()
                return text
            except Exception as e:
                self.log(f"Erro na transcrição do faster-whisper: {e}. Tentando fallback online...")

        # Fallback para o reconhecedor online do Google
        self.log("Transcrevendo com motor online (Google)...")
        return self.recognizer.recognize_google(audio, language="pt-BR").strip()

    def log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.log_filepath, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass

    def _play_audio(self, filepath):
        if os.name == 'nt':
            import ctypes
            size = 256
            buffer = ctypes.create_unicode_buffer(size)
            ctypes.windll.kernel32.GetShortPathNameW(filepath, buffer, size)
            short_path = buffer.value or filepath
            
            alias = f"jarvis_play_{int(time.time() * 1000)}"
            winmm = ctypes.windll.winmm
            try:
                winmm.mciSendStringW(f'close {alias}', None, 0, 0)
                res = winmm.mciSendStringW(f'open "{short_path}" type mpegvideo alias {alias}', None, 0, 0)
                if res != 0:
                    raise RuntimeError(f"MCI open error: {res}")
                res = winmm.mciSendStringW(f'play {alias} wait', None, 0, 0)
                if res != 0:
                    raise RuntimeError(f"MCI play error: {res}")
            finally:
                winmm.mciSendStringW(f'close {alias}', None, 0, 0)
        else:
            import subprocess
            if hasattr(os, 'uname'):
                sysname = os.uname().sysname
            else:
                sysname = ''
            
            if sysname == 'Darwin':
                subprocess.run(['afplay', filepath], check=True)
            else:
                for player in ['mpg123', 'mpv', 'play']:
                    try:
                        subprocess.run([player, filepath], check=True)
                        break
                    except FileNotFoundError:
                        continue

    def _speak_edge_tts(self, text):
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, f"jarvis_tts_{int(time.time() * 1000)}.mp3")
        try:
            async def generate():
                communicate = edge_tts.Communicate(text, self.edge_voice)
                await communicate.save(temp_file)
                
            asyncio.run(generate())
            
            if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                self._play_audio(temp_file)
                return True
            return False
        except Exception as e:
            self.log(f"Falha ao gerar/tocar áudio edge-tts: {e}")
            return False
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    def _speech_worker(self):
        pythoncom.CoInitialize()
        try:
            pyttsx3_engine = pyttsx3.init()
            pyttsx3_engine.setProperty('rate', 175)
            voices = pyttsx3_engine.getProperty('voices')
            for voice in voices:
                if any(x in voice.id.upper() for x in ['PT', 'PORTUGUESE', 'BRAZIL']):
                    pyttsx3_engine.setProperty('voice', voice.id)
                    break
        except Exception as e:
            self.log(f"ERRO no pyttsx3: {e}")
            pyttsx3_engine = None

        while self.running:
            try:
                text = self.speech_queue.get(timeout=1.0)
                if not text:
                    self.speech_queue.task_done()
                    continue
                
                success = False
                if HAS_EDGE_TTS:
                    try:
                        success = self._speak_edge_tts(text)
                    except Exception as e:
                        self.log(f"Erro durante execução do edge-tts: {e}")
                        success = False
                
                if not success:
                    if pyttsx3_engine:
                        try:
                            pyttsx3_engine.say(text)
                            pyttsx3_engine.runAndWait()
                        except Exception as e:
                            self.log(f"ERRO no pyttsx3 fallback: {e}")
                    else:
                        self.log("Nenhum sintetizador de voz disponível.")
                
                self.speech_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.log(f"ERRO TTS: {e}")
        pythoncom.CoUninitialize()

    def speak(self, text):
        self.speech_queue.put(text)

    def play_chime(self, active):
        if active:
            self.speak("Jarvis ativo. Sim, senhor?")
        else:
            self.speak("Jarvis em repouso.")

    def audio_callback(self, recognizer, audio):
        if not self.running:
            return
        try:
            text = self._transcribe(audio)
            if not text:
                self.log("Áudio não reconhecido (retornou vazio).")
                return
            self.log(f"Reconhecido: \"{text}\"")
            self.process_phrase(text)
        except sr.UnknownValueError:
            self.log("Áudio não reconhecido.")
        except sr.RequestError as e:
            self.log(f"Erro de conexão do Google: {e}")
            if self.gui_callback:
                self.gui_callback("connection_error")
        except Exception as e:
            self.log(f"ERRO inesperado na escuta: {e}")

    def get_sorted_tasks(self):
        tasks = self.task_manager.read_tasks()
        priority_order = {"Alta": 1, "Média": 2, "Baixa": 3}
        tasks.sort(key=lambda t: (
            t.get("completed", False), 
            priority_order.get(t.get("priority", "Média"), 2),
            t.get("id", 0)
        ))
        return tasks

    def process_phrase(self, text):
        phrase = text.lower().strip()
        self.log(f"Processando frase: \"{phrase}\"")

        clean_phrase = phrase.replace(",", " ").replace(".", " ").replace("?", " ").replace("!", " ")
        words = clean_phrase.split()

        wake_words = ["ligar", "ativar", "olá", "ola", "acordar", "iniciar", "alô", "alo", "escutar", "chamar"]
        sleep_words = ["desligar", "desativar", "dormir", "parar", "silenciar", "tchau", "adeus", "repouso"]
        jarvis_variations = ["jarvis", "jarv", "jar", "arvis", "xarvis", "chaves", "jarbas", "javis", "gerente", "jard", "jardi", "jardis", "gard", "gardis"]
        
        has_jarvis = any(j in words for j in jarvis_variations) or any(j in phrase for j in ["jarvis", "jarv", "arvis", "javis"])
        has_sleep = any(w in words for w in sleep_words)
        has_wake = any(w in words for w in wake_words) and not has_sleep

        if has_wake and has_jarvis:
            if not self.active_mode:
                self.active_mode = True
                self.log("Jarvis ATIVADO.")
                self.play_chime(True)
                if self.gui_callback:
                    self.gui_callback("status_active")
            return

        if has_sleep and has_jarvis:
            if self.active_mode:
                self.active_mode = False
                self.log("Jarvis DESATIVADO.")
                self.play_chime(False)
                if self.gui_callback:
                    self.gui_callback("status_inactive")
            return

        if not self.active_mode:
            return

        cmd_text = text
        for jv in jarvis_variations:
            pat = re.compile(r'^\s*' + re.escape(jv) + r'[\s,.:]*', re.IGNORECASE)
            cmd_text = pat.sub('', cmd_text).strip()
        cmd_phrase = cmd_text.lower()

        id_prefixes = ["a tarefa ", "o id ", "do id ", "de id ", "número ", "numero ", "nº ", "no ", "tarefa ", "tarefas ", "a ", "o ", "as ", "os "]
        id_prefixes.sort(key=len, reverse=True)

        # --- COMMAND 1: ADD TASK ---
        add_keywords = ["adicionar", "crie", "criar", "anotar", "adicione", "insira", "inserir"]
        if any(cmd_phrase.startswith(kw) for kw in add_keywords):
            content = cmd_text
            for kw in add_keywords:
                if content.lower().startswith(kw):
                    content = content[len(kw):].strip()
                    break
            
            # Clean common prefixes
            for prefix in ["a tarefa ", "tarefa ", "uma tarefa ", "o compromisso ", "o compromisso de "]:
                if content.lower().startswith(prefix):
                    content = content[len(prefix):].strip()
                    break
            
            if not content:
                self.speak("O que deseja adicionar, senhor?")
                return

            priority = "Média"
            lower_content = content.lower()
            if "prioridade alta" in lower_content:
                priority = "Alta"
                content = re.sub(r'com prioridade alta|prioridade alta', '', content, flags=re.IGNORECASE).strip()
            elif "prioridade média" in lower_content or "prioridade media" in lower_content:
                priority = "Média"
                content = re.sub(r'com prioridade média|com prioridade media|prioridade média|prioridade media', '', content, flags=re.IGNORECASE).strip()
            elif "prioridade baixa" in lower_content:
                priority = "Baixa"
                content = re.sub(r'com prioridade baixa|prioridade baixa', '', content, flags=re.IGNORECASE).strip()
            
            if content.lower().endswith(" com"):
                content = content[:-4].strip()

            def add_cb(tasks_list):
                new_id = max([t.get("id", 0) for t in tasks_list] + [0]) + 1
                new_task = {"id": new_id, "text": content, "completed": False, "priority": priority}
                tasks_list.append(new_task)
                return tasks_list

            if self.task_manager.update_tasks(add_cb):
                self.log(f"Adicionada por voz: {content}")
                self.speak(f"Adicionada: {content}, com prioridade {priority.lower()}.")
                if self.gui_callback:
                    self.gui_callback("refresh")
            return

        # --- COMMAND 2: COMPLETE TASK ---
        complete_keywords = ["concluir", "finalizar", "marcar como concluída", "marcar como concluida", "riscar", "completar"]
        if any(cmd_phrase.startswith(kw) for kw in complete_keywords):
            target = cmd_text
            for kw in complete_keywords:
                if target.lower().startswith(kw):
                    target = target[len(kw):].strip()
                    break
            
            if not target:
                self.speak("Qual tarefa deseja concluir, senhor?")
                return

            clean_target = target.lower().strip()
            while True:
                matched = False
                for id_pref in id_prefixes:
                    if clean_target.startswith(id_pref):
                        clean_target = clean_target[len(id_pref):].strip()
                        matched = True
                        break
                if not matched:
                    break

            completed_info = {"text": "", "found": False}

            def complete_cb(tasks_list):
                priority_order = {"Alta": 1, "Média": 2, "Baixa": 3}
                sorted_tasks = list(tasks_list)
                sorted_tasks.sort(key=lambda t: (
                    t.get("completed", False), 
                    priority_order.get(t.get("priority", "Média"), 2),
                    t.get("id", 0)
                ))
                
                if clean_target.isdigit():
                    idx = int(clean_target) - 1
                    if 0 <= idx < len(sorted_tasks):
                        target_t = sorted_tasks[idx]
                        for t in tasks_list:
                            if t["id"] == target_t["id"]:
                                t["completed"] = True
                                completed_info["text"] = t["text"]
                                completed_info["found"] = True
                                return tasks_list
                
                if clean_target:
                    for t in tasks_list:
                        if clean_target in t["text"].lower():
                            t["completed"] = True
                            completed_info["text"] = t["text"]
                            completed_info["found"] = True
                            return tasks_list
                return None

            if self.task_manager.update_tasks(complete_cb):
                self.log(f"Concluída por voz: {completed_info['text']}")
                self.speak(f"Tarefa concluída: {completed_info['text']}.")
                if self.gui_callback:
                    self.gui_callback("refresh")
            else:
                self.speak("Não encontrei essa tarefa.")
            return

        # --- COMMAND 3: DELETE TASK ---
        delete_keywords = ["remover", "deletar", "excluir", "apagar"]
        if any(cmd_phrase.startswith(kw) for kw in delete_keywords):
            target = cmd_text
            for kw in delete_keywords:
                if target.lower().startswith(kw):
                    target = target[len(kw):].strip()
                    break

            if not target:
                self.speak("Qual tarefa deseja remover, senhor?")
                return

            clean_target = target.lower().strip()
            while True:
                matched = False
                for id_pref in id_prefixes:
                    if clean_target.startswith(id_pref):
                        clean_target = clean_target[len(id_pref):].strip()
                        matched = True
                        break
                if not matched:
                    break

            deleted_info = {"text": ""}

            def delete_cb(tasks_list):
                priority_order = {"Alta": 1, "Média": 2, "Baixa": 3}
                sorted_tasks = list(tasks_list)
                sorted_tasks.sort(key=lambda t: (
                    t.get("completed", False), 
                    priority_order.get(t.get("priority", "Média"), 2),
                    t.get("id", 0)
                ))
                
                task_to_remove = None
                if clean_target.isdigit():
                    idx = int(clean_target) - 1
                    if 0 <= idx < len(sorted_tasks):
                        task_to_remove = sorted_tasks[idx]
                
                if task_to_remove:
                    deleted_info["text"] = task_to_remove["text"]
                    return [t for t in tasks_list if t["id"] != task_to_remove["id"]]
                
                if clean_target:
                    matches = [t for t in tasks_list if clean_target in t["text"].lower()]
                    if matches:
                        deleted_info["text"] = matches[0]["text"]
                        return [t for t in tasks_list if t["id"] != matches[0]["id"]]
                return None

            if self.task_manager.update_tasks(delete_cb):
                self.log(f"Removida por voz: {deleted_info['text']}")
                self.speak(f"Tarefa removida com sucesso: {deleted_info['text']}.")
                if self.gui_callback:
                    self.gui_callback("refresh")
            else:
                self.speak("Não encontrei a tarefa.")
            return

        # --- COMMAND 4: EDIT TASK ---
        edit_keywords = ["alterar", "atualizar", "mudar", "editar", "corrigir"]
        if any(cmd_phrase.startswith(kw) for kw in edit_keywords):
            target = cmd_text
            for kw in edit_keywords:
                if target.lower().startswith(kw):
                    target = target[len(kw):].strip()
                    break
            
            lower_target = target.lower()
            sep_idx = -1
            sep_len = 0
            for sep in [" para ", " pra "]:
                idx = lower_target.find(sep)
                if idx != -1:
                    sep_idx = idx
                    sep_len = len(sep)
                    break
            
            if sep_idx == -1:
                self.speak("Senhor, por favor indique a tarefa antiga e o novo texto usando 'para'.")
                return

            search_term = target[:sep_idx].strip()
            new_content = target[sep_idx + sep_len:].strip()

            priority = None
            lower_new = new_content.lower()
            if "prioridade alta" in lower_new:
                priority = "Alta"
                new_content = re.sub(r'com prioridade alta|prioridade alta', '', new_content, flags=re.IGNORECASE).strip()
            elif "prioridade média" in lower_new or "prioridade media" in lower_new:
                priority = "Média"
                new_content = re.sub(r'com prioridade média|com prioridade media|prioridade média|prioridade media', '', new_content, flags=re.IGNORECASE).strip()
            elif "prioridade baixa" in lower_new:
                priority = "Baixa"
                new_content = re.sub(r'com prioridade baixa|prioridade baixa', '', new_content, flags=re.IGNORECASE).strip()
            
            if new_content.lower().endswith(" com"):
                new_content = new_content[:-4].strip()

            clean_search = search_term.lower().strip()
            while True:
                matched = False
                for id_pref in id_prefixes:
                    if clean_search.startswith(id_pref):
                        clean_search = clean_search[len(id_pref):].strip()
                        matched = True
                        break
                if not matched:
                    break

            edit_info = {"old_text": "", "priority_msg": ""}

            def edit_cb(tasks_list):
                priority_order = {"Alta": 1, "Média": 2, "Baixa": 3}
                sorted_tasks = list(tasks_list)
                sorted_tasks.sort(key=lambda t: (
                    t.get("completed", False), 
                    priority_order.get(t.get("priority", "Média"), 2),
                    t.get("id", 0)
                ))
                
                found_task = None
                if clean_search.isdigit():
                    idx = int(clean_search) - 1
                    if 0 <= idx < len(sorted_tasks):
                        target_t = sorted_tasks[idx]
                        for t in tasks_list:
                            if t["id"] == target_t["id"]:
                                found_task = t
                                break
                
                if not found_task and clean_search:
                    matches = [t for t in tasks_list if clean_search in t["text"].lower()]
                    if matches:
                        found_task = matches[0]
                
                if found_task:
                    edit_info["old_text"] = found_task["text"]
                    found_task["text"] = new_content
                    if priority:
                        found_task["priority"] = priority
                        edit_info["priority_msg"] = f" e prioridade {priority.lower()}"
                    return tasks_list
                return None

            if self.task_manager.update_tasks(edit_cb):
                self.log(f"Alterada por voz: {edit_info['old_text']} -> {new_content}")
                self.speak(f"Tarefa alterada de '{edit_info['old_text']}' para '{new_content}'{edit_info['priority_msg']}.")
                if self.gui_callback:
                    self.gui_callback("refresh")
            else:
                self.speak(f"Não encontrei '{search_term}'.")
            return

        # --- COMMAND 5: DIRECT PRIORITY MATCH (NO VERB) ---
        p_keywords = [" como prioridade ", " com prioridade "]
        p_idx = -1
        p_len = 0
        for p_kw in p_keywords:
            idx = phrase.find(p_kw)
            if idx != -1:
                p_idx = idx
                p_len = len(p_kw)
                break
        
        if p_idx != -1:
            search_term = text[:p_idx].strip()
            priority_val = text[p_idx + p_len:].strip().lower()
            
            # Limpa prefixos de Jarvis do termo de busca
            for jv in jarvis_variations:
                pat = re.compile(r'^\s*' + re.escape(jv) + r'[\s,.:]*', re.IGNORECASE)
                search_term = pat.sub('', search_term).strip()

            clean_search = search_term.lower().strip()
            while True:
                matched = False
                for id_pref in id_prefixes:
                    if clean_search.startswith(id_pref):
                        clean_search = clean_search[len(id_pref):].strip()
                        matched = True
                        break
                if not matched:
                    break

            mapped_priority = None
            if "alta" in priority_val:
                mapped_priority = "Alta"
            elif "média" in priority_val or "media" in priority_val:
                mapped_priority = "Média"
            elif "baixa" in priority_val:
                mapped_priority = "Baixa"
            
            if mapped_priority:
                priority_info = {"text": ""}

                def priority_cb(tasks_list):
                    priority_order = {"Alta": 1, "Média": 2, "Baixa": 3}
                    sorted_tasks = list(tasks_list)
                    sorted_tasks.sort(key=lambda t: (
                        t.get("completed", False), 
                        priority_order.get(t.get("priority", "Média"), 2),
                        t.get("id", 0)
                    ))
                    
                    found_task = None
                    if clean_search.isdigit():
                        idx = int(clean_search) - 1
                        if 0 <= idx < len(sorted_tasks):
                            target_t = sorted_tasks[idx]
                            for t in tasks_list:
                                if t["id"] == target_t["id"]:
                                    found_task = t
                                    break
                    
                    if not found_task and clean_search:
                        matches = [t for t in tasks_list if clean_search in t["text"].lower()]
                        if matches:
                            found_task = matches[0]
                    
                    if found_task:
                        found_task["priority"] = mapped_priority
                        priority_info["text"] = found_task["text"]
                        return tasks_list
                    return None

                if self.task_manager.update_tasks(priority_cb):
                    self.log(f"Prioridade alterada por voz: {priority_info['text']} -> {mapped_priority}")
                    self.speak(f"Prioridade de '{priority_info['text']}' alterada para {mapped_priority.lower()}.")
                    if self.gui_callback:
                        self.gui_callback("refresh")
                else:
                    self.speak(f"Não encontrei a tarefa '{search_term}'.")
                return

        # --- COMMAND 6: LIST TASKS ---
        list_keywords = ["quais são minhas tarefas", "quais sao minhas tarefas", "listar tarefas", "o que eu tenho para fazer", "o que eu tenho pra fazer", "ver tarefas", "mostrar tarefas"]
        if any(kw in cmd_phrase for kw in list_keywords):
            tasks = self.task_manager.read_tasks()
            pending_tasks = [t for t in tasks if not t["completed"]]
            if not pending_tasks:
                self.speak("Você não tem tarefas pendentes, senhor.")
                return
            self.speak(f"Você tem {len(pending_tasks)} tarefas pendentes.")
            for i, t in enumerate(pending_tasks[:5]):
                self.speak(f"Tarefa {i+1}: {t['text']}, prioridade {t['priority'].lower()}.")
            if len(pending_tasks) > 5:
                self.speak("E mais algumas outras na lista.")
            return

        # --- FALLBACK: ADD TASK DIRECTLY ---
        content = cmd_text
        
        # Clean common prefixes if present
        for prefix in ["adicionar ", "crie ", "criar ", "anotar ", "adicione ", "insira ", "inserir ", "a tarefa ", "tarefa ", "uma tarefa "]:
            if content.lower().startswith(prefix):
                content = content[len(prefix):].strip()
                break

        if not content:
            self.speak("O que deseja adicionar, senhor?")
            return

        priority = "Média"
        lower_content = content.lower()
        if "prioridade alta" in lower_content:
            priority = "Alta"
            content = re.sub(r'com prioridade alta|prioridade alta', '', content, flags=re.IGNORECASE).strip()
        elif "prioridade média" in lower_content or "prioridade media" in lower_content:
            priority = "Média"
            content = re.sub(r'com prioridade média|com prioridade media|prioridade média|prioridade media', '', content, flags=re.IGNORECASE).strip()
        elif "prioridade baixa" in lower_content:
            priority = "Baixa"
            content = re.sub(r'com prioridade baixa|prioridade baixa', '', content, flags=re.IGNORECASE).strip()

        if content.lower().endswith(" com"):
            content = content[:-4].strip()

        def add_cb(tasks_list):
            new_id = max([t.get("id", 0) for t in tasks_list] + [0]) + 1
            new_task = {"id": new_id, "text": content, "completed": False, "priority": priority}
            tasks_list.append(new_task)
            return tasks_list

        if self.task_manager.update_tasks(add_cb):
            self.log(f"Adicionada por fallback de voz: {content}")
            self.speak(f"Adicionada: {content}.")
            if self.gui_callback:
                self.gui_callback("refresh")
        return

    def handle_question(self, question):
        api_key = os.environ.get("GEMINI_API_KEY", "")
        config_path = os.path.join(self.project_dir, "config.json")
        if not api_key and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    api_key = config.get("GEMINI_API_KEY", "")
            except Exception as e:
                self.log(f"Erro ao ler config.json: {e}")

        if not api_key:
            self.log("GEMINI_API_KEY não configurada.")
            self.speak("Desculpe, senhor. Preciso que configure minha chave da API Gemini no arquivo de configurações.")
            if self.gui_callback:
                self.gui_callback("api_key_missing")
            return

        self.speak("Aguarde um momento, vou pesquisar...")
        
        def call_gemini():
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            data = {
                "contents": [{
                    "parts": [{
                        "text": f"Você é o Jarvis, o assistente pessoal inteligente do usuário. Responda à seguinte pergunta de forma concisa, direta e prestativa: {question}"
                    }]
                }]
            }
            try:
                req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=10) as response:
                    res_data = json.loads(response.read().decode('utf-8'))
                    answer = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
                    self.log(f"Resposta do Gemini: \"{answer}\"")
                    self.speak(answer)
            except urllib.error.HTTPError as e:
                self.log(f"Erro HTTP do Gemini: {e.code} - {e.read().decode('utf-8', 'ignore')}")
                self.speak("Desculpe, ocorreu um erro com a inteligência artificial.")
            except Exception as e:
                self.log(f"Erro Gemini: {e}")
                self.speak("Desculpe, não consegui processar a resposta.")

        threading.Thread(target=call_gemini, daemon=True).start()

    def toggle_active(self):
        self.active_mode = not self.active_mode
        self.log(f"Modo de voz alternado manualmente: {self.active_mode}")
        self.play_chime(self.active_mode)
        if self.gui_callback:
            status_cmd = "status_active" if self.active_mode else "status_inactive"
            self.gui_callback(status_cmd)
        return self.active_mode

    def close(self):
        self.running = False
        if self.stop_listening_fn:
            self.stop_listening_fn(wait_for_stop=False)
        if self.hotkey_hook and keyboard:
            try:
                keyboard.remove_hotkey(self.hotkey_hook)
                self.log("Hotkey global removida.")
            except Exception as e:
                self.log(f"Erro ao remover hotkey global: {e}")
        self.log("VoiceHandler encerrado.")