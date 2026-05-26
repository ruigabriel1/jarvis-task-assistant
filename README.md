# 🎙️ Jarvis Task Assistant

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![GUI Framework](https://img.shields.io/badge/UI-CustomTkinter-darkblue.svg)](https://github.com/TomSchimansky/CustomTkinter)
[![Speech Recognition](https://img.shields.io/badge/Speech-SpeechRecognition-green.svg)](https://pypi.org/project/SpeechRecognition/)
[![AI Engine](https://img.shields.io/badge/AI-Gemini%201.5%20Flash-cyan.svg)](https://ai.google.dev/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](https://choosealicense.com/licenses/mit/)

O **Jarvis Task Assistant** é um aplicativo desktop de notas e gerenciamento de tarefas minimalista, projetado para funcionar como um widget de alta performance no estilo "Post-it". Ele combina uma interface gráfica moderna e escura (CustomTkinter) com um assistente de voz em segundo plano (SpeechRecognition e fala offline SAPI5/pyttsx3) e respostas inteligentes integradas com a API do Gemini.

---

## ✨ Principais Funcionalidades

*   **🎙️ Controle de Voz Inteligente (*Fuzzy*):** Palavras de ativação aproximadas (*"Ligar Jarvis"*, *"Olá Jar"*, *"Acordar Jarvis"*) ligam a escuta contínua. O indicador visual no cabeçalho sinaliza o status ativo (azul ciano) ou inativo (cinza).
*   **🔢 Comandos de Voz Baseados em Índices:** Permite concluir, excluir ou editar notas falando o número de exibição atual da tela (ex: *"Concluir a tarefa número 2"*, *"Apagar a 1"*), com remoção inteligente de múltiplos prefixos encadeados.
*   **✎ Edição Manual Inline:** Cards de tarefas dinâmicos com botão de lápis `✎`. Permite editar textos e prioridades inline com atalhos intuitivos de teclado (`Enter` para salvar, `Esc` para cancelar).
*   **⚙️ Sincronização e Bloqueio Concorrente:** Durante a digitação manual, o app bloqueia temporariamente atualizações de tela por comandos de voz, garantindo que o seu texto não seja sobrescrito.
*   **🤖 Chatbot Inteligente com Gemini 1.5 Flash:** Fallback de voz automático. Se você fizer uma pergunta que não seja um comando (ex: *"Como está o tempo hoje?"* ou *"Quem foi Alan Turing?"*), o Jarvis consulta o modelo da Google e responde por voz.
*   **🔒 Arquitetura Thread-Safe e Escrita Atômica:** Utiliza travas de concorrência (`RLock`) e leitura-escrita em transação atômica (`update_tasks`), prevenindo corrupção de dados entre a thread de voz e a GUI.

---

## 🛠️ Tecnologias Utilizadas

*   **Linguagem:** Python 3.8+
*   **Interface Gráfica:** CustomTkinter (Visual Premium Dark Mode)
*   **Reconhecimento de Voz:** SpeechRecognition (com API do Google Speech em segundo plano)
*   **Síntese de Voz (TTS):** pyttsx3 (Sintetizador nativo offline do Windows, sem necessidade de internet para falas básicas)
*   **Integração IA:** Google Generative AI API (Gemini 1.5 Flash)
*   **Gerenciador de Tarefas:** JSON Database com persistência thread-safe.

---

## 📂 Estrutura do Diretório

```text
jarvis-task-assistant/
├── app.pyw                  # Interface gráfica (CustomTkinter) sem janela de terminal
├── voice_handler.py          # Gerenciamento de voz, thread dedicada de áudio e LLM fallback
├── task_manager.py           # Leitura, escrita e transações atômicas no banco JSON
├── test_voice_handler.py     # Suite de 17 testes de unidade para validação offline
├── config.json               # Configuração da chave de API do Gemini (excluído do git em prod)
├── tasks.json                # Banco de dados persistente das notas/tarefas
├── start-jarvis.bat          # Script de inicialização portátil do Windows
├── jarvis.log                # Registro de execução em tempo real para auditorias
└── qa_report.md              # Relatório detalhado de QA e análise estática do subagente
```

---

## 🚀 Guia de Instalação e Inicialização

### Passo 1: Pré-requisitos
Certifique-se de ter o Python instalado e configurado no PATH do Windows. Instale as dependências executando o comando a seguir no terminal/PowerShell:
```bash
pip install customtkinter speechrecognition pyttsx3 pyaudio pythoncom
```
> **Nota:** No Windows, o `pyaudio` é necessário para captura de microfone. Se falhar, instale usando o `pip install pipwin` seguido de `pipwin install pyaudio`, ou baixe a roda pré-compilada (`.whl`).

### Passo 2: Configurar API Key
Crie um arquivo chamado `config.json` na raiz da pasta do projeto e adicione sua chave do Gemini AI:
```json
{
  "GEMINI_API_KEY": "SUA_API_KEY_AQUI"
}
```

### Passo 3: Iniciar o Jarvis
Dê duplo clique no arquivo **`start-jarvis.bat`**. O aplicativo abrirá em segundo plano silenciosamente.

---

## 💻 Inicialização Automática com o Windows (Startup)

Para fazer o Jarvis iniciar automaticamente sempre que você ligar o computador, siga estes passos:

1.  Pressione as teclas **`Win + R`** no seu teclado para abrir a caixa de diálogo "Executar".
2.  Digite **`shell:startup`** e pressione **`Enter`**. Isso abrirá a pasta de *Inicialização* do Windows.
3.  Vá até a pasta do projeto `jarvis-task-assistant`.
4.  Clique com o **botão direito** no arquivo **`start-jarvis.bat`** e escolha **Criar Atalho**.
5.  **Recorte** o atalho criado e **cole** dentro da pasta de *Inicialização* que foi aberta no passo 2.
6.  Pronto! Na próxima vez que o Windows iniciar, o Jarvis será carregado silenciosamente em segundo plano.

---

## 🛡️ Como Superar Barreiras (Solução de Problemas)

### 1. Erro de Microfone / Dispositivo de Entrada Não Encontrado
*   **Causa:** O Windows pode estar bloqueando o acesso ao microfone ou a biblioteca `PyAudio` não está mapeando a placa de áudio.
*   **Solução:** 
    *   Verifique em *Configurações do Windows > Privacidade > Microfone* se a permissão de acesso para aplicativos clássicos de desktop está ativada.
    *   Caso ocorra erro de importação do `pyaudio`, instale via terminal com privilégios de administrador: `pip install pipwin` e `pipwin install pyaudio`.

### 2. Erro de Sintetizador: "RuntimeError: run loop already started"
*   **Causa:** Múltiplas threads tentando acionar o `pyttsx3.say()` ao mesmo tempo.
*   **Solução:** Nossa arquitetura resolveu isso implementando uma fila thread-safe em `voice_handler.py`. Caso reescreva partes do código, garanta que todas as falas sejam enfileiradas através de `self.speak(text)` e consumidas unicamente pela `_speech_worker`.

### 3. API do Gemini retornando erro HTTP 404
*   **Causa:** Chave API incorreta, sem internet ou modelo descontinuado na URL.
*   **Solução:** Verifique se o `config.json` contém a chave de API correta. O app usa o endpoint `/v1/models/gemini-1.5-flash:generateContent`. Certifique-se de que sua chave possui cota ativa no Google AI Studio.

---

## 🧪 Rodando os Testes Unitários
Você pode executar o conjunto de testes unitários offline para garantir que a lógica de voz, parsing de números e filtros continuem funcionando:
```bash
python -m unittest test_voice_handler.py
```
