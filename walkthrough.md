# Jarvis Task Assistant - Manual do Usuário e Walkthrough

Este é um aplicativo de notas minimalista e direto desenvolvido para gerenciar suas tarefas diárias. O **Jarvis** possui controle por comando de voz inteligente ("Ligar Jarvis" / "Desligar Jarvis"), chatbot de suporte com Gemini AI, e uma interface gráfica moderna (CustomTkinter) com edição manual inline.

---

## 📂 Estrutura do Projeto

Os arquivos do projeto estão localizados em:
`C:\Users\ruiga\Documents\jarvis-task-assistant` e sincronizados em `C:\Users\ruiga\OneDrive\Documents\jarvis-task-assistant`

1. **`app.pyw`**: A interface gráfica moderna construída com CustomTkinter. Executável sem console de terminal (usa extensão `.pyw`).
2. **`voice_handler.py`**: O motor de escuta por voz que roda em segundo plano. Processa comandos de voz, gerencia o microfone e integra com a API do Gemini.
3. **`task_manager.py`**: Gerenciador thread-safe e seguro para leitura e gravação das tarefas em JSON.
4. **`config.json`**: Contém a configuração da chave da API do Gemini para responder dúvidas.
5. **`tasks.json`**: Banco de dados das tarefas em formato JSON.
6. **`start-jarvis.bat`**: Script de inicialização portátil para rodar o Jarvis em segundo plano com um clique.
7. **`test_voice_handler.py`**: Suite com 17 testes de unidade offline para validar toda a lógica de negócio por comando de voz.
8. **`jarvis.log`**: Log em tempo real para diagnóstico do assistente.

---

## 🎙️ Como Usar o Jarvis por Voz

O assistente possui dois modos de voz:

1. **Modo Inativo (Aguardando):** O Jarvis fica escutando apenas a palavra de ativação. Possui tolerância de termos (Ex: *"Ligar Jarvis"*, *"Olá Jarvis"*, *"Acordar Jarvis"*, *"Ligar Jar"*).
   - Quando ativado, ele dirá: *"Jarvis ativo. Sim, senhor?"* e a luz indicadora no canto superior direito da janela mudará de cinza para azul ciano.
2. **Modo Ativo (Ouvindo Comandos):** Neste modo, você pode dar ordens diretas para gerenciar suas tarefas.
   - Para colocá-lo em repouso novamente, diga *"Desligar Jarvis"* ou *"Dormir Jarvis"*.

### Principais Comandos de Voz:
* **Adicionar Tarefas:**
  - *"Adicionar comprar café"* (Adiciona com prioridade média por padrão).
  - *"Crie a tarefa estudar Python com prioridade alta"* (Adiciona e define a prioridade).
  - *"Anotar limpar a mesa com prioridade baixa"*
* **Concluir Tarefas:**
  - *"Concluir a número 2"* (Usa o número exibido na tela para facilidade).
  - *"Finalizar comprar café"* (Busca por correspondência de texto).
* **Remover/Excluir Tarefas:**
  - *"Deletar número 1"*
  - *"Excluir comprar café"*
* **Editar Tarefas:**
  - *"Alterar a número 2 para comprar leite com prioridade alta"*
  - *"Mudar café para comprar café preto"*
* **Alterar Prioridade Diretamente:**
  - *"Tarefa comprar café com prioridade baixa"*
  - *"Número 2 como prioridade alta"*
* **Listar Tarefas:**
  - *"Quais são minhas tarefas?"* ou *"O que eu tenho para fazer?"*
* **Dúvidas Gerais (Gemini Integration):**
  - Quando você fizer uma pergunta de conhecimento geral (Ex: *"Quem foi Alan Turing?"* ou *"Qual a previsão do tempo para amanhã?"*), o Jarvis buscará a resposta usando a IA do Gemini e responderá por voz.

---

## ✎ Edição Manual Inline (Interface Gráfica)

Além dos comandos de voz, você pode gerenciar suas tarefas manualmente na interface visual:
* **Adicionar:** Escreva o texto na barra inferior, escolha a prioridade e clique em "Adicionar" (ou pressione `Enter`).
* **Concluir:** Clique na caixa de seleção redonda ao lado do número da tarefa.
* **Excluir:** Clique no botão vermelho `✕` no canto direito do card da tarefa.
* **Editar:** Clique no botão de lápis `✎` para abrir a edição direta inline.
  - O campo de texto se tornará editável e um menu de seleção de prioridades aparecerá.
  - Pressione `Enter` ou clique no botão verde `✓` para salvar.
  - Pressione `Esc` ou clique no botão vermelho `✕` para cancelar a edição.
  - **Atenção:** Durante a digitação manual, as atualizações em segundo plano por voz são pausadas temporariamente para evitar que seu texto seja sobrescrito enquanto você escreve.

---

## 🚀 Como Iniciar o Aplicativo

Para iniciar o Jarvis em segundo plano de forma simples e rápida:
1. Dê dois cliques no arquivo **`start-jarvis.bat`**. Ele abrirá o Jarvis diretamente sem deixar uma janela preta de prompt de comando aberta.
2. Se quiser que o Jarvis seja iniciado automaticamente sempre que ligar o computador (Windows Startup):
   - Pressione `Win + R`, digite `shell:startup` e pressione `Enter`.
   - Crie um atalho do arquivo `start-jarvis.bat` e cole dentro dessa pasta que foi aberta.

---

## 🛠️ Executando Testes e Validação

Você pode rodar a suite de testes a qualquer momento para garantir a estabilidade do sistema:
1. Abra o Terminal ou PowerShell na pasta do projeto.
2. Execute o comando:
   ```bash
   python -m unittest test_voice_handler.py
   ```